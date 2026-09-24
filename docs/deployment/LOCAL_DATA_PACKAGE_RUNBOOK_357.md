# Prompt 357 — preparación local controlada del paquete

## Alcance y resultado

`Export-JemNexusLocalDataPackage.ps1` prepara, en Windows PowerShell 5.1, un paquete de **solo lectura** desde `(localdb)\MSSQLLocalDB`, base `JemNexus_Local`, esquema `dbo`. No acepta una conexión configurable, no se conecta a producción, no contiene modo `Apply`, no genera SQL y no modifica LocalDB.

El paquete contiene JSON determinista para 17 tablas de aplicación y copias de los 92 archivos de imágenes y 85 fichas referenciados. Conserva todas las columnas, PK y FK tal como están en la instantánea de lectura. Excluye `AppRefreshTokens`, `__EFMigrationsHistory` y cualquier archivo no referenciado, incluidas las dos imágenes huérfanas inventariadas.

Un resultado `PACKAGE_PREPARED_LOCAL_ONLY` significa solamente que se preparó y verificó un paquete local. **No autoriza ni implementa una aplicación en producción.** El diseño posterior del importador deberá volver a comprobar producción, backups, ventana, drift, rollback e invalidación de las sesiones productivas.

## Validación previa sin efectos

Abra **Windows PowerShell 5.1** desde el checkout y use una ruta privada fuera del repositorio. `PlanOnly` valida los parámetros fijos y el destino, pero no exige que este exista, no conecta, no lee archivos y no escribe nada:

```powershell
$Repo = 'C:\src\web-ventas-generica'
$PrivateRoot = 'D:\JemNexus-private-transfer'
& "$Repo\tools\deployment\Export-JemNexusLocalDataPackage.ps1" `
  -Mode PlanOnly `
  -OutputRoot $PrivateRoot
if ($LASTEXITCODE -ne 0) { throw "PlanOnly fallo: $LASTEXITCODE" }
```

Compruebe manualmente que `$PrivateRoot` no existe si no existía antes. No redirija la salida a un archivo dentro del repositorio.

## Ensayo explícito de exportación local

Use el JSON real producido previamente por `InventoryLocal`. Pase las raíces físicas verificadas **por separado**: la raíz de imágenes que contiene `product-images` y la raíz efectiva que contiene directamente las fichas cuyos nombres aparecen como `StorageKey`. No deduzca una de la otra.

Antes de ejecutar `ExportLocal`, detenga temporalmente el backend local y manténgalo detenido durante toda la captura SQL. La base real tiene `ALLOW_SNAPSHOT_ISOLATION=OFF` y `READ_COMMITTED_SNAPSHOT=1`: esta última opción solo cambia el comportamiento de `READ COMMITTED` y **no** permite abrir una transacción `Snapshot`. Por eso el exportador usa una única transacción `Serializable`; esta puede bloquear escrituras locales mientras captura metadata, filas, conteos y relaciones. Vuelva a iniciar el backend local únicamente cuando el comando haya terminado, ya sea con éxito o con error. La herramienta no ejecuta `ALTER DATABASE` ni cambia esas opciones.

```powershell
$Repo = 'C:\src\web-ventas-generica'
$PrivateRoot = 'D:\JemNexus-private-transfer'
$Inventory = 'D:\JemNexus-private-evidence\jemnexus-local-sanitized-inventory.json'
$ImageRoot = 'C:\ruta-real-imagenes'
$SheetRoot = 'C:\ruta-real-fichas'

& "$Repo\tools\deployment\Export-JemNexusLocalDataPackage.ps1" `
  -Mode ExportLocal `
  -InventoryPath $Inventory `
  -ImageUploadsRoot $ImageRoot `
  -TechnicalSheetsRoot $SheetRoot `
  -OutputRoot $PrivateRoot
if ($LASTEXITCODE -ne 0) { throw "ExportLocal fallo: $LASTEXITCODE" }
```

La herramienta abre una única transacción `Serializable`; todos los `SqlCommand` y el `SqlDataAdapter` usados para metadata, identidad, filas y relaciones reciben explícitamente esa misma conexión y transacción. Obtiene columnas y PK desde metadata, exporta ordenado por PK, compara los conteos con el inventario confirmado y comprueba que las FK estén habilitadas y confiables. Después confirma y libera la transacción **antes** de leer, copiar o calcular hashes de multimedia, por lo que no conserva bloqueos SQL durante el trabajo de archivos. Luego valida rutas, archivos y tamaños, calcula SHA-256 y relee el paquete. Trabaja primero en `.staging-*`, con herencia ACL deshabilitada y acceso para el usuario actual; solo publica el nombre final mediante un rename después de todas las verificaciones. Un timeout, bloqueo u otro error SQL elimina únicamente el staging de esa ejecución y no deja un directorio de paquete final.

## Verificación privada posterior

No abra, imprima, adjunte ni registre los JSON: pueden contener hashes de contraseña y datos personales. Inspeccione únicamente estructura, conteos y hashes en una consola privada:

```powershell
$Package = Get-ChildItem -LiteralPath $PrivateRoot -Directory -Filter 'jemnexus-local-data-package-*' |
  Sort-Object Name -Descending | Select-Object -First 1
$Manifest = Get-Content -LiteralPath (Join-Path $Package.FullName 'manifest.json') -Raw | ConvertFrom-Json

if ($Manifest.status -ne 'PREPARED_LOCAL_NOT_AUTHORIZED_FOR_PRODUCTION_APPLY') { throw 'Estado inesperado' }
if ($Manifest.tables.count -ne 17 -or $Manifest.media.count -ne 177) { throw 'Conteos inesperados' }
if ($Manifest.exclusions.refreshTokenRowsIncluded -ne 0 -or $Manifest.exclusions.orphanImageFilesIncluded -ne 0) { throw 'Exclusion invalida' }

foreach ($Property in $Manifest.tables.sha256.PSObject.Properties) {
  $Path = Join-Path $Package.FullName ("data\{0}.json" -f $Property.Name)
  if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $Property.Value) { throw "Hash de tabla invalido: $($Property.Name)" }
}
foreach ($File in $Manifest.media.files) {
  $Path = Join-Path $Package.FullName ($File.packagePath -replace '/', '\')
  if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $File.sha256) { throw 'Hash multimedia invalido' }
}
'PACKAGE_VERIFIED_LOCAL_ONLY'
```

Mantenga el directorio en almacenamiento cifrado, con ACL exclusiva, fuera del checkout y de carpetas sincronizadas. Transfiéralo solo por un canal privado aprobado. No lo comprima ni copie al repositorio como parte de este procedimiento. Si cambia LocalDB o cualquier archivo fuente, descarte el paquete completo y genere otro: `source.inventorySha256`, los conteos y cada SHA-256 sirven para detectar diferencias, no para aprobar un import.
