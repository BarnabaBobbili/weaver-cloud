-- ============================================================================
-- Synapse Analytics: Analytical Views for Weaver Data
-- ============================================================================
-- These views provide analytics-ready data for Power BI and reporting.
-- They query data exported from PostgreSQL to the Data Lake.
-- ============================================================================

-- ============================================================================
-- VIEW: User Activity Summary
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_UserActivitySummary
AS
SELECT
    user_id,
    user_email,
    date_key,
    total_encryptions,
    total_decryptions,
    total_classifications,
    total_shares,
    avg_confidence_score,
    most_common_sensitivity,
    active_minutes,
    CASE 
        WHEN total_encryptions + total_decryptions > 50 THEN 'Power User'
        WHEN total_encryptions + total_decryptions > 10 THEN 'Regular User'
        ELSE 'Light User'
    END AS user_segment
FROM OPENROWSET(
    BULK 'user_activity/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [activity];
GO

-- ============================================================================
-- VIEW: Sensitivity Classification Analytics
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_ClassificationAnalytics
AS
SELECT
    classification_id,
    user_id,
    classification_date,
    input_type,
    sensitivity_level,
    confidence_score,
    model_version,
    processing_time_ms,
    CASE sensitivity_level
        WHEN 0 THEN 'Public'
        WHEN 1 THEN 'Internal'
        WHEN 2 THEN 'Confidential'
        WHEN 3 THEN 'Restricted'
    END AS sensitivity_name,
    CASE 
        WHEN confidence_score >= 0.9 THEN 'High Confidence'
        WHEN confidence_score >= 0.7 THEN 'Medium Confidence'
        ELSE 'Low Confidence'
    END AS confidence_band
FROM OPENROWSET(
    BULK 'classifications/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [classifications];
GO

-- ============================================================================
-- VIEW: Encryption Operations
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_EncryptionOperations
AS
SELECT
    operation_id,
    user_id,
    operation_date,
    operation_type,
    algorithm_used,
    data_size_bytes,
    processing_time_ms,
    has_policy_attached,
    policy_name,
    sensitivity_level,
    CAST(data_size_bytes / 1024.0 AS DECIMAL(10,2)) AS data_size_kb
FROM OPENROWSET(
    BULK 'encryption_ops/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [encryption];
GO

-- ============================================================================
-- VIEW: Share Link Analytics
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_ShareLinkAnalytics
AS
SELECT
    share_id,
    creator_user_id,
    created_date,
    expires_date,
    access_count,
    has_password,
    max_accesses,
    sensitivity_level,
    is_expired,
    is_revoked,
    DATEDIFF(day, created_date, expires_date) AS validity_days,
    CASE 
        WHEN access_count = 0 THEN 'Never Accessed'
        WHEN access_count = 1 THEN 'Single Access'
        WHEN access_count <= 5 THEN 'Low Usage'
        ELSE 'High Usage'
    END AS usage_category
FROM OPENROWSET(
    BULK 'share_links/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [shares];
GO

-- ============================================================================
-- VIEW: Policy Compliance Summary
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_PolicyCompliance
AS
SELECT
    policy_id,
    policy_name,
    evaluation_date,
    total_evaluations,
    compliant_count,
    non_compliant_count,
    CAST(compliant_count * 100.0 / NULLIF(total_evaluations, 0) AS DECIMAL(5,2)) AS compliance_rate,
    most_violated_rule,
    CASE 
        WHEN CAST(compliant_count * 100.0 / NULLIF(total_evaluations, 0) AS DECIMAL(5,2)) >= 95 THEN 'Excellent'
        WHEN CAST(compliant_count * 100.0 / NULLIF(total_evaluations, 0) AS DECIMAL(5,2)) >= 80 THEN 'Good'
        WHEN CAST(compliant_count * 100.0 / NULLIF(total_evaluations, 0) AS DECIMAL(5,2)) >= 60 THEN 'Needs Improvement'
        ELSE 'Critical'
    END AS compliance_status
FROM OPENROWSET(
    BULK 'policy_compliance/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [compliance];
GO

-- ============================================================================
-- VIEW: Daily Metrics Dashboard
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_DailyMetrics
AS
SELECT
    date_key,
    total_users,
    active_users,
    new_users,
    total_operations,
    encryption_operations,
    decryption_operations,
    classification_operations,
    share_operations,
    avg_response_time_ms,
    error_count,
    CAST(active_users * 100.0 / NULLIF(total_users, 0) AS DECIMAL(5,2)) AS user_engagement_rate,
    CAST(error_count * 100.0 / NULLIF(total_operations, 0) AS DECIMAL(5,4)) AS error_rate
FROM OPENROWSET(
    BULK 'daily_metrics/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [metrics];
GO

-- ============================================================================
-- VIEW: ML Model Performance
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_MLModelPerformance
AS
SELECT
    model_version,
    evaluation_date,
    accuracy,
    precision_score,
    recall_score,
    f1_score,
    total_predictions,
    correct_predictions,
    avg_inference_time_ms,
    model_type,
    CASE 
        WHEN accuracy >= 0.95 THEN 'Excellent'
        WHEN accuracy >= 0.90 THEN 'Good'
        WHEN accuracy >= 0.85 THEN 'Acceptable'
        ELSE 'Needs Retraining'
    END AS model_quality
FROM OPENROWSET(
    BULK 'ml_performance/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [ml];
GO

PRINT 'Analytical views created successfully!';
GO
