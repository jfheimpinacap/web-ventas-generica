# Preflight y dry-run offline del traslado local (Prompt 352)

## Estado y límites

`tools/deployment/Test-JemNexusDataTransferReadiness.ps1` es una herramienta **PowerShell 5.1 de solo lectura**. Inventaría `JemNexus_Local` y compara el resultado con evidencia productiva externa sanitizada. No exporta filas, no importa, no elimina, no actualiza, no ejecuta migraciones, no se conecta a producción y no escribe en `uploads`. No existe `-Apply` ni SQL aplicable.

Precheck de este correctivo: ruta `/workspace/web-ventas-generica`, rama `work`, árbol limpio y HEAD `43eb90276eef50ce43e858392aca672aba34fcf3`. También se confirmaron los tres archivos de alcance antes de modificarlos.

`READY_FOR_DESIGN` significa únicamente que los dos inventarios permiten diseñar una tarea posterior. Nunca significa autorización para aplicar. `NO-GO` bloquea el diseño/aplicación hasta revisar el alcance. Un snapshot es evidencia histórica declarada, no una lectura actual: un preflight futuro deberá volver a observar producción inmediatamente antes de cualquier operación.

## Requisitos

* Windows PowerShell 5.1, autenticación integrada y acceso de lectura a `(localdb)\MSSQLLocalDB` / `JemNexus_Local`.
* Dos raíces locales explícitas: `ImageUploadsRoot` es la raíz que contiene `product-images`; `ContentRoot` contiene `uploads\technical-sheets`.
* `OutputRoot` absoluto o resoluble, **fuera del repositorio**. La herramienta nunca reemplaza archivos: `-AllowNewOutputFile` crea un nombre nuevo con timestamp cuando el nombre estable ya existe.
* Cierre/congelamiento local durante el inventario para que DB y archivos no cambien mientras se calculan hashes.

La identidad se comprueba en dos etapas. Antes de abrir la conexión se exigen, con coincidencia exacta, `DataSource=(localdb)\MSSQLLocalDB`, base `JemNexus_Local` y esquema `dbo`; la cadena se construye internamente con autenticación integrada, sin credenciales SQL ni `AttachDbFilename`. Por ello no se admiten IP, DNS ni instancias remotas o compartidas. Después de conectar, consultas de solo lectura exigen que `DB_NAME()` sea exactamente `JemNexus_Local` y que `SERVERPROPERTY('IsLocalDB')` sea el entero `1`; se rechazan `0`, `NULL`/`DBNull` y cualquier tipo o valor inesperado. El nombre efectivo devuelto por SQL Server es dinámico y solo diagnóstico: no se compara con `MSSQLLocalDB` ni con un equipo o sufijo `LOCALDB#` concreto.

## Modos y comandos exactos

Desde la raíz del repositorio:

```powershell
# 1. No conecta ni crea OutputRoot/archivos.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\deployment\Test-JemNexusDataTransferReadiness.ps1 `
  -Mode PlanOnly `
  -OutputRoot 'C:\JemNexus-Evidence\run-352'

# 2. Única conexión permitida: LocalDB esperada. Solo SELECT y metadata.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\deployment\Test-JemNexusDataTransferReadiness.ps1 `
  -Mode InventoryLocal `
  -LocalInstance '(localdb)\MSSQLLocalDB' `
  -LocalDatabase 'JemNexus_Local' `
  -LocalSchema 'dbo' `
  -ImageUploadsRoot 'C:\src\web-ventas-generica\backend-dotnet\JemNexus.Api\uploads' `
  -ContentRoot 'C:\src\web-ventas-generica\backend-dotnet\JemNexus.Api' `
  -PublicBasePath '/media' `
  -OutputRoot 'C:\JemNexus-Evidence\run-352'

# 3. Comparación offline; no abre SQL.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\deployment\Test-JemNexusDataTransferReadiness.ps1 `
  -Mode CompareSnapshot `
  -LocalReportPath 'C:\JemNexus-Evidence\run-352\jemnexus-local-sanitized-inventory.json' `
  -ProductionSnapshotPath 'C:\JemNexus-Evidence\input\production-sanitized.json' `
  -EvidenceDateUtc '2026-09-23T14:30:00Z' `
  -EvidenceSource 'ticket-ficticio-OPS-0000 / consulta read-only revisada por DBA' `
  -OutputRoot 'C:\JemNexus-Evidence\compare-352'
```

No use `$HOME` para construir rutas. Para una segunda evidencia use un `OutputRoot` vacío distinto; si necesita conservar el mismo directorio, agregue `-AllowNewOutputFile`, que crea otro archivo y no sobreescribe el existente.

## Formatos sanitizados

### Informe local

`jemnexus-local-sanitized-inventory.json` tiene `reportVersion: 1` y `reportType: JemNexusLocalSanitizedInventory`. Incluye:

* identidad fija de instancia/base/esquema, hora UTC y número de migraciones;
* conteos de las 18 tablas, pero ninguna fila completa;
* SHA-256 de usernames normalizados únicamente para detectar cambio de identidad;
* estado de tablas/columnas requeridas, FKs huérfanas, duplicados relevantes e índices únicos;
* exclusión explícita de 122 refresh tokens (cero filas o valores de token incluidos);
* manifiesto de 92 imágenes y 85 fichas: tipo, IDs técnicos, ruta relativa canónica, bytes y SHA-256;
* conteo de dos imágenes huérfanas, excluidas del manifiesto.

No contiene contraseñas ni hashes de contraseña, tokens, connection strings, emails, RUT, datos de cliente, claves/fingerprints de idempotencia ni filas completas. Proteja igualmente los IDs, rutas y hashes como evidencia operativa.

### Snapshot productivo de entrada

El archivo debe ser JSON sanitizado, obtenido fuera de esta herramienta mediante un proceso de lectura revisado. Ejemplo ficticio completo:

```json
{
  "reportType": "JemNexusProductionSanitizedSnapshot",
  "database": "jemnexusb_prod",
  "schema": "jemnexusb_api",
  "migrationCount": 22,
  "counts": {
    "AppUsers": 2,
    "AppUserPermissions": 29,
    "QuoteRequests": 8,
    "CommercialQuotes": 0
  },
  "userIdentityHashes": [
    "sha256-minusculas-del-username-ficticio-1",
    "sha256-minusculas-del-username-ficticio-2"
  ],
  "schemaChecks": {
    "missingTables": [],
    "missingColumns": [],
    "requiredIndexesPresent": true,
    "orphanForeignKeys": 0
  }
}
```

Los hashes reales deben ser SHA-256 hexadecimal de los usernames productivos normalizados a minúsculas. No incluya usernames, datos personales ni secretos. `EvidenceDateUtc` y `EvidenceSource` son parámetros obligatorios y se conservan junto con el SHA-256 del snapshot para dejar clara su procedencia.

### Resultado de comparación

`jemnexus-offline-design-readiness.json` contiene decisión (`READY_FOR_DESIGN` o `NO-GO`), bloqueos, hashes de ambos artefactos, fecha/procedencia declaradas y advertencia de obsolescencia. `NO-GO` termina con código 2; errores de parámetros/formato terminan como error PowerShell.

## Criterios de aborto

InventoryLocal aborta antes de emitir informe ante identidad distinta, un `IsLocalDB` distinto del entero `1`, migraciones/conteos distintos, tabla/columna faltante, FKs/IDs/índices inválidos, referencia multimedia ausente, tamaño de ficha diferente, ruta absoluta/traversal/fuera de raíz, symlink/reparse point, prefijo o ProductId inconsistente, o un número distinto de dos huérfanos. La validación de identidad ocurre antes de crear el directorio o informe. Imágenes y fichas se resuelven bajo raíces separadas.

CompareSnapshot produce `NO-GO` por cualquier fallo local o por drift productivo: base/esquema/migraciones, identidades o conteo de usuarios, 29 permisos, ocho `QuoteRequests`, cualquier cotización, tablas/columnas, índices o FKs. También es bloqueo cualquier cambio no contemplado que deba agregarse al contrato del snapshot.

## Pruebas y validación posterior en Windows

Las pruebas sintéticas portables no requieren SQL Server, red, .NET, Node ni PowerShell. Cubren la aceptación de LocalDB aunque su nombre efectivo sea dinámico; el rechazo de instancia no LocalDB, `NULL`, valor inesperado o base equivocada; el rechazo previo a conexión de un DataSource remoto; y que `PlanOnly` no conecte ni escriba:

```powershell
python -m unittest tools/deployment/tests/test_data_transfer_readiness.py -v
```

En un Windows controlado quedan obligatorias la nueva validación del parser y la ejecución real de `PlanOnly`, seguida de `InventoryLocal` contra la LocalDB confirmada. En particular, confirme que un nombre efectivo dinámico pasa gracias a `IsLocalDB = 1`, y que base incorrecta o `IsLocalDB` no inequívoco abortan sin informe. Verifique antes y después que `PlanOnly` no creó el directorio y que `git status --short` sigue limpio. Compare luego con un snapshot sanitizado revisado. No pruebe conexión productiva: la herramienta no la admite.

## Siguiente paso

Conserve los tres JSON, logs de comandos y hashes en almacenamiento de evidencia restringido. Si el resultado es `READY_FOR_DESIGN`, revise manualmente el manifiesto y use esta evidencia para **diseñar** una aplicación en otra tarea. Antes de una futura aplicación deben repetirse el preflight productivo, backups/restores, ensayo y aprobaciones del plan 351; este artefacto no los sustituye.
