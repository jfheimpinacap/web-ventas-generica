#requires -Version 5.1

function New-JemNexusProductionBaselineSqlConnection {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$Server,
        [Parameter(Mandatory=$true)][string]$Database,
        [Parameter(Mandatory=$true)][ValidateSet('SqlCredential','Integrated')][string]$Authentication,
        [Data.SqlClient.SqlCredential]$Credential
    )

    $builder=New-Object Data.SqlClient.SqlConnectionStringBuilder
    $builder['Data Source']=$Server
    $builder['Initial Catalog']=$Database
    $builder['Integrated Security']=($Authentication-ceq 'Integrated')
    $builder['Encrypt']=$true
    $builder['TrustServerCertificate']=$false
    $builder['ApplicationIntent']=[Data.SqlClient.ApplicationIntent]::ReadOnly
    $builder['Application Name']='JemNexusBaselineReadOnly'

    if($builder['Data Source']-cne $Server -or $builder['Initial Catalog']-cne $Database -or
       $builder['ApplicationIntent']-ne [Data.SqlClient.ApplicationIntent]::ReadOnly -or
       -not [bool]$builder['Encrypt'] -or [bool]$builder['TrustServerCertificate'] -or
       $builder['Application Name']-cne 'JemNexusBaselineReadOnly'){
        throw 'CONNECTION_CONFIGURATION_INVALID'
    }
    if(-not [string]::IsNullOrEmpty([string]$builder['User ID']) -or
       -not [string]::IsNullOrEmpty([string]$builder['Password'])){
        throw 'AUTHENTICATION_CONFIGURATION_INVALID'
    }

    $connectionString=$builder.ConnectionString
    if([string]::IsNullOrWhiteSpace($connectionString)){throw 'CONNECTION_CONFIGURATION_INVALID'}
    $connection=New-Object Data.SqlClient.SqlConnection $connectionString
    if($Authentication-ceq 'SqlCredential'){
        if([bool]$builder['Integrated Security'] -or $null-eq $Credential){
            $connection.Dispose()
            throw 'AUTHENTICATION_CONFIGURATION_INVALID'
        }
        $connection.Credential=$Credential
    } elseif(-not [bool]$builder['Integrated Security'] -or $null-ne $connection.Credential){
        $connection.Dispose()
        throw 'AUTHENTICATION_CONFIGURATION_INVALID'
    }
    return $connection
}
