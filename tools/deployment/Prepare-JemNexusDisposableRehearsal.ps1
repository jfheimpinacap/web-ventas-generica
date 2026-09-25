#requires -Version 5.1
<# Controlled creator for the fixed task-364 LocalDB target.  It never drops or
   restores a database and it never connects to production. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('PlanOnly','Prepare')][string]$Mode,
    [string]$ProductionBaselinePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Instance='(localdb)\MSSQLLocalDB'
$Database='JemNexus_DisposableRehearsal_364'
$Schema='jemnexusb_api'
$MarkerName='JemNexus.DisposableRehearsalMarker'
$MarkerValue='TASK-364|READONLY-PREFLIGHT|DISPOSABLE'
$Forbidden=@('JemNexus_Local','jemnexusb_prod')
$MigrationIds=@(
 '20260603182917_InitialCommercialSchema','20260604020543_AddAuthUsersAndAuditRelations','20260616000000_AddCategoryProductType','20260619000000_AddProductPriceDisplayFields','20260619010000_EnsureCanonicalRootCategories','20260803000000_AddMachineryTechnicalData','20260803010000_AddTechnicalSheets','20260810080000_AddProductTechnicalSheetAssociation','20260811000000_AddStructuredMachineryTechnicalData','20260812000000_AddProductMachineWeight','20260816000000_AddSellerCodes','20260817000000_AddCustomerProfiles','20260817010000_AddCommercialQuotes','20260818010000_AddCommercialQuoteIssuanceAndFolios','20260822000000_AddRefreshTokenRotation','20260822010000_AddRefreshTokenPasswordVersion','20260822020000_AddCommercialQuoteIssueIdempotency','20260824010000_AddSellerContactQuoteSnapshots','20260825010000_AddCustomerProfileStatus','20260830000000_PreserveQuotesWhenDeletingProducts','20260917000000_AddGranularSellerPermissions','20260922000000_AddCommercialQuoteIssuedBy')
$ProjectPath=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\backend-dotnet\JemNexus.Api\JemNexus.Api.csproj'))
$MigrationsPath=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\backend-dotnet\JemNexus.Api\Data\Migrations'))
$InspectorPath=Join-Path $PSScriptRoot 'Inspect-JemNexusDisposableRehearsal.ps1'

function Result([string]$status,[string[]]$blockers){[ordered]@{status=$status;instance=$Instance;database=$Database;schema=$Schema;migrations=22;blockers=@($blockers);productionAuthorized=$false}|ConvertTo-Json -Compress|Write-Output}
if($Mode -eq 'PlanOnly'){
    if($PSBoundParameters.ContainsKey('ProductionBaselinePath')){Result 'NO-GO' @('PLAN_ONLY_REJECTS_INPUT_PATHS');exit 2}
    Result 'PLAN_ONLY' @('NO_CONNECTION_OPENED','NO_FILE_READ','NO_WRITE_PERFORMED');exit 0
}
if($Database -cin $Forbidden -or $Database -cne 'JemNexus_DisposableRehearsal_364' -or $Instance -cne '(localdb)\MSSQLLocalDB'){Result 'NO-GO' @('COMPILED_DESTINATION_INVALID');exit 2}
if([string]::IsNullOrWhiteSpace($ProductionBaselinePath)){Result 'NO-GO' @('PRODUCTION_BASELINE_REQUIRED');exit 2}

$master=$null;$target=$null;$tempScript=$null
try{
    # Validate public evidence before opening SQL. No package or private rows are read.
    $item=Get-Item -LiteralPath $ProductionBaselinePath -Force
    if(-not ($item -is [IO.FileInfo]) -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'PRODUCTION_BASELINE_INVALID'}
    $baseline=Get-Content -LiteralPath $item.FullName -Raw|ConvertFrom-Json
    if($baseline.reportType -cne 'JemNexusProductionSchemaBaseline' -or $baseline.database -cne 'jemnexusb_prod' -or $baseline.schema -cne $Schema -or $baseline.historySchema -cne $Schema -or $baseline.sequenceSchema -cne $Schema -or $baseline.markerScope -cne 'database' -or [int]$baseline.migrationCount -ne 22 -or [string]::IsNullOrWhiteSpace([string]$baseline.evidenceCapturedUtc)){throw 'PRODUCTION_BASELINE_INVALID'}
    foreach($kind in @('columns','primaryKeys','foreignKeys','indexes','checks','identities','sequence')){if([string]$baseline.schemaFingerprints.$kind -notmatch '^[0-9a-f]{64}$'){throw 'PRODUCTION_BASELINE_INVALID'}}

    # Everything required to generate and inspect is proven usable before SQL is
    # opened. In particular, migration generation cannot fail after database creation.
    foreach($path in @($ProjectPath,$InspectorPath)){$local=Get-Item -LiteralPath $path -Force;if(-not ($local -is [IO.FileInfo]) -or ($local.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'LOCAL_MIGRATION_INPUTS_INVALID'}}
    $migrationDirectory=Get-Item -LiteralPath $MigrationsPath -Force
    if(-not ($migrationDirectory -is [IO.DirectoryInfo]) -or ($migrationDirectory.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'LOCAL_MIGRATION_INPUTS_INVALID'}
    $migrationFiles=@(Get-ChildItem -LiteralPath $MigrationsPath -File -Filter '*.cs'|Where-Object{$_.Name -notlike '*.Designer.cs' -and $_.Name -ne 'JemNexusDbContextModelSnapshot.cs'}|ForEach-Object{$_.BaseName}|Sort-Object -CaseSensitive)
    if($migrationFiles.Count -ne 22 -or (Compare-Object ($MigrationIds|Sort-Object -CaseSensitive) $migrationFiles -CaseSensitive)){throw 'LOCAL_MIGRATION_INPUTS_INVALID'}
    if(-not (Get-Command dotnet -CommandType Application -ErrorAction SilentlyContinue) -or -not (Get-Command powershell.exe -CommandType Application -ErrorAction SilentlyContinue)){throw 'LOCAL_MIGRATION_TOOLING_UNAVAILABLE'}
    $tempScript=[IO.Path]::GetTempFileName()
    & dotnet ef migrations script --project $ProjectPath --startup-project $ProjectPath --output $tempScript
    if($LASTEXITCODE -ne 0 -or (Get-Item -LiteralPath $tempScript).Length -eq 0){throw 'CANONICAL_MIGRATION_SCRIPT_GENERATION_FAILED'}
    $sql=Get-Content -LiteralPath $tempScript -Raw
    foreach($id in $MigrationIds){if($sql.IndexOf($id,[StringComparison]::Ordinal) -lt 0){throw 'CANONICAL_MIGRATION_SCRIPT_INCOMPLETE'}}

    $b=New-Object Data.SqlClient.SqlConnectionStringBuilder;$b.DataSource=$Instance;$b.InitialCatalog='master';$b.IntegratedSecurity=$true;$b.ApplicationName='JemNexusTask364ControlledPrepare'
    $master=New-Object Data.SqlClient.SqlConnection $b.ConnectionString;$master.Open()
    $cmd=$master.CreateCommand();$cmd.CommandText=@"
SET XACT_ABORT ON;
IF COALESCE(TRY_CONVERT(int,SERVERPROPERTY('IsLocalDB')),0)<>1 OR CONVERT(nvarchar(128),SERVERPROPERTY('InstanceName')) COLLATE Latin1_General_100_BIN2<>N'MSSQLLocalDB' THROW 51000,'SERVER_NOT_EXPECTED_LOCALDB',1;
IF DB_NAME()<>N'master' THROW 51000,'MASTER_IDENTITY_MISMATCH',1;
IF DB_ID(N'$Database') IS NOT NULL THROW 51000,'DATABASE_ALREADY_EXISTS',1;
CREATE DATABASE [$Database];
"@
    [void]$cmd.ExecuteNonQuery();$cmd.Dispose();$master.Dispose();$master=$null

    $b.InitialCatalog=$Database;$target=New-Object Data.SqlClient.SqlConnection $b.ConnectionString;$target.Open()
    $cmd=$target.CreateCommand();$cmd.CommandText=@"
IF COALESCE(TRY_CONVERT(int,SERVERPROPERTY('IsLocalDB')),0)<>1 OR DB_NAME()<>N'$Database' THROW 51000,'TARGET_IDENTITY_MISMATCH',1;
CREATE SCHEMA [$Schema] AUTHORIZATION [dbo];
CREATE USER [JemNexusTask364MigrationUser] WITHOUT LOGIN WITH DEFAULT_SCHEMA=[$Schema];
GRANT CREATE TABLE, CREATE SEQUENCE TO [JemNexusTask364MigrationUser];
GRANT ALTER, REFERENCES, SELECT, INSERT, UPDATE ON SCHEMA::[$Schema] TO [JemNexusTask364MigrationUser];
EXECUTE AS USER=N'JemNexusTask364MigrationUser';
IF HAS_PERMS_BY_NAME(DB_NAME(),N'DATABASE',N'CREATE TABLE')<>1
 OR HAS_PERMS_BY_NAME(DB_NAME(),N'DATABASE',N'CREATE SEQUENCE')<>1
 OR HAS_PERMS_BY_NAME(N'$Schema',N'SCHEMA',N'ALTER')<>1
 OR HAS_PERMS_BY_NAME(N'$Schema',N'SCHEMA',N'REFERENCES')<>1
 OR HAS_PERMS_BY_NAME(N'$Schema',N'SCHEMA',N'SELECT')<>1
 OR HAS_PERMS_BY_NAME(N'$Schema',N'SCHEMA',N'INSERT')<>1
 OR HAS_PERMS_BY_NAME(N'$Schema',N'SCHEMA',N'UPDATE')<>1
 THROW 51000,'IMPERSONATED_MIGRATION_PERMISSIONS_INSUFFICIENT',1;
"@;[void]$cmd.ExecuteNonQuery();$cmd.Dispose()

    # Execute every canonical GO batch in the same impersonated session so every
    # unqualified object resolves to $Schema.
    foreach($batch in [regex]::Split($sql,'(?im)^\s*GO\s*(?:--.*)?$')){if(-not [string]::IsNullOrWhiteSpace($batch)){$cmd=$target.CreateCommand();$cmd.CommandTimeout=300;$cmd.CommandText=$batch;[void]$cmd.ExecuteNonQuery();$cmd.Dispose()}}
    $migrationValues=(($MigrationIds|ForEach-Object{"(N'$_')"}) -join ',')
    $cmd=$target.CreateCommand();$cmd.CommandText="REVERT; IF DB_NAME()<>N'$Database' OR COALESCE(TRY_CONVERT(int,SERVERPROPERTY('IsLocalDB')),0)<>1 THROW 51000,'POST_MIGRATION_IDENTITY_MISMATCH',1; IF (SELECT COUNT(*) FROM [$Schema].[__EFMigrationsHistory])<>22 OR EXISTS(SELECT MigrationId FROM [$Schema].[__EFMigrationsHistory] EXCEPT SELECT v.Id FROM (VALUES $migrationValues)v(Id)) OR EXISTS(SELECT v.Id FROM (VALUES $migrationValues)v(Id) EXCEPT SELECT MigrationId FROM [$Schema].[__EFMigrationsHistory]) THROW 51000,'MIGRATIONS_MISMATCH',1; IF (SELECT COUNT(*) FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE s.name=N'$Schema')<>19 THROW 51000,'TABLE_SET_MISMATCH',1; IF OBJECT_ID(N'[$Schema].[__EFMigrationsHistory]',N'U') IS NULL OR NOT EXISTS(SELECT 1 FROM sys.sequences q JOIN sys.schemas s ON s.schema_id=q.schema_id WHERE s.name=N'$Schema' AND q.name=N'SellerCodeSequence') THROW 51000,'REQUIRED_OBJECTS_MISSING',1; EXEC sys.sp_addextendedproperty @name=N'$MarkerName',@value=N'$MarkerValue';";[void]$cmd.ExecuteNonQuery();$cmd.Dispose()
    $target.Dispose();$target=$null
    $inspection=& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $InspectorPath -Mode InspectDisposable -ProductionBaselinePath $item.FullName
    if($LASTEXITCODE -ne 0 -or (($inspection|Select-Object -Last 1|ConvertFrom-Json).status -cne 'READY_FOR_DISPOSABLE_REHEARSAL')){throw 'POST_PREPARATION_INSPECTION_FAILED'}
    Result 'PREPARED_AND_INSPECTED' @('PRODUCTION_DRIFT_RECHECK_REQUIRED','NO_PRODUCTION_AUTHORIZATION');exit 0
}catch{Result 'NO-GO' @($(if($_.Exception.Message -match '^[A-Z0-9_]+$'){$_.Exception.Message}else{'PARTIAL_PREPARATION_REQUIRES_MANUAL_DIAGNOSIS'}));exit 2}
finally{if($target){$target.Dispose()};if($master){$master.Dispose()};if($tempScript -and (Test-Path -LiteralPath $tempScript)){Remove-Item -LiteralPath $tempScript -Force}}
