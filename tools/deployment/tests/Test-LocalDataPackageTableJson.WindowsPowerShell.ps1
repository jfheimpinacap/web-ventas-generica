#requires -Version 5.1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\LocalDataPackageJson.ps1')

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
        Write-TableJson $path $rows
        Read-AndAssertTableJson $path $count
        $raw = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8)
        if ($count -eq 0 -and $raw -cne '[]') { throw "Una tabla vacia no produjo []: $raw" }
        $roundTrip = @($raw | ConvertFrom-Json)
        for ($index = 0; $index -lt $count; $index++) {
            if ([long]$roundTrip[$index].Id -ne $index + 1 -or [string]$roundTrip[$index].Name -cne "row-$index") {
                throw 'El orden, columnas o valores no sobrevivieron la serializacion.'
            }
        }
    }
    'WINDOWS_POWERSHELL_5_1_TABLE_JSON_TEST_OK'
} finally {
    if ([IO.Directory]::Exists($root)) { [IO.Directory]::Delete($root, $true) }
}
