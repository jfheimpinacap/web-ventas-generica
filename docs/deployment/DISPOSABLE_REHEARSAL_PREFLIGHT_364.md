# Preflight de solo lectura para el ensayo desechable (tarea 364)

## Alcance y decisión

Esta entrega implementa **únicamente** el guard de lectura previo a un futuro ensayo. No contiene importación, modo `Apply`, SQL de escritura, copia multimedia, borrado ni acceso productivo. El único éxito es `READY_FOR_DISPOSABLE_REHEARSAL`; significa que la base desechable puede pasar a revisión para un ensayo posterior y **no autoriza producción**.

El nombre compilado y exclusivo es `JemNexus_DisposableRehearsal_364`. La instancia compilada es exactamente `(localdb)\MSSQLLocalDB`, el esquema fijo de aplicación es `jemnexusb_api` y se usa autenticación integrada con `ApplicationIntent=ReadOnly`. La herramienta no acepta servidor, base ni cadena de conexión. Rechaza por identidad efectiva tanto `JemNexus_Local` como `jemnexusb_prod`, aunque un operador intente redirigir la conexión mediante configuración externa.

La ubicación se decidió por evidencia offline y sin normalizar esquemas: las migraciones y el modelo usan nombres no cualificados; el procedimiento productivo documentado exige que el esquema predeterminado sea `jemnexusb_api` precisamente para que esos nombres resuelvan allí. Por tanto, las 17 tablas de aplicación, `__EFMigrationsHistory` y `SellerCodeSequence` tienen como ubicación efectiva `jemnexusb_api`. El marcador no es un objeto de schema: su contrato y la consulta `fn_listextendedproperty(..., DEFAULT, ...)` lo sitúan como propiedad extendida de la **base de datos**. Estas cuatro ubicaciones son constantes compiladas y se informan por separado.

La auditoría estática partió del plan 351, el preflight 352, el runbook/verificación offline 360, el runbook del exportador, las 22 migraciones (desde `20260603182917_InitialCommercialSchema` hasta `20260922000000_AddCommercialQuoteIssuedBy`) y `JemNexusDbContext`. El paquete v3 privado permanece fuera del checkout: su resultado aportado (`VERIFIED_OFFLINE_PLAN_ONLY`, 17 tablas, 429 filas, 177 archivos y manifiesto `75810855b7e8f77bf5bc4089e0baf80ada30a06da34612b15b059cd0500ac4ed`) es evidencia de entrada, no se vuelve a abrir ni se incorpora aquí.

## Modos

Desde una consola privada de **Windows PowerShell 5.1**:

```powershell
# No acepta rutas, no abre conexiones y no lee ni crea archivos.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\deployment\Inspect-JemNexusDisposableRehearsal.ps1 -Mode PlanOnly

# Único modo que conecta; requiere un baseline sanitizado ya revisado.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\deployment\Inspect-JemNexusDisposableRehearsal.ps1 `
  -Mode InspectDisposable `
  -ProductionBaselinePath 'C:\JemNexus-Evidence\production-schema-baseline.json'
```

`InspectDisposable` primero valida el baseline y después comprueba, en la conexión efectiva, `SERVERPROPERTY('IsLocalDB') = 1`, `DB_NAME()` igual al nombre fijo y exactamente un marcador de base con nombre `JemNexus.DisposableRehearsalMarker` y valor `TASK-364|READONLY-PREFLIGHT|DISPOSABLE`. Un valor `NULL`, más de un resultado, un nombre parecido o un marcador ausente nunca son suficientes.

Después compara los 22 IDs exactos en `jemnexusb_api.__EFMigrationsHistory`, las 17 tablas importables y huellas canónicas independientes de todas sus columnas/tipos/nulabilidad/collation, PK, identity, FK/acciones/estado de confianza, índices/orden/filtros, checks/estado de confianza y `jemnexusb_api.SellerCodeSequence` (inicio e incremento). También exige permisos observables de conexión, lectura y futura escritura/alteración sobre `jemnexusb_api`, y coherencia entre folios emitidos y `CommercialQuoteFolioCounters`. La conexión del inspector solo ejecuta `SELECT`/CTE; observar un permiso no lo ejerce.

La salida estándar se limita a la clase de identidad sanitizada, conteos, huellas SHA-256 y códigos constantes. Nunca emite filas, nombres de servidor/equipo, credenciales, cadenas de conexión, usuarios, RUT, correo, tokens, hashes de contraseña, folios concretos ni datos personales.

## Baseline productivo sanitizado

El archivo se obtiene mediante el procedimiento productivo read-only revisado y tiene esta forma exacta mínima:

```json
{
  "reportType": "JemNexusProductionSchemaBaseline",
  "database": "jemnexusb_prod",
  "schema": "jemnexusb_api",
  "historySchema": "jemnexusb_api",
  "sequenceSchema": "jemnexusb_api",
  "markerScope": "database",
  "evidenceCapturedUtc": "2026-09-24T00:00:00Z",
  "migrationCount": 22,
  "migrationIds": ["los 22 IDs exactos enumerados por el inspector"],
  "schemaFingerprints": {
    "columns": "<sha256>",
    "primaryKeys": "<sha256>",
    "foreignKeys": "<sha256>",
    "indexes": "<sha256>",
    "checks": "<sha256>",
    "identities": "<sha256>",
    "sequence": "<sha256>"
  }
}
```

No incluya filas ni identidad humana. Las huellas se calculan con las mismas consultas, columnas, representación de `NULL`, orden ordinal y SHA-256 UTF-8 implementados por el inspector. El baseline solo demuestra lo observado cuando se capturó: **no prueba que producción siga igual**. El baseline debe declarar por separado `schema`, `historySchema`, `sequenceSchema` y `markerScope`; un valor `dbo`, una omisión o cualquier desacuerdo genera `NO-GO`, y el drift productivo debe comprobarse nuevamente inmediatamente antes de cualquier aplicación futura.

## Preparación y reconocimiento (no ejecutar en esta tarea)

Un operador Windows autorizado deberá, en una tarea separada:

1. crear una base nueva llamada exactamente `JemNexus_DisposableRehearsal_364` en `(localdb)\MSSQLLocalDB`, nunca adjuntar, renombrar ni reutilizar `JemNexus_Local`;
2. crear/configurar el principal que ejecute las migraciones con esquema predeterminado `jemnexusb_api` y aplicar allí exactamente las 22 migraciones versionadas, comprobando que las 17 tablas de aplicación, `__EFMigrationsHistory` y `SellerCodeSequence` queden en `jemnexusb_api` (no en `dbo`), sin cargar el paquete;
3. agregar a nivel de base la propiedad extendida `JemNexus.DisposableRehearsalMarker` con el valor literal indicado arriba, en el mismo procedimiento controlado que creó la base;
4. conceder al principal Windows que realizará el futuro ensayo los permisos mínimos observados por el guard, sin credenciales SQL embebidas;
5. capturar fuera del repositorio el baseline productivo sanitizado con las mismas consultas canónicas y revisión DBA;
6. ejecutar primero `PlanOnly` y luego `InspectDisposable`, conservando solo su salida sanitizada.

Este documento describe el procedimiento pero deliberadamente no proporciona ni ejecuta comandos `CREATE`, `ALTER`, `DROP`, importación o limpieza. El reconocimiento exige simultáneamente LocalDB efectiva, nombre exacto, marcador único, migraciones, esquema y baseline concordantes; el nombre o el marcador por sí solos no bastan.

## NO-GO y trabajo todavía pendiente

Son bloqueo: servidor no LocalDB o ambiguo, base distinta/prohibida, marcador ausente/duplicado, baseline inválido, migraciones ausentes o ubicadas fuera de `jemnexusb_api`, tablas de aplicación ausentes de `jemnexusb_api` (aunque haya homónimas completas en `dbo`), tabla o cualquier componente de esquema discordante, FK/check deshabilitada o no confiable reflejada por la huella, secuencia distinta, permisos insuficientes o folios incoherentes. Los fallos terminan con código 2.

Aun con resultado positivo siguen pendientes en Windows: creación controlada de la base, inspección dinámica real, restauración ensayada de backups, validación de ambas raíces multimedia, carga transaccional, identities/reseed, próximo vendedor y próximo folio, permisos funcionales/login, rollback coordinado y comprobación productiva inmediata de drift. Ninguna de esas tareas se ejecutó en este entorno.
