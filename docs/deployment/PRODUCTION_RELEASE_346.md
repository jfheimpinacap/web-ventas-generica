# Generación reproducible de release productivo — Prompts 346 y 347

## 1. Propósito y alcance

`tools/deployment/New-JemNexusProductionRelease.ps1` prepara localmente, desde un `HEAD` aprobado y limpio, el ZIP del backend, el ZIP del frontend compilado/prerenderizado, el SQL diferencial EF y sus evidencias criptográficas. La herramienta **no se conecta a producción**, no conoce credenciales, no ejecuta SQL, no aplica migraciones, no sube archivos y no opera Plesk.

El estado productivo de referencia es: base `jemnexusb_prod`, default schema `jemnexusb_api`, 20 migraciones aplicadas hasta `20260830000000_PreserveQuotesWhenDeletingProducts` y exactamente dos pendientes. Los preflight del SQL vuelven a exigir esas condiciones; el documento no sustituye la revisión humana ni una ventana aprobada.

## 2. Requisitos locales

- Windows PowerShell 5.1 en Windows.
- Git y rama productiva `main`, con árbol completamente limpio. La generación real exige el SHA completo de 40 caracteres mediante `-ExpectedCommit`.
- SDK .NET 8, herramienta `dotnet-ef` compatible y dependencias NuGet ya restauradas.
- Node y npm compatibles, con `frontend/node_modules` ya instalado.
- No hace restore ni instala dependencias. El build fallará si el entorno no fue preparado previamente.
- `OutputRoot` debe estar completamente fuera del repositorio, no existir o ser un directorio vacío autorizado expresamente.

La implementación adapta las garantías del empaquetador existente `backend-dotnet/scripts/package-plesk.ps1` (ZIP raíz, exclusión y comprobación de entradas) al contrato más estricto de este release. No invoca `publish-plesk.ps1`, porque ese script restaura, compila y prueba automáticamente; tampoco invoca `package-plesk.ps1`, porque permite un conjunto de configuración más amplio y elimina/reemplaza destinos. El nuevo flujo utiliza el mismo proyecto productivo y el comando npm canónico del repositorio.

## 3. Vista previa segura (`-PlanOnly`)

Después del merge y de sincronizar el checkout local, compruebe antes de ambos comandos que `git branch --show-current` devuelve exactamente `main`, que `git status --short` no devuelve salida y que `git rev-parse HEAD` coincide exactamente con `origin/main`. No use como release el SHA de la rama de implementación previa al merge.

```powershell
Set-Location "C:\Users\Franz\Desktop\web-ventas-generica"

$ReleaseCommit = (git rev-parse HEAD).Trim()

.\tools\deployment\New-JemNexusProductionRelease.ps1 `
  -OutputRoot "C:\Users\Franz\Desktop\jem-nexus-release-20260923" `
  -ViteApiBaseUrl "https://api.jem-nexus.cl" `
  -ExpectedBranch "main" `
  -ExpectedCommit $ReleaseCommit `
  -PlanOnly
```

`-PlanOnly` valida ruta, URL, rama, limpieza Git y el commit cuando se proporciona; imprime staging, nombres, comandos y exclusiones. No crea ni modifica `OutputRoot`, el repositorio o artefactos, y no ejecuta dotnet, npm, Node, EF, compresión, build ni prerender. Solo para una revisión excepcional de desarrollo puede pasarse explícitamente `-ExpectedBranch work`; nunca debe usarse así para producir el release.

## 4. Generación real

El comando real es idéntico y elimina únicamente `-PlanOnly`:

```powershell
Set-Location "C:\Users\Franz\Desktop\web-ventas-generica"

$ReleaseCommit = (git rev-parse HEAD).Trim()

.\tools\deployment\New-JemNexusProductionRelease.ps1 `
  -OutputRoot "C:\Users\Franz\Desktop\jem-nexus-release-20260923" `
  -ViteApiBaseUrl "https://api.jem-nexus.cl" `
  -ExpectedBranch "main" `
  -ExpectedCommit $ReleaseCommit
```

La herramienta obtiene nuevamente el HEAD real y exige igualdad exacta con el SHA completo recibido: no acepta un SHA abreviado ni un ancestro diferente de HEAD. `ExpectedBranch` vale `main` por defecto y un detached HEAD siempre se rechaza. Solo si el directorio ya existe **y está vacío** se admite `-AllowExistingEmptyOutput`; la opción nunca autoriza borrar contenido. Todo comando con exit code no cero detiene el proceso. El staging tiene el nombre exacto `<OutputRoot>\.jem-nexus-release-staging-<short-sha>`; debe ser creado por la ejecución y solo ese staging se elimina en `finally`.

Desde la corrección del Prompt 347, los ZIP, el SQL final, el manifiesto, los checksums y la lista de preservación se crean primero bajo `release-artifacts` dentro de ese staging. Ningún nombre final se publica en la raíz del output mientras falte el build frontend, la validación de URLs, la generación y validación SQL, algún auxiliar o la verificación final de hashes y contratos. Antes del primer movimiento se comprueba en conjunto que ninguno de los seis destinos exista. Si un movimiento final falla, la herramienta elimina exclusivamente los destinos que esa ejecución ya movió; nunca borra contenido previo. Un fallo anterior a la publicación solo elimina su staging. Si la herramienta creó `OutputRoot` y este termina vacío, también puede retirarlo; un output vacío preexistente y autorizado permanece.

### Comandos ejecutados

Con rutas absolutas resueltas por la herramienta, el contrato equivale a:

```text
dotnet publish backend-dotnet/JemNexus.Api/JemNexus.Api.csproj -c Release -f net8.0 --no-restore -o <staging>/backend-publish
npm run build
dotnet ef migrations script 20260830000000_PreserveQuotesWhenDeletingProducts 20260922000000_AddCommercialQuoteIssuedBy --project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj --startup-project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj --configuration Release --no-build --output <staging>/ef-migrations.sql
```

`npm run build` es el comando canónico: ejecuta TypeScript, Vite cliente, Vite SSR, prerender y `validate:prerender`. No se añade un segundo pipeline alternativo.

## 5. Variables públicas frontend

Los únicos nombres `VITE_*` consumidos realmente por el código fuente actual son:

| Parámetro | Variable de build | Regla |
|---|---|---|
| `-ViteApiBaseUrl` | `VITE_API_BASE_URL` | Obligatoria; HTTPS; rechaza localhost, loopback e IP privada/link-local. Ejemplo productivo: `https://api.jem-nexus.cl`. |
| `-ViteWhatsappNumber` | `VITE_WHATSAPP_NUMBER` | Pública y opcional; usar valor público aprobado o fallback del código. |
| `-ViteContactEmail` | `VITE_CONTACT_EMAIL` | Pública y opcional; usar valor público aprobado o fallback del código. |
| `-ViteGtmId` | `VITE_GTM_ID` | Pública y opcional; vacío deshabilita GTM. |

`VITE_PUBLIC_SITE_URL` figura en documentación histórica y `.env.example`, pero no se consume en el código actual; no se inventa como entrada. Los canonicals/prerender actuales fijan `https://jem-nexus.cl`, que también se registra como URL pública frontend en el manifiesto. `VITE_API_PROVIDER` tampoco se consume actualmente.

Las variables `VITE_*` son públicas por diseño y quedan embebidas. Nunca deben usarse para passwords, tokens, cadenas SQL ni secretos.

## 6. Outputs exactos

Para un SHA corto `<short-sha>` de 12 caracteres:

- `jem-nexus-backend-<short-sha>.zip`;
- `jem-nexus-frontend-<short-sha>.zip`;
- `jem-nexus-migrations-20260830000000-to-20260922000000.sql`;
- `manifest.json`;
- `SHA256SUMS.txt`;
- `PRESERVE_ON_SERVER.txt`.

Ambos ZIP contienen directamente los archivos desplegables, sin carpeta exterior `publish`, `backend-package` o `dist`. Las entradas se ordenan y reciben timestamp ZIP constante. El backend exige en su raíz `JemNexus.Api.dll`, `.deps.json` y `.runtimeconfig.json`; conserva dependencias y `runtimes` si el publish los produce. El frontend exige `index.html`, `assets`, diez salidas prerender, `_spa.html` y `_noindex.html`.

Después del build se inspeccionan los archivos textuales desplegables y se extraen URLs absolutas para clasificarlas por esquema, host, puerto, ruta, credenciales, query, fragmento y tipo de archivo. La URL productiva normalizada indicada en `VITE_API_BASE_URL` debe aparecer en esos artefactos; su confirmación queda en `manifest.json`.

Esta validación distingue un **destino configurado** de un literal sintético de framework. React Router puede incluir exactamente `http://localhost` como origen auxiliar al construir un objeto `URL` cuando no dispone del origen de una ventana; por sí solo no es el destino API de la aplicación. Se permite únicamente ese texto exacto en JavaScript compilado, sin puerto explícito, credenciales, query, fragmento ni ruta distinta de `/`, y solo cuando la API productiva esperada también está presente y no aparece una API local real. El manifiesto registra el número de placeholders permitidos y los archivos JavaScript que los contienen.

La excepción no se aplica en `index.html`, HTML prerenderizado, JSON, CSS, manifests, configuraciones, atributos o redirecciones desplegables. También siguen bloqueados `http://localhost:5173`, `http://localhost/api`, `https://localhost`, cualquier host `127.0.0.1` u otro loopback, direcciones privadas o link-local, y APIs HTTP. La herramienta descubre además el valor vigente de `DEFAULT_API_BASE_URL` desde `frontend/src/services/api.ts` y rechaza el bundle si contiene ese fallback real de desarrollo; no presupone su puerto ni su ruta.

## 7. Exclusiones

Backend:

- `appsettings.json`, `appsettings.Development.json`, `appsettings.Production.json`;
- `web.config` y cualquier directorio `logs`;
- `.env`, `.env.*`, temporales y cualquier output ajeno al publish controlado.

Frontend:

- `App_Data`, `.user.ini`, `web.config`;
- source maps (`*.map`) y temporales.

Estas reglas son defensivas aunque el build normal no produzca varios de esos elementos. En particular, **nunca se debe subir `appsettings.Development.json` ni un archivo de configuración local**.

## 8. Preservación y reemplazo en Plesk

Antes de extraer, conservar exactamente:

Backend, bajo `api.jem-nexus.cl`:

- `appsettings.json`;
- `web.config`;
- `logs`.

Frontend, bajo `httpdocs`:

- `App_Data`;
- `.user.ini`;
- `web.config`.

El resto del contenido actual de `httpdocs` se reemplaza por el contenido raíz del ZIP frontend. En backend se reemplaza el código con el contenido raíz del ZIP sin sobrescribir los tres elementos preservados. `PRESERVE_ON_SERVER.txt` repite deliberadamente solo esas listas.

## 9. Manifiesto y hashes

`manifest.json` registra SHA completo/corto, fecha UTC, rama, versiones dotnet/Node/npm, ambas URLs públicas, la confirmación de API productiva, cantidad y archivos de placeholders framework permitidos, límites de migración, tamaño y SHA-256 de cada uno de los tres artefactos, exclusiones, comandos y resultado de cada etapa. No registra valores opcionales de contacto, usuario SQL, credenciales, tokens ni connection strings.

En Windows PowerShell, comparar cada valor con:

```powershell
Get-FileHash 'D:\jem-releases\346\jem-nexus-backend-<short-sha>.zip' -Algorithm SHA256
Get-FileHash 'D:\jem-releases\346\jem-nexus-frontend-<short-sha>.zip' -Algorithm SHA256
Get-FileHash 'D:\jem-releases\346\jem-nexus-migrations-20260830000000-to-20260922000000.sql' -Algorithm SHA256
Get-Content 'D:\jem-releases\346\SHA256SUMS.txt'
```

No edite un artefacto después de calcular hashes; regenere todo desde el mismo SHA si cambia cualquier entrada.

## 10. SQL diferencial: revisión sin ejecución

Abra el `.sql` en un editor de texto, no en una acción automática de ejecución. Revise en este orden:

1. preflight agregado por la herramienta;
2. bloque marcado `BEGIN/END SQL EMITIDO POR EF CORE; NO MODIFICADO`;
3. postflight y `SELECT` final verificable.

El cuerpo central procede literalmente de `dotnet ef migrations script` no idempotente entre:

- inicio exclusivo/aplicado: `20260830000000_PreserveQuotesWhenDeletingProducts`;
- destino inclusivo: `20260922000000_AddCommercialQuoteIssuedBy`.

Debe registrar una vez `20260917000000_AddGranularSellerPermissions` y una vez `20260922000000_AddCommercialQuoteIssuedBy`, y ninguna otra migración. La herramienta comprueba creación/backfill de `AppUserPermissions`, `IssuedById` nullable, backfill único desde `ResponsibleSellerId`, conversión a obligatorio, índice, FK a `AppUsers` sin cascada, y ausencia de `DROP TABLE`, `DROP COLUMN`, `TRUNCATE` y borrados de tablas críticas. No genera ni ejecuta `Down` o rollback.

## 11. Preflight, schema obligatorio y postflight

El preflight usa `SET XACT_ABORT ON` y `THROW`. Exige `DB_NAME() = N'jemnexusb_prod'`, `SCHEMA_NAME() = N'jemnexusb_api'`, historial en `[jemnexusb_api].[__EFMigrationsHistory]`, exactamente las 20 migraciones conocidas, última migración exacta, ninguna desconocida, destinos aún ausentes, tabla `AppUserPermissions` ausente e `IssuedById` ausente. Antes del primer `GO`, crea la tabla temporal de sesión `#JemNexusReleasePreflight`, guarda allí el conteo inicial de `QuoteRequests` e inicia la transacción exterior.

El default schema `jemnexusb_api` es obligatorio porque las migraciones EF actuales emiten identificadores no cualificados. La herramienta no reescribe SQL con regex y no asume `dbo`: el default schema correcto hace que esos nombres resuelvan al schema productivo confirmado. El script completo debe ejecutarse de una sola vez en **una única ventana, conexión y sesión de SSMS**. La tabla temporal sobrevive a los separadores `GO`, a diferencia de una variable escalar; no existe un `TRY/CATCH` que atraviese lotes.

El SQL de EF puede emitir sus propios `BEGIN TRANSACTION` y `COMMIT`. En SQL Server son transacciones anidadas por contador: esos `COMMIT` internos reducen `@@TRANCOUNT`, pero no hacen persistentes los cambios mientras la transacción exterior siga abierta. `SET XACT_ABORT ON` permanece activo entre lotes de la misma conexión. El wrapper no realiza ningún commit deliberado ante un fallo; si SSMS detiene la ejecución, el operador debe conservar la sesión para inspección y ejecutar el rollback aprobado, o cerrar la conexión para que SQL Server revierta la transacción pendiente.

El postflight exige ambas migraciones una vez, tabla de permisos, exactamente 29 permisos por seller calculados mediante joins/subconsultas (sin IDs de usuario hardcodeados), ausencia de `users.manage`, columna obligatoria, índice, FK `NO_ACTION`, cero cotizaciones con emisor nulo y conteo de `QuoteRequests` igual al valor leído desde `#JemNexusReleasePreflight`. Solo después de todas las verificaciones ejecuta el `COMMIT` exterior; luego emite el `SELECT` verificable y elimina la tabla temporal antes de finalizar correctamente.

## 12. Protecciones operativas y cosas que no realiza

- Rechaza rama distinta de `ExpectedBranch` (`main` por defecto), detached HEAD, árbol sucio, SHA esperado ausente en modo real, SHA no completo o distinto del HEAD exacto, URLs inseguras, output dentro/encima del repositorio, output existente no vacío y staging preexistente.
- No usa `$HOME`, globs de borrado ni rutas amplias. Solo elimina el staging exacto que creó.
- No contiene ni solicita secretos; no descubre configuración local.
- No hace restore, instalación, conexión SQL, acceso HTTP, despliegue, backup, mantenimiento, smoke tests, importación EP ni cambios de usuarios/datos.
- Generar el SQL no lo ejecuta. Generar ZIP no autoriza su promoción.
- La corrección del Prompt 347 no modifica código productivo frontend o backend: solo endurece y precisa la validación de artefactos y hace atómica su publicación local.

### Limpieza de un output parcial de la versión anterior

Una ejecución de la versión anterior podía dejar, por ejemplo, un ZIP backend con nombre final si el frontend o el SQL fallaban después. La herramienta corregida no busca ni elimina esos archivos históricos. Antes de volver a generar, el operador debe inspeccionar el output afectado, conservar cualquier evidencia necesaria y borrar **manualmente y de forma explícita** solo los artefactos parciales identificados; no debe usar globs ni apuntar al repositorio. Después debe utilizar un `OutputRoot` nuevo o uno existente, vacío y autorizado con `-AllowExistingEmptyOutput`. Con la versión corregida, un fallo previo a la promoción no deja ZIP, SQL, manifiesto ni checksums finales.

## 13. Orden posterior previsto

1. Revisión humana de artefactos, contenido, manifiesto y hashes.
2. Inicio aprobado de ventana de mantenimiento y confirmación de respaldos.
3. Ejecución manual controlada del SQL, en una única sesión, después de una última revisión.
4. Despliegue backend preservando configuración, `web.config` y logs.
5. Smoke test API mediante `https://api.jem-nexus.cl/health` y contratos aprobados.
6. Reemplazo frontend preservando los tres elementos de `httpdocs`.
7. Smoke test completo del sitio, auth, permisos, cotización, CORS, archivos y observabilidad.

## 14. Rollback

El rollback es la restauración coordinada de los respaldos de SQL, backend, frontend, configuración y contenido persistente ya obtenidos para la ventana. No se usa una migración `Down`: podría perder permisos o `IssuedById`. Si falla el SQL, mantener mantenimiento, conservar evidencia y decidir restauración o roll-forward revisado; si falla código, restaurar versiones solo cuando sean compatibles con el schema resultante.

La importación EP continúa siendo posterior, independiente y fuera de esta release.
