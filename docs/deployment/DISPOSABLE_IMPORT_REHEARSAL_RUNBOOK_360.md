# Tarea 360 — verificación offline y diseño del ensayo desechable

## Corrección 361 — regeneración obligatoria del paquete

El paquete ya publicado bajo `C:\Users\Franz\JemNexus-private-transfer-20260924-v2` queda **rechazado para importar**: cuatro archivos correspondientes a tablas con cero filas no contienen JSON válido. Debe conservarse intacto como evidencia privada; no se repara en el sitio, no se copia al repositorio y no se solicita ni divulga su contenido.

La causa se comprobó en el camino real del exportador. `Convert-TableRows` ya materializaba un `object[]`, pero `Write-Json` enviaba ese valor por el pipeline a `ConvertTo-Json`. Windows PowerShell enumera el array en ese límite: con cero filas no invoca al cmdlet y se escribe un archivo vacío; con una fila entrega un objeto escalar y se pierde el array superior; con varias entrega la colección de objetos que `ConvertTo-Json` sí representa como array, en su orden original. La corrección compartida usa `ConvertTo-Json -InputObject` sobre el `object[]`: así produce respectivamente `[]`, `[ {...} ]` y un array ordenado de varios registros. Antes del rename, el exportador relee desde disco los 17 archivos, exige sintaxis JSON, array superior y la cardinalidad capturada, y además conserva la comprobación SHA-256. Un fallo sigue eliminando exclusivamente el `.staging-*` de esa ejecución.

Después del merge, ejecute primero el harness que usa exactamente las funciones compartidas por el exportador (no una reproducción):

```powershell
$Repo = 'C:\src\web-ventas-generica'
& "$Repo\tools\deployment\tests\Test-LocalDataPackageTableJson.WindowsPowerShell.ps1"
if (-not $?) { throw 'Harness de JSON de tablas fallo' }
```

Debe ejecutarse con **Windows PowerShell 5.1** y terminar con `WINDOWS_POWERSHELL_5_1_TABLE_JSON_TEST_OK`. Solo entonces repita `ExportLocal` con los parámetros privados ya validados, pero con un `OutputRoot` nuevo y distinto:

```powershell
$NewPrivateRoot = 'C:\Users\Franz\JemNexus-private-transfer-20260924-v3'
& "$Repo\tools\deployment\Export-JemNexusLocalDataPackage.ps1" `
  -Mode ExportLocal `
  -InventoryPath $Inventory `
  -ImageUploadsRoot $ImageRoot `
  -TechnicalSheetsRoot $SheetRoot `
  -OutputRoot $NewPrivateRoot
if (-not $?) { throw 'Nueva exportacion local fallo' }

$NewPackage = Get-ChildItem -LiteralPath $NewPrivateRoot -Directory -Filter 'jemnexus-local-data-package-*' |
  Sort-Object Name -Descending | Select-Object -First 1
py -3 "$Repo\tools\deployment\verify_local_data_package.py" --mode VerifyPackage --package $NewPackage.FullName
if ($LASTEXITCODE -ne 0) { throw 'Verificacion del paquete v3 fallo' }
```

No ejecute `VerifyPackage` como aprobación del paquete `v2`: el único candidato nuevo será el generado en `v3` después de que pase el harness.

## Estado y límite de seguridad

El paquete privado confirmado en Windows **no forma parte del repositorio** y no debe adjuntarse, copiarse ni mostrarse. Esta entrega implementa solamente un verificador offline y un plan determinista. No contiene cliente SQL, cadena de conexión, credenciales, SQL de escritura, copia/promoción de multimedia ni modo `Apply`. Por ello no puede modificar LocalDB, una base remota ni producción.

La sustitución de las 8 `QuoteRequests` productivas por las 0 locales, de las cuentas soporte/vendedor por las 3 locales, y la incorporación de las 9 cotizaciones y sus relaciones ya están autorizadas. `AppRefreshTokens` queda excluida. No son decisiones pendientes; el drift inmediatamente anterior a una futura aplicación sí es condición de aborto.

## Resultado de la auditoría estática

### Hechos demostrados por artefactos versionados

* El exportador fija `(localdb)\MSSQLLocalDB`, `JemNexus_Local` y `dbo`, abre una transacción `Serializable`, ordena cada tabla por su PK y exporta 17 tablas. Excluye `AppRefreshTokens` y `__EFMigrationsHistory`; publica solo después de verificar hashes y 177 medios.
* El manifiesto confirmado corresponde a 3 usuarios, 58 permisos, 9 cotizaciones, 9 ítems, 1 contador, 8 registros de idempotencia, 0 solicitudes y los restantes conteos que suman 429 filas. Contiene 92 imágenes y 85 fichas. La ejecución Windows y esos conteos son evidencia operativa aportada, no repetida aquí.
* El modelo vigente define PK simples salvo `AppUserPermissions` y `CommercialQuoteIssueIdempotencyRecords` (compuestas), y `CommercialQuoteFolioCounters.Year` (no identity). Las relaciones de cotizaciones exigen seller y emisor; ítems dependen de cabecera; el producto de un ítem es anulable. `SellerCodeSequence` es una secuencia, no una tabla.
* Hay 22 archivos de migración aplicables (sin contar designers/snapshot). Las migraciones vigentes agregan permisos granulares e `IssuedBy`; la migración de preservación de cotizaciones cambia la semántica al eliminar productos.
* Las imágenes se sirven desde la raíz configurable de uploads bajo `product-images/<ProductId>/...`; las fichas usan la raíz de contenido bajo `uploads/technical-sheets/<StorageKey>`. Una transacción SQL no abarca ninguno de esos archivos.

### Supuestos que requieren ensayo dinámico en Windows

* Que el nuevo paquete privado `v3` pasa todos los hashes, estructura, IDs y relaciones del verificador de esta entrega; el paquete `v2` está rechazado.
* Que un SQL Server de ensayo tiene exactamente las 22 migraciones, el esquema, columnas, tipos, nulabilidad, PK, identity, FK/delete actions, checks, índices/filtros, secuencia, collation y permisos esperados.
* Que la instancia es local, la base es nueva y desechable, no es `JemNexus_Local` ni `jemnexusb_prod`, y ningún alias/DNS/linked server conduce a un host remoto. Nada en esta entrega intenta demostrarlo conectándose.
* Que el baseline clonado que representa producción todavía tiene exactamente 8 solicitudes y el estado inventariado de cuentas/cotizaciones; deberá medirse otra vez justo antes de cualquier aplicación futura.
* Que las dos raíces multimedia efectivas tienen ACL, capacidad, persistencia y mecanismo de snapshot/rename/rollback adecuados, y que los backups SQL y de ambas raíces restauran correctamente.
* Que identities, próximo valor de `SellerCodeSequence`, folios y permisos funcionan después de una carga. El chequeo estático no puede probar el siguiente valor generado ni un login de recuperación.

## Verificador offline implementado

`verify_local_data_package.py` usa únicamente la biblioteca estándar y dispone de dos modos:

* `PlanOnly`: no acepta ruta de paquete; no conecta, no lee y no escribe. Emite solo conteos, el hash del orden lógico y bloqueos.
* `VerifyPackage`: requiere una ruta absoluta y lee el paquete sin modificarlo. Exige las claves exactas del manifiesto, identidad local fija, las exclusiones, 17 archivos JSON, 429 filas, PK únicas, FK/auditoría válidas, 177 entradas (92+85), tamaño y SHA-256. Rechaza JSON inválido/no finito, claves JSON duplicadas, estructuras inesperadas, conteos o hashes distintos, rutas absolutas/externas/traversal, separadores no canónicos, duplicados, archivos faltantes o extra, y enlaces simbólicos/reparse points que Python exponga como enlaces.

La salida JSON está deliberadamente limitada a `status`, `counts`, `hashes` y `blockers`. Los errores son códigos constantes: nunca imprime filas, IDs, rutas, nombres, datos personales, contraseñas ni hashes de contraseña. No redirija la salida a un lugar público aunque sea sanitizada.

El orden lógico cuyo hash entrega el programa es: usuarios; permisos; marcas/categorías/proveedores/fichas; productos; imágenes/especificaciones/promociones/home; clientes; solicitudes (conjunto vacío); cotizaciones; ítems/contador/idempotencia. El retiro de un destino futuro debe ejecutarse en el orden inverso calculado desde FK, nunca deshabilitando constraints.

## Comandos de Windows posteriores

Use una consola privada y una ruta fuera del checkout. Estos comandos no conectan a SQL Server:

```powershell
$Repo = 'C:\src\web-ventas-generica'
$Package = $NewPackage.FullName # paquete nuevo bajo JemNexus-private-transfer-20260924-v3

# Debe funcionar aunque $Package no exista, porque PlanOnly ni siquiera acepta la ruta.
py -3 "$Repo\tools\deployment\verify_local_data_package.py" --mode PlanOnly
if ($LASTEXITCODE -ne 0) { throw 'PlanOnly fallo' }

# Verificación privada, offline y de solo lectura.
py -3 "$Repo\tools\deployment\verify_local_data_package.py" --mode VerifyPackage --package $Package
if ($LASTEXITCODE -ne 0) { throw 'Verificacion offline fallo' }
```

Éxito offline requiere `VERIFIED_OFFLINE_PLAN_ONLY`, `tables=17`, `rows=429`, `media=177` y cuatro SHA-256, junto con los bloqueos esperados que recuerdan que no existe escritura. Cualquier otro bloqueo aborta; no se debe abrir ni imprimir un archivo de datos para diagnosticarlo.

## Diseño del futuro ensayo (no implementado deliberadamente)

Una tarea posterior y separada podrá implementar escritura **solo** después de crear un guard independiente y probado que, dentro de la misma conexión y antes de toda escritura:

1. Rechace cualquier parámetro de servidor, URL o credencial. La configuración compilada debe permitir únicamente una instancia local explícita y un nombre de base generado con prefijo exclusivo, por ejemplo `JemNexus_DisposableRehearsal_`; debe rechazar por comparación ordinal `JemNexus_Local`, `jemnexusb_prod` y todo nombre que no tenga ese prefijo.
2. Compruebe mediante SQL que `SERVERPROPERTY('IsLocalDB') = 1`, que el nombre efectivo coincide exactamente con el nombre aleatorio recién creado, que no es réplica, que no hay linked servers y que el esquema de ensayo esperado existe. También debe usar un marcador aleatorio de desechabilidad creado junto con la base y comprobado en la misma transacción/sesión.
3. Compruebe schema fingerprint, 22 migraciones exactas y metadata completa contra una especificación revisada. Si no puede demostrar cualquiera de esos hechos, termina antes de `BEGIN TRANSACTION` de escritura. En particular, un nombre parecido no demuestra desechabilidad.
4. Capture el baseline y aborte ante cualquier diferencia: 8 solicitudes, cuentas esperadas, cotizaciones esperadas, filas por tabla, constraints confiables, claves naturales, espacio, backups restaurables y hashes de medios staged.

La implementación de escritura se detiene en esta tarea porque el checkout Linux y la prohibición de ejecutar SQL Server no permiten demostrar esa identidad con seguridad. No se añade un interruptor oculto ni una opción productiva.

### Fidelidad del ensayo futuro

* Insertar valores explícitos bajo `IDENTITY_INSERT` una tabla identity a la vez y verificar mínimos/máximos/conjuntos de PK; resembrar cada identity al máximo correcto. No asignar IDs nuevos.
* Conservar literalmente timestamps y FK de auditoría. Cargar primero los tres usuarios y luego las 58 concesiones; no recalcular ni sustituir autores. Verificar permisos efectivos positivos y negativos.
* No modificar `__EFMigrationsHistory` ni ejecutar migraciones. Verificar sus 22 IDs antes y después. Conservar índices, checks, FK habilitadas/confiables y grants/default schema del principal de aplicación.
* Conservar las 9 cotizaciones, 9 ítems, 8 idempotencias, snapshots, importes, estado, folio/año/secuencia y el contador. Ajustar y probar `SellerCodeSequence`; simular el próximo folio dentro del ensayo y revertir esa simulación.
* Mantener `AppRefreshTokens` vacío. El reemplazo 8→0 de solicitudes y cuentas→3 se ejecuta solo si el baseline inmediato coincide; drift aborta, no reabre la autorización.

### Coordinación SQL y multimedia

1. Con mantenimiento activo, verificar el paquete; copiar cada conjunto a dos directorios staging separados y recalcular hashes.
2. Crear snapshots/backups restaurados y probados del SQL inicial y de ambas raíces. Preparar destinos versionados; no sobrescribir el live.
3. Promover medios mediante rename/swap reversible y registrar solo hashes/conteos. Después abrir la transacción SQL, cargar/verificar y confirmar.
4. Si falla antes del commit, hacer rollback SQL y restaurar el puntero/directorio multimedia anterior. Si falla después del commit pero antes de tráfico, mantener mantenimiento y restaurar **coordinadamente** SQL y ambos conjuntos de archivos. Nunca asumir que el rollback SQL revierte archivos.
5. Abrir tráfico solo tras hashes completos, FK/unique/check, identities/secuencia, 22 migraciones, folios, permisos/login controlado y lecturas HTTP de medios. Descartar la base y credenciales del ensayo al terminar.

Son criterios de aborto: identidad local/desechable no demostrada, alias o servidor remoto, nombre prohibido, drift, esquema/migraciones/permisos distintos, hash/conteo/ruta/enlace inesperado, FK o índice inválido, backup sin restore probado, promoción no reversible, falta de espacio/ACL, o imposibilidad de recuperar conjuntamente DB y archivos.
