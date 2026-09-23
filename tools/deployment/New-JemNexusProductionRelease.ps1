[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$OutputRoot,
    [Parameter(Mandatory = $true)][string]$ViteApiBaseUrl,
    [string]$ViteWhatsappNumber = '',
    [string]$ViteContactEmail = '',
    [string]$ViteGtmId = '',
    [string]$ExpectedBranch = 'main',
    [string]$ExpectedCommit = '',
    [switch]$AllowExistingEmptyOutput,
    [switch]$PlanOnly
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$StartMigration = '20260830000000_PreserveQuotesWhenDeletingProducts'
$PermissionMigration = '20260917000000_AddGranularSellerPermissions'
$EndMigration = '20260922000000_AddCommercialQuoteIssuedBy'
$FrontendPublicUrl = 'https://jem-nexus.cl'
$ExpectedApiHost = 'api.jem-nexus.cl'
$ExpectedDatabase = 'jemnexusb_prod'
$ExpectedSchema = 'jemnexusb_api'
$BackendExclusions = @('appsettings.json', 'appsettings.Development.json', 'appsettings.Production.json', 'web.config', 'logs/', '.env', '.env.*', '*.tmp')
$FrontendExclusions = @('App_Data/', '.user.ini', 'web.config', '*.map', '*.tmp')
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
    $StartMigration
)

function Invoke-CheckedCommand {
    param([Parameter(Mandatory = $true)][string]$FilePath, [Parameter(Mandatory = $true)][string[]]$Arguments)
    Write-Host ("+ {0} {1}" -f $FilePath, ($Arguments -join ' '))
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "El comando '$FilePath' termino con codigo $LASTEXITCODE." }
}

function Get-CommandText {
    param([string]$FilePath, [string[]]$Arguments)
    $rendered = @($Arguments | ForEach-Object { if ($_ -match '[\s"]') { '"' + $_.Replace('"', '\"') + '"' } else { $_ } })
    return ($FilePath + ' ' + ($rendered -join ' ')).Trim()
}

function Get-ToolVersion {
    param([string]$FilePath, [string[]]$Arguments)
    $value = (& $FilePath @Arguments)
    if ($LASTEXITCODE -ne 0) { throw "No se pudo detectar la version de $FilePath." }
    return (($value -join '').Trim())
}

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path, [string]$BasePath)
    if ([System.IO.Path]::IsPathRooted($Path)) { return [System.IO.Path]::GetFullPath($Path) }
    return [System.IO.Path]::GetFullPath((Join-Path $BasePath $Path))
}

function Test-IsChildPath {
    param([string]$Parent, [string]$Candidate)
    $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $candidateFull = [System.IO.Path]::GetFullPath($Candidate).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    return $candidateFull.StartsWith($parentFull, [StringComparison]::OrdinalIgnoreCase)
}

function Assert-ProductionHttpsUrl {
    param([Parameter(Mandatory = $true)][string]$Value, [Parameter(Mandatory = $true)][string]$Name, [switch]$Api)
    $uri = $null
    if (-not [Uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne 'https') { throw "$Name debe ser una URL HTTPS absoluta." }
    if ($uri.UserInfo -or $uri.Query -or $uri.Fragment) { throw "$Name no puede contener credenciales, query ni fragmento." }
    if ($Api) {
        $hostName = $uri.DnsSafeHost.ToLowerInvariant()
        if ($hostName -eq 'localhost' -or $hostName -eq '::1' -or $hostName.EndsWith('.local')) { throw "$Name no puede apuntar a localhost o loopback." }
        $ip = $null
        if ([Net.IPAddress]::TryParse($hostName, [ref]$ip)) {
            if ($ip.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetworkV6 -and $ip.IsIPv4MappedToIPv6) { $ip = $ip.MapToIPv4() }
            $bytes = $ip.GetAddressBytes()
            $private = [Net.IPAddress]::IsLoopback($ip) -or
                ($bytes.Length -eq 4 -and (($bytes[0] -eq 0) -or ($bytes[0] -eq 10) -or ($bytes[0] -eq 127) -or ($bytes[0] -eq 192 -and $bytes[1] -eq 168) -or ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or ($bytes[0] -eq 169 -and $bytes[1] -eq 254))) -or
                ($bytes.Length -eq 16 -and (($bytes[0] -band 0xFE) -eq 0xFC -or ($bytes[0] -eq 0xFE -and ($bytes[1] -band 0xC0) -eq 0x80)))
            if ($private) { throw "$Name no puede apuntar a una direccion privada, link-local o loopback." }
        }
        if ($hostName -cne $ExpectedApiHost) { throw "$Name debe usar el host productivo permitido '$ExpectedApiHost'." }
    }
    return $uri.AbsoluteUri.TrimEnd('/')
}

function Get-DevelopmentApiFallback {
    param([Parameter(Mandatory = $true)][string]$SourcePath)
    $source = [IO.File]::ReadAllText($SourcePath)
    $match = [regex]::Match($source, '(?m)^\s*const\s+DEFAULT_API_BASE_URL\s*=\s*([''"])(?<url>https?://[^''"]+)\1')
    if (-not $match.Success) { throw "No se pudo descubrir DEFAULT_API_BASE_URL desde $SourcePath." }
    $fallback = $null
    if (-not [Uri]::TryCreate($match.Groups['url'].Value, [UriKind]::Absolute, [ref]$fallback)) { throw 'DEFAULT_API_BASE_URL no es una URL absoluta valida.' }
    return $fallback.AbsoluteUri.TrimEnd('/')
}

function Test-NonPublicHost {
    param([Parameter(Mandatory = $true)][Uri]$Uri)
    $hostName = $Uri.DnsSafeHost.ToLowerInvariant()
    if ($hostName -eq 'localhost' -or $hostName.EndsWith('.localhost') -or $hostName.EndsWith('.local')) { return $true }
    $ip = $null
    if (-not [Net.IPAddress]::TryParse($hostName, [ref]$ip)) { return $false }
    if ($ip.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetworkV6 -and $ip.IsIPv4MappedToIPv6) { $ip = $ip.MapToIPv4() }
    $bytes = $ip.GetAddressBytes()
    return [Net.IPAddress]::IsLoopback($ip) -or
        ($bytes.Length -eq 4 -and (($bytes[0] -eq 0) -or ($bytes[0] -eq 10) -or ($bytes[0] -eq 127) -or ($bytes[0] -eq 192 -and $bytes[1] -eq 168) -or ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or ($bytes[0] -eq 169 -and $bytes[1] -eq 254))) -or
        ($bytes.Length -eq 16 -and (($bytes[0] -band 0xFE) -eq 0xFC -or ($bytes[0] -eq 0xFE -and ($bytes[1] -band 0xC0) -eq 0x80)))
}

function Test-ExcludedRelativePath {
    param([string]$RelativePath, [ValidateSet('Backend', 'Frontend')][string]$Kind)
    $normalized = $RelativePath.Replace('\', '/')
    $name = [IO.Path]::GetFileName($normalized)
    if ($Kind -eq 'Backend') {
        return $name -match '^appsettings(?:\..+)?\.json$' -or $name -ieq 'web.config' -or
            $normalized -match '(^|/)logs(/|$)' -or $name -match '^\.env($|\.)' -or $name -match '\.(tmp|temp)$'
    }
    return $normalized -match '(^|/)App_Data(/|$)' -or $name -in @('.user.ini', 'web.config') -or $name -match '\.(map|tmp|temp)$'
}

function Copy-FilteredTree {
    param([string]$Source, [string]$Destination, [ValidateSet('Backend', 'Frontend')][string]$Kind)
    New-Item -ItemType Directory -Path $Destination | Out-Null
    foreach ($file in @(Get-ChildItem -LiteralPath $Source -File -Recurse | Sort-Object FullName)) {
        $relative = $file.FullName.Substring($Source.TrimEnd('\', '/').Length).TrimStart('\', '/')
        if (Test-ExcludedRelativePath -RelativePath $relative -Kind $Kind) { continue }
        $target = Join-Path $Destination $relative
        $targetDirectory = Split-Path $target -Parent
        if (-not (Test-Path -LiteralPath $targetDirectory)) { New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null }
        Copy-Item -LiteralPath $file.FullName -Destination $target
    }
}

function New-DeterministicZip {
    param([string]$Source, [string]$Destination)
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path -LiteralPath $Destination) { throw "El ZIP de destino ya existe: $Destination" }
    $archive = [IO.Compression.ZipFile]::Open($Destination, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($file in @(Get-ChildItem -LiteralPath $Source -File -Recurse | Sort-Object FullName)) {
            $relative = $file.FullName.Substring($Source.TrimEnd('\', '/').Length).TrimStart('\', '/').Replace('\', '/')
            $entry = $archive.CreateEntry($relative, [IO.Compression.CompressionLevel]::Optimal)
            $entry.LastWriteTime = [DateTimeOffset]::new(1980, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
            $input = $file.OpenRead()
            $output = $entry.Open()
            try { $input.CopyTo($output) } finally { $output.Dispose(); $input.Dispose() }
        }
    } finally { $archive.Dispose() }
}

function Assert-RequiredFile {
    param([string]$Root, [string]$RelativePath)
    if (-not (Test-Path -LiteralPath (Join-Path $Root $RelativePath) -PathType Leaf)) { throw "Falta archivo requerido: $RelativePath" }
}

function Assert-FrontendOutput {
    param([string]$DistPath, [string]$ExpectedApiUrl, [string]$DevelopmentApiFallback)
    Assert-RequiredFile $DistPath 'index.html'
    if (-not (Test-Path -LiteralPath (Join-Path $DistPath 'assets') -PathType Container)) { throw 'Falta el directorio frontend assets.' }
    foreach ($path in @('catalogo/index.html', 'maquinaria-nueva/index.html', 'maquinaria-usada/index.html', 'repuestos/index.html', 'servicios/index.html', 'cotizar/index.html', 'contacto/index.html', 'sobre-nosotros/index.html', 'preguntas-frecuentes/index.html', '_spa.html', '_noindex.html')) { Assert-RequiredFile $DistPath $path }
    $apiConfirmed = $false
    $frameworkPlaceholderFiles = New-Object System.Collections.Generic.List[string]
    foreach ($file in @(Get-ChildItem -LiteralPath $DistPath -File -Recurse)) {
        if ($file.Extension.ToLowerInvariant() -notin @('.html', '.js', '.css', '.json', '.xml', '.txt', '.webmanifest', '.manifest', '.config', '.ini')) { continue }
        $content = [IO.File]::ReadAllText($file.FullName)
        if ($content.Contains($ExpectedApiUrl)) { $apiConfirmed = $true }
        if ($content.Contains($DevelopmentApiFallback)) { throw "Fallback API de desarrollo encontrado en $($file.FullName)." }
        foreach ($match in [regex]::Matches($content, '(?i)https?://[^\s"''<>`]+')) {
            $absoluteUrl = $match.Value.TrimEnd(')', ']', '}', ',', ';')
            $uri = $null
            if (-not [Uri]::TryCreate($absoluteUrl, [UriKind]::Absolute, [ref]$uri)) { continue }
            $isExactFrameworkPlaceholder = $absoluteUrl -ceq 'http://localhost'
            if ($isExactFrameworkPlaceholder) {
                if ($file.Extension -cne '.js' -or $uri.Port -ne 80 -or $uri.AbsolutePath -cne '/' -or $uri.Query -or $uri.Fragment -or $uri.UserInfo) {
                    throw "Placeholder localhost fuera de un JavaScript compilado: $($file.FullName)."
                }
                $relative = $file.FullName.Substring($DistPath.TrimEnd('\', '/').Length).TrimStart('\', '/').Replace('\', '/')
                $frameworkPlaceholderFiles.Add($relative)
                continue
            }
            if (Test-NonPublicHost $uri) { throw "URL local, privada, link-local o loopback encontrada en $($file.FullName): $absoluteUrl" }
            if ($uri.Scheme -eq 'http' -and ($uri.DnsSafeHost -match '(?i)api' -or $uri.AbsolutePath -match '(?i)(^|/)api(?:/|$)')) {
                throw "URL API HTTP encontrada en $($file.FullName): $absoluteUrl"
            }
        }
    }
    if (-not $apiConfirmed) { throw "La API productiva esperada '$ExpectedApiUrl' no aparece en los artefactos frontend." }
    return [ordered]@{
        api_productiva_confirmada = $ExpectedApiUrl
        placeholders_framework_permitidos = $frameworkPlaceholderFiles.Count
        archivos_placeholders_framework = @($frameworkPlaceholderFiles | Sort-Object -Unique)
    }
}

function Assert-GeneratedMigrationSql {
    param([string]$Sql)
    foreach ($migration in @($PermissionMigration, $EndMigration)) {
        $count = [regex]::Matches($Sql, "(?is)INSERT\s+INTO\s+\[__EFMigrationsHistory\].*?N'$([regex]::Escape($migration))'").Count
        if ($count -ne 1) { throw "Se esperaba una insercion de historial para $migration; se encontraron $count." }
    }
    $contracts = @(
        '(?is)CREATE\s+TABLE\s+\[AppUserPermissions\]',
        '(?is)INSERT\s+INTO\s+\[AppUserPermissions\].*?FROM\s+\[AppUsers\].*?\[Role\]\s*=\s*N''seller''',
        '(?is)ADD\s+\[IssuedById\]\s+int\s+NULL',
        '(?is)UPDATE\s+\[CommercialQuotes\]\s+SET\s+\[IssuedById\]\s*=\s*\[ResponsibleSellerId\]',
        '(?is)ALTER\s+COLUMN\s+\[IssuedById\]\s+int\s+NOT\s+NULL',
        '(?is)CREATE\s+INDEX\s+\[IX_CommercialQuotes_IssuedById\]',
        '(?is)FOREIGN\s+KEY\s*\(\[IssuedById\]\).*?REFERENCES\s+\[AppUsers\]'
    )
    foreach ($contract in $contracts) { if ($Sql -notmatch $contract) { throw "El SQL EF no cumple el contrato esperado: $contract" } }
    if ([regex]::Matches($Sql, '(?is)INSERT\s+INTO\s+\[AppUserPermissions\]').Count -ne 29) { throw 'El SQL EF debe contener exactamente 29 backfills de permisos.' }
    if ([regex]::Matches($Sql, '(?is)UPDATE\s+\[CommercialQuotes\]\s+SET\s+\[IssuedById\]\s*=\s*\[ResponsibleSellerId\]').Count -ne 1) { throw 'El backfill de IssuedById debe aparecer exactamente una vez.' }
    if ($Sql -match '(?i)\bDROP\s+(?:TABLE|COLUMN)\b|\bTRUNCATE\b|\bDELETE\s+(?:FROM\s+)?\[?(?:CommercialQuotes|QuoteRequests|AppUsers|AppUserPermissions)\]?') { throw 'El SQL EF contiene una operacion destructiva prohibida.' }
    if ($Sql -match '(?i)ON\s+DELETE\s+CASCADE[^;]*IssuedBy|IssuedBy[^;]*ON\s+DELETE\s+CASCADE') { throw 'La FK IssuedBy no puede usar cascada.' }
}

function ConvertTo-ProtectedMigrationSql {
    param([Parameter(Mandatory = $true)][string]$Sql)
    $batches = @([regex]::Split($Sql, '(?im)^\s*GO\s*(?:--[^\r\n]*)?\r?$') | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($batches.Count -eq 0) { throw 'El SQL EF no contiene lotes ejecutables.' }

    $protected = New-Object System.Collections.Generic.List[string]
    $directTransactionCount = 0
    $dynamicBatchCount = 0
    for ($index = 0; $index -lt $batches.Count; $index++) {
        $ordinal = $index + 1
        $previousOrdinal = $index
        $body = $batches[$index].Trim()
        $isBeginTransaction = $body -match '(?is)^BEGIN\s+TRANSACTION\s*;?\s*$'
        $isCommit = $body -match '(?is)^COMMIT\s*;?\s*$'
        $containsTransactionControl = $body -match '(?im)^\s*(?:BEGIN\s+(?:TRANSACTION|TRAN)|COMMIT(?:\s+(?:TRANSACTION|TRAN))?|ROLLBACK(?:\s+(?:TRANSACTION|TRAN))?)\b'
        if ($containsTransactionControl -and -not ($isBeginTransaction -or $isCommit)) {
            throw "El lote EF $ordinal mezcla o usa una variante inesperada de control transaccional."
        }
        if ($isBeginTransaction -or $isCommit) {
            $directTransactionCount++
            $execution = @"
    -- CONTROL TRANSACCIONAL EF DIRECTO: no puede cruzar sp_executesql
    $body
"@
        } else {
            $dynamicBatchCount++
            $escapedBody = $body.Replace("'", "''")
            $execution = "    EXEC sys.sp_executesql N'$escapedBody';"
        }
        $protected.Add(@"
-- BEGIN LOTE EF PROTEGIDO $ordinal; REQUIERE ORDINAL $previousOrdinal
IF OBJECT_ID(N'tempdb..#JemNexusReleasePreflight', N'U') IS NULL
BEGIN
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW 51001, 'Centinela de release ausente; lote EF bloqueado.', 1;
END;
IF XACT_STATE() <> 1
BEGIN
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    UPDATE #JemNexusReleasePreflight SET [ExecutionFailed] = 1;
    THROW 51001, 'Transaccion exterior ausente o no confirmable; lote EF bloqueado.', 1;
END;
DECLARE @ObservedOrdinal$ordinal int;
EXEC sys.sp_executesql N'SELECT @Value = [LastCompletedBatch] FROM #JemNexusReleasePreflight WHERE [ExecutionFailed] = 0;', N'@Value int OUTPUT', @Value = @ObservedOrdinal$ordinal OUTPUT;
IF @ObservedOrdinal$ordinal <> $previousOrdinal
BEGIN
    ROLLBACK TRANSACTION;
    UPDATE #JemNexusReleasePreflight SET [ExecutionFailed] = 1;
    THROW 51001, 'Secuencia de lotes EF invalida; lote bloqueado.', 1;
END;
BEGIN TRY
$execution
    IF XACT_STATE() <> 1 THROW 51001, 'El lote EF dejo inactiva o invalida la transaccion exterior.', 1;
    UPDATE #JemNexusReleasePreflight
       SET [LastCompletedBatch] = $ordinal
     WHERE [LastCompletedBatch] = $previousOrdinal AND [ExecutionFailed] = 0;
    IF @@ROWCOUNT <> 1 THROW 51001, 'No se pudo registrar el avance secuencial del lote EF.', 1;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    IF OBJECT_ID(N'tempdb..#JemNexusReleasePreflight', N'U') IS NOT NULL
        UPDATE #JemNexusReleasePreflight SET [ExecutionFailed] = 1;
    THROW;
END CATCH;
-- END LOTE EF PROTEGIDO $ordinal
GO
"@)
    }
    if ($directTransactionCount -ne 4 -or $dynamicBatchCount -ne ($batches.Count - $directTransactionCount)) { throw 'La clasificacion derivada de lotes EF no es consistente.' }
    $beginCount = @($batches | Where-Object { $_.Trim() -match '(?is)^BEGIN\s+TRANSACTION\s*;?\s*$' }).Count
    $commitCount = @($batches | Where-Object { $_.Trim() -match '(?is)^COMMIT\s*;?\s*$' }).Count
    if ($beginCount -ne 2 -or $commitCount -ne 2) { throw "El SQL EF debe contener exactamente dos BEGIN TRANSACTION y dos COMMIT puros; se derivaron $beginCount y $commitCount." }
    return [pscustomobject]@{ Sql = ($protected -join "`r`n"); BatchCount = $batches.Count; DirectTransactionBatchCount = $directTransactionCount; DynamicBatchCount = $dynamicBatchCount; BeginTransactionBatchCount = $beginCount; CommitBatchCount = $commitCount }
}

function Assert-ProtectedMigrationSql {
    param([Parameter(Mandatory = $true)][string]$Sql, [Parameter(Mandatory = $true)][int]$BatchCount, [Parameter(Mandatory = $true)][int]$DirectTransactionBatchCount, [Parameter(Mandatory = $true)][int]$DynamicBatchCount)
    if ($BatchCount -le 0) { throw 'La cantidad de lotes EF protegidos debe ser positiva.' }
    if ($BatchCount -ne 41) { throw "El SQL EF actual debe derivar exactamente 41 lotes; se derivaron $BatchCount." }
    $lines = [regex]::Split($Sql, "\r\n|\n|\r")
    $markerPattern = '^-- BEGIN LOTE EF PROTEGIDO (?<Ordinal>\d+); REQUIERE ORDINAL (?<PreviousOrdinal>\d+)$'
    $markers = @($lines | ForEach-Object { [regex]::Match($_, $markerPattern) } | Where-Object { $_.Success })
    if ($markers.Count -ne $BatchCount) { throw 'No todos los lotes EF quedaron protegidos.' }
    for ($ordinal = 1; $ordinal -le $BatchCount; $ordinal++) {
        $previousOrdinal = $ordinal - 1
        $marker = $markers[$ordinal - 1]
        if ([int]$marker.Groups['Ordinal'].Value -ne $ordinal -or [int]$marker.Groups['PreviousOrdinal'].Value -ne $previousOrdinal) { throw "Falta la guarda secuencial exacta del lote EF $ordinal." }
        if ($Sql.IndexOf("SET [LastCompletedBatch] = $ordinal", [StringComparison]::Ordinal) -lt 0) { throw "Falta el avance posterior del lote EF $ordinal." }
        if ($Sql.IndexOf("-- END LOTE EF PROTEGIDO $ordinal", [StringComparison]::Ordinal) -lt 0) { throw "Falta el marcador final exacto del lote EF $ordinal." }
    }
    if ([regex]::Matches($Sql, "OBJECT_ID\(N'tempdb\.\.#JemNexusReleasePreflight'").Count -lt ($BatchCount + 1)) { throw 'Faltan comprobaciones del centinela entre lotes.' }
    if ([regex]::Matches($Sql, 'IF XACT_STATE\(\) <> 1').Count -lt ($BatchCount + 1)) { throw 'Faltan comprobaciones de la transaccion exterior.' }
    $efRegionStart = $Sql.IndexOf('-- BEGIN SQL EMITIDO POR EF CORE;', [StringComparison]::Ordinal)
    if ($efRegionStart -lt 0) { throw 'Falta el limite inicial exacto del SQL EF protegido.' }
    $efRegionEnd = $Sql.IndexOf('-- END SQL EMITIDO POR EF CORE;', $efRegionStart, [StringComparison]::Ordinal)
    if ($efRegionEnd -lt 0) { throw 'Falta el limite final exacto del SQL EF protegido.' }
    $efRegion = $Sql.Substring($efRegionStart, $efRegionEnd - $efRegionStart)
    $directMarkers = [regex]::Matches($efRegion, '(?m)^\s*-- CONTROL TRANSACCIONAL EF DIRECTO:')
    if ($directMarkers.Count -ne $DirectTransactionBatchCount -or $DirectTransactionBatchCount -ne 4) { throw 'Los cuatro lotes de control transaccional no quedaron directos y protegidos.' }
    $dynamicBodies = [regex]::Matches($efRegion, '(?m)^\s*EXEC sys\.sp_executesql N''(?!(?:SELECT @Value|SELECT @Ordinal))')
    if ($dynamicBodies.Count -ne $DynamicBatchCount -or ($DirectTransactionBatchCount + $DynamicBatchCount) -ne $BatchCount) { throw 'La clasificacion de cuerpos EF directos y dinamicos no coincide con los lotes derivados.' }
    if ($DynamicBatchCount -ne 37) { throw "El SQL EF actual debe derivar 37 cuerpos dinamicos; se derivaron $DynamicBatchCount." }
    foreach ($dynamicBody in $dynamicBodies) {
        $payloadEnd = $efRegion.IndexOf("`n    IF XACT_STATE() <> 1 THROW 51001", $dynamicBody.Index, [StringComparison]::Ordinal)
        if ($payloadEnd -lt 0) { throw 'No se pudo delimitar un cuerpo EF dinamico.' }
        $payload = $efRegion.Substring($dynamicBody.Index, $payloadEnd - $dynamicBody.Index)
        if ($payload -match '(?im)^\s*(?:BEGIN\s+TRANSACTION|COMMIT(?:\s+TRANSACTION)?|ROLLBACK\s+TRANSACTION)\s*;?\s*$') { throw 'Un control transaccional quedo dentro de sp_executesql.' }
    }
    if ($Sql.IndexOf('IF @PostflightOrdinal <>', [StringComparison]::Ordinal) -lt 0) { throw 'El postflight no exige la secuencia EF completa.' }
    $postflightStart = $Sql.IndexOf('-- BEGIN POSTFLIGHT PROTEGIDO;', [StringComparison]::Ordinal)
    if ($postflightStart -lt 0) { throw 'Falta el limite inicial exacto del postflight protegido.' }
    $dynamicPostflightStart = $Sql.IndexOf('-- BEGIN VALIDACION POSTFLIGHT DINAMICA', $postflightStart, [StringComparison]::Ordinal)
    if ($dynamicPostflightStart -lt 0) { throw 'Falta el limite inicial de la validacion dinamica del postflight.' }
    $dynamicPostflightEnd = $Sql.IndexOf('-- END VALIDACION POSTFLIGHT DINAMICA', $dynamicPostflightStart, [StringComparison]::Ordinal)
    if ($dynamicPostflightEnd -lt 0) { throw 'Falta el limite final de la validacion dinamica del postflight.' }
    $postflightPrefix = $Sql.Substring($postflightStart, $dynamicPostflightStart - $postflightStart)
    if ($postflightPrefix -match '(?i)\[IssuedById\]|\[AppUserPermissions\]|IX_CommercialQuotes_IssuedById|FK_CommercialQuotes_AppUsers_IssuedById') { throw 'Una referencia al schema nuevo aparece antes de la compilacion diferida del postflight.' }
    $dynamicPostflight = $Sql.Substring($dynamicPostflightStart, $dynamicPostflightEnd - $dynamicPostflightStart)
    if ($dynamicPostflight -match '(?im)^\s*(?:BEGIN|COMMIT|ROLLBACK)\s+TRANSACTION\b') { throw 'La validacion dinamica del postflight contiene control transaccional.' }
    $outerCommit = $Sql.IndexOf('COMMIT TRANSACTION;', $dynamicPostflightEnd, [StringComparison]::Ordinal)
    $success = $Sql.IndexOf("N'POSTFLIGHT_OK'", $outerCommit, [StringComparison]::Ordinal)
    $cleanup = $Sql.IndexOf('DROP TABLE #JemNexusReleasePreflight;', $success, [StringComparison]::Ordinal)
    if ($outerCommit -lt $dynamicPostflightEnd -or $success -lt $outerCommit -or $cleanup -lt $success) { throw 'El orden postflight debe ser validacion, COMMIT exterior, POSTFLIGHT_OK y limpieza.' }
}

function Get-SqlPreflight {
    $values = ($KnownMigrations | ForEach-Object { "    (N'$_')" }) -join ",`r`n"
    return @"
SET XACT_ABORT ON;
IF DB_NAME() <> N'$ExpectedDatabase' THROW 51000, 'Base de datos inesperada.', 1;
DECLARE @DefaultSchema sysname = SCHEMA_NAME();
IF @DefaultSchema <> N'$ExpectedSchema' THROW 51000, 'Default schema inesperado.', 1;
IF OBJECT_ID(N'[$ExpectedSchema].[__EFMigrationsHistory]', N'U') IS NULL THROW 51000, 'No existe el historial EF esperado.', 1;
DECLARE @KnownMigrations TABLE ([MigrationId] nvarchar(150) NOT NULL PRIMARY KEY);
INSERT INTO @KnownMigrations ([MigrationId]) VALUES
$values;
IF (SELECT COUNT(*) FROM [$ExpectedSchema].[__EFMigrationsHistory]) <> 20 THROW 51000, 'El historial no contiene exactamente 20 migraciones.', 1;
IF EXISTS (SELECT 1 FROM @KnownMigrations k WHERE NOT EXISTS (SELECT 1 FROM [$ExpectedSchema].[__EFMigrationsHistory] h WHERE h.[MigrationId] = k.[MigrationId])) THROW 51000, 'Falta una migracion conocida anterior.', 1;
IF EXISTS (SELECT 1 FROM [$ExpectedSchema].[__EFMigrationsHistory] h WHERE NOT EXISTS (SELECT 1 FROM @KnownMigrations k WHERE k.[MigrationId] = h.[MigrationId])) THROW 51000, 'Existe una migracion desconocida.', 1;
IF (SELECT TOP (1) [MigrationId] FROM [$ExpectedSchema].[__EFMigrationsHistory] ORDER BY [MigrationId] DESC) <> N'$StartMigration' THROW 51000, 'La ultima migracion no coincide con el limite inicial.', 1;
IF EXISTS (SELECT 1 FROM [$ExpectedSchema].[__EFMigrationsHistory] WHERE [MigrationId] IN (N'$PermissionMigration', N'$EndMigration')) THROW 51000, 'Una migracion destino ya esta registrada.', 1;
IF OBJECT_ID(N'[$ExpectedSchema].[AppUserPermissions]', N'U') IS NOT NULL THROW 51000, 'AppUserPermissions ya existe.', 1;
IF COL_LENGTH(N'[$ExpectedSchema].[CommercialQuotes]', N'IssuedById') IS NOT NULL THROW 51000, 'IssuedById ya existe.', 1;
CREATE TABLE #JemNexusReleasePreflight ([QuoteRequestCount] bigint NOT NULL, [LastCompletedBatch] int NOT NULL, [ExecutionFailed] bit NOT NULL);
INSERT INTO #JemNexusReleasePreflight ([QuoteRequestCount], [LastCompletedBatch], [ExecutionFailed]) SELECT COUNT_BIG(*), 0, 0 FROM [$ExpectedSchema].[QuoteRequests];
BEGIN TRANSACTION;
GO
"@
}

function Get-SqlPostflight {
    param([Parameter(Mandatory = $true)][int]$FinalBatchOrdinal)
    return @"
-- BEGIN POSTFLIGHT PROTEGIDO; REQUIERE ORDINAL $FinalBatchOrdinal
IF OBJECT_ID(N'tempdb..#JemNexusReleasePreflight', N'U') IS NULL
BEGIN
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW 51002, 'Centinela de release ausente; postflight y COMMIT bloqueados.', 1;
END;
IF XACT_STATE() <> 1
BEGIN
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    UPDATE #JemNexusReleasePreflight SET [ExecutionFailed] = 1;
    THROW 51002, 'Transaccion exterior ausente o no confirmable; postflight y COMMIT bloqueados.', 1;
END;
DECLARE @PostflightOrdinal int, @PostflightFailed bit;
EXEC sys.sp_executesql N'SELECT @Ordinal = [LastCompletedBatch], @Failed = [ExecutionFailed] FROM #JemNexusReleasePreflight;', N'@Ordinal int OUTPUT, @Failed bit OUTPUT', @Ordinal = @PostflightOrdinal OUTPUT, @Failed = @PostflightFailed OUTPUT;
IF @PostflightOrdinal <> $FinalBatchOrdinal OR @PostflightFailed <> 0
BEGIN
    ROLLBACK TRANSACTION;
    UPDATE #JemNexusReleasePreflight SET [ExecutionFailed] = 1;
    THROW 51002, 'La secuencia completa de lotes EF no fue confirmada; postflight y COMMIT bloqueados.', 1;
END;
BEGIN TRY
DECLARE @TargetMigrations int, @SellerCount bigint, @SellerPermissionCount bigint, @CommercialQuoteCount bigint, @QuoteRequestCount bigint;
-- BEGIN VALIDACION POSTFLIGHT DINAMICA (sin control transaccional)
EXEC sys.sp_executesql N'
IF DB_NAME() <> N''$ExpectedDatabase'' OR SCHEMA_NAME() <> N''$ExpectedSchema'' THROW 51000, ''Destino cambio durante la ejecucion.'', 1;
IF EXISTS (SELECT [MigrationId] FROM [$ExpectedSchema].[__EFMigrationsHistory] WHERE [MigrationId] IN (N''$PermissionMigration'', N''$EndMigration'') GROUP BY [MigrationId] HAVING COUNT(*) <> 1) OR (SELECT COUNT(*) FROM [$ExpectedSchema].[__EFMigrationsHistory] WHERE [MigrationId] IN (N''$PermissionMigration'', N''$EndMigration'')) <> 2 THROW 51000, ''Las migraciones destino no quedaron registradas una vez.'', 1;
IF OBJECT_ID(N''[$ExpectedSchema].[AppUserPermissions]'', N''U'') IS NULL THROW 51000, ''AppUserPermissions no existe tras migrar.'', 1;
IF EXISTS (SELECT 1 FROM [$ExpectedSchema].[AppUsers] u WHERE u.[Role] = N''seller'' AND (SELECT COUNT(*) FROM [$ExpectedSchema].[AppUserPermissions] p WHERE p.[UserId] = u.[Id]) <> 29) THROW 51000, ''Un seller no tiene exactamente 29 permisos.'', 1;
IF EXISTS (SELECT 1 FROM [$ExpectedSchema].[AppUserPermissions] p INNER JOIN [$ExpectedSchema].[AppUsers] u ON u.[Id] = p.[UserId] WHERE u.[Role] = N''seller'' AND p.[Permission] = N''users.manage'') THROW 51000, ''Un seller posee users.manage.'', 1;
IF EXISTS (SELECT 1 FROM sys.columns WHERE [object_id] = OBJECT_ID(N''[$ExpectedSchema].[CommercialQuotes]'') AND [name] = N''IssuedById'' AND [is_nullable] <> 0) OR COL_LENGTH(N''[$ExpectedSchema].[CommercialQuotes]'', N''IssuedById'') IS NULL THROW 51000, ''IssuedById falta o permite NULL.'', 1;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE [object_id] = OBJECT_ID(N''[$ExpectedSchema].[CommercialQuotes]'') AND [name] = N''IX_CommercialQuotes_IssuedById'') THROW 51000, ''Falta el indice IssuedById.'', 1;
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE [parent_object_id] = OBJECT_ID(N''[$ExpectedSchema].[CommercialQuotes]'') AND [name] = N''FK_CommercialQuotes_AppUsers_IssuedById'' AND [delete_referential_action_desc] = N''NO_ACTION'') THROW 51000, ''Falta la FK IssuedById NO_ACTION.'', 1;
IF EXISTS (SELECT 1 FROM [$ExpectedSchema].[CommercialQuotes] WHERE [IssuedById] IS NULL) THROW 51000, ''Hay cotizaciones sin emisor.'', 1;
IF (SELECT COUNT_BIG(*) FROM [$ExpectedSchema].[QuoteRequests]) <> (SELECT [QuoteRequestCount] FROM #JemNexusReleasePreflight) THROW 51000, ''Cambio el conteo de QuoteRequests.'', 1;
SELECT @TargetMigrationsOut = COUNT(*) FROM [$ExpectedSchema].[__EFMigrationsHistory] WHERE [MigrationId] IN (N''$PermissionMigration'', N''$EndMigration'');
SELECT @SellerCountOut = COUNT_BIG(*) FROM [$ExpectedSchema].[AppUsers] WHERE [Role] = N''seller'';
SELECT @SellerPermissionCountOut = COUNT_BIG(*) FROM [$ExpectedSchema].[AppUserPermissions] p INNER JOIN [$ExpectedSchema].[AppUsers] u ON u.[Id] = p.[UserId] WHERE u.[Role] = N''seller'';
SELECT @CommercialQuoteCountOut = COUNT_BIG(*) FROM [$ExpectedSchema].[CommercialQuotes];
SELECT @QuoteRequestCountOut = COUNT_BIG(*) FROM [$ExpectedSchema].[QuoteRequests];',
N'@TargetMigrationsOut int OUTPUT, @SellerCountOut bigint OUTPUT, @SellerPermissionCountOut bigint OUTPUT, @CommercialQuoteCountOut bigint OUTPUT, @QuoteRequestCountOut bigint OUTPUT',
@TargetMigrationsOut = @TargetMigrations OUTPUT, @SellerCountOut = @SellerCount OUTPUT, @SellerPermissionCountOut = @SellerPermissionCount OUTPUT, @CommercialQuoteCountOut = @CommercialQuoteCount OUTPUT, @QuoteRequestCountOut = @QuoteRequestCount OUTPUT;
-- END VALIDACION POSTFLIGHT DINAMICA
IF XACT_STATE() <> 1 THROW 51002, 'La validacion postflight dejo invalida la transaccion exterior.', 1;
COMMIT TRANSACTION;
SELECT DB_NAME() AS [DatabaseName], SCHEMA_NAME() AS [DefaultSchema], @TargetMigrations AS [TargetMigrations], @SellerCount AS [SellerCount], @SellerPermissionCount AS [SellerPermissionCount], @CommercialQuoteCount AS [CommercialQuoteCount], @QuoteRequestCount AS [QuoteRequestCount], N'POSTFLIGHT_OK' AS [Result];
DROP TABLE #JemNexusReleasePreflight;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    IF OBJECT_ID(N'tempdb..#JemNexusReleasePreflight', N'U') IS NOT NULL
        UPDATE #JemNexusReleasePreflight SET [ExecutionFailed] = 1;
    THROW;
END CATCH;
-- END POSTFLIGHT PROTEGIDO
GO
"@
}

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$outputPath = Get-FullPath -Path $OutputRoot -BasePath (Get-Location).Path
$apiUrl = Assert-ProductionHttpsUrl -Value $ViteApiBaseUrl -Name 'VITE_API_BASE_URL' -Api
$siteUrl = Assert-ProductionHttpsUrl -Value $FrontendPublicUrl -Name 'URL publica frontend'

if ((Test-IsChildPath $repoRoot $outputPath) -or (Test-IsChildPath $outputPath $repoRoot)) { throw 'OutputRoot debe estar completamente fuera del repositorio y sus carpetas fuente.' }

$branchOutput = @(& git -C $repoRoot branch --show-current)
if ($LASTEXITCODE -ne 0) { throw 'No se pudo determinar la rama Git.' }
$branch = ($branchOutput -join '').Trim()
if ([string]::IsNullOrWhiteSpace($branch)) { throw "HEAD esta detached; se esperaba la rama '$ExpectedBranch'." }
$commitOutput = @(& git -C $repoRoot rev-parse HEAD)
if ($LASTEXITCODE -ne 0) { throw 'No se pudo determinar HEAD.' }
$commit = ($commitOutput -join '').Trim()
$status = @(& git -C $repoRoot status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or $status.Count -ne 0) { throw 'El arbol Git debe estar limpio.' }
if ($branch -ne $ExpectedBranch) { throw "Rama inesperada: '$branch'; se esperaba '$ExpectedBranch'." }
if ($commit -notmatch '^[0-9a-f]{40}$') { throw 'HEAD no es un SHA Git completo valido.' }
if ($ExpectedCommit) {
    if ($ExpectedCommit -cnotmatch '^[0-9a-fA-F]{40}$') { throw 'ExpectedCommit debe contener exactamente 40 caracteres hexadecimales.' }
    $expectedCommitCanonical = $ExpectedCommit.ToLowerInvariant()
    if ($commit -cne $expectedCommitCanonical) { throw "Commit inesperado: HEAD observado '$commit'; se esperaba '$expectedCommitCanonical'." }
} elseif (-not $PlanOnly) {
    throw 'ExpectedCommit es obligatorio para generar un release real.'
}
$shortSha = $commit.Substring(0, 12)

$backendName = "jem-nexus-backend-$shortSha.zip"
$frontendName = "jem-nexus-frontend-$shortSha.zip"
$sqlName = 'jem-nexus-migrations-20260830000000-to-20260922000000.sql'
$stagingRoot = Join-Path $outputPath ".jem-nexus-release-staging-$shortSha"
$backendPublish = Join-Path $stagingRoot 'backend-publish'
$backendPackage = Join-Path $stagingRoot 'backend-package'
$frontendPackage = Join-Path $stagingRoot 'frontend-package'
$rawSql = Join-Path $stagingRoot 'ef-migrations.sql'
$releaseStaging = Join-Path $stagingRoot 'release-artifacts'
$backendProject = Join-Path $repoRoot 'backend-dotnet\JemNexus.Api\JemNexus.Api.csproj'
$frontendRoot = Join-Path $repoRoot 'frontend'
$frontendDist = Join-Path $frontendRoot 'dist'
$frontendApiSource = Join-Path $frontendRoot 'src\services\api.ts'

$publishArgs = @('publish', $backendProject, '-c', 'Release', '-f', 'net8.0', '--no-restore', '-o', $backendPublish)
$npmArgs = @('run', 'build')
$efArgs = @('ef', 'migrations', 'script', $StartMigration, $EndMigration, '--project', $backendProject, '--startup-project', $backendProject, '--configuration', 'Release', '--no-build', '--output', $rawSql)
$commands = @(
    (Get-CommandText 'dotnet' $publishArgs),
    (Get-CommandText 'npm' $npmArgs),
    (Get-CommandText 'dotnet' $efArgs)
)

$outputAlreadyExists = Test-Path -LiteralPath $outputPath
if ($outputAlreadyExists) {
    if (-not $AllowExistingEmptyOutput) { throw 'OutputRoot ya existe; use -AllowExistingEmptyOutput solo para un directorio vacio.' }
    if (-not (Test-Path -LiteralPath $outputPath -PathType Container) -or @(Get-ChildItem -LiteralPath $outputPath -Force).Count -ne 0) { throw 'OutputRoot existente debe ser un directorio vacio.' }
}

if ($PlanOnly) {
    Write-Host 'PLAN ONLY: no se crearan directorios, archivos, ZIP ni SQL; no se ejecutaran dotnet, npm, Node, EF ni compresion.'
    Write-Host "Repositorio: $repoRoot"
    Write-Host "Output: $outputPath"
    Write-Host "Staging controlado: $stagingRoot"
    Write-Host "Backend: $backendName"
    Write-Host "Frontend: $frontendName"
    Write-Host "SQL: $sqlName"
    Write-Host "Frontend URL: $siteUrl"
    Write-Host "API URL (VITE_API_BASE_URL): $apiUrl"
    Write-Host 'Comandos previstos:'
    $commands | ForEach-Object { Write-Host "- $_" }
    Write-Host ('Exclusiones backend: ' + ($BackendExclusions -join ', '))
    Write-Host ('Exclusiones frontend: ' + ($FrontendExclusions -join ', '))
    Write-Host 'Outputs auxiliares: manifest.json, SHA256SUMS.txt, PRESERVE_ON_SERVER.txt'
    exit 0
}

if (-not $outputAlreadyExists) { New-Item -ItemType Directory -Path $outputPath | Out-Null }
if (Test-Path -LiteralPath $stagingRoot) { throw 'El staging exacto ya existe; no se eliminara una ruta que esta ejecucion no creo.' }
New-Item -ItemType Directory -Path $stagingRoot | Out-Null
New-Item -ItemType Directory -Path $releaseStaging | Out-Null

$stages = New-Object System.Collections.Generic.List[object]
$previousViteEnvironment = @{}
foreach ($name in @('VITE_API_BASE_URL', 'VITE_WHATSAPP_NUMBER', 'VITE_CONTACT_EMAIL', 'VITE_GTM_ID')) {
    $previousViteEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
try {
    $env:VITE_API_BASE_URL = $apiUrl
    $env:VITE_WHATSAPP_NUMBER = $ViteWhatsappNumber
    $env:VITE_CONTACT_EMAIL = $ViteContactEmail
    $env:VITE_GTM_ID = $ViteGtmId

    Invoke-CheckedCommand dotnet $publishArgs
    $stages.Add([ordered]@{ name = 'backend_publish'; result = 'passed' })
    foreach ($required in @('JemNexus.Api.dll', 'JemNexus.Api.deps.json', 'JemNexus.Api.runtimeconfig.json')) { Assert-RequiredFile $backendPublish $required }
    Copy-FilteredTree $backendPublish $backendPackage Backend
    New-DeterministicZip $backendPackage (Join-Path $releaseStaging $backendName)
    $stages.Add([ordered]@{ name = 'backend_package'; result = 'passed' })

    Push-Location $frontendRoot
    try { Invoke-CheckedCommand npm $npmArgs } finally { Pop-Location }
    $developmentApiFallback = Get-DevelopmentApiFallback $frontendApiSource
    $frontendValidation = Assert-FrontendOutput $frontendDist $apiUrl $developmentApiFallback
    Copy-FilteredTree $frontendDist $frontendPackage Frontend
    New-DeterministicZip $frontendPackage (Join-Path $releaseStaging $frontendName)
    $stages.Add([ordered]@{ name = 'frontend_build_validate_package'; result = 'passed' })

    Invoke-CheckedCommand dotnet $efArgs
    $efSql = [IO.File]::ReadAllText($rawSql)
    Assert-GeneratedMigrationSql $efSql
    $protectedEf = ConvertTo-ProtectedMigrationSql $efSql
    $finalSql = (Get-SqlPreflight) + "`r`n-- BEGIN SQL EMITIDO POR EF CORE; CUERPOS SIN CAMBIOS, EJECUCION PROTEGIDA`r`n" + $protectedEf.Sql + "`r`n-- END SQL EMITIDO POR EF CORE; CUERPOS SIN CAMBIOS, EJECUCION PROTEGIDA`r`n" + (Get-SqlPostflight $protectedEf.BatchCount)
    Assert-ProtectedMigrationSql $finalSql $protectedEf.BatchCount $protectedEf.DirectTransactionBatchCount $protectedEf.DynamicBatchCount
    [IO.File]::WriteAllText((Join-Path $releaseStaging $sqlName), $finalSql, [Text.UTF8Encoding]::new($false))
    $stages.Add([ordered]@{ name = 'sql_generate_static_validation'; result = 'passed' })

    $artifacts = @()
    foreach ($name in @($backendName, $frontendName, $sqlName)) {
        $file = Get-Item -LiteralPath (Join-Path $releaseStaging $name)
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $artifacts += [ordered]@{ name = $name; size_bytes = $file.Length; sha256 = $hash }
    }
    $versions = [ordered]@{
        dotnet = Get-ToolVersion dotnet @('--version')
        node = Get-ToolVersion node @('--version')
        npm = Get-ToolVersion npm @('--version')
    }
    $manifest = [ordered]@{
        commit = [ordered]@{ full = $commit; short = $shortSha }
        created_utc = [DateTime]::UtcNow.ToString('o')
        branch = $branch
        tool_versions = $versions
        frontend_public_url = $siteUrl
        api_public_url = $apiUrl
        frontend_validation = $frontendValidation
        migrations = [ordered]@{ from = $StartMigration; to = $EndMigration }
        sql = [ordered]@{
            proteccion_fail_safe_entre_lotes = $true
            lotes_ef_protegidos = $protectedEf.BatchCount
            lotes_control_transaccion_directos = $protectedEf.DirectTransactionBatchCount
            lotes_ef_dinamicos = $protectedEf.DynamicBatchCount
            centinela = 'tabla temporal de sesion con ordinal secuencial y marcador de fallo'
            postflight_compilacion_diferida = $true
            postflight_exige_secuencia_completa = $true
            commit_exterior_despues_de_secuencia = $true
        }
        artifacts = $artifacts
        exclusions = [ordered]@{ backend = $BackendExclusions; frontend = $FrontendExclusions }
        commands = $commands
        stages = $stages
    }
    [IO.File]::WriteAllText((Join-Path $releaseStaging 'manifest.json'), ($manifest | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    $sumLines = $artifacts | ForEach-Object { "$($_.sha256)  $($_.name)" }
    [IO.File]::WriteAllLines((Join-Path $releaseStaging 'SHA256SUMS.txt'), $sumLines, [Text.UTF8Encoding]::new($false))
    $preserve = @('Backend:', 'appsettings.json', 'web.config', 'logs', '', 'Frontend:', 'App_Data', '.user.ini', 'web.config')
    [IO.File]::WriteAllLines((Join-Path $releaseStaging 'PRESERVE_ON_SERVER.txt'), $preserve, [Text.UTF8Encoding]::new($false))

    $releaseNames = @($backendName, $frontendName, $sqlName, 'manifest.json', 'SHA256SUMS.txt', 'PRESERVE_ON_SERVER.txt')
    foreach ($name in $releaseNames) { Assert-RequiredFile $releaseStaging $name }
    foreach ($artifact in $artifacts) {
        $actualHash = (Get-FileHash -LiteralPath (Join-Path $releaseStaging $artifact.name) -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -cne $artifact.sha256) { throw "Hash final inconsistente para $($artifact.name)." }
        if ($sumLines -notcontains "$($artifact.sha256)  $($artifact.name)") { throw "Checksum final ausente para $($artifact.name)." }
    }
    $manifestCheck = Get-Content -LiteralPath (Join-Path $releaseStaging 'manifest.json') -Raw | ConvertFrom-Json
    if ($manifestCheck.commit.full -cne $commit -or $manifestCheck.api_public_url -cne $apiUrl) { throw 'El manifiesto final no cumple los contratos de commit y API.' }
    $stages.Add([ordered]@{ name = 'final_artifact_validation'; result = 'passed' })

    # La comprobacion global de colisiones sucede antes del primer movimiento.
    foreach ($name in $releaseNames) {
        if (Test-Path -LiteralPath (Join-Path $outputPath $name)) { throw "Colision de publicacion final: $name" }
    }
    $movedByThisRun = New-Object System.Collections.Generic.List[string]
    try {
        foreach ($name in $releaseNames) {
            $destination = Join-Path $outputPath $name
            Move-Item -LiteralPath (Join-Path $releaseStaging $name) -Destination $destination
            $movedByThisRun.Add($destination)
        }
    } catch {
        foreach ($published in $movedByThisRun) {
            if (Test-Path -LiteralPath $published -PathType Leaf) { Remove-Item -LiteralPath $published -Force }
        }
        throw "Fallo la publicacion final; se revirtieron exclusivamente los archivos de esta ejecucion. $($_.Exception.Message)"
    }
    Write-Host "Release preparada en: $outputPath"
} finally {
    foreach ($name in $previousViteEnvironment.Keys) { [Environment]::SetEnvironmentVariable($name, $previousViteEnvironment[$name], 'Process') }
    if (Test-Path -LiteralPath $stagingRoot) { Remove-Item -LiteralPath $stagingRoot -Recurse -Force }
    if (-not $outputAlreadyExists -and (Test-Path -LiteralPath $outputPath -PathType Container) -and @(Get-ChildItem -LiteralPath $outputPath -Force).Count -eq 0) { Remove-Item -LiteralPath $outputPath -Force }
}
