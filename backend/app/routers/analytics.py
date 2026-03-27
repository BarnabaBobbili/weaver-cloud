from datetime import datetime, timedelta, timezone
from math import ceil
from pathlib import Path
import logging
import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit import AuditLog
from app.models.classification import ClassificationRecord
from app.models.encryption import EncryptedPayload, ShareLink
from app.models.user import User
from app.security.rbac import require_roles

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
STARTED_AT = datetime.now(timezone.utc)


def _should_use_synapse(query_type: str) -> bool:
    """
    Determine if a query should route to Azure Synapse Analytics.

    Heavy analytical queries (trends, cross-user aggregations, historical analysis)
    go to Synapse. Real-time dashboard counts stay on PostgreSQL.

    Args:
        query_type: Type of query ('realtime', 'trends', 'aggregation')

    Returns:
        True if query should use Synapse, False for PostgreSQL
    """
    # For now, all queries use PostgreSQL until Synapse is fully configured
    # In production, route heavy queries to Synapse:
    # return query_type in ['trends', 'aggregation', 'historical']
    return False


@router.get("/overview")
async def overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    """
    Real-time dashboard overview.

    This endpoint provides fast dashboard counts directly from PostgreSQL.
    For heavy trend analysis, use the /trends endpoint which can route to Synapse.
    """
    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)
    week_ago = now - timedelta(days=7)

    # These are real-time counts - keep in PostgreSQL for low latency
    total_cls = (
        await db.execute(select(func.count()).select_from(ClassificationRecord))
    ).scalar() or 0
    total_enc = (
        await db.execute(select(func.count()).select_from(EncryptedPayload))
    ).scalar() or 0
    total_users = (
        await db.execute(select(func.count()).select_from(User))
    ).scalar() or 0
    active_shares = (
        await db.execute(
            select(func.count())
            .select_from(ShareLink)
            .where(ShareLink.is_revoked == False)  # noqa: E712
        )
    ).scalar() or 0
    cls_week = (
        await db.execute(
            select(func.count())
            .select_from(ClassificationRecord)
            .where(ClassificationRecord.created_at >= week_ago)
        )
    ).scalar() or 0
    cls_month = (
        await db.execute(
            select(func.count())
            .select_from(ClassificationRecord)
            .where(ClassificationRecord.created_at >= month_ago)
        )
    ).scalar() or 0
    enc_week = (
        await db.execute(
            select(func.count())
            .select_from(EncryptedPayload)
            .where(EncryptedPayload.created_at >= week_ago)
        )
    ).scalar() or 0
    avg_confidence = (
        await db.execute(
            select(func.avg(ClassificationRecord.confidence_score)).where(
                ClassificationRecord.created_at >= month_ago
            )
        )
    ).scalar()
    most_common = (
        await db.execute(
            select(ClassificationRecord.predicted_level, func.count().label("count"))
            .group_by(ClassificationRecord.predicted_level)
            .order_by(func.count().desc())
            .limit(1)
        )
    ).first()

    return {
        "total_classifications": total_cls,
        "total_encryptions": total_enc,
        "total_users": total_users,
        "active_shares": active_shares,
        "classifications_this_week": cls_week,
        "encryptions_this_week": enc_week,
        "expiring_shares": 0,
        "classifications_this_month": cls_month,
        "avg_confidence": round(float(avg_confidence), 4)
        if avg_confidence is not None
        else None,
        "most_common_level": most_common[0] if most_common else None,
        "most_common_pct": round((most_common[1] / total_cls) * 100, 1)
        if most_common and total_cls
        else 0,
    }


@router.get("")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["user", "analyst", "admin"])),
):
    """
    Unified dashboard endpoint with charts.

    Returns user-specific data for regular users, system-wide data for admins.
    Automatically determines scope based on user role.
    """
    import os
    from pathlib import Path

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    is_admin = current_user.role == "admin"

    # Determine scope: user-specific or system-wide
    if is_admin:
        # Admin sees system-wide data
        total_cls = (
            await db.execute(select(func.count()).select_from(ClassificationRecord))
        ).scalar() or 0

        cls_week = (
            await db.execute(
                select(func.count())
                .select_from(ClassificationRecord)
                .where(ClassificationRecord.created_at >= week_ago)
            )
        ).scalar() or 0

        total_enc = (
            await db.execute(select(func.count()).select_from(EncryptedPayload))
        ).scalar() or 0

        enc_week = (
            await db.execute(
                select(func.count())
                .select_from(EncryptedPayload)
                .where(EncryptedPayload.created_at >= week_ago)
            )
        ).scalar() or 0

        total_users = (
            await db.execute(select(func.count()).select_from(User))
        ).scalar() or 0

        active_shares = (
            await db.execute(
                select(func.count())
                .select_from(ShareLink)
                .where(ShareLink.is_revoked == False)
                .where((ShareLink.expires_at == None) | (ShareLink.expires_at > now))
            )
        ).scalar() or 0

        # System-wide sensitivity distribution
        dist_rows = (
            await db.execute(
                select(
                    ClassificationRecord.predicted_level, func.count().label("count")
                )
                .where(ClassificationRecord.created_at >= month_ago)
                .group_by(ClassificationRecord.predicted_level)
            )
        ).all()

        # System-wide daily activity
        daily_activity = []
        for i in range(7):
            day = now - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            day_cls = (
                await db.execute(
                    select(func.count())
                    .select_from(ClassificationRecord)
                    .where(ClassificationRecord.created_at >= day_start)
                    .where(ClassificationRecord.created_at < day_end)
                )
            ).scalar() or 0

            day_enc = (
                await db.execute(
                    select(func.count())
                    .select_from(EncryptedPayload)
                    .where(EncryptedPayload.created_at >= day_start)
                    .where(EncryptedPayload.created_at < day_end)
                )
            ).scalar() or 0

            daily_activity.append(
                {
                    "date": day_start.strftime("%Y-%m-%d"),
                    "day": day_start.strftime("%a"),
                    "classifications": day_cls,
                    "encryptions": day_enc,
                }
            )

    else:
        # Regular user sees own data
        total_cls = (
            await db.execute(
                select(func.count())
                .select_from(ClassificationRecord)
                .where(ClassificationRecord.user_id == current_user.id)
            )
        ).scalar() or 0

        cls_week = (
            await db.execute(
                select(func.count())
                .select_from(ClassificationRecord)
                .where(ClassificationRecord.user_id == current_user.id)
                .where(ClassificationRecord.created_at >= week_ago)
            )
        ).scalar() or 0

        total_enc = (
            await db.execute(
                select(func.count())
                .select_from(EncryptedPayload)
                .where(EncryptedPayload.owner_id == current_user.id)
            )
        ).scalar() or 0

        enc_week = (
            await db.execute(
                select(func.count())
                .select_from(EncryptedPayload)
                .where(EncryptedPayload.owner_id == current_user.id)
                .where(EncryptedPayload.created_at >= week_ago)
            )
        ).scalar() or 0

        total_users = None  # Not relevant for regular users

        active_shares = (
            await db.execute(
                select(func.count())
                .select_from(ShareLink)
                .where(ShareLink.user_id == current_user.id)
                .where(ShareLink.is_revoked == False)
                .where((ShareLink.expires_at == None) | (ShareLink.expires_at > now))
            )
        ).scalar() or 0

        # User's sensitivity distribution
        dist_rows = (
            await db.execute(
                select(
                    ClassificationRecord.predicted_level, func.count().label("count")
                )
                .where(ClassificationRecord.user_id == current_user.id)
                .where(ClassificationRecord.created_at >= month_ago)
                .group_by(ClassificationRecord.predicted_level)
            )
        ).all()

        # User's daily activity
        daily_activity = []
        for i in range(7):
            day = now - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            day_cls = (
                await db.execute(
                    select(func.count())
                    .select_from(ClassificationRecord)
                    .where(ClassificationRecord.user_id == current_user.id)
                    .where(ClassificationRecord.created_at >= day_start)
                    .where(ClassificationRecord.created_at < day_end)
                )
            ).scalar() or 0

            day_enc = (
                await db.execute(
                    select(func.count())
                    .select_from(EncryptedPayload)
                    .where(EncryptedPayload.owner_id == current_user.id)
                    .where(EncryptedPayload.created_at >= day_start)
                    .where(EncryptedPayload.created_at < day_end)
                )
            ).scalar() or 0

            daily_activity.append(
                {
                    "date": day_start.strftime("%Y-%m-%d"),
                    "day": day_start.strftime("%a"),
                    "classifications": day_cls,
                    "encryptions": day_enc,
                }
            )

    daily_activity.reverse()

    distribution = {level: count for level, count in dist_rows}

    # Determine ML model source (admin only)
    ml_model_source = None
    ml_model_version = None
    if is_admin:
        ml_model_source = "local"

        # Check for ML service endpoint (highest priority - DistilBERT model)
        ml_endpoint_url = os.environ.get("AZURE_ML_ENDPOINT_URL")
        logger.info(f"ML endpoint URL from env: {ml_endpoint_url}")

        if ml_endpoint_url:
            # Try to verify ML service is healthy
            try:
                import httpx

                # Extract base URL from classify endpoint
                base_url = ml_endpoint_url.replace("/classify", "")
                logger.info(f"Checking ML service health at: {base_url}/health")

                async with httpx.AsyncClient(timeout=5.0) as client:
                    health_response = await client.get(f"{base_url}/health")
                    logger.info(
                        f"ML service response status: {health_response.status_code}"
                    )

                    if health_response.status_code == 200:
                        health_data = health_response.json()
                        logger.info(f"ML service health data: {health_data}")
                        ml_model_source = "ml_service"
                        ml_model_version = health_data.get(
                            "model_version", "distilbert-mnli-v1.0"
                        )
            except Exception as e:
                logger.warning(f"ML service health check failed: {e}")
                # Fall through to check other sources

        # Check for cloud-trained model (second priority)
        if ml_model_source == "local":
            cloud_model_path = (
                Path(__file__).parent.parent
                / "ml_models"
                / "cloud_trained"
                / "sensitivity_classifier.joblib"
            )
            if cloud_model_path.exists():
                ml_model_source = "cloud_trained"
            elif os.environ.get("AZURE_ML_ENDPOINT"):
                ml_model_source = "azure_endpoint"

        logger.info(
            f"Final ML model source: {ml_model_source}, version: {ml_model_version}"
        )

    result = {
        "total_classifications": total_cls,
        "classifications_this_week": cls_week,
        "total_encryptions": total_enc,
        "encryptions_this_week": enc_week,
        "active_shares": active_shares,
        "sensitivity_distribution": {
            "public": distribution.get("public", 0),
            "internal": distribution.get("internal", 0),
            "confidential": distribution.get("confidential", 0),
            "highly_sensitive": distribution.get("highly_sensitive", 0),
        },
        "daily_activity": daily_activity,
    }

    if is_admin:
        result["total_users"] = total_users
        result["ml_model_source"] = ml_model_source
        if ml_model_version:
            result["ml_model_version"] = ml_model_version

    return result


@router.get("/sensitivity-distribution")
async def sensitivity_distribution(
    range: str = "30D",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    days = 30
    if range.endswith("D"):
        try:
            days = int(range[:-1])
        except ValueError:
            pass
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await db.execute(
            select(ClassificationRecord.predicted_level, func.count().label("count"))
            .where(ClassificationRecord.created_at >= since)
            .group_by(ClassificationRecord.predicted_level)
        )
    ).all()
    distribution = {level: count for level, count in rows}
    return {
        "public": distribution.get("public", 0),
        "internal": distribution.get("internal", 0),
        "confidential": distribution.get("confidential", 0),
        "highly_sensitive": distribution.get("highly_sensitive", 0),
    }


@router.get("/sensitivity-timeseries")
async def sensitivity_timeseries(
    range: str = "30D",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    days = 30
    if range.endswith("D"):
        try:
            days = int(range[:-1])
        except ValueError:
            pass

    since = datetime.now(timezone.utc) - timedelta(days=days)
    bucket = func.date_trunc("day", ClassificationRecord.created_at)
    rows = (
        await db.execute(
            select(
                bucket.label("bucket"),
                ClassificationRecord.predicted_level,
                func.count().label("count"),
            )
            .where(ClassificationRecord.created_at >= since)
            .group_by(bucket, ClassificationRecord.predicted_level)
            .order_by(bucket.asc())
        )
    ).all()

    points: dict[str, dict[str, int | str]] = {}
    for bucket_value, level, count in rows:
        if bucket_value is None:
            continue
        key = bucket_value.strftime("%Y-%m-%d")
        if key not in points:
            points[key] = {
                "date": bucket_value.strftime("%b %d").replace(" 0", " "),
                "public": 0,
                "internal": 0,
                "confidential": 0,
                "highly_sensitive": 0,
            }
        points[key][level] = count

    return {"items": [points[key] for key in sorted(points.keys())]}


@router.get("/algorithm-usage")
async def algorithm_usage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    rows = (
        await db.execute(
            select(
                EncryptedPayload.encryption_algo, func.count().label("count")
            ).group_by(EncryptedPayload.encryption_algo)
        )
    ).all()
    return [{"algorithm": algorithm, "count": count} for algorithm, count in rows]


@router.get("/audit-logs")
async def audit_logs(
    page: int = 1,
    limit: int = 20,
    action: str = "",
    severity: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    query = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.user_id)
    count_query = select(func.count()).select_from(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if severity:
        query = query.where(AuditLog.severity == severity)
        count_query = count_query.where(AuditLog.severity == severity)

    total = (await db.execute(count_query)).scalar() or 0
    rows = (
        await db.execute(
            query.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()
    return {
        "items": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "user_email": email,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "details": log.details,
                "severity": log.severity,
                "created_at": str(log.created_at),
            }
            for log, email in rows
        ],
        "total": total,
        "page": page,
        "pages": ceil(total / limit) if limit else 1,
    }


@router.get("/admin/health")
async def admin_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    return {
        "db_records": {
            "users": (await db.execute(select(func.count()).select_from(User))).scalar()
            or 0,
            "classifications": (
                await db.execute(select(func.count()).select_from(ClassificationRecord))
            ).scalar()
            or 0,
            "encryptions": (
                await db.execute(select(func.count()).select_from(EncryptedPayload))
            ).scalar()
            or 0,
            "shares": (
                await db.execute(select(func.count()).select_from(ShareLink))
            ).scalar()
            or 0,
        },
        "uptime": str(datetime.now(timezone.utc) - STARTED_AT),
        "memory": "n/a",
    }


@router.get("/admin/user-summary")
async def admin_user_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    now = datetime.now(timezone.utc)
    last_30_days = now - timedelta(days=30)
    total_users = (
        await db.execute(select(func.count()).select_from(User))
    ).scalar() or 0
    mfa_enabled = (
        await db.execute(
            select(func.count()).select_from(User).where(User.mfa_enabled == True)
        )  # noqa: E712
    ).scalar() or 0
    locked_accounts = (
        await db.execute(
            select(func.count())
            .select_from(User)
            .where(User.locked_until.is_not(None), User.locked_until > now)
        )
    ).scalar() or 0
    registrations = (
        await db.execute(
            select(func.count())
            .select_from(User)
            .where(User.created_at >= last_30_days)
        )
    ).scalar() or 0
    return {
        "registrations_last_30_days": registrations,
        "locked_accounts": locked_accounts,
        "mfa_adoption_pct": round((mfa_enabled / total_users) * 100, 1)
        if total_users
        else 0,
        "total_users": total_users,
    }


@router.get("/admin/security-alerts")
async def admin_security_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    now = datetime.now(timezone.utc)
    last_24_hours = now - timedelta(hours=24)
    failed_logins = (
        await db.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action == "login_failed",
                AuditLog.created_at >= last_24_hours,
            )
        )
    ).scalar() or 0
    locked_accounts = (
        await db.execute(
            select(func.count())
            .select_from(User)
            .where(User.locked_until.is_not(None), User.locked_until > now)
        )
    ).scalar() or 0
    expiring_shares = (
        await db.execute(
            select(func.count())
            .select_from(ShareLink)
            .where(
                ShareLink.expires_at.is_not(None),
                ShareLink.expires_at <= now + timedelta(days=1),
                ShareLink.is_revoked == False,  # noqa: E712
            )
        )
    ).scalar() or 0
    return {
        "failed_logins_24h": failed_logins,
        "locked_accounts": locked_accounts,
        "expiring_shares": expiring_shares,
    }


# =============================================================================
# SYNAPSE ANALYTICS ENDPOINTS
# =============================================================================


@router.post("/synapse/export")
async def trigger_synapse_export(
    include_daily_rollup: bool = True,
    current_user: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger data export to Synapse Data Lake.

    This exports data from PostgreSQL to Azure Data Lake for Synapse to query.
    Should be called periodically (e.g., daily) or on-demand.
    """
    from app.services.synapse_service import get_synapse_service

    synapse = get_synapse_service()

    try:
        result = await synapse.run_daily_etl(
            db, include_daily_rollup=include_daily_rollup
        )
        return {
            "status": "success",
            "message": "Data export completed",
            "details": result,
        }
    except Exception as e:
        logger.error(f"Synapse export failed: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/synapse/export/internal")
async def trigger_synapse_export_internal(
    include_daily_rollup: bool = False,
    sync_key: str | None = Header(default=None, alias="X-Synapse-Sync-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    Internal automated export endpoint for scheduler jobs.

    Auth is API-key based so timer jobs can trigger export without interactive login.
    """
    expected_key = os.environ.get("SYNAPSE_SYNC_API_KEY", "")
    if not expected_key:
        raise HTTPException(
            status_code=503, detail="SYNAPSE_SYNC_API_KEY is not configured"
        )
    if not sync_key or not secrets.compare_digest(sync_key, expected_key):
        raise HTTPException(status_code=401, detail="Invalid sync key")

    from app.services.synapse_service import get_synapse_service

    synapse = get_synapse_service()

    try:
        result = await synapse.run_daily_etl(
            db, include_daily_rollup=include_daily_rollup
        )
        return {
            "status": "success",
            "message": "Internal sync completed",
            "details": result,
        }
    except Exception as e:
        logger.error(f"Internal Synapse export failed: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/synapse/status")
async def synapse_status(
    current_user: User = Depends(require_roles(["admin"])),
):
    """Get Synapse Analytics system status and available data."""
    from app.services.synapse_service import get_synapse_service

    synapse = get_synapse_service()
    summary = await synapse.get_analytics_summary()

    return {
        "status": summary.get("status", "unknown"),
        "workspace": summary.get("workspace"),
        "containers": summary.get("containers", []),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/synapse/powerbi-connection")
async def synapse_powerbi_connection(
    current_user: User = Depends(require_roles(["admin"])),
):
    """Get Power BI connection details for Synapse Analytics."""
    from app.services.synapse_service import get_synapse_service

    synapse = get_synapse_service()
    connection_info = synapse.get_synapse_connection_info()

    return {
        "connection": connection_info,
        "instructions": [
            "1. Open Power BI Desktop",
            "2. Get Data → Azure → Azure Synapse Analytics SQL",
            "3. Enter the SQL endpoint from connection details",
            "4. Use Azure AD authentication",
            "5. Select the analytical views (vw_*) to import",
        ],
        "available_views": [
            "vw_UserActivitySummary",
            "vw_ClassificationAnalytics",
            "vw_EncryptionOperations",
            "vw_ShareLinkAnalytics",
            "vw_PolicyCompliance",
            "vw_DailyMetrics",
            "vw_MLModelPerformance",
        ],
    }


@router.get("/synapse/dashboards")
async def synapse_dashboards(
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    """Get list of available Synapse analytics dashboards."""
    dashboards = [
        {
            "id": "sensitivity-distribution",
            "name": "Sensitivity Distribution",
            "description": "Classification distribution by sensitivity level over time",
            "synapse_view": "vw_SensitivityDistribution",
            "refresh_frequency": "daily",
            "chart_type": "stacked_bar",
        },
        {
            "id": "user-activity",
            "name": "User Activity Heatmap",
            "description": "User engagement patterns by hour and day",
            "synapse_view": "vw_HourlyActivityHeatmap",
            "refresh_frequency": "hourly",
            "chart_type": "heatmap",
        },
        {
            "id": "policy-compliance",
            "name": "Policy Compliance Trends",
            "description": "Policy effectiveness and compliance rates over time",
            "synapse_view": "vw_PolicyEffectiveness",
            "refresh_frequency": "daily",
            "chart_type": "line",
        },
        {
            "id": "data-volume",
            "name": "Data Volume Trends",
            "description": "Encryption data volume and file statistics",
            "synapse_view": "vw_DataVolumeTrends",
            "refresh_frequency": "daily",
            "chart_type": "area",
        },
        {
            "id": "ml-performance",
            "name": "ML Model Performance",
            "description": "Classification model accuracy and metrics",
            "synapse_view": "vw_MLModelPerformance",
            "refresh_frequency": "daily",
            "chart_type": "gauge",
        },
        {
            "id": "user-cohorts",
            "name": "User Cohort Analysis",
            "description": "User retention and engagement cohorts",
            "synapse_view": "vw_UserCohorts",
            "refresh_frequency": "weekly",
            "chart_type": "cohort_table",
        },
    ]

    return {"dashboards": dashboards}
