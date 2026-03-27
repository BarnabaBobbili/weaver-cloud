-- ============================================================================
-- Synapse Analytics: Create Weaver Analytics Database
-- ============================================================================
-- Run this first in Synapse Studio using the "Built-in" serverless pool
-- ============================================================================

-- Create the analytics database
CREATE DATABASE WeaverAnalytics;
GO

-- Switch to the new database
USE WeaverAnalytics;
GO

-- Create master key for encryption
CREATE MASTER KEY ENCRYPTION BY PASSWORD = 'Synapse@SecureKey2026!';
GO

PRINT 'WeaverAnalytics database created successfully!';
GO
