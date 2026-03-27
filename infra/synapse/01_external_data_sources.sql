-- ============================================================================
-- Synapse Analytics: External Data Source Configuration
-- ============================================================================
-- This script sets up external data sources for querying data in Azure Data Lake
-- and PostgreSQL through Synapse serverless SQL pool.
-- ============================================================================

-- Create master key for encryption (required for credentials)
IF NOT EXISTS (SELECT * FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##')
BEGIN
    CREATE MASTER KEY ENCRYPTION BY PASSWORD = 'Synapse@SecureKey2026!';
END
GO

-- ============================================================================
-- DATA LAKE EXTERNAL DATA SOURCE
-- ============================================================================

-- Create credential for accessing the data lake storage
CREATE DATABASE SCOPED CREDENTIAL WeaverDataLakeCredential
WITH IDENTITY = 'SHARED ACCESS SIGNATURE',
SECRET = ''; -- Will be populated with SAS token
GO

-- Create external data source for raw data
CREATE EXTERNAL DATA SOURCE WeaverRawData
WITH (
    LOCATION = 'https://weaversynapsest1332.dfs.core.windows.net/raw-data',
    CREDENTIAL = WeaverDataLakeCredential
);
GO

-- Create external data source for processed data
CREATE EXTERNAL DATA SOURCE WeaverProcessedData
WITH (
    LOCATION = 'https://weaversynapsest1332.dfs.core.windows.net/processed-data',
    CREDENTIAL = WeaverDataLakeCredential
);
GO

-- Create external data source for analytics
CREATE EXTERNAL DATA SOURCE WeaverAnalytics
WITH (
    LOCATION = 'https://weaversynapsest1332.dfs.core.windows.net/analytics',
    CREDENTIAL = WeaverDataLakeCredential
);
GO

-- ============================================================================
-- EXTERNAL FILE FORMATS
-- ============================================================================

-- Parquet format (optimized for analytics)
CREATE EXTERNAL FILE FORMAT ParquetFormat
WITH (
    FORMAT_TYPE = PARQUET,
    DATA_COMPRESSION = 'org.apache.hadoop.io.compress.SnappyCodec'
);
GO

-- CSV format (for data exports)
CREATE EXTERNAL FILE FORMAT CsvFormat
WITH (
    FORMAT_TYPE = DELIMITEDTEXT,
    FORMAT_OPTIONS (
        FIELD_TERMINATOR = ',',
        STRING_DELIMITER = '"',
        FIRST_ROW = 2,
        USE_TYPE_DEFAULT = TRUE
    )
);
GO

-- JSON format (for log data)
CREATE EXTERNAL FILE FORMAT JsonFormat
WITH (
    FORMAT_TYPE = DELIMITEDTEXT,
    FORMAT_OPTIONS (
        FIELD_TERMINATOR = '0x0b',
        STRING_DELIMITER = '0x0b',
        ROW_TERMINATOR = '0x0a'
    )
);
GO

PRINT 'External data sources and file formats created successfully!';
GO
