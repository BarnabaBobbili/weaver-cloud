-- ============================================================================
-- Synapse Analytics: Resilient View Bootstrap
-- ============================================================================
-- Creates all expected analytics/Power BI views even when some parquet folders
-- are not populated yet.
-- ============================================================================

-- ============================================================================
-- Real view over currently exported daily metrics parquet
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_DailyMetrics
AS
SELECT
    TRY_CAST(date_key AS INT) AS date_key,
    COALESCE(total_users, 0) AS total_users,
    COALESCE(active_users, 0) AS active_users,
    COALESCE(new_users, 0) AS new_users,
    COALESCE(total_operations, 0) AS total_operations,
    COALESCE(encryption_operations, 0) AS encryption_operations,
    COALESCE(decryption_operations, 0) AS decryption_operations,
    COALESCE(classification_operations, 0) AS classification_operations,
    COALESCE(share_operations, 0) AS share_operations,
    CAST(avg_response_time_ms AS FLOAT) AS avg_response_time_ms,
    COALESCE(error_count, 0) AS error_count,
    CAST(
        CASE WHEN COALESCE(total_users, 0) = 0 THEN 0
             ELSE COALESCE(active_users, 0) * 100.0 / total_users
        END
        AS DECIMAL(5,2)
    ) AS user_engagement_rate,
    CAST(
        CASE WHEN COALESCE(total_operations, 0) = 0 THEN 0
             ELSE COALESCE(error_count, 0) * 100.0 / total_operations
        END
        AS DECIMAL(8,4)
    ) AS error_rate
FROM OPENROWSET(
    BULK 'daily_metrics/*/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) WITH (
    date_key VARCHAR(32),
    total_users BIGINT,
    active_users BIGINT,
    new_users BIGINT,
    total_operations BIGINT,
    encryption_operations BIGINT,
    decryption_operations BIGINT,
    classification_operations BIGINT,
    share_operations BIGINT,
    avg_response_time_ms FLOAT,
    error_count BIGINT
) AS [metrics];
GO

-- ============================================================================
-- Typed empty analytical views (auto-fill once corresponding parquet paths are
-- exported and these are replaced with source-specific OPENROWSET definitions).
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_UserActivitySummary
AS
SELECT
    CAST(NULL AS BIGINT) AS user_id,
    CAST(NULL AS NVARCHAR(320)) AS user_email,
    CAST(NULL AS INT) AS date_key,
    CAST(NULL AS BIGINT) AS total_encryptions,
    CAST(NULL AS BIGINT) AS total_decryptions,
    CAST(NULL AS BIGINT) AS total_classifications,
    CAST(NULL AS BIGINT) AS total_shares,
    CAST(NULL AS FLOAT) AS avg_confidence_score,
    CAST(NULL AS NVARCHAR(64)) AS most_common_sensitivity,
    CAST(NULL AS INT) AS active_minutes,
    CAST(NULL AS NVARCHAR(32)) AS user_segment
WHERE 1 = 0;
GO

CREATE OR ALTER VIEW dbo.vw_ClassificationAnalytics
AS
SELECT
    CAST(NULL AS BIGINT) AS classification_id,
    CAST(NULL AS BIGINT) AS user_id,
    CAST(NULL AS DATETIME2) AS classification_date,
    CAST(NULL AS NVARCHAR(32)) AS input_type,
    CAST(NULL AS INT) AS sensitivity_level,
    CAST(NULL AS FLOAT) AS confidence_score,
    CAST(NULL AS NVARCHAR(64)) AS model_version,
    CAST(NULL AS INT) AS processing_time_ms,
    CAST(NULL AS NVARCHAR(32)) AS sensitivity_name,
    CAST(NULL AS NVARCHAR(32)) AS confidence_band
WHERE 1 = 0;
GO

CREATE OR ALTER VIEW dbo.vw_EncryptionOperations
AS
SELECT
    CAST(NULL AS BIGINT) AS operation_id,
    CAST(NULL AS BIGINT) AS user_id,
    CAST(NULL AS DATETIME2) AS operation_date,
    CAST(NULL AS NVARCHAR(32)) AS operation_type,
    CAST(NULL AS NVARCHAR(128)) AS algorithm_used,
    CAST(NULL AS BIGINT) AS data_size_bytes,
    CAST(NULL AS INT) AS processing_time_ms,
    CAST(NULL AS BIT) AS has_policy_attached,
    CAST(NULL AS NVARCHAR(128)) AS policy_name,
    CAST(NULL AS INT) AS sensitivity_level,
    CAST(NULL AS DECIMAL(10,2)) AS data_size_kb
WHERE 1 = 0;
GO

CREATE OR ALTER VIEW dbo.vw_ShareLinkAnalytics
AS
SELECT
    CAST(NULL AS BIGINT) AS share_id,
    CAST(NULL AS BIGINT) AS creator_user_id,
    CAST(NULL AS DATETIME2) AS created_date,
    CAST(NULL AS DATETIME2) AS expires_date,
    CAST(NULL AS BIGINT) AS access_count,
    CAST(NULL AS BIT) AS has_password,
    CAST(NULL AS BIGINT) AS max_accesses,
    CAST(NULL AS INT) AS sensitivity_level,
    CAST(NULL AS BIT) AS is_expired,
    CAST(NULL AS BIT) AS is_revoked,
    CAST(NULL AS INT) AS validity_days,
    CAST(NULL AS NVARCHAR(32)) AS usage_category
WHERE 1 = 0;
GO

CREATE OR ALTER VIEW dbo.vw_PolicyCompliance
AS
SELECT
    CAST(NULL AS BIGINT) AS policy_id,
    CAST(NULL AS NVARCHAR(128)) AS policy_name,
    CAST(NULL AS DATETIME2) AS evaluation_date,
    CAST(NULL AS BIGINT) AS total_evaluations,
    CAST(NULL AS BIGINT) AS compliant_count,
    CAST(NULL AS BIGINT) AS non_compliant_count,
    CAST(NULL AS DECIMAL(5,2)) AS compliance_rate,
    CAST(NULL AS NVARCHAR(128)) AS most_violated_rule,
    CAST(NULL AS NVARCHAR(32)) AS compliance_status
WHERE 1 = 0;
GO

CREATE OR ALTER VIEW dbo.vw_MLModelPerformance
AS
SELECT
    CAST(NULL AS NVARCHAR(64)) AS model_version,
    CAST(NULL AS DATETIME2) AS evaluation_date,
    CAST(NULL AS FLOAT) AS accuracy,
    CAST(NULL AS FLOAT) AS precision_score,
    CAST(NULL AS FLOAT) AS recall_score,
    CAST(NULL AS FLOAT) AS f1_score,
    CAST(NULL AS BIGINT) AS total_predictions,
    CAST(NULL AS BIGINT) AS correct_predictions,
    CAST(NULL AS FLOAT) AS avg_inference_time_ms,
    CAST(NULL AS NVARCHAR(64)) AS model_type,
    CAST(NULL AS NVARCHAR(32)) AS model_quality
WHERE 1 = 0;
GO

CREATE OR ALTER VIEW dbo.vw_SensitivityDistribution
AS
SELECT
    CAST(NULL AS INT) AS date_key,
    CAST(NULL AS INT) AS sensitivity_level,
    CAST(NULL AS NVARCHAR(32)) AS sensitivity_name,
    CAST(NULL AS BIGINT) AS total_classifications,
    CAST(NULL AS FLOAT) AS avg_confidence,
    CAST(NULL AS FLOAT) AS min_confidence,
    CAST(NULL AS FLOAT) AS max_confidence,
    CAST(NULL AS BIGINT) AS unique_users
WHERE 1 = 0;
GO

CREATE OR ALTER VIEW dbo.vw_HourlyActivityHeatmap
AS
SELECT
    CAST(NULL AS INT) AS date_key,
    CAST(NULL AS INT) AS hour_of_day,
    CAST(NULL AS NVARCHAR(16)) AS day_of_week,
    CAST(NULL AS NVARCHAR(32)) AS operation_type,
    CAST(NULL AS BIGINT) AS operation_count,
    CAST(NULL AS BIGINT) AS unique_users,
    CAST(NULL AS FLOAT) AS avg_processing_time_ms
WHERE 1 = 0;
GO

CREATE OR ALTER VIEW dbo.vw_UserCohorts
AS
SELECT
    CAST(NULL AS NVARCHAR(16)) AS cohort_month,
    CAST(NULL AS NVARCHAR(16)) AS cohort_week,
    CAST(NULL AS BIGINT) AS user_count,
    CAST(NULL AS FLOAT) AS retention_week_1,
    CAST(NULL AS FLOAT) AS retention_week_2,
    CAST(NULL AS FLOAT) AS retention_week_3,
    CAST(NULL AS FLOAT) AS retention_week_4,
    CAST(NULL AS FLOAT) AS avg_lifetime_operations,
    CAST(NULL AS FLOAT) AS avg_lifetime_encryptions,
    CAST(NULL AS BIGINT) AS power_user_count,
    CAST(NULL AS BIGINT) AS churned_user_count
WHERE 1 = 0;
GO

CREATE OR ALTER VIEW dbo.vw_PolicyEffectiveness
AS
SELECT
    CAST(NULL AS BIGINT) AS policy_id,
    CAST(NULL AS NVARCHAR(128)) AS policy_name,
    CAST(NULL AS DATETIME2) AS week_start_date,
    CAST(NULL AS BIGINT) AS total_applications,
    CAST(NULL AS BIGINT) AS compliant_operations,
    CAST(NULL AS BIGINT) AS blocked_operations,
    CAST(NULL AS BIGINT) AS override_requests,
    CAST(NULL AS FLOAT) AS compliance_rate,
    CAST(NULL AS NVARCHAR(16)) AS trend_direction
WHERE 1 = 0;
GO

CREATE OR ALTER VIEW dbo.vw_TopUsers
AS
SELECT
    CAST(NULL AS BIGINT) AS user_id,
    CAST(NULL AS NVARCHAR(320)) AS user_email,
    CAST(NULL AS NVARCHAR(16)) AS month_key,
    CAST(NULL AS BIGINT) AS total_operations,
    CAST(NULL AS BIGINT) AS encryptions,
    CAST(NULL AS BIGINT) AS decryptions,
    CAST(NULL AS BIGINT) AS classifications,
    CAST(NULL AS BIGINT) AS shares_created,
    CAST(NULL AS FLOAT) AS avg_sensitivity_level,
    CAST(NULL AS FLOAT) AS compliance_score,
    CAST(NULL AS INT) AS user_rank
WHERE 1 = 0;
GO

CREATE OR ALTER VIEW dbo.vw_DataVolumeTrends
AS
SELECT
    CAST(NULL AS INT) AS date_key,
    CAST(NULL AS FLOAT) AS total_data_processed_mb,
    CAST(NULL AS FLOAT) AS encrypted_data_mb,
    CAST(NULL AS FLOAT) AS decrypted_data_mb,
    CAST(NULL AS FLOAT) AS avg_file_size_kb,
    CAST(NULL AS FLOAT) AS largest_file_kb,
    CAST(NULL AS BIGINT) AS file_count,
    CAST(NULL AS FLOAT) AS cumulative_data_mb
WHERE 1 = 0;
GO

CREATE OR ALTER VIEW dbo.vw_SecurityAlerts
AS
SELECT
    CAST(NULL AS INT) AS date_key,
    CAST(NULL AS NVARCHAR(64)) AS alert_type,
    CAST(NULL AS NVARCHAR(32)) AS severity,
    CAST(NULL AS BIGINT) AS alert_count,
    CAST(NULL AS BIGINT) AS affected_users,
    CAST(NULL AS BIGINT) AS resolved_count,
    CAST(NULL AS FLOAT) AS avg_resolution_time_hours,
    CAST(NULL AS NVARCHAR(256)) AS top_trigger_reason
WHERE 1 = 0;
GO

PRINT 'Resilient analytics views created successfully!';
GO
