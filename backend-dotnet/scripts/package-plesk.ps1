[CmdletBinding()]
param(
    [string]$SourcePath = "backend-dotnet\publish\JemNexus.Api",
    [string]$DestinationPath = "backend-dotnet\publish\JemNexus.Api-plesk.zip",
    [switch]$IncludeWebConfig
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))

function Resolve-RepositoryPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $repoRoot $Path))
}

$sourceFullPath = Resolve-RepositoryPath -Path $SourcePath
$destinationFullPath = Resolve-RepositoryPath -Path $DestinationPath
$destinationDirectory = Split-Path $destinationFullPath -Parent

function Get-SafeRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )

    $baseFullPath = [System.IO.Path]::GetFullPath($BasePath)
    $targetFullPath = [System.IO.Path]::GetFullPath($TargetPath)

    if (-not $baseFullPath.EndsWith([System.IO.Path]::DirectorySeparatorChar.ToString())) {
        $baseFullPath = $baseFullPath + [System.IO.Path]::DirectorySeparatorChar
    }

    $baseUri = [System.Uri]::new($baseFullPath)
    $targetUri = [System.Uri]::new($targetFullPath)

    return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($targetUri).ToString()).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
}

function Test-PleskPackageExcludedPath {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][bool]$IncludeWebConfigValue
    )

    $normalizedPath = $RelativePath.Replace('\', '/')
    $fileName = [System.IO.Path]::GetFileName($RelativePath)

    if (-not $IncludeWebConfigValue -and $fileName -ieq "web.config") {
        return $true
    }

    if ($normalizedPath -imatch '(^|/)logs(/|$)') {
        return $true
    }

    if ($fileName -imatch '^stdout.*\.log$' -or $fileName -imatch 'stdout.*\.txt$') {
        return $true
    }

    if ($fileName -imatch '^\.env($|\.)' -or $fileName -imatch '\.env\.local$' -or $fileName -imatch '^.*\.local$') {
        return $true
    }

    return $false
}

Write-Host "Preparing safe Plesk ZIP for JEM Nexus API..."
Write-Host "Repository root: $repoRoot"
Write-Host "Publish source: $sourceFullPath"
Write-Host "ZIP destination: $destinationFullPath"
Write-Host "This script does not connect to Plesk, upload files, run SQL, run migrations, or touch secrets."

if (-not (Test-Path $sourceFullPath)) {
    throw "Publish source was not found. Run backend-dotnet\scripts\publish-plesk.ps1 before packaging."
}

if ($IncludeWebConfig) {
    Write-Warning "IncludeWebConfig was requested. This is exceptional and can overwrite production Plesk environment variables."
} else {
    Write-Host "El ZIP excluye web.config para no sobrescribir variables productivas de Plesk."
}

if (-not (Test-Path $destinationDirectory)) {
    New-Item -ItemType Directory -Path $destinationDirectory | Out-Null
}

if (Test-Path $destinationFullPath) {
    Remove-Item $destinationFullPath -Force
}

$zipArchive = [System.IO.Compression.ZipFile]::Open($destinationFullPath, [System.IO.Compression.ZipArchiveMode]::Create)
$includedCount = 0
$excludedPaths = New-Object System.Collections.Generic.List[string]

try {
    Get-ChildItem -Path $sourceFullPath -Recurse -File | ForEach-Object {
        $relativePath = Get-SafeRelativePath -BasePath $sourceFullPath -TargetPath $_.FullName
        $zipEntryName = $relativePath.Replace('\', '/')

        if (Test-PleskPackageExcludedPath -RelativePath $relativePath -IncludeWebConfigValue ([bool]$IncludeWebConfig)) {
            $excludedPaths.Add($zipEntryName)
        } else {
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipArchive, $_.FullName, $zipEntryName, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
            $includedCount++
        }
    }
}
finally {
    $zipArchive.Dispose()
}

$requiredEntries = @(
    "JemNexus.Api.dll",
    "JemNexus.Api.runtimeconfig.json",
    "JemNexus.Api.deps.json"
)

$validationArchive = [System.IO.Compression.ZipFile]::OpenRead($destinationFullPath)
try {
    $entryNames = @($validationArchive.Entries | ForEach-Object { $_.FullName })
    $webConfigEntries = @($entryNames | Where-Object { [System.IO.Path]::GetFileName($_) -ieq "web.config" })

    if (-not $IncludeWebConfig -and $webConfigEntries.Count -gt 0) {
        throw "Unsafe ZIP validation failed: web.config is present even though -IncludeWebConfig was not used."
    }

    foreach ($requiredEntry in $requiredEntries) {
        if ($entryNames -notcontains $requiredEntry) {
            throw "ZIP validation failed: required entry '$requiredEntry' was not found."
        }
    }

    Write-Host "ZIP validation passed. Packaged files: $($validationArchive.Entries.Count)"
}
finally {
    $validationArchive.Dispose()
}

Write-Host "Safe Plesk ZIP ready: $destinationFullPath"
Write-Host "Files included: $includedCount"

if ($excludedPaths.Count -gt 0) {
    Write-Host "Excluded paths:"
    $excludedPaths | Sort-Object | ForEach-Object { Write-Host "- $_" }
}

Write-Host "Upload and extract this ZIP manually in Plesk only after taking a backup. Do not replace the production web.config during normal publishes."
