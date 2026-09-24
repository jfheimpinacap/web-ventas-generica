#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('PlanOnly', 'ExportLocal')]
    [string]$Mode,
    [string]$LocalInstance = '(localdb)\MSSQLLocalDB',
    [string]$LocalDatabase = 'JemNexus_Local',
    [string]$LocalSchema = 'dbo',
    [string]$InventoryPath,
    [string]$ImageUploadsRoot,
    [string]$TechnicalSheetsRoot,
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'LocalDataPackageJson.ps1')

$ExpectedInstance = '(localdb)\MSSQLLocalDB'
$ExpectedDatabase = 'JemNexus_Local'
$ExpectedSchema = 'dbo'
$PackageVersion = 1
$Tables = @(
    'AppUsers','AppUserPermissions','Brands','Categories','Suppliers','TechnicalSheets',
    'Products','ProductImages','ProductSpecs','Promotions','HomeSectionItems','QuoteRequests',
    'CustomerProfiles','CommercialQuotes','CommercialQuoteItems','CommercialQuoteFolioCounters',
    'CommercialQuoteIssueIdempotencyRecords'
)
$ExpectedCounts = [ordered]@{
    AppUsers=3; AppUserPermissions=58; Brands=3; Categories=10; Suppliers=0; TechnicalSheets=85
    Products=92; ProductImages=92; ProductSpecs=58; Promotions=0; HomeSectionItems=0
    QuoteRequests=0; CustomerProfiles=1; CommercialQuotes=9; CommercialQuoteItems=9
    CommercialQuoteFolioCounters=1; CommercialQuoteIssueIdempotencyRecords=8
}

function Fail([string]$Message) { throw $Message }
function Canonical([string]$Path) { [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) }
function Assert-LocalIdentityParameters {
    if ($LocalInstance -cne $ExpectedInstance -or $LocalDatabase -cne $ExpectedDatabase -or $LocalSchema -cne $ExpectedSchema) {
        Fail 'Solo se permite (localdb)\MSSQLLocalDB / JemNexus_Local / dbo.'
    }
}
function Assert-OutsideRepository([string]$Path) {
    $candidate = Canonical $Path
    $repo = Canonical (Join-Path $PSScriptRoot '..\..')
    if ($candidate -eq $repo -or $candidate.StartsWith($repo + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        Fail 'OutputRoot debe estar fuera del repositorio.'
    }
    $candidate
}
function Assert-NoReparsePoint([string]$Path, [string]$Root) {
    $rootPath = Canonical $Root; $cursor = Get-Item -LiteralPath $Path -Force
    $itemPath = Canonical $cursor.FullName
    if ($itemPath -ne $rootPath -and -not $itemPath.StartsWith($rootPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { Fail 'Ruta fuera de la raiz permitida.' }
    while ($null -ne $cursor) {
        if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { Fail 'Se rechazo un enlace simbolico/reparse point multimedia.' }
        if ((Canonical $cursor.FullName) -eq $rootPath) { return }
        if ($cursor -is [IO.FileInfo]) { $cursor = $cursor.Directory }
        elseif ($cursor -is [IO.DirectoryInfo]) { $cursor = [IO.Directory]::GetParent($cursor.FullName) }
        else { Fail 'Elemento de sistema de archivos inesperado.' }
    }
    Fail 'No se alcanzo la raiz multimedia permitida.'
}
function Resolve-SafeFile([string]$Root, [string]$Relative) {
    if ([string]::IsNullOrWhiteSpace($Relative) -or [IO.Path]::IsPathRooted($Relative) -or $Relative -match '(^|[\\/])\.\.([\\/]|$)') { Fail 'Ruta multimedia insegura.' }
    $rootPath = Canonical $Root
    $candidate = Canonical (Join-Path $rootPath $Relative)
    if (-not $candidate.StartsWith($rootPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { Fail 'Ruta multimedia externa.' }
    if (-not [IO.File]::Exists($candidate)) { Fail 'Archivo multimedia referenciado faltante.' }
    Assert-NoReparsePoint $candidate $rootPath
    $candidate
}
function Invoke-Select([Data.SqlClient.SqlConnection]$Connection, [Data.SqlClient.SqlTransaction]$Transaction, [string]$Sql, [hashtable]$Parameters = @{}) {
    if ($Sql -notmatch '^\s*(SELECT|WITH)\b') { Fail 'Solo se admiten consultas SELECT/CTE.' }
    $command = $Connection.CreateCommand(); $command.Transaction = $Transaction; $command.CommandText = $Sql; $command.CommandTimeout = 120
    foreach ($key in $Parameters.Keys) { $parameter = $command.Parameters.Add("@$key", [Data.SqlDbType]::NVarChar, 128); $parameter.Value = $Parameters[$key] }
    $table = New-Object Data.DataTable
    $adapter = New-Object Data.SqlClient.SqlDataAdapter $command
    try { [void]$adapter.Fill($table); Write-Output -NoEnumerate $table } finally { $adapter.Dispose(); $command.Dispose() }
}
function Write-Json([string]$Path, $Value) { [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 20 -Compress), (New-Object Text.UTF8Encoding($false))) }
function Get-Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Assert-Inventory($Inventory) {
    if ($Inventory.reportType -ne 'JemNexusLocalSanitizedInventory' -or $Inventory.reportVersion -ne 1) { Fail 'Inventario local incompatible.' }
    if ($Inventory.source.instance -cne $ExpectedInstance -or $Inventory.source.database -cne $ExpectedDatabase -or $Inventory.source.schema -cne $ExpectedSchema) { Fail 'Identidad del inventario inesperada.' }
    if ([int]$Inventory.migrationCount -ne 22 -or [long]$Inventory.exclusions.refreshTokenRowsIncluded -ne 0) { Fail 'Inventario no autoriza esta preparacion.' }
    foreach ($name in $ExpectedCounts.Keys) { if ([long]$Inventory.counts.$name -ne [long]$ExpectedCounts[$name]) { Fail "Conteo de inventario inesperado: $name" } }
    if ([long]$Inventory.counts.AppRefreshTokens -ne 122 -or [long]$Inventory.media.images.orphanCount -ne 2) { Fail 'Exclusiones esperadas no coinciden.' }
    if (@($Inventory.media.manifest).Count -ne 177) { Fail 'Manifiesto multimedia del inventario incompleto.' }
}

Assert-LocalIdentityParameters
$output = Assert-OutsideRepository $OutputRoot
if ($Mode -eq 'PlanOnly') {
    Write-Output 'PLAN_ONLY: no conecta, no lee multimedia y no crea staging ni paquete. ExportLocal es solo lectura de JemNexus_Local y no autoriza aplicar en produccion.'
    Write-Output 'Se prepararian 17 tablas; AppRefreshTokens y __EFMigrationsHistory quedan excluidas.'
    exit 0
}

if ([string]::IsNullOrWhiteSpace($InventoryPath) -or -not [IO.File]::Exists($InventoryPath)) { Fail 'ExportLocal requiere InventoryPath existente.' }
if ([string]::IsNullOrWhiteSpace($ImageUploadsRoot) -or [string]::IsNullOrWhiteSpace($TechnicalSheetsRoot)) { Fail 'ExportLocal requiere las dos raices multimedia por separado.' }
$inventoryFile = Canonical $InventoryPath
$inventory = Get-Content -LiteralPath $inventoryFile -Raw | ConvertFrom-Json
Assert-Inventory $inventory
$imageRoot = Canonical $ImageUploadsRoot; $sheetRoot = Canonical $TechnicalSheetsRoot
if (-not [IO.Directory]::Exists($imageRoot) -or -not [IO.Directory]::Exists($sheetRoot)) { Fail 'Las dos raices multimedia deben existir.' }
Assert-NoReparsePoint $imageRoot $imageRoot; Assert-NoReparsePoint $sheetRoot $sheetRoot
if (-not [IO.Directory]::Exists($output)) { [void][IO.Directory]::CreateDirectory($output) }
Assert-NoReparsePoint $output $output
$packageName = 'jemnexus-local-data-package-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$finalPath = Join-Path $output $packageName
$staging = Join-Path $output ('.staging-' + [Guid]::NewGuid().ToString('N'))
if ([IO.Directory]::Exists($finalPath)) { Fail 'El destino final ya existe.' }

$connection = $null; $transaction = $null
try {
    [void][IO.Directory]::CreateDirectory($staging)
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $rule = New-Object Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.AddAccessRule($rule); Set-Acl -LiteralPath $staging -AclObject $acl
    $dataPath = Join-Path $staging 'data'; $mediaPath = Join-Path $staging 'media'
    [void][IO.Directory]::CreateDirectory($dataPath); [void][IO.Directory]::CreateDirectory($mediaPath)

    $connectionString = "Data Source=$ExpectedInstance;Initial Catalog=$ExpectedDatabase;Integrated Security=True;Application Name=JemNexusLocalPackageExport;ApplicationIntent=ReadOnly"
    $connection = New-Object Data.SqlClient.SqlConnection $connectionString; $connection.Open()
    # JemNexus_Local has ALLOW_SNAPSHOT_ISOLATION=OFF.  A single SERIALIZABLE
    # transaction makes metadata, rows, counts and SQL relationship checks one
    # coherent capture without changing database options.
    $transaction = $connection.BeginTransaction([Data.IsolationLevel]::Serializable)
    $identityTable = Invoke-Select $connection $transaction "SELECT DB_NAME() DatabaseName, SCHEMA_NAME() DefaultSchema, SERVERPROPERTY('IsLocalDB') IsLocalDB"
    $identityRow = $identityTable.Rows[0]
    if ($identityTable.Rows.Count -ne 1 -or [string]$identityRow.DatabaseName -cne $ExpectedDatabase -or [string]$identityRow.DefaultSchema -cne $ExpectedSchema -or $identityRow.IsLocalDB -isnot [int] -or [int]$identityRow.IsLocalDB -ne 1) { Fail 'La identidad efectiva no es la LocalDB permitida.' }

    $metadata = Invoke-Select $connection $transaction @"
SELECT t.name TableName, c.name ColumnName, c.column_id ColumnId,
       CASE WHEN pk.column_id IS NULL THEN 0 ELSE 1 END IsPrimaryKey,
       ISNULL(pk.key_ordinal,0) PrimaryKeyOrdinal
FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
JOIN sys.columns c ON c.object_id=t.object_id
LEFT JOIN (SELECT ic.object_id,ic.column_id,ic.key_ordinal FROM sys.indexes i JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id WHERE i.is_primary_key=1) pk ON pk.object_id=c.object_id AND pk.column_id=c.column_id
WHERE s.name=@schema ORDER BY t.name,c.column_id
"@ @{schema=$ExpectedSchema}
    $tableMetadata = @{}
    foreach ($row in $metadata.Rows) { $name=[string]$row.TableName; if (-not $tableMetadata.ContainsKey($name)) { $tableMetadata[$name]=@() }; $tableMetadata[$name] += $row }
    $counts=[ordered]@{}; $dataHashes=[ordered]@{}; $exportedRows=@{}
    foreach ($name in $Tables) {
        if (-not $tableMetadata.ContainsKey($name)) { Fail "Falta tabla requerida: $name" }
        $columns=@($tableMetadata[$name] | Sort-Object {[int]$_.ColumnId} | ForEach-Object {'[' + ([string]$_.ColumnName).Replace(']',']]') + ']'})
        $keys=@($tableMetadata[$name] | Where-Object {[int]$_.IsPrimaryKey -eq 1} | Sort-Object {[int]$_.PrimaryKeyOrdinal} | ForEach-Object {'[' + ([string]$_.ColumnName).Replace(']',']]') + ']'})
        if ($keys.Count -eq 0) { Fail "Tabla sin PK: $name" }
        $rows=Invoke-Select $connection $transaction ("SELECT {0} FROM [dbo].[{1}] ORDER BY {2}" -f ($columns -join ','),$name,($keys -join ','))
        if ($rows.Rows.Count -ne [long]$ExpectedCounts[$name] -or $rows.Rows.Count -ne [long]$inventory.counts.$name) { Fail "Drift de conteo: $name" }
        $records=Convert-TableRows $rows; $exportedRows[$name]=$records
        $counts[$name]=[long]$rows.Rows.Count
    }
    # FK validation is evaluated inside the same SERIALIZABLE capture as the rows.
    $fk = Invoke-Select $connection $transaction "SELECT COUNT_BIG(*) InvalidCount FROM sys.foreign_keys fk WHERE fk.parent_object_id IN (SELECT object_id FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE s.name=@schema) AND (fk.is_disabled=1 OR fk.is_not_trusted=1)" @{schema=$ExpectedSchema}
    if ([long]$fk.Rows[0].InvalidCount -ne 0) { Fail 'Hay foreign keys deshabilitadas o no confiables.' }

    # Release SERIALIZABLE locks before any filesystem read, copy or hashing.
    # All database-derived media references needed below are already in memory.
    $transaction.Commit(); $transaction.Dispose(); $transaction=$null
    $connection.Close(); $connection.Dispose(); $connection=$null

    foreach ($name in $Tables) {
        $file=Join-Path $dataPath ($name + '.json'); Write-TableJson $file $exportedRows[$name]
        $dataHashes[$name]=Get-Hash $file
    }

    $inventoryMedia=@{}
    foreach ($item in $inventory.media.manifest) {
        $key=('{0}|{1}|{2}' -f [string]$item.kind,[long]$item.id,([string]$item.relativePath).Replace('\','/'))
        if ($inventoryMedia.ContainsKey($key)) { Fail 'Entrada multimedia duplicada en el inventario.' }
        $inventoryMedia[$key]=$item
    }
    $media=New-Object Collections.Generic.List[object]; $seen=@{}
    foreach ($row in $exportedRows.ProductImages) {
        $public=[string]$row.Image; $prefix='/media/product-images/'
        if (-not $public.StartsWith($prefix,[StringComparison]::Ordinal)) { Fail 'Ruta publica de imagen inesperada.' }
        $relative=$public.Substring('/media/'.Length); $parts=$relative.Split('/')
        if ($parts.Count -ne 3 -or $parts[0] -cne 'product-images' -or $parts[1] -cne [string]$row.ProductId -or [IO.Path]::GetFileName($parts[2]) -cne $parts[2]) { Fail 'Ruta de imagen no coincide con su ProductId.' }
        $source=Resolve-SafeFile $imageRoot $relative; $seen[(Canonical $source)]=$true
        $inventoryKey=('product-image|{0}|{1}' -f [long]$row.Id,$relative.Replace('\','/'))
        if (-not $inventoryMedia.ContainsKey($inventoryKey) -or (Get-Hash $source) -cne [string]$inventoryMedia[$inventoryKey].sha256 -or [long](Get-Item $source).Length -ne [long]$inventoryMedia[$inventoryKey].sizeBytes) { Fail 'Imagen cambiada respecto del inventario.' }
        $destination=Join-Path $mediaPath (Join-Path 'images' $relative); [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination)); [IO.File]::Copy($source,$destination,$false)
        $media.Add([pscustomobject][ordered]@{kind='product-image';recordId=[long]$row.Id;parentId=[long]$row.ProductId;packagePath=('media/images/'+$relative.Replace('\','/'));sizeBytes=[long](Get-Item $destination).Length;sha256=(Get-Hash $destination)})
    }
    foreach ($row in $exportedRows.TechnicalSheets) {
        $relative=[string]$row.StorageKey
        if ([IO.Path]::GetFileName($relative) -cne $relative) { Fail 'StorageKey de ficha insegura.' }
        $source=Resolve-SafeFile $sheetRoot $relative
        $inventoryKey=('technical-sheet|{0}|{1}' -f [long]$row.Id,$relative.Replace('\','/'))
        if (-not $inventoryMedia.ContainsKey($inventoryKey) -or (Get-Hash $source) -cne [string]$inventoryMedia[$inventoryKey].sha256 -or [long](Get-Item $source).Length -ne [long]$inventoryMedia[$inventoryKey].sizeBytes) { Fail 'Ficha cambiada respecto del inventario.' }
        $destination=Join-Path $mediaPath (Join-Path 'technical-sheets' $relative)
        [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination)); [IO.File]::Copy($source,$destination,$false)
        if ([long](Get-Item $destination).Length -ne [long]$row.SizeBytes) { Fail 'Tamano de ficha no coincide.' }
        $media.Add([pscustomobject][ordered]@{kind='technical-sheet';recordId=[long]$row.Id;parentId=$null;packagePath=('media/technical-sheets/'+$relative.Replace('\','/'));sizeBytes=[long](Get-Item $destination).Length;sha256=(Get-Hash $destination)})
    }
    # Enumerar los archivos de imagen permite probar que los no referenciados se excluyen.
    $physicalImages=@(Get-ChildItem -LiteralPath (Join-Path $imageRoot 'product-images') -File -Recurse)
    foreach ($file in $physicalImages) { Assert-NoReparsePoint $file.FullName $imageRoot }
    $orphanCount=@($physicalImages | Where-Object {-not $seen.ContainsKey((Canonical $_.FullName))}).Count
    if ($orphanCount -ne 2 -or $media.Count -ne 177) { Fail 'Conteo de multimedia/exclusion de huerfanos inesperado.' }

    # Windows PowerShell 5.1 cannot reliably bind @($media) when $media is a
    # Collections.Generic.List[object] (it can throw "Argument types do not
    # match" while the surrounding ordered dictionary is being constructed).
    # Materialize the entries through the collection's native API instead of
    # asking the array-subexpression operator to enumerate the generic list.
    $mediaFiles=[object[]]$media.ToArray()
    $manifest=[ordered]@{
        packageVersion=$PackageVersion; packageType='JemNexusLocalDataPackage'; createdUtc=[DateTime]::UtcNow.ToString('o')
        status='PREPARED_LOCAL_NOT_AUTHORIZED_FOR_PRODUCTION_APPLY'
        source=[ordered]@{instance=$ExpectedInstance;database=$ExpectedDatabase;schema=$ExpectedSchema;inventorySha256=(Get-Hash $inventoryFile)}
        exclusions=[ordered]@{tables=@('AppRefreshTokens','__EFMigrationsHistory');refreshTokenRowsIncluded=0;orphanImageFilesIncluded=0;observedOrphanImageFiles=$orphanCount}
        tables=[ordered]@{count=17;rowCounts=$counts;sha256=$dataHashes}
        media=[ordered]@{count=$mediaFiles.Count;files=$mediaFiles}
        limitations=@('No contiene importador, SQL destructivo ni autorizacion de apply.','Debe verificarse nuevamente contra la fuente y produccion antes de disenar cualquier aplicacion.')
    }
    $manifestPath=Join-Path $staging 'manifest.json'; Write-Json $manifestPath $manifest
    # Validacion final desde disco antes de la unica publicacion (rename atomico en el mismo volumen).
    $roundTrip=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $roundTripMediaFiles=@($roundTrip.media.files)
    if ($roundTrip.status -ne 'PREPARED_LOCAL_NOT_AUTHORIZED_FOR_PRODUCTION_APPLY' -or [int]$roundTrip.tables.count -ne 17 -or [int]$roundTrip.media.count -ne 177 -or $roundTripMediaFiles.Count -ne 177) { Fail 'Validacion final del manifiesto fallo.' }
    foreach ($name in $Tables) {
        $tablePath=Join-Path $dataPath ($name+'.json')
        Read-AndAssertTableJson $tablePath ([long]$counts[$name])
        if ((Get-Hash $tablePath) -cne [string]$roundTrip.tables.sha256.$name) { Fail "Hash de datos invalido: $name" }
    }
    foreach ($item in $roundTripMediaFiles) { $path=Join-Path $staging ([string]$item.packagePath).Replace('/',[IO.Path]::DirectorySeparatorChar); if ((Get-Hash $path) -cne [string]$item.sha256) { Fail 'Hash multimedia invalido.' } }
    [IO.Directory]::Move($staging,$finalPath)
    Write-Output "PACKAGE_PREPARED_LOCAL_ONLY: $finalPath"
} catch {
    if ($null -ne $transaction) { try { $transaction.Rollback() } catch {}; $transaction.Dispose() }
    if ([IO.Directory]::Exists($staging)) { [IO.Directory]::Delete($staging,$true) }
    throw
} finally {
    if ($null -ne $connection) { if ($connection.State -ne [Data.ConnectionState]::Closed) { $connection.Close() }; $connection.Dispose() }
}
