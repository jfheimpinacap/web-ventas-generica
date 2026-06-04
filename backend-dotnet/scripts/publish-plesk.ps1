[CmdletBinding()]
param(
    [string]$Configuration = "Release",
    [string]$OutputPath = "backend-dotnet\publish\JemNexus.Api"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$slnPath = Join-Path $repoRoot "backend-dotnet\JemNexus.sln"
$projectPath = Join-Path $repoRoot "backend-dotnet\JemNexus.Api\JemNexus.Api.csproj"
$publishPath = Join-Path $repoRoot $OutputPath

Write-Host "Preparing local Plesk publish package for JEM Nexus API..."
Write-Host "Repository root: $repoRoot"
Write-Host "Configuration: $Configuration"
Write-Host "Publish output: $publishPath"
Write-Host "This script does not connect to Plesk, upload files, run SQL, or execute dotnet ef database update."

if (Test-Path $publishPath) {
    Write-Host "Removing previous publish output..."
    Remove-Item $publishPath -Recurse -Force
}

Write-Host "Restoring solution..."
dotnet restore $slnPath

Write-Host "Building solution..."
dotnet build $slnPath -c $Configuration --no-restore

Write-Host "Running tests..."
dotnet test $slnPath -c $Configuration --no-build

Write-Host "Publishing API project..."
dotnet publish $projectPath -c $Configuration -o $publishPath --no-build

Write-Host "Publish package ready at: $publishPath"
Write-Host "Upload the contents of this folder manually to the Plesk subdomain folder for api.jem-nexus.cl."
