USE WeaverAnalytics;
GO
IF NOT EXISTS (SELECT * FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##')
BEGIN
    CREATE MASTER KEY ENCRYPTION BY PASSWORD = 'Synapse@SecureKey2026!';
END
GO
IF NOT EXISTS (SELECT * FROM sys.database_scoped_credentials WHERE name='WeaverDataLakeCredential')
CREATE DATABASE SCOPED CREDENTIAL WeaverDataLakeCredential WITH IDENTITY='Managed Identity';
GO
IF NOT EXISTS (SELECT * FROM sys.external_data_sources WHERE name='WeaverRawData')
CREATE EXTERNAL DATA SOURCE WeaverRawData WITH (LOCATION='https://weaversynapsest1332.dfs.core.windows.net/raw-data', CREDENTIAL=WeaverDataLakeCredential);
GO
IF NOT EXISTS (SELECT * FROM sys.external_data_sources WHERE name='WeaverProcessedData')
CREATE EXTERNAL DATA SOURCE WeaverProcessedData WITH (LOCATION='https://weaversynapsest1332.dfs.core.windows.net/processed-data', CREDENTIAL=WeaverDataLakeCredential);
GO
IF NOT EXISTS (SELECT * FROM sys.external_data_sources WHERE name='WeaverAnalytics')
CREATE EXTERNAL DATA SOURCE WeaverAnalytics WITH (LOCATION='https://weaversynapsest1332.dfs.core.windows.net/analytics', CREDENTIAL=WeaverDataLakeCredential);
GO
IF NOT EXISTS (SELECT * FROM sys.external_file_formats WHERE name='ParquetFormat')
CREATE EXTERNAL FILE FORMAT ParquetFormat WITH (FORMAT_TYPE = PARQUET);
GO
