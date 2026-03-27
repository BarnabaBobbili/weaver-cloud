"""
Azure Synapse Service — Analytics data pipeline to Azure Synapse Analytics.

This module handles:
- Data export from PostgreSQL to Azure Data Lake
- Synapse serverless SQL queries
- Power BI data preparation
- ETL pipeline coordination with Service Bus
"""
from __future__ import annotations

import os
import io
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.storage.filedatalake import DataLakeServiceClient
import pandas as pd

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
    1. PostgreSQL (OLTP) → Data Lake (raw-data)
    2. Data Lake → Synapse serverless SQL (analytics views)
    3. Synapse → Power BI (dashboards)
    
    Data Flow:
    - Real-time events go to Service Bus queues
    - Batch export writes Parquet files to Data Lake
    - Synapse queries Data Lake via OPENROWSET
    """
    
    _instance: Optional["SynapseService"] = None
    _datalake_client: Optional[DataLakeServiceClient] = None
    _credential: Optional[Any] = None
    _initialized: bool = False
    
    def __new__(cls) -> "SynapseService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        try:
            # Use Managed Identity if available
            if AZURE_CLIENT_ID:
                self._credential = ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)
                logger.info("Using Managed Identity for Synapse Data Lake")
            else:
                self._credential = DefaultAzureCredential()
                logger.info("Using DefaultAzureCredential for Synapse Data Lake")
            
            # Initialize Data Lake client
            account_url = f"https://{SYNAPSE_STORAGE_ACCOUNT}.dfs.core.windows.net"
            self._datalake_client = DataLakeServiceClient(
                account_url=account_url,
                credential=self._credential
            )
            
            self._initialized = True
            logger.info(f"Synapse service initialized - Storage: {SYNAPSE_STORAGE_ACCOUNT}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Synapse service: {e}")
            logger.warning("Synapse integration will be disabled - analytics features unavailable")
    
    async def export_to_datalake(
        self,
        data: List[Dict[str, Any]],
        container: str,
        path: str,
        format: str = "parquet"
    ) -> bool:
        """
        Export data to Azure Data Lake for Synapse analysis.
        
        Args:
            data: List of records to export
            container: Data Lake container (raw-data, processed-data, analytics)
            path: File path within container
            format: Export format (parquet, csv, json)
            
        Returns:
            True if successful
        """
        if not self._datalake_client:
            logger.warning("Data Lake client not initialized - skipping export")
            return False
        
        try:
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Serialize based on format
            if format == "parquet":
                buffer = io.BytesIO()
                df.to_parquet(buffer, index=False, engine="pyarrow")
                buffer.seek(0)
                content = buffer.read()
                content_type = "application/octet-stream"
            elif format == "csv":
                content = df.to_csv(index=False).encode("utf-8")
                content_type = "text/csv"
            else:  # json
                content = df.to_json(orient="records").encode("utf-8")
                content_type = "application/json"
            
            # Upload to Data Lake
            file_system_client = self._datalake_client.get_file_system_client(container)
            file_client = file_system_client.get_file_client(path)
            
            file_client.upload_data(content, overwrite=True)
            
            logger.info(f"Exported {len(data)} records to {container}/{path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export to Data Lake: {e}")
            return False
    
    async def export_classifications(
        self,
        classifications: List[Dict[str, Any]],
        date_partition: Optional[datetime] = None
    ) -> bool:
        """
        Export classification events for analytics.
        
        Args:
            classifications: Classification records
            date_partition: Date for partitioning (default: today)
            
        Returns:
            True if successful
        """
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
            format="parquet"
        )
    
    async def export_encryption_events(
        self,
        events: List[Dict[str, Any]],
        date_partition: Optional[datetime] = None
    ) -> bool:
        """
        Export encryption events for analytics.
        """
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
            format="parquet"
        )
    
    async def export_user_activity(
        self,
        activity: List[Dict[str, Any]],
        date_partition: Optional[datetime] = None
    ) -> bool:
        """
        Export user activity summaries for analytics.
        """
        if not activity:
            return True
        
        date_partition = date_partition or datetime.utcnow()
        date_key = date_partition.strftime("%Y%m%d")
        
        path = f"user_activity/date_key={date_key}/activity.parquet"
        
        return await self.export_to_datalake(
            data=activity,
            container="analytics",
            path=path,
            format="parquet"
        )
    
    async def export_daily_metrics(
        self,
        metrics: Dict[str, Any],
        date: Optional[datetime] = None
    ) -> bool:
        """
        Export daily aggregated metrics.
        """
        date = date or datetime.utcnow()
        date_key = date.strftime("%Y%m%d")
        
        metrics["date_key"] = date_key
        
        path = f"daily_metrics/date_key={date_key}/metrics.parquet"
        
        return await self.export_to_datalake(
            data=[metrics],
            container="analytics",
            path=path,
            format="parquet"
        )
    
    async def run_daily_etl(self, db_session: Any) -> Dict[str, Any]:
        """
        Run daily ETL pipeline to sync PostgreSQL data to Synapse.
        
        This should be triggered by a scheduled job (e.g., Azure Functions timer).
        
        Args:
            db_session: SQLAlchemy async session
            
        Returns:
            ETL run summary
        """
        from sqlalchemy import text
        
        start_time = datetime.utcnow()
        results = {
            "start_time": start_time.isoformat(),
            "exports": {},
            "errors": [],
        }
        
        try:
            yesterday = start_time - timedelta(days=1)
            yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Export audit logs
            audit_query = text("""
                SELECT 
                    id, user_id, action, resource_type, resource_id,
                    details, ip_address, user_agent, created_at
                FROM audit_logs
                WHERE created_at BETWEEN :start_date AND :end_date
            """)
            
            audit_result = await db_session.execute(
                audit_query,
                {"start_date": yesterday_start, "end_date": yesterday_end}
            )
            audit_rows = [dict(row._mapping) for row in audit_result.fetchall()]
            
            if audit_rows:
                success = await self.export_to_datalake(
                    data=audit_rows,
                    container="raw-data",
                    path=f"audit_logs/{yesterday.strftime('%Y/%m/%d')}/audit.parquet",
                    format="parquet"
                )
                results["exports"]["audit_logs"] = {
                    "count": len(audit_rows),
                    "success": success
                }
            
            # Calculate and export daily metrics
            metrics_query = text("""
                SELECT 
                    COUNT(DISTINCT user_id) as active_users,
                    COUNT(*) as total_operations,
                    COUNT(CASE WHEN action = 'encrypt' THEN 1 END) as encryption_operations,
                    COUNT(CASE WHEN action = 'decrypt' THEN 1 END) as decryption_operations,
                    COUNT(CASE WHEN action = 'classify' THEN 1 END) as classification_operations
                FROM audit_logs
                WHERE created_at BETWEEN :start_date AND :end_date
            """)
            
            metrics_result = await db_session.execute(
                metrics_query,
                {"start_date": yesterday_start, "end_date": yesterday_end}
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
                    "metrics": daily_metrics
                }
            
            results["end_time"] = datetime.utcnow().isoformat()
            results["duration_seconds"] = (datetime.utcnow() - start_time).total_seconds()
            results["status"] = "success"
            
            logger.info(f"Daily ETL completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Daily ETL failed: {e}")
            results["errors"].append(str(e))
            results["status"] = "failed"
            return results
    
    def get_synapse_connection_info(self) -> Dict[str, str]:
        """Get Synapse connection information for Power BI."""
        return {
            "workspace": SYNAPSE_WORKSPACE,
            "sql_endpoint": SYNAPSE_SQL_ENDPOINT,
            "storage_account": SYNAPSE_STORAGE_ACCOUNT,
            "data_lake_url": f"https://{SYNAPSE_STORAGE_ACCOUNT}.dfs.core.windows.net",
            "note": "Use Azure AD authentication for Power BI connection"
        }
    
    async def get_analytics_summary(self) -> Dict[str, Any]:
        """Get summary of available analytics data."""
        if not self._datalake_client:
            return {"status": "not_configured", "containers": []}
        
        try:
            containers = []
            for container in ["raw-data", "processed-data", "analytics", "powerbi"]:
                try:
                    fs_client = self._datalake_client.get_file_system_client(container)
                    paths = list(fs_client.get_paths(max_results=10))
                    containers.append({
                        "name": container,
                        "file_count": len(paths),
                        "sample_paths": [p.name for p in paths[:5]]
                    })
                except Exception:
                    containers.append({"name": container, "file_count": 0, "sample_paths": []})
            
            return {
                "status": "connected",
                "workspace": SYNAPSE_WORKSPACE,
                "containers": containers
            }
            
        except Exception as e:
            logger.error(f"Failed to get analytics summary: {e}")
            return {"status": "error", "error": str(e)}


# Singleton instance
_synapse_service: Optional[SynapseService] = None


def get_synapse_service() -> SynapseService:
    """Get the singleton Synapse service instance."""
    global _synapse_service
    if _synapse_service is None:
        _synapse_service = SynapseService()
    return _synapse_service
