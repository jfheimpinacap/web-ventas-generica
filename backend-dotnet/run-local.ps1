[CmdletBinding()]
param(
    [switch]$UpdateDatabase
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectPath = Join-Path $PSScriptRoot "JemNexus.Api\JemNexus.Api.csproj"
$expectedConnectionString = "Server=(localdb)\MSSQLLocalDB;Database=JemNexus_Local;Trusted_Connection=True;TrustServerCertificate=True"
$connectionString = $expectedConnectionString

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    throw "No se encontró dotnet en PATH. Instale o configure el SDK .NET antes de continuar."
}

if (-not (Test-Path -LiteralPath $projectPath -PathType Leaf)) {
    throw "No se encontró el proyecto esperado: $projectPath"
}

function Invoke-DotNetChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage
    )

    & dotnet @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage Código de salida: $LASTEXITCODE."
    }
}

$env:ASPNETCORE_ENVIRONMENT = "Development"
$env:DOTNET_ENVIRONMENT = "Development"
$env:ASPNETCORE_URLS = "http://localhost:5000"
$env:ConnectionStrings__DefaultConnection = $connectionString
$env:JWT_SECRET = ([Guid]::NewGuid().ToString("N") + [Guid]::NewGuid().ToString("N"))

Write-Host "Entorno: Development"
Write-Host "URL: http://localhost:5000"
Write-Host "Base de datos: JemNexus_Local"
Write-Host "Proyecto: $projectPath"
Write-Host "Actualización explícita de la base solicitada: $($UpdateDatabase.IsPresent)"

if ($UpdateDatabase) {
    if ($connectionString -cne $expectedConnectionString -or
        $connectionString -notmatch '^Server=\(localdb\)\\MSSQLLocalDB;' -or
        $connectionString -notmatch ';Database=JemNexus_Local;') {
        throw "La actualización se permite exclusivamente en (localdb)\MSSQLLocalDB, base JemNexus_Local."
    }

    Invoke-DotNetChecked -Arguments @("ef", "--version") -FailureMessage "dotnet-ef no está disponible; no se actualizará la base ni se iniciará el backend."
    Invoke-DotNetChecked -Arguments @("build", "--no-restore", $projectPath) -FailureMessage "La compilación previa a la actualización falló."
    Invoke-DotNetChecked -Arguments @(
        "ef", "database", "update", "--no-build",
        "--project", $projectPath,
        "--startup-project", $projectPath,
        "--connection", $connectionString
    ) -FailureMessage "La actualización de JemNexus_Local falló; no se iniciará el backend."
}

Invoke-DotNetChecked -Arguments @(
    "run", "--no-restore", "--no-launch-profile", "--project", $projectPath
) -FailureMessage "El backend finalizó con error."
