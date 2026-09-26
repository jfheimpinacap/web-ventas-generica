# Preparación controlada de LocalDB desechable (tarea 365)

## Contrato confirmado

El inspector 364 fija `(localdb)\MSSQLLocalDB`, `JemNexus_DisposableRehearsal_364`, el esquema efectivo `jemnexusb_api` y el marcador de base `JemNexus.DisposableRehearsalMarker=TASK-364|READONLY-PREFLIGHT|DISPOSABLE`. Su oráculo exige los 22 IDs que enumera el script, las 17 tablas importables y huellas SHA-256 de columnas, PK, FK, índices, checks, identities y `SellerCodeSequence`. No se fijan valores de huella en el repositorio: proceden únicamente del baseline productivo sanitizado y el inspector vuelve a calcularlos.

Se incorpora como evidencia aportada por el usuario la consulta productiva: las 17 tablas, `__EFMigrationsHistory` y `SellerCodeSequence` están en `jemnexusb_api` (**19/19 MATCH**). Es evidencia fechada/externa, no una consulta repetida ni autorización de escritura.

## Ejecución Windows (no ejecutada aquí)

Desde la raíz del checkout limpio, en **Windows PowerShell 5.1**, con SDK/herramientas EF ya restaurados y el baseline revisado fuera del repositorio:

```powershell
python -m unittest tools.deployment.tests.test_disposable_rehearsal_preparation tools.deployment.tests.test_disposable_rehearsal_preflight
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\deployment\Prepare-JemNexusDisposableRehearsal.ps1 -Mode PlanOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\deployment\Prepare-JemNexusDisposableRehearsal.ps1 -Mode Prepare -ProductionBaselinePath 'C:\JemNexus-Evidence\production-schema-baseline.json'
```

`PlanOnly` retorna antes de leer rutas, abrir conexiones, generar scripts o escribir. `Prepare` no acepta servidor, base ni connection string. El orden fail-closed es: validar íntegramente el archivo seguro y legible con todos los campos que consume el inspector; comprobar los 22 fuentes canónicos, proyecto, inspector, `dotnet` y Windows PowerShell; generar el script y comprobar que contiene los 22 IDs; y **solo entonces** abrir `master`. Allí exige que `IsLocalDB` sea el entero `1` (un valor `NULL`, no convertible o diferente es rechazo), comprueba la instancia efectiva, aborta si la base fija ya existe y únicamente después la crea.

Dentro de esa base fija —nunca en servidor, `JemNexus_Local` ni producción— crea el usuario `WITHOUT LOGIN` y le concede solo `CREATE TABLE` y `CREATE SEQUENCE` en la base, más `ALTER`, `REFERENCES`, `SELECT`, `INSERT` y `UPDATE` sobre `jemnexusb_api`. Es el conjunto que requieren las 22 migraciones auditadas: tablas/secuencia, cambios de objetos e índices/constraints/FK, y lecturas/inserciones/actualizaciones de datos y del historial EF. Ya impersonado, verifica cada permiso efectivo **antes del primer lote EF**; `IMPERSONATED_MIGRATION_PERMISSIONS_INSUFFICIENT` aborta sin ejecutar ningún cuerpo de migración. Ejecuta después el SQL ya generado en esa única sesión, verifica los 22 IDs y los 19 objetos, y solo entonces crea el marcador con alcance de base. Finalmente ejecuta el inspector 364; únicamente `PREPARED_AND_INSPECTED` es éxito. Todo fallo es `NO-GO`; una base parcialmente creada queda intacta para diagnóstico manual. No existe `DROP`, restauración ni limpieza automática.

Antes y después, confirmar que no se configuraron variables para producción y conservar solo las salidas sanitizadas. No abrir el paquete privado v3 ni ejecutar importación. Tras el comando, ejecutar nuevamente `InspectDisposable` de forma independiente y revisar que sea `READY_FOR_DISPOSABLE_REHEARSAL`; esto todavía no autoriza Apply.

## Baseline productivo, procedimiento separado

La configuración real confirmada de `jemnexusb_prod` es `SnapshotIsolation = OFF`, `ReadCommittedSnapshot = 0` y `@@TRANCOUNT = 0`; la consulta que lo confirmó fue de solo lectura. **No se autoriza cambiar esas opciones.** La captura se adaptó a ese contrato: no usa snapshot ni serializable, no abre transacción y no toma bloqueos explícitos. Cada consulta corre en `READ COMMITTED` con `LOCK_TIMEOUT 15000`; cualquier timeout/error hace `NO-GO`. El coste es deliberadamente acotado a catálogos, los 22 IDs de migración y agregados, sin filas personales.

`Capture-JemNexusProductionSchemaBaseline.ps1` es el orquestador obligatorio. Abre **dos conexiones independientes**, y en cada una ejecuta la consulta completa. Antes de metadata, el SQL exige por igualdad ordinal `DB_NAME() = jemnexusb_prod`, el `SERVERPROPERTY('ServerName')` esperado por el DBA y el principal efectivo de base `USER_NAME() = jemnexusb_api`, además de las dos opciones `OFF` y `@@TRANCOUNT = 0`. Cada observación contiene exactamente los 22 IDs y las siete tablas de metadata. El orquestador aplica exactamente el algoritmo del inspector: columnas en el orden contractual, `NULL` como `<NULL>`, CR eliminado, LF convertido en espacio, líneas ordenadas con comparación case-sensitive, unión por LF y SHA-256 de UTF-8.

Solo si ambas observaciones completas tienen **los mismos 22 IDs y las mismas siete huellas**, el orquestador escribe el JSON mediante archivo temporal y rename y muestra `BASELINE_CAPTURE_VERIFIED_AND_SAVED`. La ruta final debe no existir (un baseline anterior se archiva fuera de esa ruta antes de empezar). Un cambio entre pasadas, migración ausente/adicional, identidad inesperada, timeout, error o result set parcial produce `NO-GO`, cierra conexión, elimina el temporal y no deja baseline utilizable. No se debe convertir ni copiar manualmente una cuadrícula de SSMS: `OBSERVATION_COMPLETE` solo completa una pasada y nunca equivale a un baseline.

### Comandos exactos en estación Windows aprobada

En **Windows PowerShell 5.1**, desde la raíz del checkout revisado, cree previamente una carpeta privada con ACL limitada. Sustituya el nombre por el valor exacto que el DBA haya confirmado; no use alias, comodines ni `REPLACE_ME`:

La evidencia SSMS solo demuestra el principal productivo `jemnexusb_api`; no demuestra que la cuenta Windows local pueda autenticarse. Por ello se debe elegir explícitamente un modo. El modo normal solicita localmente una credencial SQL mediante el cuadro seguro de `Get-Credential`; la contraseña permanece como `SecureString`, se marca como solo lectura antes de construir `SqlCredential`, se reutiliza únicamente en memoria para las dos conexiones y se libera al finalizar. Cancelar el diálogo aborta antes de construir o abrir una conexión:

```powershell
$server = 'NOMBRE-SQL-PRODUCTIVO-EXACTO'
$evidence = 'C:\JemNexus-Evidence-Private\production-schema-baseline.json'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\deployment\Capture-JemNexusProductionSchemaBaseline.ps1 -ExpectedProductionServer $server -OutputPath $evidence -Authentication SqlCredential
if ($LASTEXITCODE -ne 0) { throw 'NO-GO: baseline no creado' }
Get-FileHash -LiteralPath $evidence -Algorithm SHA256 | Format-List Algorithm,Hash
```

No escriba la contraseña en el comando, la consola, variables de entorno ni archivos. Si el DBA confirmó previamente que la identidad Windows del proceso tiene acceso y se desea usarla de forma explícita, el único comando alternativo es el siguiente; este modo no solicita credenciales y no intenta fallback a SQL:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\deployment\Capture-JemNexusProductionSchemaBaseline.ps1 -ExpectedProductionServer $server -OutputPath $evidence -Authentication Integrated
```

Ambos modos mantienen `Encrypt=True` y `TrustServerCertificate=False`. Un error de autenticación, cadena de confianza, nombre del certificado o conexión termina con el diagnóstico sanitizado `AUTHENTICATION_OR_TLS_CONNECTION_FAILED`: es **NO-GO**. No se permite activar `TrustServerCertificate`, deshabilitar cifrado ni cambiar automáticamente de autenticación. `ApplicationIntent=ReadOnly` expresa intención al servidor, pero **no es un permiso ni una barrera contra escrituras**; la protección de la herramienta es que su superficie ejecutable está fijada al SQL de lectura auditado, sin aceptar consultas arbitrarias.

Para revisión DBA en **SSMS**, active `Query > SQLCMD Mode`, conéctese explícitamente a `jemnexusb_prod`, no abra una transacción, anteponga esta línea al archivo SQL y ejecute una sola observación:

```sql
:setvar ExpectedProductionServer "NOMBRE-SQL-PRODUCTIVO-EXACTO"
```

El resultado SSMS es solo diagnóstico: debe terminar en `OBSERVATION_COMPLETE`, no se guarda como baseline y no sustituye las dos conexiones del orquestador. No use “Results to File” como mecanismo de conversión. Guarde el JSON y su hash únicamente en la carpeta privada aprobada; registre en el ticket privado hora UTC, operador, equipo controlado, servidor esperado, estado final y SHA-256. No pegue en chat grandes result sets, rutas internas, nombres reales de host, cadenas, usuarios ni ninguna evidencia sensible.

Dos observaciones iguales son evidencia suficiente para diseñar y ensayar en LocalDB; **no garantizan el estado productivo futuro**. Debe repetirse el control de drift inmediatamente antes de cualquier eventual Apply. Este cambio no implementa ni autoriza Apply.

El preparador LocalDB jamás carga ni ejecuta ese SQL ni abre producción. El JSON resultante es evidencia fechada: **no sustituye** el control de drift inmediatamente anterior a un eventual Apply. Este trabajo no implementa Apply, las 429 filas, multimedia, restauración o borrado de bases.
