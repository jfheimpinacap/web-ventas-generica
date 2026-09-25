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

`PlanOnly` retorna antes de leer rutas, abrir conexiones, generar scripts o escribir. `Prepare` no acepta servidor, base ni connection string. El orden fail-closed es: validar íntegramente el archivo seguro y legible con todos los campos que consume el inspector; comprobar los 22 fuentes canónicos, proyecto, inspector, `dotnet` y Windows PowerShell; generar el script y comprobar que contiene los 22 IDs; y **solo entonces** abrir `master`. Allí comprueba LocalDB e instancia efectiva, aborta si la base fija ya existe y únicamente después la crea. Ejecuta el SQL ya generado en una única sesión impersonada cuyo esquema predeterminado es `jemnexusb_api`, verifica los 22 IDs y los 19 objetos, y solo después crea el marcador con alcance de base. Finalmente ejecuta el inspector 364; únicamente `PREPARED_AND_INSPECTED` es éxito. Todo fallo es `NO-GO`; una base parcialmente creada queda intacta para diagnóstico manual. No existe `DROP`, restauración ni limpieza automática.

Antes y después, confirmar que no se configuraron variables para producción y conservar solo las salidas sanitizadas. No abrir el paquete privado v3 ni ejecutar importación. Tras el comando, ejecutar nuevamente `InspectDisposable` de forma independiente y revisar que sea `READY_FOR_DISPOSABLE_REHEARSAL`; esto todavía no autoriza Apply.

## Baseline productivo, procedimiento separado

`Capture-JemNexusProductionSchemaBaseline.sql` se entrega para revisión DBA. Se ejecuta **solo** dentro de una sesión read-only ya autenticada por el operador en producción. Primero exige `DB_NAME() = jemnexusb_prod` y después comprueba en `sys.databases` que `ALLOW_SNAPSHOT_ISOLATION` está realmente `ON`, antes de seleccionar ese aislamiento o iniciar la transacción. `READ_COMMITTED_SNAPSHOT` no satisface ni sustituye esta guarda. Si está deshabilitado, termina con el NO-GO accionable `SNAPSHOT_ISOLATION_NOT_ENABLED_ENABLE_ALLOW_SNAPSHOT_ISOLATION_BEFORE_CAPTURE`, sin cambiar opciones, iniciar la captura ni emitir la cabecera de un baseline. No intenta habilitarlo, evitando el impacto operativo y bloqueos que supondría hacerlo automáticamente. Con la opción ya habilitada, usa una transacción snapshot consistente que revierte y se limita a metadatos/agregados. Sus result sets deben pasarse por el mismo algoritmo canónico del inspector (UTF-8, `NULL` como `<NULL>`, columnas en el orden declarado, filas ordenadas ordinalmente) para construir exactamente los campos documentados en 364. No contiene cuentas, contraseñas ni filas de negocio.

El preparador LocalDB jamás carga ni ejecuta ese SQL ni abre producción. El JSON resultante es evidencia fechada: **no sustituye** el control de drift inmediatamente anterior a un eventual Apply. Este trabajo no implementa Apply, las 429 filas, multimedia, restauración o borrado de bases.
