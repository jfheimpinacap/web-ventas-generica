#requires -Version 5.1
$ErrorActionPreference='Stop'
. (Join-Path (Split-Path -Parent $PSScriptRoot) 'New-JemNexusProductionBaselineSqlConnection.ps1')
$secret=New-Object Security.SecureString
$sqlConnection=$null
$integratedConnection=$null
$endpoint='tcp:synthetic-endpoint.invalid,1444'
$expectedIdentity="SYNTHETIC\INSTANCE'O"
try {
    # Synthetic value assembled without materializing a plaintext password.
    foreach($code in @(83,121,110,116,104,101,116,105,99,45,52,50)){$secret.AppendChar([char]$code)}
    if(-not $secret.IsReadOnly()){$secret.MakeReadOnly()}
    if(-not $secret.IsReadOnly()){throw 'SECURE_STRING_NOT_READ_ONLY'}
    $credential=New-Object Data.SqlClient.SqlCredential -ArgumentList @('synthetic_login',$secret)

    $sqlConnection=New-JemNexusProductionBaselineSqlConnection -Server $endpoint -Database 'jemnexusb_prod' -Authentication SqlCredential -Credential $credential
    $sqlBuilder=New-Object Data.SqlClient.SqlConnectionStringBuilder $sqlConnection.ConnectionString
    if($sqlBuilder['Data Source']-cne $endpoint -or $sqlBuilder['Initial Catalog']-cne 'jemnexusb_prod'){throw 'SYNTHETIC_TARGET_INVALID'}
    if($sqlBuilder['ApplicationIntent']-ne [Data.SqlClient.ApplicationIntent]::ReadOnly -or $sqlBuilder['Application Name']-cne 'JemNexusBaselineReadOnly' -or -not [bool]$sqlBuilder['Encrypt'] -or [bool]$sqlBuilder['TrustServerCertificate']){throw 'READ_ONLY_TLS_CONFIGURATION_INVALID'}
    if([bool]$sqlBuilder['Integrated Security'] -or -not [string]::IsNullOrEmpty([string]$sqlBuilder['User ID']) -or -not [string]::IsNullOrEmpty([string]$sqlBuilder['Password'])){throw 'CONNECTION_STRING_CONTAINS_CREDENTIAL'}
    if(-not [object]::ReferenceEquals($sqlConnection.Credential,$credential)){throw 'SQL_CREDENTIAL_NOT_ASSIGNED'}
    if($sqlConnection.State-ne [Data.ConnectionState]::Closed){throw 'CONNECTION_WAS_OPENED'}
    $template=Get-Content -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'Capture-JemNexusProductionSchemaBaseline.sql') -Raw
    $sqlCredentialCommand=New-JemNexusProductionBaselineCommandText -Template $template -ExpectedServerIdentity $expectedIdentity
    if($sqlCredentialCommand-notlike "*N'SYNTHETIC\INSTANCE''O'*" -or $sqlCredentialCommand-like "*$endpoint*" -or $sqlCredentialCommand-like '*$(ExpectedServerIdentity)*'){throw 'SQL_IDENTITY_SUBSTITUTION_INVALID'}

    $integratedConnection=New-JemNexusProductionBaselineSqlConnection -Server $endpoint -Database 'jemnexusb_prod' -Authentication Integrated
    $integratedBuilder=New-Object Data.SqlClient.SqlConnectionStringBuilder $integratedConnection.ConnectionString
    if($integratedBuilder['Data Source']-cne $endpoint -or $integratedBuilder['Initial Catalog']-cne 'jemnexusb_prod'){throw 'SYNTHETIC_TARGET_INVALID'}
    if($integratedBuilder['ApplicationIntent']-ne [Data.SqlClient.ApplicationIntent]::ReadOnly -or $integratedBuilder['Application Name']-cne 'JemNexusBaselineReadOnly' -or -not [bool]$integratedBuilder['Encrypt'] -or [bool]$integratedBuilder['TrustServerCertificate']){throw 'READ_ONLY_TLS_CONFIGURATION_INVALID'}
    if(-not [string]::IsNullOrEmpty([string]$integratedBuilder['User ID']) -or -not [string]::IsNullOrEmpty([string]$integratedBuilder['Password'])){throw 'CONNECTION_STRING_CONTAINS_CREDENTIAL'}
    if(-not [bool]$integratedBuilder['Integrated Security'] -or $null-ne $integratedConnection.Credential){throw 'INTEGRATED_AUTHENTICATION_INVALID'}
    if($integratedConnection.State-ne [Data.ConnectionState]::Closed){throw 'CONNECTION_WAS_OPENED'}
    $integratedCommand=New-JemNexusProductionBaselineCommandText -Template $template -ExpectedServerIdentity $expectedIdentity
    if($integratedCommand-cne $sqlCredentialCommand -or $integratedCommand-like "*$endpoint*"){throw 'AUTHENTICATION_SQL_ROUTING_INVALID'}
    Write-Output 'SQL_CREDENTIAL_CONSTRUCTION_OK'
    Write-Output 'INTEGRATED_CONSTRUCTION_OK'
} finally {
    if($null-ne $sqlConnection){$sqlConnection.Dispose()}
    if($null-ne $integratedConnection){$integratedConnection.Dispose()}
    $secret.Dispose()
}
