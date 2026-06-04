/*
    CleanupFailedPleskApply.sql

    Purpose:
    - Diagnose and optionally clean the known partial state left by the failed
      Plesk SQL Server apply where the database was empty before the attempt.
    - This script does NOT create schema, users, logins, or credentials.
    - This script is intentionally scoped to jemnexusb_prod and the only
      expected leftover tables: dbo.Suppliers and dbo.__EFMigrationsHistory.

    How to use safely:
    1) Run with @ApplyCleanup = 0 first and review the diagnostics.
    2) Only if the diagnostics show no unexpected tables, change @ApplyCleanup
       to 1 and run again to drop only the known leftover tables.
    3) After cleanup, apply the regenerated hotfix schema script; do not rerun
       any old script that still contains SQL Server cascade paths.
*/

SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @ExpectedDatabaseName sysname = N'jemnexusb_prod';
DECLARE @ApplyCleanup bit = 0;

PRINT N'Current database: ' + DB_NAME();

IF DB_NAME() <> @ExpectedDatabaseName
BEGIN
    THROW 51000, 'Safety stop: this cleanup script is scoped to jemnexusb_prod only. Check the connection database before continuing.', 1;
END;

PRINT N'Current user tables:';
SELECT
    s.name AS SchemaName,
    t.name AS TableName
FROM sys.tables AS t
INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
ORDER BY s.name, t.name;

DECLARE @Expected TABLE (SchemaName sysname NOT NULL, TableName sysname NOT NULL);
INSERT INTO @Expected (SchemaName, TableName)
VALUES (N'dbo', N'__EFMigrationsHistory'), (N'dbo', N'Suppliers');

IF EXISTS (
    SELECT 1
    FROM sys.tables AS t
    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    WHERE NOT EXISTS (
        SELECT 1
        FROM @Expected AS e
        WHERE e.SchemaName = s.name AND e.TableName = t.name
    )
)
BEGIN
    PRINT N'Unexpected user tables detected:';
    SELECT
        s.name AS SchemaName,
        t.name AS TableName
    FROM sys.tables AS t
    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    WHERE NOT EXISTS (
        SELECT 1
        FROM @Expected AS e
        WHERE e.SchemaName = s.name AND e.TableName = t.name
    )
    ORDER BY s.name, t.name;

    THROW 51001, 'Safety stop: unexpected tables exist. Do not run automatic cleanup; inspect manually before dropping anything.', 1;
END;

IF NOT EXISTS (SELECT 1 FROM sys.tables)
BEGIN
    PRINT N'No user tables exist. Nothing to clean.';
    RETURN;
END;

PRINT N'Only known failed-apply leftovers were detected. Expected leftovers may now be cleaned if @ApplyCleanup = 1.';

IF @ApplyCleanup = 0
BEGIN
    PRINT N'Diagnostic-only mode: no tables were dropped. Set @ApplyCleanup = 1 only after reviewing the output.';
    RETURN;
END;

BEGIN TRANSACTION;

IF OBJECT_ID(N'dbo.Suppliers', N'U') IS NOT NULL
BEGIN
    PRINT N'Dropping dbo.Suppliers...';
    DROP TABLE dbo.Suppliers;
END;

IF OBJECT_ID(N'dbo.__EFMigrationsHistory', N'U') IS NOT NULL
BEGIN
    PRINT N'Dropping dbo.__EFMigrationsHistory...';
    DROP TABLE dbo.__EFMigrationsHistory;
END;

COMMIT TRANSACTION;

PRINT N'Cleanup completed. Re-run diagnostics and verify there are no user tables before applying the corrected schema script.';
