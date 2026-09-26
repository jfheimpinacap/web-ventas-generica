#requires -Version 5.1
<#
.SYNOPSIS
Read-only gate for the task 364 disposable import rehearsal database.

.NOTES
This tool has no Apply mode and accepts neither server/database names nor a
connection string.  InspectDisposable always uses Windows integrated security,
the compiled LocalDB endpoint and the compiled disposable database name.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('PlanOnly','InspectDisposable')][string]$Mode,
    [string]$ProductionBaselinePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedInstance = '(localdb)\MSSQLLocalDB'
$ExpectedDatabase = 'JemNexus_DisposableRehearsal_364'
$ApplicationSchema = 'jemnexusb_api'
$HistorySchema = 'jemnexusb_api'
$SequenceSchema = 'jemnexusb_api'
$MarkerScope = 'database'
$ExpectedMarkerName = 'JemNexus.DisposableRehearsalMarker'
$ExpectedMarkerValue = 'TASK-364|READONLY-PREFLIGHT|DISPOSABLE'
$ForbiddenDatabases = @('JemNexus_Local','jemnexusb_prod')
$ImportTables = @(
    'AppUsers','AppUserPermissions','Brands','Categories','Suppliers','TechnicalSheets',
    'Products','ProductImages','ProductSpecs','Promotions','HomeSectionItems','QuoteRequests',
    'CustomerProfiles','CommercialQuotes','CommercialQuoteItems','CommercialQuoteFolioCounters',
    'CommercialQuoteIssueIdempotencyRecords'
)
$KnownMigrations = @(
    '20260603182917_InitialCommercialSchema','20260604020543_AddAuthUsersAndAuditRelations',
    '20260616000000_AddCategoryProductType','20260619000000_AddProductPriceDisplayFields',
    '20260619010000_EnsureCanonicalRootCategories','20260803000000_AddMachineryTechnicalData',
    '20260803010000_AddTechnicalSheets','20260810080000_AddProductTechnicalSheetAssociation',
    '20260811000000_AddStructuredMachineryTechnicalData','20260812000000_AddProductMachineWeight',
    '20260816000000_AddSellerCodes','20260817000000_AddCustomerProfiles',
    '20260817010000_AddCommercialQuotes','20260818010000_AddCommercialQuoteIssuanceAndFolios',
    '20260822000000_AddRefreshTokenRotation','20260822010000_AddRefreshTokenPasswordVersion',
    '20260822020000_AddCommercialQuoteIssueIdempotency','20260824010000_AddSellerContactQuoteSnapshots',
    '20260825010000_AddCustomerProfileStatus','20260830000000_PreserveQuotesWhenDeletingProducts',
    '20260917000000_AddGranularSellerPermissions','20260922000000_AddCommercialQuoteIssuedBy'
)
$RequiredChecks = @('CK_AppUsers_Role_SellerCode')
$RequiredSequence = 'SellerCodeSequence'
$FingerprintKinds = @('columns','primaryKeys','foreignKeys','indexes','checks','identities','sequence')

function Get-Sha256Text([string]$Value) {
    $sha=[Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value))).Replace('-','').ToLowerInvariant()) }
    finally { $sha.Dispose() }
}
function Write-Result([string]$Status,[System.Collections.IDictionary]$Counts,[System.Collections.IDictionary]$Fingerprints,[string[]]$Blockers) {
    [ordered]@{status=$Status;identity=[ordered]@{localdb=($Status -eq 'READY_FOR_DISPOSABLE_REHEARSAL');databaseClass='TASK_364_FIXED_DISPOSABLE';applicationSchema=$ApplicationSchema;historySchema=$HistorySchema;sequenceSchema=$SequenceSchema;markerScope=$MarkerScope};counts=$Counts;schemaFingerprints=$Fingerprints;blockers=@($Blockers);productionAuthorized=$false} |
        ConvertTo-Json -Depth 6 -Compress | Write-Output
}
function Invoke-ReadOnly([Data.SqlClient.SqlConnection]$Connection,[string]$Sql) {
    $clean=([regex]::Replace([regex]::Replace($Sql,'/\*.*?\*/',' ','Singleline'),'--[^\r\n]*',' ')).Trim()
    if($clean -notmatch '^(?i:SELECT|WITH)\b' -or $clean -match '(?i)\b(INSERT|UPDATE|DELETE|MERGE|ALTER|CREATE|DROP|TRUNCATE|EXEC(?:UTE)?|GRANT|REVOKE|DENY|DBCC)\b'){throw 'QUERY_NOT_READ_ONLY'}
    $command=$Connection.CreateCommand();$command.CommandText=$Sql;$command.CommandTimeout=30
    $table=New-Object Data.DataTable;$adapter=New-Object Data.SqlClient.SqlDataAdapter $command
    try{[void]$adapter.Fill($table);Write-Output -NoEnumerate $table}finally{$adapter.Dispose();$command.Dispose()}
}
function Get-CanonicalHash([Data.DataTable]$Table,[string[]]$Columns) {
    $lines=New-Object Collections.Generic.List[string]
    foreach($row in $Table.Rows){$values=@();foreach($column in $Columns){$value=$row[$column];$values += $(if($value -is [DBNull]){'<NULL>'}else{([string]$value).Replace("`r",'').Replace("`n",' ')})};$lines.Add(($values -join '|'))}
    return Get-Sha256Text (($lines | Sort-Object -CaseSensitive) -join "`n")
}

if($Mode -eq 'PlanOnly') {
    if($PSBoundParameters.ContainsKey('ProductionBaselinePath')){Write-Result 'NO-GO' @{} @{} @('PLAN_ONLY_REJECTS_INPUT_PATHS');exit 2}
    Write-Result 'PLAN_ONLY' @{expectedMigrations=22;importTables=17} @{} @('DATABASE_NOT_INSPECTED','PRODUCTION_DRIFT_RECHECK_REQUIRED','NO_DATABASE_WRITE_IMPLEMENTED')
    exit 0
}

if([string]::IsNullOrWhiteSpace($ProductionBaselinePath)){Write-Result 'NO-GO' @{} @{} @('PRODUCTION_BASELINE_REQUIRED');exit 2}
$blockers=New-Object Collections.Generic.List[string]
$counts=[ordered]@{};$fingerprints=[ordered]@{};$connection=$null
try {
    # Validate the sanitized baseline before opening SQL.  It is evidence, not a live-production assertion.
    $baselineItem=Get-Item -LiteralPath $ProductionBaselinePath -Force
    if(-not ($baselineItem -is [IO.FileInfo]) -or ($baselineItem.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'PRODUCTION_BASELINE_INVALID'}
    $baseline=Get-Content -LiteralPath $baselineItem.FullName -Raw | ConvertFrom-Json
    if($baseline.reportType -cne 'JemNexusProductionSchemaBaseline' -or $baseline.database -cne 'jemnexusb_prod' -or $baseline.schema -cne $ApplicationSchema -or $baseline.historySchema -cne $HistorySchema -or $baseline.sequenceSchema -cne $SequenceSchema -or $baseline.markerScope -cne $MarkerScope -or [int]$baseline.migrationCount -ne 22 -or [string]::IsNullOrWhiteSpace([string]$baseline.evidenceCapturedUtc)){throw 'PRODUCTION_BASELINE_INVALID'}
    $baselineMigrations=@($baseline.migrationIds|ForEach-Object{[string]$_})
    if($baselineMigrations.Count -ne 22 -or (Compare-Object $KnownMigrations $baselineMigrations -CaseSensitive)){throw 'PRODUCTION_BASELINE_INVALID'}
    foreach($kind in $FingerprintKinds){if(([string]$baseline.schemaFingerprints.$kind) -notmatch '^[0-9a-f]{64}$'){throw 'PRODUCTION_BASELINE_INVALID'}}

    $builder=New-Object Data.SqlClient.SqlConnectionStringBuilder
    $builder.DataSource=$ExpectedInstance;$builder.InitialCatalog=$ExpectedDatabase
    $builder.IntegratedSecurity=$true;$builder.ApplicationName='JemNexusTask364ReadOnlyPreflight'
    $builder.ApplicationIntent=[Data.SqlClient.ApplicationIntent]::ReadOnly
    $connection=New-Object Data.SqlClient.SqlConnection $builder.ConnectionString;$connection.Open()

    $identity=Invoke-ReadOnly $connection "SELECT CONVERT(int,SERVERPROPERTY('IsLocalDB')) IsLocalDB,DB_NAME() DatabaseName,COUNT_BIG(*) MarkerCount,MAX(CONVERT(nvarchar(256),value)) MarkerValue FROM fn_listextendedproperty('$ExpectedMarkerName',DEFAULT,DEFAULT,DEFAULT,DEFAULT,DEFAULT,DEFAULT)"
    if($identity.Rows.Count -ne 1){$blockers.Add('IDENTITY_AMBIGUOUS')}
    else {
        $row=$identity.Rows[0]
        if($row.IsLocalDB -is [DBNull] -or [int]$row.IsLocalDB -ne 1){$blockers.Add('SERVER_NOT_LOCALDB')}
        if([string]$row.DatabaseName -cne $ExpectedDatabase -or [string]$row.DatabaseName -cin $ForbiddenDatabases){$blockers.Add('DATABASE_IDENTITY_MISMATCH')}
        if([long]$row.MarkerCount -ne 1 -or [string]$row.MarkerValue -cne $ExpectedMarkerValue){$blockers.Add('DISPOSABLE_MARKER_MISSING_OR_AMBIGUOUS')}
    }
    if($blockers.Count -gt 0){throw 'IDENTITY_GATE_FAILED'}

    $migrations=Invoke-ReadOnly $connection "SELECT MigrationId FROM [$HistorySchema].[__EFMigrationsHistory] ORDER BY MigrationId"
    $applied=@($migrations.Rows|ForEach-Object{[string]$_.MigrationId})
    if($applied.Count -ne 22 -or (Compare-Object $KnownMigrations $applied -CaseSensitive)){$blockers.Add('MIGRATIONS_MISMATCH')}

    $tables=Invoke-ReadOnly $connection "SELECT t.name TableName FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE s.name='$ApplicationSchema' AND t.name IN ('$($ImportTables -join "','")') ORDER BY t.name"
    if($tables.Rows.Count -ne 17){$blockers.Add('IMPORT_TABLE_SET_MISMATCH')}
    $metadataQueries=[ordered]@{
      columns=@("SELECT t.name TableName,c.column_id Ordinal,c.name ColumnName,ty.name TypeName,c.max_length MaxLength,c.precision Precision,c.scale Scale,c.is_nullable Nullable,c.collation_name Collation FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.columns c ON c.object_id=t.object_id JOIN sys.types ty ON ty.user_type_id=c.user_type_id WHERE s.name='$ApplicationSchema' AND t.name IN ('$($ImportTables -join "','")') ORDER BY t.name,c.column_id",@('TableName','Ordinal','ColumnName','TypeName','MaxLength','Precision','Scale','Nullable','Collation'))
      primaryKeys=@("SELECT t.name TableName,k.name KeyName,ic.key_ordinal Ordinal,c.name ColumnName FROM sys.key_constraints k JOIN sys.tables t ON t.object_id=k.parent_object_id JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.index_columns ic ON ic.object_id=t.object_id AND ic.index_id=k.unique_index_id JOIN sys.columns c ON c.object_id=t.object_id AND c.column_id=ic.column_id WHERE s.name='$ApplicationSchema' AND k.type='PK' AND t.name IN ('$($ImportTables -join "','")') ORDER BY t.name,ic.key_ordinal",@('TableName','KeyName','Ordinal','ColumnName'))
      foreignKeys=@("SELECT ps.name ParentSchema,pt.name TableName,fk.name ForeignKey,pc.name ColumnName,rs.name ReferencedSchema,rt.name ReferencedTable,rc.name ReferencedColumn,fk.delete_referential_action_desc DeleteAction,fk.is_disabled IsDisabled,fk.is_not_trusted IsNotTrusted FROM sys.foreign_keys fk JOIN sys.tables pt ON pt.object_id=fk.parent_object_id JOIN sys.schemas ps ON ps.schema_id=pt.schema_id JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id=fk.object_id JOIN sys.columns pc ON pc.object_id=fkc.parent_object_id AND pc.column_id=fkc.parent_column_id JOIN sys.tables rt ON rt.object_id=fk.referenced_object_id JOIN sys.schemas rs ON rs.schema_id=rt.schema_id JOIN sys.columns rc ON rc.object_id=fkc.referenced_object_id AND rc.column_id=fkc.referenced_column_id WHERE ps.name='$ApplicationSchema' AND pt.name IN ('$($ImportTables -join "','")') ORDER BY pt.name,fk.name,fkc.constraint_column_id",@('ParentSchema','TableName','ForeignKey','ColumnName','ReferencedSchema','ReferencedTable','ReferencedColumn','DeleteAction','IsDisabled','IsNotTrusted'))
      indexes=@("SELECT t.name TableName,i.name IndexName,i.is_unique IsUnique,i.filter_definition FilterDefinition,ic.key_ordinal Ordinal,c.name ColumnName FROM sys.indexes i JOIN sys.tables t ON t.object_id=i.object_id JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id WHERE s.name='$ApplicationSchema' AND i.is_hypothetical=0 AND i.name IS NOT NULL AND t.name IN ('$($ImportTables -join "','")') ORDER BY t.name,i.name,ic.key_ordinal,ic.index_column_id",@('TableName','IndexName','IsUnique','FilterDefinition','Ordinal','ColumnName'))
      checks=@("SELECT t.name TableName,cc.name CheckName,cc.definition Definition,cc.is_disabled IsDisabled,cc.is_not_trusted IsNotTrusted FROM sys.check_constraints cc JOIN sys.tables t ON t.object_id=cc.parent_object_id JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE s.name='$ApplicationSchema' AND t.name IN ('$($ImportTables -join "','")') ORDER BY t.name,cc.name",@('TableName','CheckName','Definition','IsDisabled','IsNotTrusted'))
      identities=@("SELECT t.name TableName,ic.name ColumnName,CONVERT(nvarchar(40),ic.seed_value) SeedValue,CONVERT(nvarchar(40),ic.increment_value) IncrementValue FROM sys.identity_columns ic JOIN sys.tables t ON t.object_id=ic.object_id JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE s.name='$ApplicationSchema' AND t.name IN ('$($ImportTables -join "','")') ORDER BY t.name,ic.name",@('TableName','ColumnName','SeedValue','IncrementValue'))
      sequence=@("SELECT s.name SchemaName,q.name SequenceName,CONVERT(nvarchar(40),q.start_value) StartValue,CONVERT(nvarchar(40),q.increment) IncrementValue FROM sys.sequences q JOIN sys.schemas s ON s.schema_id=q.schema_id WHERE s.name='$SequenceSchema' AND q.name='$RequiredSequence'",@('SchemaName','SequenceName','StartValue','IncrementValue'))
    }
    foreach($kind in $metadataQueries.Keys){$spec=$metadataQueries[$kind];$data=Invoke-ReadOnly $connection $spec[0];$fingerprints[$kind]=Get-CanonicalHash $data $spec[1];$counts[$kind]=$data.Rows.Count;if($fingerprints[$kind] -cne [string]$baseline.schemaFingerprints.$kind){$blockers.Add(('SCHEMA_{0}_MISMATCH' -f $kind.ToUpperInvariant()))}}
    if([int]$counts.primaryKeys -lt 17 -or [int]$counts.identities -ne 14 -or [int]$counts.sequence -ne 1 -or [int]$counts.checks -lt 1){$blockers.Add('EXPECTED_SCHEMA_SHAPE_MISMATCH')}
    $foreignKeyRows=Invoke-ReadOnly $connection $metadataQueries.foreignKeys[0]
    if(@($foreignKeyRows.Rows|Where-Object{[bool]$_.IsDisabled -or [bool]$_.IsNotTrusted}).Count -gt 0){$blockers.Add('FOREIGN_KEYS_DISABLED_OR_UNTRUSTED')}
    $checkRows=Invoke-ReadOnly $connection $metadataQueries.checks[0]
    if(@($checkRows.Rows|Where-Object{[bool]$_.IsDisabled -or [bool]$_.IsNotTrusted}).Count -gt 0 -or @($checkRows.Rows|Where-Object{$_.CheckName -cin $RequiredChecks}).Count -ne $RequiredChecks.Count){$blockers.Add('CHECK_CONSTRAINTS_INVALID')}
    $identityRows=Invoke-ReadOnly $connection $metadataQueries.identities[0]
    if(@($identityRows.Rows|Where-Object{$_.SeedValue -cne '1' -or $_.IncrementValue -cne '1'}).Count -gt 0){$blockers.Add('IDENTITY_CONFIGURATION_INVALID')}
    $sequenceRows=Invoke-ReadOnly $connection $metadataQueries.sequence[0]
    if($sequenceRows.Rows.Count -ne 1 -or [string]$sequenceRows.Rows[0].StartValue -cne '1' -or [string]$sequenceRows.Rows[0].IncrementValue -cne '1'){$blockers.Add('SELLER_SEQUENCE_INVALID')}

    $permission=Invoke-ReadOnly $connection "SELECT HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONNECT') CanConnect,HAS_PERMS_BY_NAME('$ApplicationSchema','SCHEMA','SELECT') CanSelect,HAS_PERMS_BY_NAME('$ApplicationSchema','SCHEMA','INSERT') CanInsert,HAS_PERMS_BY_NAME('$ApplicationSchema','SCHEMA','UPDATE') CanUpdate,HAS_PERMS_BY_NAME('$ApplicationSchema','SCHEMA','DELETE') CanDelete,HAS_PERMS_BY_NAME('$ApplicationSchema','SCHEMA','ALTER') CanAlter"
    foreach($name in @('CanConnect','CanSelect','CanInsert','CanUpdate','CanDelete','CanAlter')){if([int]$permission.Rows[0][$name] -ne 1){$blockers.Add('IMPORT_PERMISSIONS_INSUFFICIENT');break}}
    $folios=Invoke-ReadOnly $connection "SELECT (SELECT COUNT_BIG(*) FROM [$ApplicationSchema].[CommercialQuoteFolioCounters]) CounterRows,(SELECT COUNT_BIG(*) FROM [$ApplicationSchema].[CommercialQuotes] q LEFT JOIN [$ApplicationSchema].[CommercialQuoteFolioCounters] fc ON fc.Year=q.FolioYear WHERE q.FolioYear IS NOT NULL AND q.FolioSequenceNumber IS NOT NULL AND (fc.LastNumber IS NULL OR fc.LastNumber<q.FolioSequenceNumber)) InvalidFolios"
    $counts.folioCounters=[long]$folios.Rows[0].CounterRows
    if($folios.Rows[0].InvalidFolios -isnot [DBNull] -and [long]$folios.Rows[0].InvalidFolios -ne 0){$blockers.Add('FOLIO_STATE_INVALID')}
} catch {
    if($blockers.Count -eq 0){$blockers.Add($(if($_.Exception.Message -match '^[A-Z0-9_]+$'){$_.Exception.Message}else{'INSPECTION_FAILED'}))}
} finally {if($connection){$connection.Dispose()}}

$counts.migrations=22;$counts.importTables=17
$status=$(if($blockers.Count -eq 0){'READY_FOR_DISPOSABLE_REHEARSAL'}else{'NO-GO'})
if($status -eq 'READY_FOR_DISPOSABLE_REHEARSAL'){$blockers.Add('PRODUCTION_DRIFT_RECHECK_REQUIRED');$blockers.Add('NO_PRODUCTION_AUTHORIZATION')}
Write-Result $status $counts $fingerprints @($blockers)
exit $(if($status -eq 'READY_FOR_DISPOSABLE_REHEARSAL'){0}else{2})
