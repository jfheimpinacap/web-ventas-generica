# Shared JSON routines for the exporter and the Windows PowerShell 5.1 harness.

function Convert-TableRows($Table) {
    $result = New-Object Collections.Generic.List[object]
    foreach ($row in $Table.Rows) {
        $record = [ordered]@{}
        foreach ($column in $Table.Columns) {
            $value = $row[$column.ColumnName]
            $record[$column.ColumnName] = if ($value -is [DBNull]) { $null } elseif ($value -is [byte[]]) { [Convert]::ToBase64String($value) } else { $value }
        }
        $result.Add([pscustomobject]$record)
    }
    Write-Output -NoEnumerate ([object[]]$result.ToArray())
}

function Write-TableJson([string]$Path, [object[]]$Rows) {
    # -InputObject is intentional.  A pipeline enumerates arrays: zero values
    # produce no JSON and one value loses its surrounding array in PowerShell 5.1.
    $json = ConvertTo-Json -InputObject ([object[]]$Rows) -Depth 20 -Compress
    [IO.File]::WriteAllText($Path, $json, (New-Object Text.UTF8Encoding($false)))
}

function Read-AndAssertTableJson([string]$Path, [long]$ExpectedCount) {
    $json = [IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8)
    try { $value = $json | ConvertFrom-Json } catch { throw "JSON de tabla invalido: $([IO.Path]::GetFileName($Path))" }
    if (-not $json.TrimStart().StartsWith('[', [StringComparison]::Ordinal)) {
        throw "JSON de tabla no es un array: $([IO.Path]::GetFileName($Path))"
    }
    $items = @($value)
    $actualCount = [long]($items.Count)
    if ($actualCount -ne $ExpectedCount) {
        throw "Cardinalidad JSON de tabla invalida: $([IO.Path]::GetFileName($Path))"
    }
    foreach ($item in $items) {
        if ($null -eq $item -or $item -isnot [pscustomobject]) {
            throw "Fila JSON de tabla invalida: $([IO.Path]::GetFileName($Path))"
        }
    }
}
