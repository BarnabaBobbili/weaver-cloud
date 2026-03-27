"""
Azure Synapse Service — Analytics data pipeline to Azure Synapse Analytics.

This module handles:
- Data export from PostgreSQL to Azure Data Lake
- Incremental, checkpointed sync of all PostgreSQL tables
- Synapse serverless SQL query readiness for Power BI
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

import pandas as pd
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.storage.filedatalake import DataLakeServiceClient
from sqlalchemy import text

from app.config import settings

logger = logging.getLogger(__name__)

# Bootstrap config from environment
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
SYNAPSE_WORKSPACE = os.environ.get("SYNAPSE_WORKSPACE", "weaver-synapse-ws")
SYNAPSE_STORAGE_ACCOUNT = os.environ.get("SYNAPSE_STORAGE_ACCOUNT", "weaversynapsest1332")
SYNAPSE_SQL_ENDPOINT = os.environ.get("SYNAPSE_SQL_ENDPOINT", "weaver-synapse-ws-ondemand.sql.azuresynapse.net")


class SynapseService:
    """
    Service for analytics data pipeline to Azure Synapse.

    Architecture:
    1. PostgreSQL (OLTP) -> Data Lake (analytics)
    2. Data Lake -> Synapse serverless SQL views
    3. Synapse -> Power BI
    """

    _instance: Optional["SynapseService"] = None
    _datalake_client: Optional[DataLakeServiceClient] = None
    _credential: Optional[Any] = None
    _initialized: bool = False

    _metadata_table = "synapse_sync_checkpoints"
    _snapshot_default = {"share_links", "notifications", "refresh_tokens"}
    _append_only_hint = {
        "audit_logs",
        "classification_records",
        "encrypted_payloads",
        "share_access_logs",
    }

    def __new__(cls) -> "SynapseService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        try:
            if AZURE_CLIENT_ID:
                self._credential = ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)
                logger.info("Using Managed Identity for Synapse Data Lake")
            else:
                self._credential = DefaultAzureCredential()
                logger.info("Using DefaultAzureCredential for Synapse Data Lake")

            account_url = f"https://{SYNAPSE_STORAGE_ACCOUNT}.dfs.core.windows.net"
            self._datalake_client = DataLakeServiceClient(
                account_url=account_url,
                credential=self._credential,
            )

            self._initialized = True
            logger.info("Synapse service initialized - Storage: %s", SYNAPSE_STORAGE_ACCOUNT)

        except Exception as e:
            logger.error("Failed to initialize Synapse service: %s", e)
            logger.warning("Synapse integration will be disabled - analytics features unavailable")

    @staticmethod
    def _quote_ident(identifier: str) -> str:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", identifier):
            raise ValueError(f"Invalid SQL identifier: {identifier}")
        return f'"{identifier}"'

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, memoryview):
            value = bytes(value)
        if isinstance(value, (bytes, bytearray)):
            return base64.b64encode(value).decode("ascii")
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, UUID):
            return str(value)
        return value

    def _normalize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {k: self._normalize_value(v) for k, v in row.items()}

    @property
    def _batch_size(self) -> int:
        return max(100, int(settings.SYNAPSE_SYNC_BATCH_SIZE))

    @property
    def _sync_prefix(self) -> str:
        return settings.SYNAPSE_SYNC_PREFIX.strip("/") or "postgres_sync"

    @property
    def _snapshot_tables(self) -> set[str]:
        raw = os.environ.get("SYNAPSE_SYNC_SNAPSHOT_TABLES", "")
        if not raw.strip():
            return set(self._snapshot_default)
        return {t.strip() for t in raw.split(",") if t.strip()}

    async def export_to_datalake(
        self,
        data: List[Dict[str, Any]],
        container: str,
        path: str,
        format: str = "parquet",
    ) -> bool:
        """
        Export data to Azure Data Lake for Synapse analysis.
        """
        if not self._datalake_client:
            logger.warning("Data Lake client not initialized - skipping export")
            return False
        if not data:
            return True

        try:
            df = pd.DataFrame(data)

            if format == "parquet":
                buffer = io.BytesIO()
                df.to_parquet(buffer, index=False, engine="pyarrow")
                buffer.seek(0)
                content = buffer.read()
            elif format == "csv":
                content = df.to_csv(index=False).encode("utf-8")
            else:
                content = df.to_json(orient="records").encode("utf-8")

            file_system_client = self._datalake_client.get_file_system_client(container)
            file_client = file_system_client.get_file_client(path)
            file_client.upload_data(content, overwrite=True)

            logger.info("Exported %s records to %s/%s", len(data), container, path)
            return True
        except Exception as e:
            logger.error("Failed to export to Data Lake (%s/%s): %s", container, path, e)
            return False

    async def _ensure_sync_metadata(self, db_session: Any) -> None:
        await db_session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {self._metadata_table} (
                    table_name TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    cursor_column TEXT NULL,
                    last_cursor_ts TIMESTAMPTZ NULL,
                    last_cursor_id TEXT NULL,
                    last_snapshot_at TIMESTAMPTZ NULL,
                    last_success_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    rows_exported BIGINT NOT NULL DEFAULT 0
                );
                """
            )
        )

    async def _discover_public_tables(self, db_session: Any) -> List[str]:
        rows = (
            await db_session.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                    ORDER BY table_name;
                    """
                )
            )
        ).fetchall()
        tables = [r[0] for r in rows]
        return [t for t in tables if t != self._metadata_table]

    async def _get_table_columns(self, db_session: Any, table_name: str) -> List[str]:
        rows = (
            await db_session.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                    ORDER BY ordinal_position;
                    """
                ),
                {"table_name": table_name},
            )
        ).fetchall()
        return [r[0] for r in rows]

    async def _get_checkpoint(self, db_session: Any, table_name: str) -> Optional[Dict[str, Any]]:
        row = (
            await db_session.execute(
                text(
                    f"""
                    SELECT table_name, mode, cursor_column, last_cursor_ts, last_cursor_id,
                           last_snapshot_at, last_success_at, rows_exported
                    FROM {self._metadata_table}
                    WHERE table_name = :table_name;
                    """
                ),
                {"table_name": table_name},
            )
        ).mappings().first()
        return dict(row) if row else None

    async def _save_checkpoint(
        self,
        db_session: Any,
        table_name: str,
        mode: str,
        cursor_column: Optional[str],
        last_cursor_ts: Optional[datetime],
        last_cursor_id: Optional[str],
        last_snapshot_at: Optional[datetime],
        rows_exported: int,
    ) -> None:
        await db_session.execute(
            text(
                f"""
                INSERT INTO {self._metadata_table}
                (
                    table_name, mode, cursor_column, last_cursor_ts, last_cursor_id,
                    last_snapshot_at, last_success_at, rows_exported
                )
                VALUES
                (
                    :table_name, :mode, :cursor_column, :last_cursor_ts, :last_cursor_id,
                    :last_snapshot_at, NOW(), :rows_exported
                )
                ON CONFLICT (table_name) DO UPDATE SET
                    mode = EXCLUDED.mode,
                    cursor_column = EXCLUDED.cursor_column,
                    last_cursor_ts = EXCLUDED.last_cursor_ts,
                    last_cursor_id = EXCLUDED.last_cursor_id,
                    last_snapshot_at = EXCLUDED.last_snapshot_at,
                    last_success_at = NOW(),
                    rows_exported = EXCLUDED.rows_exported;
                """
            ),
            {
                "table_name": table_name,
                "mode": mode,
                "cursor_column": cursor_column,
                "last_cursor_ts": last_cursor_ts,
                "last_cursor_id": last_cursor_id,
                "last_snapshot_at": last_snapshot_at,
                "rows_exported": rows_exported,
            },
        )

    def _pick_strategy(self, table_name: str, columns: List[str]) -> Dict[str, Optional[str]]:
        cols = set(columns)
        if table_name in self._snapshot_tables:
            return {"mode": "snapshot", "cursor_column": None}
        if "updated_at" in cols and "id" in cols:
            return {"mode": "incremental", "cursor_column": "updated_at"}
        if "created_at" in cols and "id" in cols:
            mode = "incremental" if table_name in self._append_only_hint else "snapshot"
            return {"mode": mode, "cursor_column": "created_at" if mode == "incremental" else None}
        return {"mode": "snapshot", "cursor_column": None}

    async def _sync_table_incremental(
        self,
        db_session: Any,
        table_name: str,
        columns: List[str],
        cursor_column: str,
    ) -> Dict[str, Any]:
        table_ident = self._quote_ident(table_name)
        cursor_ident = self._quote_ident(cursor_column)
        col_expr = ", ".join(self._quote_ident(c) for c in columns)
        id_expr = 'CAST("id" AS TEXT)'

        checkpoint = await self._get_checkpoint(db_session, table_name) or {}
        last_cursor_ts = checkpoint.get("last_cursor_ts")
        last_cursor_id = checkpoint.get("last_cursor_id") or ""

        total_rows = 0
        batch_no = 0
        now = datetime.utcnow()

        while True:
            if last_cursor_ts is None:
                query = text(
                    f"""
                    SELECT {col_expr}
                    FROM {table_ident}
                    ORDER BY {cursor_ident} ASC, {id_expr} ASC
                    LIMIT :limit;
                    """
                )
                params = {"limit": self._batch_size}
            else:
                query = text(
                    f"""
                    SELECT {col_expr}
                    FROM {table_ident}
                    WHERE ({cursor_ident} > :cursor_ts)
                       OR ({cursor_ident} = :cursor_ts AND {id_expr} > :cursor_id)
                    ORDER BY {cursor_ident} ASC, {id_expr} ASC
                    LIMIT :limit;
                    """
                )
                params = {
                    "cursor_ts": last_cursor_ts,
                    "cursor_id": last_cursor_id,
                    "limit": self._batch_size,
                }

            rows = (await db_session.execute(query, params)).mappings().all()
            if not rows:
                break

            batch = [self._normalize_row(dict(r)) for r in rows]
            batch_path = (
                f"{self._sync_prefix}/{table_name}/mode=incremental/"
                f"dt={now.strftime('%Y-%m-%d')}/hour={now.strftime('%H')}/"
                f"batch_{now.strftime('%Y%m%d_%H%M%S_%f')}_{batch_no:04d}.parquet"
            )
            ok = await self.export_to_datalake(batch, "analytics", batch_path, "parquet")
            if not ok:
                raise RuntimeError(f"Failed exporting incremental batch for {table_name}")

            total_rows += len(batch)
            last_row = dict(rows[-1])
            last_cursor_ts = last_row.get(cursor_column)
            last_cursor_id = str(last_row.get("id", ""))
            batch_no += 1

            if len(rows) < self._batch_size:
                break

        await self._save_checkpoint(
            db_session=db_session,
            table_name=table_name,
            mode="incremental",
            cursor_column=cursor_column,
            last_cursor_ts=last_cursor_ts,
            last_cursor_id=last_cursor_id,
            last_snapshot_at=checkpoint.get("last_snapshot_at"),
            rows_exported=total_rows,
        )
        return {"table": table_name, "mode": "incremental", "rows": total_rows, "status": "success"}

    async def _sync_table_snapshot(
        self,
        db_session: Any,
        table_name: str,
        columns: List[str],
    ) -> Dict[str, Any]:
        table_ident = self._quote_ident(table_name)
        col_expr = ", ".join(self._quote_ident(c) for c in columns)
        has_id = "id" in columns

        total_rows = 0
        part_no = 0
        snapshot_ts = datetime.utcnow()
        last_id = ""

        while True:
            if has_id:
                query = text(
                    f"""
                    SELECT {col_expr}
                    FROM {table_ident}
                    WHERE CAST("id" AS TEXT) > :last_id
                    ORDER BY CAST("id" AS TEXT) ASC
                    LIMIT :limit;
                    """
                )
                params = {"last_id": last_id, "limit": self._batch_size}
            else:
                if part_no > 0:
                    break
                query = text(f"SELECT {col_expr} FROM {table_ident};")
                params = {}

            rows = (await db_session.execute(query, params)).mappings().all()
            if not rows:
                break

            batch = [self._normalize_row(dict(r)) for r in rows]
            batch_path = (
                f"{self._sync_prefix}/{table_name}/mode=snapshot/"
                f"snapshot_ts={snapshot_ts.strftime('%Y%m%d_%H%M%S')}/"
                f"part_{part_no:04d}.parquet"
            )
            ok = await self.export_to_datalake(batch, "analytics", batch_path, "parquet")
            if not ok:
                raise RuntimeError(f"Failed exporting snapshot batch for {table_name}")

            total_rows += len(batch)
            part_no += 1
            if has_id:
                last_id = str(dict(rows[-1]).get("id", ""))
                if len(rows) < self._batch_size:
                    break
            else:
                break

        checkpoint = await self._get_checkpoint(db_session, table_name) or {}
        await self._save_checkpoint(
            db_session=db_session,
            table_name=table_name,
            mode="snapshot",
            cursor_column=None,
            last_cursor_ts=checkpoint.get("last_cursor_ts"),
            last_cursor_id=checkpoint.get("last_cursor_id"),
            last_snapshot_at=snapshot_ts,
            rows_exported=total_rows,
        )
        return {"table": table_name, "mode": "snapshot", "rows": total_rows, "status": "success"}

    async def sync_all_postgres_tables(self, db_session: Any) -> Dict[str, Any]:
        """
        Export all PostgreSQL tables to Data Lake with checkpointed sync.
        """
        started = datetime.utcnow()
        await self._ensure_sync_metadata(db_session)
        tables = await self._discover_public_tables(db_session)

        details: List[Dict[str, Any]] = []
        succeeded = 0
        failed = 0
        total_rows = 0

        for table_name in tables:
            try:
                columns = await self._get_table_columns(db_session, table_name)
                if not columns:
                    continue

                strategy = self._pick_strategy(table_name, columns)
                if strategy["mode"] == "incremental" and strategy["cursor_column"]:
                    result = await self._sync_table_incremental(
                        db_session=db_session,
                        table_name=table_name,
                        columns=columns,
                        cursor_column=strategy["cursor_column"],
                    )
                else:
                    result = await self._sync_table_snapshot(
                        db_session=db_session,
                        table_name=table_name,
                        columns=columns,
                    )

                total_rows += int(result.get("rows", 0))
                succeeded += 1
                details.append(result)

            except Exception as e:
                failed += 1
                logger.exception("Failed syncing table %s: %s", table_name, e)
                details.append(
                    {
                        "table": table_name,
                        "status": "failed",
                        "error": str(e),
                    }
                )

        ended = datetime.utcnow()
        return {
            "status": "success" if failed == 0 else "partial_success",
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "duration_seconds": (ended - started).total_seconds(),
            "tables_total": len(tables),
            "tables_succeeded": succeeded,
            "tables_failed": failed,
            "rows_exported_total": total_rows,
            "details": details,
        }

    async def export_classifications(
        self,
        classifications: List[Dict[str, Any]],
        date_partition: Optional[datetime] = None,
    ) -> bool:
        if not classifications:
            return True
        date_partition = date_partition or datetime.utcnow()
        partition_path = date_partition.strftime("%Y/%m/%d")
        timestamp = date_partition.strftime("%Y%m%d_%H%M%S")
        path = f"classifications/{partition_path}/batch_{timestamp}.parquet"
        return await self.export_to_datalake(
            data=classifications,
            container="analytics",
            path=path,
            format="parquet",
        )

    async def export_encryption_events(
        self,
        events: List[Dict[str, Any]],
        date_partition: Optional[datetime] = None,
    ) -> bool:
        if not events:
            return True
        date_partition = date_partition or datetime.utcnow()
        partition_path = date_partition.strftime("%Y/%m/%d")
        timestamp = date_partition.strftime("%Y%m%d_%H%M%S")
        path = f"encryption_ops/{partition_path}/batch_{timestamp}.parquet"
        return await self.export_to_datalake(
            data=events,
            container="analytics",
            path=path,
            format="parquet",
        )

    async def export_user_activity(
        self,
        activity: List[Dict[str, Any]],
        date_partition: Optional[datetime] = None,
    ) -> bool:
        if not activity:
            return True
        date_partition = date_partition or datetime.utcnow()
        date_key = date_partition.strftime("%Y%m%d")
        path = f"user_activity/date_key={date_key}/activity.parquet"
        return await self.export_to_datalake(
            data=activity,
            container="analytics",
            path=path,
            format="parquet",
        )

    async def export_daily_metrics(
        self,
        metrics: Dict[str, Any],
        date: Optional[datetime] = None,
    ) -> bool:
        date = date or datetime.utcnow()
        date_key = date.strftime("%Y%m%d")
        metrics["date_key"] = date_key
        path = f"daily_metrics/date_key={date_key}/metrics.parquet"
        return await self.export_to_datalake(
            data=[metrics],
            container="analytics",
            path=path,
            format="parquet",
        )

    async def run_daily_etl(
        self,
        db_session: Any,
        include_daily_rollup: bool = True,
    ) -> Dict[str, Any]:
        """
        Run ETL pipeline:
        1) Optional daily rollup export (yesterday metrics)
        2) Full PostgreSQL table sync with checkpoints
        """
        start_time = datetime.utcnow()
        results: Dict[str, Any] = {
            "start_time": start_time.isoformat(),
            "exports": {},
            "errors": [],
        }

        try:
            if include_daily_rollup:
                yesterday = start_time - timedelta(days=1)
                yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
                yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)

                metrics_query = text(
                    """
                    SELECT
                        COUNT(DISTINCT user_id) as active_users,
                        COUNT(*) as total_operations,
                        COUNT(CASE WHEN action = 'encrypt' THEN 1 END) as encryption_operations,
                        COUNT(CASE WHEN action = 'decrypt' THEN 1 END) as decryption_operations,
                        COUNT(CASE WHEN action = 'classify' THEN 1 END) as classification_operations
                    FROM audit_logs
                    WHERE created_at BETWEEN :start_date AND :end_date
                    """
                )

                metrics_result = await db_session.execute(
                    metrics_query,
                    {"start_date": yesterday_start, "end_date": yesterday_end},
                )
                metrics_row = metrics_result.fetchone()
                if metrics_row:
                    daily_metrics = {
                        "date_key": yesterday.strftime("%Y%m%d"),
                        "active_users": metrics_row.active_users or 0,
                        "total_operations": metrics_row.total_operations or 0,
                        "encryption_operations": metrics_row.encryption_operations or 0,
                        "decryption_operations": metrics_row.decryption_operations or 0,
                        "classification_operations": metrics_row.classification_operations or 0,
                    }
                    success = await self.export_daily_metrics(daily_metrics, yesterday)
                    results["exports"]["daily_metrics"] = {
                        "success": success,
                        "metrics": daily_metrics,
                    }

            pg_sync = await self.sync_all_postgres_tables(db_session)
            results["exports"]["postgres_sync"] = pg_sync

            results["end_time"] = datetime.utcnow().isoformat()
            results["duration_seconds"] = (datetime.utcnow() - start_time).total_seconds()
            results["status"] = "success" if pg_sync.get("tables_failed", 0) == 0 else "partial_success"
            return results

        except Exception as e:
            logger.exception("ETL failed: %s", e)
            results["errors"].append(str(e))
            results["status"] = "failed"
            results["end_time"] = datetime.utcnow().isoformat()
            results["duration_seconds"] = (datetime.utcnow() - start_time).total_seconds()
            return results

    def get_synapse_connection_info(self) -> Dict[str, str]:
        return {
            "workspace": SYNAPSE_WORKSPACE,
            "sql_endpoint": SYNAPSE_SQL_ENDPOINT,
            "storage_account": SYNAPSE_STORAGE_ACCOUNT,
            "data_lake_url": f"https://{SYNAPSE_STORAGE_ACCOUNT}.dfs.core.windows.net",
            "note": "Use Azure AD authentication for Power BI connection",
        }

    async def get_analytics_summary(self) -> Dict[str, Any]:
        if not self._datalake_client:
            return {"status": "not_configured", "containers": []}

        try:
            containers = []
            for container in ["raw-data", "processed-data", "analytics", "powerbi"]:
                try:
                    fs_client = self._datalake_client.get_file_system_client(container)
                    paths = list(fs_client.get_paths(max_results=10))
                    containers.append(
                        {
                            "name": container,
                            "file_count": len(paths),
                            "sample_paths": [p.name for p in paths[:5]],
                        }
                    )
                except Exception:
                    containers.append({"name": container, "file_count": 0, "sample_paths": []})

            return {
                "status": "connected",
                "workspace": SYNAPSE_WORKSPACE,
                "containers": containers,
            }
        except Exception as e:
            logger.error("Failed to get analytics summary: %s", e)
            return {"status": "error", "error": str(e)}


_synapse_service: Optional[SynapseService] = None


def get_synapse_service() -> SynapseService:
    """Get the singleton Synapse service instance."""
    global _synapse_service
    if _synapse_service is None:
        _synapse_service = SynapseService()
    return _synapse_service
