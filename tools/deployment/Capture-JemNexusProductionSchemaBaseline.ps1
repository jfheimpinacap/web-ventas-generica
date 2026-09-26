#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ExpectedProductionServer,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [Parameter(Mandatory=$true)][ValidateSet('SqlCredential','Integrated')][string]$Authentication
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Database='jemnexusb_prod'
$SqlCredential=$null
$Secret=$null
$Kinds=@('columns','primaryKeys','foreignKeys','indexes','checks','identities','sequence')
$Columns=@{
 columns=@('TableName','Ordinal','ColumnName','TypeName','MaxLength','Precision','Scale','Nullable','Collation');primaryKeys=@('TableName','KeyName','Ordinal','ColumnName');foreignKeys=@('ParentSchema','TableName','ForeignKey','ColumnName','ReferencedSchema','ReferencedTable','ReferencedColumn','DeleteAction','IsDisabled','IsNotTrusted');indexes=@('TableName','IndexName','IsUnique','FilterDefinition','Ordinal','ColumnName');checks=@('TableName','CheckName','Definition','IsDisabled','IsNotTrusted');identities=@('TableName','ColumnName','SeedValue','IncrementValue');sequence=@('SchemaName','SequenceName','StartValue','IncrementValue')
}
$KnownMigrations=@('20260603182917_InitialCommercialSchema','20260604020543_AddAuthUsersAndAuditRelations','20260616000000_AddCategoryProductType','20260619000000_AddProductPriceDisplayFields','20260619010000_EnsureCanonicalRootCategories','20260803000000_AddMachineryTechnicalData','20260803010000_AddTechnicalSheets','20260810080000_AddProductTechnicalSheetAssociation','20260811000000_AddStructuredMachineryTechnicalData','20260812000000_AddProductMachineWeight','20260816000000_AddSellerCodes','20260817000000_AddCustomerProfiles','20260817010000_AddCommercialQuotes','20260818010000_AddCommercialQuoteIssuanceAndFolios','20260822000000_AddRefreshTokenRotation','20260822010000_AddRefreshTokenPasswordVersion','20260822020000_AddCommercialQuoteIssueIdempotency','20260824010000_AddSellerContactQuoteSnapshots','20260825010000_AddCustomerProfileStatus','20260830000000_PreserveQuotesWhenDeletingProducts','20260917000000_AddGranularSellerPermissions','20260922000000_AddCommercialQuoteIssuedBy')
function Hash([Data.DataTable]$Table,[string[]]$Names){$lines=@($Table.Rows|ForEach-Object{$r=$_;(@($Names|ForEach-Object{$v=$r[$_];if($v -is [DBNull]){'<NULL>'}else{([string]$v).Replace("`r",'').Replace("`n",' ')}})-join '|')}|Sort-Object -CaseSensitive);$sha=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes(($lines-join "`n")))).Replace('-','').ToLowerInvariant())}finally{$sha.Dispose()}}
function Observe {
 $template=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'Capture-JemNexusProductionSchemaBaseline.sql') -Raw
 $sql=$template.Replace('$(ExpectedProductionServer)',$ExpectedProductionServer.Replace("'","''"))
 $b=New-Object Data.SqlClient.SqlConnectionStringBuilder;$b.DataSource=$ExpectedProductionServer;$b.InitialCatalog=$Database;$b.IntegratedSecurity=($Authentication-ceq 'Integrated');$b.Encrypt=$true;$b.TrustServerCertificate=$false;$b.ApplicationIntent=[Data.SqlClient.ApplicationIntent]::ReadOnly;$b.ApplicationName='JemNexusBaselineReadOnly'
 if($Authentication-ceq 'SqlCredential' -and ($b.IntegratedSecurity-or -not [string]::IsNullOrEmpty($b.UserID)-or -not [string]::IsNullOrEmpty($b.Password))){throw 'AUTHENTICATION_CONFIGURATION_INVALID'}
 $c=New-Object Data.SqlClient.SqlConnection $b.ConnectionString
 if($Authentication-ceq 'SqlCredential'){$c.Credential=$SqlCredential}
 try{
  try{$c.Open()}catch{throw 'AUTHENTICATION_OR_TLS_CONNECTION_FAILED'}
  $cmd=$c.CreateCommand();$cmd.CommandText=$sql;$cmd.CommandTimeout=30;$ds=New-Object Data.DataSet;$a=New-Object Data.SqlClient.SqlDataAdapter $cmd
  try{[void]$a.Fill($ds)}catch{throw 'READ_ONLY_OBSERVATION_FAILED'}finally{$a.Dispose();$cmd.Dispose()}
 }finally{$c.Dispose()}
 if($ds.Tables.Count-ne 10 -or [string]$ds.Tables[9].Rows[0].CaptureStatus-cne 'OBSERVATION_COMPLETE'){throw 'INCOMPLETE_OBSERVATION'}
 $h=$ds.Tables[0].Rows[0];$ids=@($ds.Tables[1].Rows|ForEach-Object{[string]$_.MigrationId});if($ids.Count-ne 22 -or (Compare-Object $KnownMigrations $ids -CaseSensitive)){throw 'MIGRATIONS_MISMATCH'}
 $fp=[ordered]@{};for($i=0;$i-lt 7;$i++){$fp[$Kinds[$i]]=Hash $ds.Tables[$i+2] $Columns[$Kinds[$i]]}
 [ordered]@{reportType=[string]$h.reportType;database=[string]$h.database;schema=[string]$h.schema;historySchema=[string]$h.historySchema;sequenceSchema=[string]$h.sequenceSchema;markerScope=[string]$h.markerScope;migrationCount=22;migrationIds=$ids;schemaFingerprints=$fp}
}
try {
 if([string]::IsNullOrWhiteSpace($ExpectedProductionServer)-or $ExpectedProductionServer-ceq 'REPLACE_ME'){throw 'EXPECTED_PRODUCTION_SERVER_REQUIRED'}
 $full=[IO.Path]::GetFullPath($OutputPath);$parent=Split-Path -Parent $full
 if(-not(Test-Path -LiteralPath $parent -PathType Container)){throw 'OUTPUT_DIRECTORY_MISSING'}
 if(Test-Path -LiteralPath $full){throw 'OUTPUT_ALREADY_EXISTS'}
 if($Authentication-ceq 'SqlCredential'){
  $prompt=Get-Credential -Message 'Credencial SQL para la captura read-only de jemnexusb_prod'
  if($null-eq $prompt-or [string]::IsNullOrWhiteSpace($prompt.UserName)-or $null-eq $prompt.Password){throw 'SQL_CREDENTIAL_REQUIRED'}
  $Secret=$prompt.Password
  if(-not $Secret.IsReadOnly()){$Secret.MakeReadOnly()}
  $SqlCredential=New-Object Data.SqlClient.SqlCredential -ArgumentList @($prompt.UserName,$Secret)
  $prompt=$null
 }
 $one=Observe;$two=Observe
 $a=$one|ConvertTo-Json -Depth 6 -Compress;$b=$two|ConvertTo-Json -Depth 6 -Compress;if($a-cne $b){throw 'OBSERVATIONS_DIFFER_NO_GO'}
 $one['evidenceCapturedUtc']=[DateTime]::UtcNow.ToString('o');$json=$one|ConvertTo-Json -Depth 6
 $temp=Join-Path $parent ('.baseline-'+[Guid]::NewGuid().ToString('N')+'.tmp');try{[IO.File]::WriteAllText($temp,$json,(New-Object Text.UTF8Encoding($false)));Move-Item -LiteralPath $temp -Destination $full -ErrorAction Stop}finally{if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp -Force}}
 Write-Output 'BASELINE_CAPTURE_VERIFIED_AND_SAVED'
} catch {
 $allowed=@('EXPECTED_PRODUCTION_SERVER_REQUIRED','OUTPUT_DIRECTORY_MISSING','OUTPUT_ALREADY_EXISTS','SQL_CREDENTIAL_REQUIRED','AUTHENTICATION_CONFIGURATION_INVALID','AUTHENTICATION_OR_TLS_CONNECTION_FAILED','READ_ONLY_OBSERVATION_FAILED','INCOMPLETE_OBSERVATION','MIGRATIONS_MISMATCH','OBSERVATIONS_DIFFER_NO_GO')
 $diagnostic=$(if($_.Exception.Message-cin $allowed){$_.Exception.Message}else{'BASELINE_CAPTURE_FAILED'})
 Write-Error ('NO-GO: '+$diagnostic);exit 2
} finally {if($null-ne $Secret){$Secret.Dispose();$Secret=$null};$SqlCredential=$null}
