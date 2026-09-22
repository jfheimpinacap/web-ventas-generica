#requires -Version 7.2
<#
.SYNOPSIS
Recopila evidencia sanitizada y de solo lectura de una instalacion productiva de Jem Nexus.

.NOTES
No descubre destinos ni credenciales. La cadena SQL se lee solamente desde
JEM_PRODUCTION_READONLY_CONNECTION_STRING. El archivo del JWT siempre se intenta eliminar.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][uri]$BaseUrl,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$ExpectedHost,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$ExpectedDatabase,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$ExpectedSqlServer,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$TokenFile,
    [ValidateRange(1, 1440)][int]$MinimumTokenLifetimeMinutes = 10,
    [string]$ExpectedIssuer,
    [string]$ExpectedAudience,
    [string]$OutputPath,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:ExitCode = 3
$script:TokenValid = $false
$script:TokenFileRemoved = $false
$script:Blockers = [System.Collections.Generic.List[string]]::new()
$script:Warnings = [System.Collections.Generic.List[string]]::new()

$KnownMigrations = @(
    '20260603182917_InitialCommercialSchema',
    '20260604020543_AddAuthUsersAndAuditRelations',
    '20260616000000_AddCategoryProductType',
    '20260619000000_AddProductPriceDisplayFields',
    '20260619010000_EnsureCanonicalRootCategories',
    '20260803000000_AddMachineryTechnicalData',
    '20260803010000_AddTechnicalSheets',
    '20260810080000_AddProductTechnicalSheetAssociation',
    '20260811000000_AddStructuredMachineryTechnicalData',
    '20260812000000_AddProductMachineWeight',
    '20260816000000_AddSellerCodes',
    '20260817000000_AddCustomerProfiles',
    '20260817010000_AddCommercialQuotes',
    '20260818010000_AddCommercialQuoteIssuanceAndFolios',
    '20260822000000_AddRefreshTokenRotation',
    '20260822010000_AddRefreshTokenPasswordVersion',
    '20260822020000_AddCommercialQuoteIssueIdempotency',
    '20260824010000_AddSellerContactQuoteSnapshots',
    '20260825010000_AddCustomerProfileStatus',
    '20260830000000_PreserveQuotesWhenDeletingProducts',
    '20260917000000_AddGranularSellerPermissions',
    '20260922000000_AddCommercialQuoteIssuedBy'
)
$KnownPermissions = @(
    'brands.create','brands.delete','brands.update',
    'categories.create','categories.delete','categories.update',
    'commercial_quotes.issue','customers.create','customers.set_status','customers.update',
    'home_sections.create','home_sections.delete','home_sections.update',
    'product_images.manage','product_specs.manage',
    'products.create','products.delete','products.update',
    'promotions.create','promotions.delete','promotions.update',
    'quote_notifications.test','quote_requests.update',
    'suppliers.create','suppliers.delete','suppliers.update',
    'technical_sheets.create','technical_sheets.delete','technical_sheets.update',
    'users.manage'
)

function Add-Blocker([string]$Message) { $script:Blockers.Add($Message) }
function Add-Warning([string]$Message) { $script:Warnings.Add($Message) }

function Test-PublicAddress([System.Net.IPAddress]$Address) {
    if ([System.Net.IPAddress]::IsLoopback($Address)) { return $false }
    $bytes = $Address.GetAddressBytes()
    if ($Address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork) {
        return -not ($bytes[0] -eq 10 -or $bytes[0] -eq 127 -or
            ($bytes[0] -eq 169 -and $bytes[1] -eq 254) -or
            ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or
            ($bytes[0] -eq 192 -and $bytes[1] -eq 168))
    }
    return -not ($Address.IsIPv6LinkLocal -or $Address.IsIPv6SiteLocal -or
        (($bytes[0] -band 0xfe) -eq 0xfc))
}

function Assert-SafeDestination {
    if (-not $BaseUrl.IsAbsoluteUri -or $BaseUrl.Scheme -cne 'https') { throw 'BaseUrl debe ser HTTPS absoluta.' }
    if ($BaseUrl.UserInfo -or $BaseUrl.Fragment) { throw 'BaseUrl no puede contener credenciales ni fragmento.' }
    if ($BaseUrl.Query) { throw 'BaseUrl no puede contener query string.' }
    if ($BaseUrl.AbsolutePath -ne '/') { throw 'BaseUrl debe apuntar a la raiz del host.' }
    if ($ExpectedHost -match '[/\\:@?#]' -or $BaseUrl.DnsSafeHost -cne $ExpectedHost) { throw 'El host no coincide exactamente con ExpectedHost.' }
    if ($ExpectedHost -in @('localhost','127.0.0.1','::1')) { throw 'Los destinos locales estan prohibidos.' }
    $parsedIp = $null
    if ([System.Net.IPAddress]::TryParse($ExpectedHost, [ref]$parsedIp) -and -not (Test-PublicAddress $parsedIp)) {
        throw 'Las direcciones privadas, locales y link-local estan prohibidas.'
    }
    foreach ($address in [System.Net.Dns]::GetHostAddresses($ExpectedHost)) {
        if (-not (Test-PublicAddress $address)) { throw 'El host resuelve a una direccion no publica.' }
    }
}

function ConvertFrom-Base64Url([string]$Value) {
    $padded = $Value.Replace('-', '+').Replace('_', '/')
    switch ($padded.Length % 4) { 2 { $padded += '==' } 3 { $padded += '=' } 1 { throw 'JWT mal formado.' } }
    return [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($padded))
}

function Read-TemporaryToken {
    $item = Get-Item -LiteralPath $TokenFile -Force
    if (-not ($item -is [System.IO.FileInfo]) -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'TokenFile debe ser un archivo local regular.' }
    if ($item.Extension -cne '.txt') { throw 'TokenFile debe tener extension .txt.' }
    $lines = @(Get-Content -LiteralPath $item.FullName)
    if ($lines.Count -ne 1 -or [string]::IsNullOrWhiteSpace($lines[0])) { throw 'TokenFile debe contener exactamente una linea no vacia.' }
    $token = $lines[0].Trim()
    $parts = $token.Split('.')
    if ($parts.Count -ne 3 -or @($parts | Where-Object { $_ -notmatch '^[A-Za-z0-9_-]+$' }).Count -gt 0) { throw 'El token no tiene formato JWT basico.' }
    $payload = ConvertFrom-Json (ConvertFrom-Base64Url $parts[1])
    if (-not $payload.exp) { throw 'El JWT no contiene expiracion.' }
    $expires = [DateTimeOffset]::FromUnixTimeSeconds([long]$payload.exp)
    if ($expires -le [DateTimeOffset]::UtcNow.AddMinutes($MinimumTokenLifetimeMinutes)) { throw 'El JWT no conserva el margen minimo de vigencia.' }
    if ($ExpectedIssuer -and $payload.iss -cne $ExpectedIssuer) { throw 'El issuer del JWT no coincide.' }
    if ($ExpectedAudience) {
        $audiences = @($payload.aud)
        if ($ExpectedAudience -cnotin $audiences) { throw 'El audience del JWT no coincide.' }
    }
    $script:TokenValid = $true
    return $token
}

function Invoke-SafeGet([string]$Path, [string]$Token, [bool]$Authenticated = $true) {
    $method = 'GET'
    if ($method -notin @('GET','HEAD')) { throw 'Metodo HTTP no permitido.' }
    $target = [uri]::new($BaseUrl, $Path)
    if ($target.Scheme -cne 'https' -or $target.DnsSafeHost -cne $ExpectedHost) { throw 'Destino HTTP fuera del host validado.' }
    $handler = [Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $handler.UseCookies = $false
    $client = [Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(20)
    try {
        $request = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Get, $target)
        $request.Headers.Accept.ParseAdd('application/json')
        if ($Authenticated) { $request.Headers.Authorization = [Net.Http.Headers.AuthenticationHeaderValue]::new('Bearer', $Token) }
        $response = $client.Send($request)
        $status = [int]$response.StatusCode
        if ($status -ge 300 -and $status -lt 400) {
            $location = $response.Headers.Location
            if (-not $location) { Add-Blocker "$Path devolvio redirect sin destino." }
            else {
                $redirect = if ($location.IsAbsoluteUri) { $location } else { [uri]::new($target, $location) }
                if ($redirect.Scheme -cne 'https' -or $redirect.DnsSafeHost -cne $ExpectedHost) { throw 'Redirect hacia un host o esquema no autorizado.' }
                Add-Blocker "$Path devolvio redirect; no se siguio automaticamente."
            }
            return [ordered]@{ status = $status; compatible = $false }
        }
        if ($status -in @(401,403)) { throw [UnauthorizedAccessException]::new("$Path devolvio $status.") }
        if ($status -eq 404) { Add-Blocker "$Path devolvio 404."; return [ordered]@{ status = $status; compatible = $false } }
        if (-not $response.IsSuccessStatusCode) { Add-Blocker "$Path devolvio HTTP $status."; return [ordered]@{ status = $status; compatible = $false } }
        $mediaType = $response.Content.Headers.ContentType.MediaType
        if ($mediaType -notmatch '^application/(.+\+)?json$') { Add-Blocker "$Path no devolvio JSON."; return [ordered]@{ status = $status; compatible = $false } }
        $json = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        if ([Text.Encoding]::UTF8.GetByteCount($json) -gt 20MB) {
            Add-Blocker "$Path excedio el limite seguro de respuesta de 20 MiB."
            return [ordered]@{ status = $status; compatible = $false }
        }
        $trimmedJson = $json.TrimStart()
        $body = $json | ConvertFrom-Json
        return [ordered]@{ status = $status; compatible = $true; json_array = $trimmedJson.StartsWith('['); body = $body }
    } finally { $client.Dispose(); $handler.Dispose() }
}

function Remove-SqlCommentsAndStrings([string]$Sql) {
    $withoutBlocks = [regex]::Replace($Sql, '/\*.*?\*/', ' ', 'Singleline')
    $withoutLines = [regex]::Replace($withoutBlocks, '--[^\r\n]*', ' ')
    return [regex]::Replace($withoutLines, "N?'(?:''|[^'])*'", "''")
}

function Invoke-ReadOnlyQuery([System.Data.SqlClient.SqlConnection]$Connection, [string]$Sql, [hashtable]$Parameters = @{}) {
    $inspected = (Remove-SqlCommentsAndStrings $Sql).Trim()
    if ($inspected -notmatch '^(?i:SELECT|WITH)\b') { throw 'SQL rechazado: debe comenzar con SELECT o WITH.' }
    if ($inspected -match '(?i)\b(INSERT|UPDATE|DELETE|MERGE|ALTER|CREATE|DROP|TRUNCATE|EXEC(?:UTE)?|GRANT|REVOKE|DENY|DBCC)\b') {
        throw 'SQL rechazado: contiene un verbo no permitido.'
    }
    $command = $Connection.CreateCommand()
    $command.CommandText = $Sql
    $command.CommandTimeout = 15
    foreach ($key in $Parameters.Keys) { [void]$command.Parameters.AddWithValue("@$key", $Parameters[$key]) }
    $table = [Data.DataTable]::new()
    $reader = $command.ExecuteReader()
    try { $table.Load($reader) } finally { $reader.Dispose(); $command.Dispose() }
    return @($table.Rows)
}

function Open-ValidatedSqlConnection {
    $raw = [Environment]::GetEnvironmentVariable('JEM_PRODUCTION_READONLY_CONNECTION_STRING')
    if ([string]::IsNullOrWhiteSpace($raw)) { throw 'Falta JEM_PRODUCTION_READONLY_CONNECTION_STRING.' }
    $builder = [Data.SqlClient.SqlConnectionStringBuilder]::new($raw)
    if ($builder.DataSource -cne $ExpectedSqlServer -or $builder.InitialCatalog -cne $ExpectedDatabase) { throw 'El servidor o base SQL no coincide con el destino esperado.' }
    if ($builder.ApplicationIntent -ne [Data.SqlClient.ApplicationIntent]::ReadOnly) { throw 'ApplicationIntent debe ser ReadOnly.' }
    if (-not $builder.Encrypt) { throw [ArgumentException]::new('Encrypt=True es obligatorio.') }
    if ($builder.TrustServerCertificate) { throw [ArgumentException]::new('TrustServerCertificate=True es inseguro y esta prohibido.') }
    $connection = [Data.SqlClient.SqlConnection]::new($builder.ConnectionString)
    $connection.Open()
    $actual = Invoke-ReadOnlyQuery $connection 'SELECT DB_NAME() AS DatabaseName, CONVERT(nvarchar(128), SERVERPROPERTY(''ServerName'')) AS ServerName;'
    if ($actual.Count -ne 1 -or $actual[0].DatabaseName -cne $ExpectedDatabase -or $actual[0].ServerName -cne $ExpectedSqlServer) {
        $connection.Dispose(); throw 'La identidad informada por SQL no coincide con la esperada.'
    }
    return $connection
}

function Test-Column([Data.SqlClient.SqlConnection]$Connection, [string]$Table, [string]$Column) {
    $rows = Invoke-ReadOnlyQuery $Connection 'SELECT COUNT_BIG(*) AS MatchCount FROM sys.columns c INNER JOIN sys.tables t ON t.object_id = c.object_id WHERE t.name = @table AND c.name = @column;' @{ table=$Table; column=$Column }
    return [long]$rows[0].MatchCount -eq 1
}

function Write-AtomicJson([string]$Json) {
    if (-not $OutputPath) { return }
    $full = [IO.Path]::GetFullPath($OutputPath)
    $repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
    if ($full.StartsWith($repo + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'OutputPath debe estar fuera del repositorio.' }
    if ((Test-Path -LiteralPath $full) -and -not $Force) { throw 'OutputPath ya existe; use -Force de forma explicita.' }
    $parent = Split-Path -Parent $full
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw 'El directorio de OutputPath no existe.' }
    $temporary = Join-Path $parent ('.' + [IO.Path]::GetFileName($full) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::WriteAllText($temporary, $Json, [Text.UTF8Encoding]::new($false))
        if ((Test-Path -LiteralPath $full) -and $Force) { [IO.File]::Replace($temporary, $full, $null) }
        else { [IO.File]::Move($temporary, $full) }
    } finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force } }
}

$token = $null
$connection = $null
$report = $null
try {
    Assert-SafeDestination
    $token = Read-TemporaryToken

    $healthRaw = Invoke-SafeGet '/health' $token $false
    $meRaw = Invoke-SafeGet '/api/auth/me' $token
    $usersRaw = Invoke-SafeGet '/api/admin/users' $token
    $productsRaw = Invoke-SafeGet '/api/products?include_unpublished=true' $token
    $imagesRaw = Invoke-SafeGet '/api/product-images' $token
    $sheetsRaw = Invoke-SafeGet '/api/technical-sheets' $token
    if (-not $healthRaw.compatible -or $healthRaw.json_array -or $healthRaw.body.status -ne 'ok' -or
        $healthRaw.body.app -ne 'JEM Nexus API' -or $healthRaw.body.environment -ne 'Production' -or -not $healthRaw.body.timestamp) {
        Add-Blocker 'Health no coincide con el contrato esperado.'
    }
    if (-not $meRaw.compatible -or $meRaw.json_array -or -not $meRaw.body.id -or -not $meRaw.body.username -or
        -not $meRaw.body.role -or $null -eq $meRaw.body.permissions) { Add-Blocker '/api/auth/me no coincide con AuthUserResponse.' }
    foreach ($listCheck in @($usersRaw,$productsRaw,$imagesRaw,$sheetsRaw)) {
        if ($listCheck.compatible -and -not $listCheck.json_array) { Add-Blocker 'Un endpoint de listado no devolvio un array JSON completo.' }
    }

    try { $connection = Open-ValidatedSqlConnection }
    catch [ArgumentException] { throw }
    catch { $script:ExitCode = 5; throw }
    $historyExists = [long](Invoke-ReadOnlyQuery $connection "SELECT COUNT_BIG(*) AS MatchCount FROM sys.tables WHERE name = '__EFMigrationsHistory';")[0].MatchCount -eq 1
    $applied = if ($historyExists) { @(Invoke-ReadOnlyQuery $connection 'SELECT MigrationId FROM __EFMigrationsHistory ORDER BY MigrationId;' | ForEach-Object { [string]$_.MigrationId }) } else { @() }
    if (-not $historyExists) { Add-Blocker 'No existe __EFMigrationsHistory.' }
    $missing = @($KnownMigrations | Where-Object { $_ -cnotin $applied })
    $unknown = @($applied | Where-Object { $_ -cnotin $KnownMigrations })
    if ($missing.Count) { Add-Blocker 'Hay migraciones conocidas ausentes.' }
    if ($unknown.Count) { Add-Blocker 'Hay migraciones productivas desconocidas.' }

    $permissionTable = [long](Invoke-ReadOnlyQuery $connection "SELECT COUNT_BIG(*) AS MatchCount FROM sys.tables WHERE name = 'AppUserPermissions';")[0].MatchCount -eq 1
    $issuedColumn = Test-Column $connection 'CommercialQuotes' 'IssuedById'
    $schema = [ordered]@{ app_user_permissions_present=$permissionTable; issued_by_present=$issuedColumn; issued_by_pending=($KnownMigrations[-1] -cnotin $applied) }
    if ($permissionTable) {
        $schema.permission_key = @(Invoke-ReadOnlyQuery $connection "SELECT kc.name AS Name, c.name AS ColumnName, ic.key_ordinal AS KeyOrdinal FROM sys.key_constraints kc INNER JOIN sys.index_columns ic ON ic.object_id=kc.parent_object_id AND ic.index_id=kc.unique_index_id INNER JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id WHERE kc.parent_object_id=OBJECT_ID('AppUserPermissions') AND kc.type='PK' ORDER BY ic.key_ordinal;" | ForEach-Object { [ordered]@{ name=$_.Name; column=$_.ColumnName; ordinal=[int]$_.KeyOrdinal } })
        $schema.permission_foreign_key = @(Invoke-ReadOnlyQuery $connection "SELECT fk.name AS Name, OBJECT_NAME(fk.referenced_object_id) AS PrincipalTable, fk.delete_referential_action_desc AS DeleteAction FROM sys.foreign_keys fk WHERE fk.parent_object_id=OBJECT_ID('AppUserPermissions');" | ForEach-Object { [ordered]@{ name=$_.Name; principal=$_.PrincipalTable; delete_action=$_.DeleteAction } })
        $schema.granted_permission_count = [long](Invoke-ReadOnlyQuery $connection 'SELECT COUNT_BIG(*) AS PermissionCount FROM AppUserPermissions;')[0].PermissionCount
        $permissionKeyColumns = @($schema.permission_key | ForEach-Object column)
        if ($permissionKeyColumns.Count -ne 2 -or $permissionKeyColumns[0] -cne 'UserId' -or $permissionKeyColumns[1] -cne 'Permission' -or
            @($schema.permission_foreign_key | Where-Object { $_.principal -eq 'AppUsers' -and $_.delete_action -eq 'CASCADE' }).Count -ne 1) {
            Add-Blocker 'La PK o FK de AppUserPermissions no coincide con el modelo.'
        }
    } else { Add-Blocker 'La tabla AppUserPermissions esta pendiente o ausente.' }
    if ($issuedColumn) {
        $columnInfo = Invoke-ReadOnlyQuery $connection "SELECT c.is_nullable AS IsNullable FROM sys.columns c WHERE c.object_id=OBJECT_ID('CommercialQuotes') AND c.name='IssuedById';"
        $schema.issued_by_nullable = [bool]$columnInfo[0].IsNullable
        $schema.issued_by_index = @((Invoke-ReadOnlyQuery $connection "SELECT i.name AS Name FROM sys.indexes i INNER JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id INNER JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id WHERE i.object_id=OBJECT_ID('CommercialQuotes') AND c.name='IssuedById';").Name)
        $schema.issued_by_foreign_key = @(Invoke-ReadOnlyQuery $connection "SELECT fk.name AS Name, OBJECT_NAME(fk.referenced_object_id) AS PrincipalTable, fk.delete_referential_action_desc AS DeleteAction FROM sys.foreign_keys fk INNER JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id=fk.object_id INNER JOIN sys.columns c ON c.object_id=fkc.parent_object_id AND c.column_id=fkc.parent_column_id WHERE fk.parent_object_id=OBJECT_ID('CommercialQuotes') AND c.name='IssuedById';" | ForEach-Object { [ordered]@{ name=$_.Name; principal=$_.PrincipalTable; delete_action=$_.DeleteAction } })
        $integrity = (Invoke-ReadOnlyQuery $connection 'SELECT COALESCE(SUM(CASE WHEN q.IssuedById IS NULL THEN 1 ELSE 0 END),0) AS NullIssuedBy, COALESCE(SUM(CASE WHEN iu.Id IS NULL THEN 1 ELSE 0 END),0) AS OrphanIssuedBy, COALESCE(SUM(CASE WHEN ru.Id IS NULL THEN 1 ELSE 0 END),0) AS OrphanResponsible, COALESCE(SUM(CASE WHEN q.IssuedById <> q.ResponsibleSellerId THEN 1 ELSE 0 END),0) AS SeparateActors FROM CommercialQuotes q LEFT JOIN AppUsers iu ON iu.Id=q.IssuedById LEFT JOIN AppUsers ru ON ru.Id=q.ResponsibleSellerId;')[0]
        $schema.quote_integrity = [ordered]@{ null_issued_by=[long]$integrity.NullIssuedBy; orphan_issued_by=[long]$integrity.OrphanIssuedBy; orphan_responsible=[long]$integrity.OrphanResponsible; separate_responsible_and_issuer=[long]$integrity.SeparateActors }
        $validIssuedByForeignKey = @($schema.issued_by_foreign_key | Where-Object { $_.principal -eq 'AppUsers' -and $_.delete_action -eq 'NO_ACTION' }).Count -eq 1
        if ($schema.issued_by_nullable -or $schema.issued_by_index.Count -eq 0 -or -not $validIssuedByForeignKey -or $schema.quote_integrity.null_issued_by -or $schema.quote_integrity.orphan_issued_by -or $schema.quote_integrity.orphan_responsible) { Add-Blocker 'La estructura o integridad de IssuedById no coincide.' }
    } else { Add-Blocker 'IssuedById esta pendiente o ausente; se omitieron consultas a esa columna.' }

    $userRows = if ($permissionTable) { Invoke-ReadOnlyQuery $connection 'SELECT u.Id, u.Username, u.Role, u.IsActive, CASE WHEN u.SellerCode IS NULL THEN 0 ELSE 1 END AS HasSellerCode, COUNT(p.Permission) AS PermissionCount FROM AppUsers u LEFT JOIN AppUserPermissions p ON p.UserId=u.Id GROUP BY u.Id,u.Username,u.Role,u.IsActive,u.SellerCode ORDER BY u.Role,u.Username,u.Id;' } else { Invoke-ReadOnlyQuery $connection 'SELECT u.Id, u.Username, u.Role, u.IsActive, CASE WHEN u.SellerCode IS NULL THEN 0 ELSE 1 END AS HasSellerCode, 0 AS PermissionCount FROM AppUsers u ORDER BY u.Role,u.Username,u.Id;' }
    $currentId = if ($meRaw.compatible -and $meRaw.body.id) { [int]$meRaw.body.id } else { -1 }
    $users = @($userRows | ForEach-Object { [ordered]@{ id=[int]$_.Id; username=[string]$_.Username; role=[string]$_.Role; active=[bool]$_.IsActive; has_seller_code=[bool]$_.HasSellerCode; permission_count=[int]$_.PermissionCount; current_session=([int]$_.Id -eq $currentId) } })
    $targets = @('support','soporte','supadmin','jmateluna','fheim')
    $targetPresence = [ordered]@{}; foreach ($name in $targets) { $targetPresence[$name] = @($users | Where-Object username -CEQ $name).Count -gt 0 }
    if (-not $targetPresence.supadmin -or -not $targetPresence.jmateluna -or -not $targetPresence.fheim) { Add-Blocker 'Faltan cuentas requeridas por el estado objetivo.' }
    $activeAdmins = @($users | Where-Object { $_.role -eq 'support_admin' -and $_.active }).Count
    $sellersWithoutCode = @($users | Where-Object { $_.role -eq 'seller' -and -not $_.has_seller_code } | ForEach-Object id)
    $duplicates = @(Invoke-ReadOnlyQuery $connection 'SELECT SellerCode, COUNT_BIG(*) AS UserCount FROM AppUsers WHERE SellerCode IS NOT NULL GROUP BY SellerCode HAVING COUNT_BIG(*) > 1;' | ForEach-Object { [ordered]@{ seller_code=$_.SellerCode; count=[long]$_.UserCount } })
    $unknownRoles = @($users | Where-Object { $_.role -notin @('seller','support_admin') } | ForEach-Object { $_.role } | Sort-Object -Unique)
    $permissionRows = if ($permissionTable) { @(Invoke-ReadOnlyQuery $connection 'SELECT u.Id AS UserId, u.Role, p.Permission FROM AppUserPermissions p INNER JOIN AppUsers u ON u.Id=p.UserId ORDER BY u.Id,p.Permission;') } else { @() }
    $unknownPermissions = @($permissionRows | Where-Object { $_.Permission -cnotin $KnownPermissions } | ForEach-Object { [ordered]@{ user_id=[int]$_.UserId; permission=[string]$_.Permission } })
    $improperManage = @($permissionRows | Where-Object { $_.Role -eq 'seller' -and $_.Permission -eq 'users.manage' } | ForEach-Object { [int]$_.UserId })
    if ($activeAdmins -lt 1 -or $sellersWithoutCode.Count -or $duplicates.Count -or $unknownRoles.Count -or $unknownPermissions.Count -or $improperManage.Count) { Add-Blocker 'El inventario de usuarios, roles, codigos o permisos requiere revision.' }

    $catalogRows = Invoke-ReadOnlyQuery $connection "SELECT p.Id,p.Name,p.Model,p.Sku,b.Name AS Brand,COUNT(DISTINCT i.Id) AS ImageCount,CASE WHEN p.TechnicalSheetId IS NULL THEN 0 ELSE 1 END AS SheetCount,SUM(CASE WHEN i.Id IS NOT NULL AND (i.Image IS NULL OR LTRIM(RTRIM(i.Image))='') THEN 1 ELSE 0 END) AS MissingImageReferences,CASE WHEN p.TechnicalSheetId IS NOT NULL AND (ts.StorageKey IS NULL OR LTRIM(RTRIM(ts.StorageKey))='') THEN 1 ELSE 0 END AS MissingSheetReference FROM Products p LEFT JOIN Brands b ON b.Id=p.BrandId LEFT JOIN ProductImages i ON i.ProductId=p.Id LEFT JOIN TechnicalSheets ts ON ts.Id=p.TechnicalSheetId WHERE UPPER(ISNULL(b.Name,''))='EP' GROUP BY p.Id,p.Name,p.Model,p.Sku,b.Name,p.TechnicalSheetId,ts.StorageKey ORDER BY p.Model,p.Id;"
    $catalog = @($catalogRows | ForEach-Object { [ordered]@{ id=[int]$_.Id; name=$_.Name; model=$_.Model; sku=$_.Sku; brand=$_.Brand; image_count=[int]$_.ImageCount; sheet_count=[int]$_.SheetCount; missing_image_references=[int]$_.MissingImageReferences; missing_sheet_reference=[bool]$_.MissingSheetReference } })
    $catalogDuplicates = @(Invoke-ReadOnlyQuery $connection "SELECT p.Model,COUNT_BIG(*) AS ProductCount FROM Products p LEFT JOIN Brands b ON b.Id=p.BrandId WHERE UPPER(ISNULL(b.Name,''))='EP' AND p.Model IS NOT NULL GROUP BY p.Model HAVING COUNT_BIG(*) > 1;" | ForEach-Object { [ordered]@{ model=$_.Model; count=[long]$_.ProductCount } })
    $excludedBrands = @(Invoke-ReadOnlyQuery $connection "SELECT b.Name AS Brand,COUNT_BIG(*) AS ProductCount FROM Products p INNER JOIN Brands b ON b.Id=p.BrandId WHERE UPPER(b.Name) IN ('LGMG','JLG') GROUP BY b.Name ORDER BY b.Name;" | ForEach-Object { [ordered]@{ brand=$_.Brand; count=[long]$_.ProductCount } })
    if ($catalogDuplicates.Count -or @($catalog | Where-Object { $_.missing_image_references -or $_.missing_sheet_reference }).Count) { Add-Blocker 'El catalogo EP tiene duplicados o referencias multimedia faltantes.' }

    foreach ($apiCheck in @($usersRaw,$productsRaw,$imagesRaw,$sheetsRaw)) { if (-not $apiCheck.compatible) { Add-Blocker 'La evidencia API GET esta incompleta.' } }
    $apiCounts = [ordered]@{
        users = if ($usersRaw.compatible -and $usersRaw.json_array) { @($usersRaw.body).Count } else { $null }
        products = if ($productsRaw.compatible -and $productsRaw.json_array) { @($productsRaw.body).Count } else { $null }
        images = if ($imagesRaw.compatible -and $imagesRaw.json_array) { @($imagesRaw.body).Count } else { $null }
        technical_sheets = if ($sheetsRaw.compatible -and $sheetsRaw.json_array) { @($sheetsRaw.body).Count } else { $null }
    }
    $sqlCountsRow = (Invoke-ReadOnlyQuery $connection "SELECT (SELECT COUNT_BIG(*) FROM AppUsers WHERE Role IN ('seller','support_admin')) AS Users, (SELECT COUNT_BIG(*) FROM Products) AS Products, (SELECT COUNT_BIG(*) FROM ProductImages) AS Images, (SELECT COUNT_BIG(*) FROM TechnicalSheets) AS TechnicalSheets;")[0]
    $sqlCounts = [ordered]@{ users=[long]$sqlCountsRow.Users; products=[long]$sqlCountsRow.Products; images=[long]$sqlCountsRow.Images; technical_sheets=[long]$sqlCountsRow.TechnicalSheets }
    if ($null -eq $apiCounts.users -or $apiCounts.users -ne $sqlCounts.users -or
        $null -eq $apiCounts.products -or $apiCounts.products -ne $sqlCounts.products -or
        $null -eq $apiCounts.images -or $apiCounts.images -ne $sqlCounts.images -or
        $null -eq $apiCounts.technical_sheets -or $apiCounts.technical_sheets -ne $sqlCounts.technical_sheets) {
        Add-Blocker 'Los conteos API no demuestran inventarios completos frente a SQL.'
    }
    $identity = if ($meRaw.compatible) { [ordered]@{ id=$meRaw.body.id; username=$meRaw.body.username; role=$meRaw.body.role; permissions=@($meRaw.body.permissions) } } else { [ordered]@{ available=$false } }
    $report = [ordered]@{
        generated_at_utc=[DateTimeOffset]::UtcNow.ToString('o')
        target=[ordered]@{ validated=$true; scheme='https'; host=$ExpectedHost; database=$ExpectedDatabase; sql_server=$ExpectedSqlServer }
        token=[ordered]@{ TOKEN_VALID=$script:TokenValid; TOKEN_FILE_REMOVED=$false }
        health=if ($healthRaw.compatible) { [ordered]@{ status_code=$healthRaw.status; status=$healthRaw.body.status; app=$healthRaw.body.app; environment=$healthRaw.body.environment } } else { [ordered]@{ status_code=$healthRaw.status; compatible=$false } }
        identity=$identity
        migrations=[ordered]@{ history_present=$historyExists; applied=$applied; known=$KnownMigrations; missing=$missing; unknown=$unknown; granular_permissions_applied=('20260917000000_AddGranularSellerPermissions' -cin $applied); issued_by_applied=('20260922000000_AddCommercialQuoteIssuedBy' -cin $applied) }
        schema=$schema
        users=[ordered]@{ inventory=$users; target_usernames=$targetPresence; active_superadministrators=$activeAdmins; sellers_without_code=$sellersWithoutCode; duplicate_codes=$duplicates; unknown_roles=$unknownRoles; unknown_permissions=$unknownPermissions; sellers_with_users_manage=$improperManage }
        ep_catalog=[ordered]@{ product_count=$catalog.Count; products=$catalog; possible_duplicate_models=$catalogDuplicates; excluded_brand_presence=$excludedBrands }
        multimedia=[ordered]@{ api_images_status=$imagesRaw.status; api_technical_sheets_status=$sheetsRaw.status; api_counts=$apiCounts; sql_counts=$sqlCounts; inventories_complete=($apiCounts.users -eq $sqlCounts.users -and $apiCounts.products -eq $sqlCounts.products -and $apiCounts.images -eq $sqlCounts.images -and $apiCounts.technical_sheets -eq $sqlCounts.technical_sheets); content_downloaded=$false }
        observable_configuration=[ordered]@{ health_environment=if($healthRaw.compatible){$healthRaw.body.environment}else{$null}; encrypted_sql=$true; application_intent='ReadOnly' }
        blockers=@($script:Blockers); warnings=@($script:Warnings); decision='PENDING'
    }
    $report.decision = if ($script:Blockers.Count -eq 0) { 'READY_FOR_REVIEW' } else { 'NO-GO' }
    $script:ExitCode = if ($report.decision -eq 'READY_FOR_REVIEW') { 0 } else { 2 }
} catch [UnauthorizedAccessException] {
    $script:ExitCode = 4
    Add-Blocker $_.Exception.Message
} catch {
    Add-Blocker $_.Exception.Message
} finally {
    if ($connection) { $connection.Dispose() }
    $token = $null
    try {
        if (Test-Path -LiteralPath $TokenFile -PathType Leaf) { Remove-Item -LiteralPath $TokenFile -Force }
        $script:TokenFileRemoved = -not (Test-Path -LiteralPath $TokenFile)
    } catch { $script:TokenFileRemoved = $false; Add-Blocker 'No fue posible eliminar TokenFile.'; if ($script:ExitCode -eq 0) { $script:ExitCode = 3 } }
}

if ($report) {
    $report.token.TOKEN_FILE_REMOVED = $script:TokenFileRemoved
    $report.blockers = @($script:Blockers)
    if (-not $script:TokenFileRemoved) { $report.decision = 'NO-GO' }
    $json = $report | ConvertTo-Json -Depth 12
    try { Write-AtomicJson $json } catch { $script:ExitCode = 3; throw }
    Write-Output $json
} else {
    [ordered]@{ TOKEN_VALID=$script:TokenValid; TOKEN_FILE_REMOVED=$script:TokenFileRemoved; decision='NO-GO'; blockers=@($script:Blockers) } | ConvertTo-Json -Depth 4 | Write-Output
}
exit $script:ExitCode
