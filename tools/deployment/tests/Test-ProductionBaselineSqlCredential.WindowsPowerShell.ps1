#requires -Version 5.1
$ErrorActionPreference='Stop'
$secret=New-Object Security.SecureString
$connection=$null
try {
    # Synthetic value assembled without materializing a plaintext password.
    foreach($code in @(83,121,110,116,104,101,116,105,99,45,52,50)){$secret.AppendChar([char]$code)}
    if(-not $secret.IsReadOnly()){$secret.MakeReadOnly()}
    if(-not $secret.IsReadOnly()){throw 'SECURE_STRING_NOT_READ_ONLY'}
    $credential=New-Object Data.SqlClient.SqlCredential -ArgumentList @('synthetic_login',$secret)

    $builder=New-Object Data.SqlClient.SqlConnectionStringBuilder
    $builder.DataSource='synthetic.invalid';$builder.InitialCatalog='jemnexusb_prod'
    $builder.IntegratedSecurity=$false;$builder.Encrypt=$true;$builder.TrustServerCertificate=$false
    if($builder.IntegratedSecurity-or -not [string]::IsNullOrEmpty($builder.UserID)-or -not [string]::IsNullOrEmpty($builder.Password)){throw 'CONNECTION_STRING_CONTAINS_CREDENTIAL'}

    $connection=New-Object Data.SqlClient.SqlConnection $builder.ConnectionString
    $connection.Credential=$credential
    if(-not [object]::ReferenceEquals($connection.Credential,$credential)){throw 'SQL_CREDENTIAL_NOT_ASSIGNED'}
    if($connection.State-ne [Data.ConnectionState]::Closed){throw 'CONNECTION_WAS_OPENED'}
    Write-Output 'SQL_CREDENTIAL_CONSTRUCTION_OK'
} finally {
    if($null-ne $connection){$connection.Dispose()}
    $secret.Dispose()
}
