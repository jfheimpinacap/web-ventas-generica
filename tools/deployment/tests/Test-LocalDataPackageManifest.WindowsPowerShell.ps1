#requires -Version 5.1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Equal($Expected, $Actual, [string]$Message) {
    if ($Expected -cne $Actual) { throw "$Message (esperado=$Expected, actual=$Actual)" }
}

function Test-ManifestRoundTrip([int]$Count) {
    # Deliberately reproduce the exporter's concrete collection and entry types.
    $media = New-Object Collections.Generic.List[object]
    for ($index = 0; $index -lt $Count; $index++) {
        $hash = $index.ToString('x64')
        $media.Add([pscustomobject][ordered]@{
            kind = 'synthetic'
            recordId = [long]$index
            parentId = $null
            packagePath = "media/synthetic/$index.bin"
            sizeBytes = [long]($index + 1)
            sha256 = $hash
        })
    }

    $expectedMediaType = [System.Collections.Generic.List[object]]
    $actualMediaType = $media.GetType()
    if ($actualMediaType -ne $expectedMediaType) {
        throw "Tipo efectivo de media inesperado (esperado=$($expectedMediaType.FullName), actual=$($actualMediaType.FullName))"
    }
    $mediaFiles = [object[]]$media.ToArray()
    $manifest = [ordered]@{
        packageVersion = 1
        packageType = 'JemNexusLocalDataPackage'
        tables = [ordered]@{ count = 17 }
        media = [ordered]@{ count = $mediaFiles.Count; files = $mediaFiles }
    }
    $json = $manifest | ConvertTo-Json -Depth 20 -Compress
    $roundTrip = $json | ConvertFrom-Json
    $files = @($roundTrip.media.files)

    Assert-Equal $Count ([int]$roundTrip.media.count) 'Conteo declarado incorrecto'
    Assert-Equal $Count $files.Count 'Cardinalidad JSON incorrecta'
    Assert-Equal 17 ([int]$roundTrip.tables.count) 'Conteo de tablas alterado'
    for ($index = 0; $index -lt $Count; $index++) {
        if ($files[$index] -is [Array]) { throw 'Se serializo un array multimedia anidado' }
        Assert-Equal "media/synthetic/$index.bin" ([string]$files[$index].packagePath) 'Entrada multimedia alterada o anidada'
        Assert-Equal $index.ToString('x64') ([string]$files[$index].sha256) 'Hash multimedia alterado'
    }
}

foreach ($count in 0, 1, 177) { Test-ManifestRoundTrip $count }
'WINDOWS_POWERSHELL_5_1_MANIFEST_TEST_OK'
