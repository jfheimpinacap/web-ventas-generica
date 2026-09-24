#requires -Version 5.1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\LocalDataPackageJson.ps1')

function Assert-TableJsonRejected([string]$Path, [string]$Json, [long]$ExpectedCount) {
    [IO.File]::WriteAllText($Path, $Json, (New-Object Text.UTF8Encoding($false)))
    $rejected = $false
    try { Read-AndAssertTableJson $Path $ExpectedCount } catch { $rejected = $true }
    if (-not $rejected) { throw "La validacion acepto JSON de tabla inseguro: $Json" }
}

$root = Join-Path ([IO.Path]::GetTempPath()) ('jemnexus-table-json-' + [Guid]::NewGuid().ToString('N'))
try {
    [void][IO.Directory]::CreateDirectory($root)
    foreach ($count in 0, 1, 3) {
        $table = New-Object Data.DataTable
        [void]$table.Columns.Add('Id', [long])
        [void]$table.Columns.Add('Name', [string])
        for ($index = 0; $index -lt $count; $index++) {
            $row = $table.NewRow(); $row.Id = $index + 1; $row.Name = "row-$index"; [void]$table.Rows.Add($row)
        }
        $path = Join-Path $root "$count.json"
        $rows = Convert-TableRows $table
        if ($rows -isnot [object[]] -or $rows.Count -ne $count) {
            throw 'Convert-TableRows no devolvio un array superior con la cardinalidad esperada.'
        }
        Write-TableJson $path $rows
        Read-AndAssertTableJson $path $count
        $raw = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8)
        if ($count -eq 0 -and $raw -cne '[]') { throw "Una tabla vacia no produjo []: $raw" }
        $roundTrip = @($raw | ConvertFrom-Json)
        $actualCount = [long]($roundTrip.Count)
        if ($actualCount -isnot [long] -or $actualCount -ne [long]$count) { throw "Conteo round-trip inesperado: $actualCount" }
        for ($index = 0; $index -lt $count; $index++) {
            $columnNames = @($roundTrip[$index].PSObject.Properties.Name)
            if ($columnNames.Count -ne 2 -or $columnNames[0] -cne 'Id' -or $columnNames[1] -cne 'Name') {
                throw 'Las columnas o su orden no sobrevivieron la serializacion.'
            }
            if ([long]($roundTrip[$index].Id) -ne $index + 1 -or [string]($roundTrip[$index].Name) -cne "row-$index") {
                throw 'El orden, columnas o valores no sobrevivieron la serializacion.'
            }
        }
    }
    Assert-TableJsonRejected (Join-Path $root 'empty.json') '' 0
    Assert-TableJsonRejected (Join-Path $root 'invalid.json') '[' 0
    Assert-TableJsonRejected (Join-Path $root 'object.json') '{"Id":1}' 1
    Assert-TableJsonRejected (Join-Path $root 'scalar-row.json') '[1]' 1
    Assert-TableJsonRejected (Join-Path $root 'wrong-count.json') '[]' 1
    'WINDOWS_POWERSHELL_5_1_TABLE_JSON_TEST_OK'
} finally {
    if ([IO.Directory]::Exists($root)) { [IO.Directory]::Delete($root, $true) }
}
