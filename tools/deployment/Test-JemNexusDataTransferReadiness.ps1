#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('PlanOnly', 'InventoryLocal', 'CompareSnapshot')]
    [string]$Mode,
    [string]$LocalInstance = '(localdb)\MSSQLLocalDB',
    [string]$LocalDatabase = 'JemNexus_Local',
    [string]$LocalSchema = 'dbo',
    [string]$ImageUploadsRoot,
    [string]$ContentRoot,
    [string]$PublicBasePath = '/media',
    [string]$OutputRoot,
    [string]$LocalReportPath,
    [string]$ProductionSnapshotPath,
    [string]$EvidenceDateUtc,
    [string]$EvidenceSource,
    [switch]$AllowNewOutputFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedInstance = '(localdb)\MSSQLLocalDB'
$ExpectedDatabase = 'JemNexus_Local'
$ExpectedSchema = 'dbo'
$ExpectedMigrations = 22
$ReportVersion = 1
$ApplicationTables = @(
    'AppUsers','AppRefreshTokens','AppUserPermissions','Categories','Brands','Suppliers',
    'Products','ProductImages','ProductSpecs','Promotions','HomeSectionItems','QuoteRequests',
    'TechnicalSheets','CustomerProfiles','CommercialQuotes','CommercialQuoteItems',
    'CommercialQuoteFolioCounters','CommercialQuoteIssueIdempotencyRecords'
)
$RequiredColumns = [ordered]@{
    AppUsers = @('Id','Username','Role','SellerCode'); AppRefreshTokens = @('Id','UserId','TokenHash')
    AppUserPermissions = @('UserId','Permission'); Categories = @('Id','ParentId'); Brands = @('Id','Logo')
    Suppliers = @('Id'); Products = @('Id','CategoryId','BrandId','SupplierId','TechnicalSheetId')
    ProductImages = @('Id','ProductId','Image'); ProductSpecs = @('Id','ProductId')
    Promotions = @('Id','ProductId','Image'); HomeSectionItems = @('Id','ProductId')
    QuoteRequests = @('Id','ProductId'); TechnicalSheets = @('Id','StorageKey','SizeBytes','ContentType')
    CustomerProfiles = @('Id','NormalizedRut'); CommercialQuotes = @('Id','CustomerProfileId','ResponsibleSellerId','IssuedById','Folio','FolioYear','FolioSequenceNumber')
    CommercialQuoteItems = @('Id','CommercialQuoteId','ProductId','Position')
    CommercialQuoteFolioCounters = @('Year','LastNumber')
    CommercialQuoteIssueIdempotencyRecords = @('ResponsibleSellerId','IdempotencyKey','CommercialQuoteId','RequestFingerprint')
}

function Fail([string]$Message) { throw $Message }
function Get-Sha256Text([string]$Value) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value))).Replace('-', '').ToLowerInvariant()) }
    finally { $sha.Dispose() }
}
function Get-CanonicalPath([string]$Path) { return [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) }
function Assert-OutsideRepository([string]$Path) {
    $candidate = Get-CanonicalPath $Path
    $repo = Get-CanonicalPath (Join-Path $PSScriptRoot '..\..')
    $boundary = $repo + [IO.Path]::DirectorySeparatorChar
    if ($candidate -eq $repo -or $candidate.StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase)) { Fail "OutputRoot debe estar fuera del repositorio: $candidate" }
    return $candidate
}
function Assert-ExistingInput([string]$Path, [string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Path) -or -not [IO.File]::Exists($Path)) { Fail "$Name no existe o no es archivo: '$Path'" }
    return (Get-CanonicalPath $Path)
}
function Assert-NoReparsePoint([string]$Path, [string]$AllowedRoot) {
    $root = Get-CanonicalPath $AllowedRoot; $itemPath = Get-CanonicalPath $Path
    $boundary = $root + [IO.Path]::DirectorySeparatorChar
    if (-not $itemPath.StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase)) { Fail "Ruta fuera de la raiz permitida: $itemPath" }
    $cursor = Get-Item -LiteralPath $itemPath -Force
    while ($null -ne $cursor -and (Get-CanonicalPath $cursor.FullName).StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
        if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { Fail "Enlace simbolico/reparse point rechazado: $($cursor.FullName)" }
        if ((Get-CanonicalPath $cursor.FullName) -eq $root) { break }
        # Get-Item returns FileInfo for media files (FileInfo has Directory, not Parent)
        # and DirectoryInfo while walking their ancestors. Keep that distinction explicit
        # so this works under StrictMode in Windows PowerShell 5.1.
        if ($cursor -is [IO.FileInfo]) { $cursor = $cursor.Directory }
        elseif ($cursor -is [IO.DirectoryInfo]) { $cursor = [IO.Directory]::GetParent($cursor.FullName) }
        else { Fail "Tipo de elemento de sistema de archivos inesperado: $($cursor.GetType().FullName)" }
    }
}
function Resolve-SafeFile([string]$Root, [string]$Relative) {
    if ([string]::IsNullOrWhiteSpace($Relative) -or [IO.Path]::IsPathRooted($Relative) -or $Relative -match '(^|[\\/])\.\.([\\/]|$)') { Fail "Ruta multimedia insegura: '$Relative'" }
    $rootPath = Get-CanonicalPath $Root
    $candidate = Get-CanonicalPath (Join-Path $rootPath $Relative)
    $boundary = $rootPath + [IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase)) { Fail "Ruta multimedia fuera de uploads: '$Relative'" }
    if (-not [IO.File]::Exists($candidate)) { Fail "Archivo multimedia faltante: '$Relative'" }
    Assert-NoReparsePoint $candidate $rootPath
    return $candidate
}
function Invoke-SelectTable([Data.SqlClient.SqlConnection]$Connection, [string]$Sql, [hashtable]$Parameters = @{}) {
    if ($Sql -notmatch '^\s*SELECT\b' -and $Sql -notmatch '^\s*WITH\b') { Fail 'La herramienta solo permite consultas SELECT/CTE.' }
    $command = $Connection.CreateCommand(); $command.CommandText = $Sql; $command.CommandTimeout = 60
    $placeholders = @([regex]::Matches($Sql, '(?<!@)@[A-Za-z_][A-Za-z0-9_]*') | ForEach-Object { $_.Value.Substring(1) } | Sort-Object -Unique)
    foreach ($placeholder in $placeholders) { if (-not $Parameters.ContainsKey($placeholder)) { Fail "Falta el parametro SQL @$placeholder." } }
    foreach ($key in $Parameters.Keys) {
        if ($placeholders -notcontains $key) { Fail "El parametro SQL @$key no aparece en la consulta." }
        $specification = $Parameters[$key]
        if ($specification -isnot [hashtable] -or -not $specification.ContainsKey('Value') -or -not $specification.ContainsKey('SqlDbType')) { Fail "El parametro SQL @$key requiere Value y SqlDbType explicitos." }
        $parameter = $command.Parameters.Add("@$key", [Data.SqlDbType]$specification.SqlDbType)
        if ($specification.ContainsKey('Size')) { $parameter.Size = [int]$specification.Size }
        $parameter.Value = if ($null -eq $specification.Value) { [DBNull]::Value } else { $specification.Value }
    }
    $table = New-Object Data.DataTable
    $adapter = New-Object Data.SqlClient.SqlDataAdapter $command
    try {
        [void]$adapter.Fill($table)
        # DataTable implements IEnumerable.  Prevent PowerShell from unrolling it into
        # zero, one or many DataRow objects; every caller relies on the DataTable contract.
        Write-Output -NoEnumerate $table
    } finally { $adapter.Dispose(); $command.Dispose() }
}
function Get-Scalar([Data.SqlClient.SqlConnection]$Connection, [string]$Sql, [hashtable]$Parameters = @{}) {
    $table = Invoke-SelectTable $Connection $Sql $Parameters
    if ($table.Rows.Count -ne 1 -or $table.Columns.Count -ne 1) { Fail 'La consulta escalar no devolvio exactamente una celda.' }
    return $table.Rows[0][0]
}
function Get-FileRecord([string]$Kind, [long]$Id, [long]$ParentId, [string]$Relative, [string]$Physical) {
    $item = Get-Item -LiteralPath $Physical
    return [ordered]@{ kind=$Kind; id=$Id; parentId=$ParentId; relativePath=$Relative.Replace('\','/'); sizeBytes=[long]$item.Length; sha256=(Get-FileHash -LiteralPath $Physical -Algorithm SHA256).Hash.ToLowerInvariant() }
}
function Test-ExpectedShape($Report) {
    $failures = New-Object Collections.Generic.List[string]
    if ($Report.reportVersion -ne $ReportVersion) { $failures.Add('reportVersion inesperada') }
    if ($Report.source.instance -ne $ExpectedInstance -or $Report.source.database -ne $ExpectedDatabase -or $Report.source.schema -ne $ExpectedSchema) { $failures.Add('identidad local inesperada') }
    if ([int]$Report.migrationCount -ne $ExpectedMigrations) { $failures.Add('migraciones locales distintas de 22') }
    $expected = [ordered]@{AppUsers=3;AppRefreshTokens=122;AppUserPermissions=58;Brands=3;Categories=10;Suppliers=0;Products=92;ProductImages=92;ProductSpecs=58;Promotions=0;HomeSectionItems=0;QuoteRequests=0;TechnicalSheets=85;CustomerProfiles=1;CommercialQuotes=9;CommercialQuoteItems=9;CommercialQuoteFolioCounters=1;CommercialQuoteIssueIdempotencyRecords=8}
    foreach ($name in $expected.Keys) { if ([long]$Report.counts.$name -ne $expected[$name]) { $failures.Add("conteo local inesperado: $name") } }
    if ([long]$Report.exclusions.refreshTokens -ne 122) { $failures.Add('deben excluirse exactamente 122 sesiones') }
    if ([long]$Report.media.images.referenced -ne 92 -or [long]$Report.media.images.present -ne 92) { $failures.Add('imagenes referenciadas/fisicas incompletas') }
    if ([long]$Report.media.images.orphanCount -ne 2 -or [long]$Report.media.images.transferCount -ne 92) { $failures.Add('deben excluirse exactamente dos imagenes huerfanas') }
    if ([long]$Report.media.technicalSheets.referenced -ne 85 -or [long]$Report.media.technicalSheets.present -ne 85) { $failures.Add('fichas referenciadas/fisicas incompletas') }
    if ($Report.schema.missingTables.Count -gt 0 -or $Report.schema.missingColumns.Count -gt 0) { $failures.Add('faltan tablas o columnas') }
    if ([long]$Report.integrity.orphanForeignKeys -ne 0 -or [long]$Report.integrity.duplicateUniqueKeys -ne 0 -or -not $Report.integrity.requiredIndexesPresent) { $failures.Add('IDs/FKs/indices relevantes no son validos') }
    # A generic List is also enumerable.  Without -NoEnumerate the caller receives
    # $null, a System.String, or Object[] for zero, one or many failures respectively,
    # making the single-failure $shapeFailures.Count access fail under StrictMode.
    Write-Output -NoEnumerate $failures
}

if ($Mode -eq 'PlanOnly') {
    if ($LocalInstance -cne $ExpectedInstance -or $LocalDatabase -cne $ExpectedDatabase -or $LocalSchema -cne $ExpectedSchema) { Fail 'Instancia, base o esquema local inesperado.' }
    if ([string]::IsNullOrWhiteSpace($OutputRoot)) { Fail 'PlanOnly requiere OutputRoot explicito para validarlo, aunque no lo crea.' }
    [void](Assert-OutsideRepository $OutputRoot)
    Write-Output 'PLAN_ONLY: sin conexiones ni escritura. InventoryLocal leeria identidad, metadata, conteos, IDs/FKs e inventariaria hashes bajo dos raices. CompareSnapshot leeria dos JSON sanitizados y produciria READY_FOR_DESIGN o NO-GO.'
    Write-Output "Destino solicitado (no creado): $OutputRoot"
    exit 0
}

if ($Mode -eq 'InventoryLocal') {
    if ($LocalInstance -cne $ExpectedInstance -or $LocalDatabase -cne $ExpectedDatabase -or $LocalSchema -cne $ExpectedSchema) { Fail 'Instancia, base o esquema local inesperado; se rechazo antes de conectar.' }
    if ([string]::IsNullOrWhiteSpace($ImageUploadsRoot) -or [string]::IsNullOrWhiteSpace($ContentRoot) -or [string]::IsNullOrWhiteSpace($OutputRoot)) { Fail 'InventoryLocal requiere ImageUploadsRoot, ContentRoot y OutputRoot explicitos.' }
    $output = Assert-OutsideRepository $OutputRoot
    $imageRoot = Get-CanonicalPath $ImageUploadsRoot
    $sheetRoot = Get-CanonicalPath (Join-Path $ContentRoot 'uploads\technical-sheets')
    if (-not [IO.Directory]::Exists($imageRoot) -or -not [IO.Directory]::Exists($sheetRoot)) { Fail 'Las dos raices multimedia deben existir.' }
    Assert-NoReparsePoint (Join-Path $imageRoot 'product-images') $imageRoot
    Assert-NoReparsePoint $sheetRoot (Get-CanonicalPath (Join-Path $ContentRoot 'uploads'))
    $connectionString = "Data Source=$LocalInstance;Initial Catalog=$LocalDatabase;Integrated Security=True;Application Name=JemNexusReadOnlyPreflight;ApplicationIntent=ReadOnly"
    $connection = New-Object Data.SqlClient.SqlConnection $connectionString
    try {
        $connection.Open()
        $identity = Invoke-SelectTable $connection "SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(256)) AS ServerName, DB_NAME() AS DatabaseName, SCHEMA_NAME() AS DefaultSchema, SERVERPROPERTY('IsLocalDB') AS IsLocalDB"
        if ($identity.Rows.Count -ne 1) { Fail 'La consulta de identidad local no devolvio exactamente una fila.' }
        $identityRow = $identity.Rows[0]
        if ([string]$identityRow.DatabaseName -cne $ExpectedDatabase -or [string]$identityRow.DefaultSchema -cne $ExpectedSchema) { Fail 'La identidad efectiva de base/esquema no coincide.' }
        $isLocalDb = $identityRow.IsLocalDB
        if ($isLocalDb -is [DBNull] -or $isLocalDb -isnot [int] -or $isLocalDb -ne 1) { Fail "SERVERPROPERTY('IsLocalDB') no confirmo inequívocamente una instancia LocalDB." }
        Write-Verbose 'Servidor efectivo confirmado como LocalDB (nombre efectivo omitido del diagnostico).'
        $migrationCount = [int](Get-Scalar $connection "SELECT COUNT_BIG(*) FROM [$ExpectedSchema].[__EFMigrationsHistory]")
        $schemaParameter = @{ schema = @{ Value = $ExpectedSchema; SqlDbType = [Data.SqlDbType]::NVarChar; Size = 128 } }
        $metadata = Invoke-SelectTable $connection "SELECT t.name AS TableName, c.name AS ColumnName FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.columns c ON c.object_id=t.object_id WHERE s.name=@schema" $schemaParameter
        $available = @{}; foreach ($row in $metadata.Rows) { if (-not $available.ContainsKey([string]$row.TableName)) { $available[[string]$row.TableName] = @{} }; $available[[string]$row.TableName][[string]$row.ColumnName]=$true }
        $missingTables = @(); $missingColumns = @()
        foreach ($tableName in $RequiredColumns.Keys) { if (-not $available.ContainsKey($tableName)) { $missingTables += $tableName } else { foreach ($column in $RequiredColumns[$tableName]) { if (-not $available[$tableName].ContainsKey($column)) { $missingColumns += "$tableName.$column" } } } }
        if ($missingTables.Count -gt 0 -or $missingColumns.Count -gt 0) { Fail "Esquema incompleto: tablas=[$($missingTables -join ',')] columnas=[$($missingColumns -join ',')]" }
        $counts = [ordered]@{}; foreach ($tableName in $ApplicationTables) { $counts[$tableName] = [long](Get-Scalar $connection "SELECT COUNT_BIG(*) FROM [$ExpectedSchema].[$tableName]") }
        $images = Invoke-SelectTable $connection "SELECT [Id],[ProductId],[Image] FROM [$ExpectedSchema].[ProductImages] ORDER BY [Id]"
        $sheets = Invoke-SelectTable $connection "SELECT [Id],[StorageKey],[SizeBytes] FROM [$ExpectedSchema].[TechnicalSheets] ORDER BY [Id]"
        $users = Invoke-SelectTable $connection "SELECT [Username] FROM [$ExpectedSchema].[AppUsers] ORDER BY [Id]"
        $integritySql = @"
SELECT
 CAST((SELECT COUNT_BIG(*) FROM [dbo].[Products] p LEFT JOIN [dbo].[Categories] c ON c.Id=p.CategoryId WHERE c.Id IS NULL) +
      (SELECT COUNT_BIG(*) FROM [dbo].[ProductImages] i LEFT JOIN [dbo].[Products] p ON p.Id=i.ProductId WHERE p.Id IS NULL) +
      (SELECT COUNT_BIG(*) FROM [dbo].[CommercialQuotes] q LEFT JOIN [dbo].[AppUsers] u ON u.Id=q.ResponsibleSellerId WHERE u.Id IS NULL) +
      (SELECT COUNT_BIG(*) FROM [dbo].[CommercialQuoteItems] i LEFT JOIN [dbo].[CommercialQuotes] q ON q.Id=i.CommercialQuoteId WHERE q.Id IS NULL) AS bigint) AS OrphanForeignKeys,
 CAST((SELECT COUNT_BIG(*) FROM (SELECT Username FROM [dbo].[AppUsers] GROUP BY Username HAVING COUNT_BIG(*)>1) d) +
      (SELECT COUNT_BIG(*) FROM (SELECT Slug FROM [dbo].[Products] GROUP BY Slug HAVING COUNT_BIG(*)>1) d) +
      (SELECT COUNT_BIG(*) FROM (SELECT CommercialQuoteId,Position FROM [dbo].[CommercialQuoteItems] GROUP BY CommercialQuoteId,Position HAVING COUNT_BIG(*)>1) d) AS bigint) AS DuplicateUniqueKeys,
 CAST(CASE WHEN (SELECT COUNT_BIG(*) FROM sys.indexes i JOIN sys.tables t ON t.object_id=i.object_id JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE s.name=@schema AND ((t.name='AppUsers' AND i.is_unique=1) OR (t.name='CommercialQuoteItems' AND i.is_unique=1) OR (t.name='CommercialQuoteIssueIdempotencyRecords' AND i.is_unique=1))) >= 6 THEN 1 ELSE 0 END AS bit) AS RequiredIndexesPresent
"@
        $integrityRows = Invoke-SelectTable $connection $integritySql $schemaParameter
        $manifest = @(); $referencedImagePaths = @{}
        $prefix = $PublicBasePath.TrimEnd('/').Replace('\','/') + '/product-images/'
        foreach ($row in $images.Rows) {
            $public = [string]$row.Image; if (-not $public.StartsWith($prefix,[StringComparison]::Ordinal)) { Fail "Ruta publica de imagen inesperada para ID $($row.Id)" }
            $relative = $public.Substring($PublicBasePath.TrimEnd('/').Length).TrimStart('/'); $parts = $relative.Split('/')
            if ($parts.Count -ne 3 -or $parts[0] -cne 'product-images' -or $parts[1] -cne ([string]$row.ProductId) -or [IO.Path]::GetFileName($parts[2]) -cne $parts[2]) { Fail "Ruta de imagen invalida para ID $($row.Id)" }
            $physical = Resolve-SafeFile $imageRoot $relative; $referencedImagePaths[(Get-CanonicalPath $physical)]=$true
            $manifest += Get-FileRecord 'product-image' ([long]$row.Id) ([long]$row.ProductId) $relative $physical
        }
        foreach ($row in $sheets.Rows) {
            $key=[string]$row.StorageKey; if ([IO.Path]::GetFileName($key) -cne $key) { Fail "StorageKey invalida para ficha ID $($row.Id)" }
            $physical=Resolve-SafeFile $sheetRoot $key; if ([long](Get-Item -LiteralPath $physical).Length -ne [long]$row.SizeBytes) { Fail "Tamano de ficha no coincide para ID $($row.Id)" }
            $manifest += Get-FileRecord 'technical-sheet' ([long]$row.Id) 0 $key $physical
        }
        $physicalImages = @(Get-ChildItem -LiteralPath (Join-Path $imageRoot 'product-images') -File -Recurse)
        foreach ($file in $physicalImages) { Assert-NoReparsePoint $file.FullName $imageRoot }
        $orphans = @($physicalImages | Where-Object { -not $referencedImagePaths.ContainsKey((Get-CanonicalPath $_.FullName)) })
        $userHashes=@(); foreach($row in $users.Rows){$userHashes += Get-Sha256Text(([string]$row.Username).ToLowerInvariant())}
        $report=[ordered]@{reportVersion=$ReportVersion;reportType='JemNexusLocalSanitizedInventory';createdUtc=[DateTime]::UtcNow.ToString('o');source=[ordered]@{instance=$ExpectedInstance;database=$ExpectedDatabase;schema=$ExpectedSchema};migrationCount=$migrationCount;counts=$counts;userIdentityHashes=@($userHashes|Sort-Object);exclusions=[ordered]@{refreshTokens=[long]$counts.AppRefreshTokens;refreshTokenRowsIncluded=0;orphanImages=$orphans.Count};schema=[ordered]@{missingTables=@($missingTables);missingColumns=@($missingColumns)};integrity=[ordered]@{orphanForeignKeys=[long]$integrityRows.Rows[0].OrphanForeignKeys;duplicateUniqueKeys=[long]$integrityRows.Rows[0].DuplicateUniqueKeys;requiredIndexesPresent=[bool]$integrityRows.Rows[0].RequiredIndexesPresent};media=[ordered]@{images=[ordered]@{referenced=$images.Rows.Count;present=@($manifest|Where-Object kind -eq 'product-image').Count;orphanCount=$orphans.Count;transferCount=$images.Rows.Count};technicalSheets=[ordered]@{referenced=$sheets.Rows.Count;present=@($manifest|Where-Object kind -eq 'technical-sheet').Count;transferCount=$sheets.Rows.Count};manifest=@($manifest)}}
        $shapeFailures=Test-ExpectedShape $report; if($shapeFailures.Count -gt 0){Fail "Inventario local NO-GO: $($shapeFailures -join '; ')"}
        if (-not [IO.Directory]::Exists($output)) { [void][IO.Directory]::CreateDirectory($output) }
        $target=Join-Path $output 'jemnexus-local-sanitized-inventory.json'
        if ([IO.File]::Exists($target) -and -not $AllowNewOutputFile) { Fail "El informe ya existe; use otro OutputRoot o -AllowNewOutputFile para crear un nombre nuevo." }
        if ([IO.File]::Exists($target)) { $target=Join-Path $output ("jemnexus-local-sanitized-inventory-{0}.json" -f ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))) }
        [IO.File]::WriteAllText($target, ($report|ConvertTo-Json -Depth 12), (New-Object Text.UTF8Encoding($false)))
        Write-Output "INVENTORY_LOCAL_READY: $target"
    } finally { if ($connection.State -ne [Data.ConnectionState]::Closed) { $connection.Close() }; $connection.Dispose() }
    exit 0
}

# CompareSnapshot is deliberately offline and writes only its decision report.
$localPath = Assert-ExistingInput $LocalReportPath 'LocalReportPath'
$snapshotPath = Assert-ExistingInput $ProductionSnapshotPath 'ProductionSnapshotPath'
if ([string]::IsNullOrWhiteSpace($EvidenceDateUtc) -or [string]::IsNullOrWhiteSpace($EvidenceSource) -or [string]::IsNullOrWhiteSpace($OutputRoot)) { Fail 'CompareSnapshot requiere EvidenceDateUtc, EvidenceSource y OutputRoot.' }
$parsedDate=[DateTime]::MinValue; if(-not [DateTime]::TryParse($EvidenceDateUtc,[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::AdjustToUniversal,[ref]$parsedDate)){Fail 'EvidenceDateUtc no es una fecha valida.'}
$output=Assert-OutsideRepository $OutputRoot
$local=Get-Content -LiteralPath $localPath -Raw | ConvertFrom-Json
$production=Get-Content -LiteralPath $snapshotPath -Raw | ConvertFrom-Json
$failures=New-Object Collections.Generic.List[string]
foreach($failure in (Test-ExpectedShape $local)){$failures.Add($failure)}
if($production.reportType -ne 'JemNexusProductionSanitizedSnapshot'){$failures.Add('tipo de snapshot productivo inesperado')}
if($production.database -ne 'jemnexusb_prod' -or $production.schema -ne 'jemnexusb_api'){$failures.Add('base/esquema productivo inesperado')}
if([int]$production.migrationCount -ne 22){$failures.Add('migraciones productivas distintas de 22')}
if([long]$production.counts.AppUsers -ne 2){$failures.Add('drift de usuarios productivos')}
if([long]$production.counts.AppUserPermissions -ne 29){$failures.Add('drift de permisos productivos')}
if([long]$production.counts.QuoteRequests -ne 8){$failures.Add('drift de QuoteRequests productivos')}
if([long]$production.counts.CommercialQuotes -ne 0){$failures.Add('cotizaciones productivas inesperadas')}
$expectedProductionUsers=@((Get-Sha256Text 'soporte'),(Get-Sha256Text 'vendedor'))|Sort-Object
$actualProductionUsers=@($production.userIdentityHashes)|Sort-Object
if(($expectedProductionUsers -join ',') -cne ($actualProductionUsers -join ',')){$failures.Add('identidades productivas cambiaron')}
if($production.schemaChecks.missingTables.Count -gt 0 -or $production.schemaChecks.missingColumns.Count -gt 0 -or -not $production.schemaChecks.requiredIndexesPresent -or [long]$production.schemaChecks.orphanForeignKeys -ne 0){$failures.Add('metadata/IDs/FKs/indices productivos invalidos')}
$decision=if($failures.Count -eq 0){'READY_FOR_DESIGN'}else{'NO-GO'}
$result=[ordered]@{reportVersion=$ReportVersion;reportType='JemNexusOfflineDesignReadiness';createdUtc=[DateTime]::UtcNow.ToString('o');decision=$decision;productionEvidence=[ordered]@{declaredDateUtc=$parsedDate.ToUniversalTime().ToString('o');declaredSource=$EvidenceSource;snapshotSha256=(Get-FileHash -LiteralPath $snapshotPath -Algorithm SHA256).Hash.ToLowerInvariant();warning='Evidencia externa declarada; no demuestra el estado productivo actual. Revalidar inmediatamente antes de cualquier apply futuro.'};localReportSha256=(Get-FileHash -LiteralPath $localPath -Algorithm SHA256).Hash.ToLowerInvariant();blockers=@($failures);scope='Solo habilita diseno posterior; no existe metodo de aplicacion aprobado.'}
if(-not [IO.Directory]::Exists($output)){[void][IO.Directory]::CreateDirectory($output)}
$target=Join-Path $output 'jemnexus-offline-design-readiness.json';if([IO.File]::Exists($target)-and -not $AllowNewOutputFile){Fail 'El informe de comparacion ya existe.'};if([IO.File]::Exists($target)){$target=Join-Path $output ("jemnexus-offline-design-readiness-{0}.json" -f ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')))}
[IO.File]::WriteAllText($target,($result|ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))
Write-Output "$decision`: $target"
if($decision -eq 'NO-GO'){exit 2}
