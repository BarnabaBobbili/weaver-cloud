-- ============================================================================
-- Synapse Analytics: Power BI Ready Aggregations
-- ============================================================================
-- Pre-aggregated views optimized for Power BI dashboards.
-- These views minimize query complexity and improve report performance.
-- ============================================================================

-- ============================================================================
-- AGGREGATION: Sensitivity Distribution by Date
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_SensitivityDistribution
AS
SELECT
    date_key,
    sensitivity_level,
    sensitivity_name,
    total_classifications,
    avg_confidence,
    min_confidence,
    max_confidence,
    unique_users
FROM OPENROWSET(
    BULK 'aggregations/sensitivity_distribution/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [dist];
GO

-- ============================================================================
-- AGGREGATION: Hourly Activity Heatmap
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_HourlyActivityHeatmap
AS
SELECT
    date_key,
    hour_of_day,
    day_of_week,
    operation_type,
    operation_count,
    unique_users,
    avg_processing_time_ms
FROM OPENROWSET(
    BULK 'aggregations/hourly_activity/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [heatmap];
GO

-- ============================================================================
-- AGGREGATION: User Cohort Analysis
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_UserCohorts
AS
SELECT
    cohort_month,
    cohort_week,
    user_count,
    retention_week_1,
    retention_week_2,
    retention_week_3,
    retention_week_4,
    avg_lifetime_operations,
    avg_lifetime_encryptions,
    power_user_count,
    churned_user_count
FROM OPENROWSET(
    BULK 'aggregations/user_cohorts/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [cohorts];
GO

-- ============================================================================
-- AGGREGATION: Policy Effectiveness Over Time
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_PolicyEffectiveness
AS
SELECT
    policy_id,
    policy_name,
    week_start_date,
    total_applications,
    compliant_operations,
    blocked_operations,
    override_requests,
    compliance_rate,
    trend_direction
FROM OPENROWSET(
    BULK 'aggregations/policy_effectiveness/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [policy];
GO

-- ============================================================================
-- AGGREGATION: Top Users Leaderboard
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_TopUsers
AS
SELECT
    user_id,
    user_email,
    month_key,
    total_operations,
    encryptions,
    decryptions,
    classifications,
    shares_created,
    avg_sensitivity_level,
    compliance_score,
    user_rank
FROM OPENROWSET(
    BULK 'aggregations/top_users/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [users];
GO

-- ============================================================================
-- AGGREGATION: Data Volume Trends
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_DataVolumeTrends
AS
SELECT
    date_key,
    total_data_processed_mb,
    encrypted_data_mb,
    decrypted_data_mb,
    avg_file_size_kb,
    largest_file_kb,
    file_count,
    cumulative_data_mb
FROM OPENROWSET(
    BULK 'aggregations/data_volume/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [volume];
GO

-- ============================================================================
-- AGGREGATION: Security Alerts Summary
-- ============================================================================
CREATE OR ALTER VIEW dbo.vw_SecurityAlerts
AS
SELECT
    date_key,
    alert_type,
    severity,
    alert_count,
    affected_users,
    resolved_count,
    avg_resolution_time_hours,
    top_trigger_reason
FROM OPENROWSET(
    BULK 'aggregations/security_alerts/*.parquet',
    DATA_SOURCE = 'WeaverAnalytics',
    FORMAT = 'PARQUET'
) AS [alerts];
GO

-- ============================================================================
-- STORED PROCEDURE: Refresh Analytics Summary
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.sp_RefreshAnalyticsSummary
AS
BEGIN
    -- This procedure would be called by a scheduled pipeline
    -- to refresh materialized aggregations
    
    PRINT 'Analytics summary refresh started at: ' + CAST(GETDATE() AS VARCHAR);
    
    -- In production, this would:
    -- 1. Read new data from raw-data container
    -- 2. Process and transform
    -- 3. Write to analytics container
    -- 4. Update metadata
    
    PRINT 'Analytics summary refresh completed at: ' + CAST(GETDATE() AS VARCHAR);
END;
GO

PRINT 'Power BI aggregations created successfully!';
GO
