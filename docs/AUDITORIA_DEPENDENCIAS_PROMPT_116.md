# Auditoría de dependencias — Prompt 116

**Fecha:** 2026-08-13 (UTC)

**Repositorio/rama:** `/workspace/web-ventas-generica`, `work`

**HEAD auditado:** `3cc4bf7` (`Merge pull request #249 ... estandarizar-acciones-en-listados-administrativos`)

## 1. Estado inicial, continuidad y alcance

El árbol comenzó limpio (`## work`). El historial contiene `5ceca86 fix: standardize admin list actions`, integrado por el HEAD de merge `3cc4bf7`; además, la inspección del commit confirma cambios reales en las acciones de listas administrativas (iconos, agrupación y estilo de peligro). Por tanto, existe continuidad con el trabajo identificado como Prompt 115A.

Se auditaron exclusivamente `frontend/package.json`, `frontend/package-lock.json`, `backend-dotnet/JemNexus.Api/JemNexus.Api.csproj`, `backend-dotnet/JemNexus.Api.Tests/JemNexus.Api.Tests.csproj` y `backend-dotnet/JemNexus.sln`. No se auditó el backend Django. No existen bajo el repositorio `global.json`, `packages.lock.json`, `Directory.Packages.props`, `Directory.Build.*` ni `nuget.config`; tampoco hay administración central de versiones NuGet. `find .. -name AGENTS.md -print` no encontró instrucciones adicionales.

Esta auditoría no cambió manifiestos, lockfiles, proyectos, framework objetivo ni código. Los datos “más reciente” que requieren consultar registros se consideran **pendientes**, porque tanto npm como NuGet devolvieron HTTP 403 desde este entorno y `dotnet` no está instalado. No se interpreta esa limitación como ausencia de vulnerabilidades.

## 2. Entorno

| Herramienta | Resultado |
|---|---|
| Node.js | `v24.15.0` |
| npm | `11.4.2`; advierte que la configuración ambiental `http-proxy` dejará de aceptarse en la siguiente major |
| SDK/runtime .NET | No disponible: `dotnet --info`, `--list-sdks` y `--list-runtimes` terminaron 127 (`command not found`) |
| Configuración de framework | Ambos proyectos declaran `net8.0` |

Node 24 satisface los engines resueltos, aunque no hay `engines` en el manifiesto ni `global.json`, por lo que la versión de herramientas no está fijada reproduciblemente.

## 3. Frontend: inventario directo declarado y resuelto

`npm ci` instaló 117 paquetes sin alterar el lockfile. `npm ls --depth=0` y el lockfile dieron:

| Uso | Paquete | Rango declarado | Resuelto | Engines/peers relevantes |
|---|---|---:|---:|---|
| producción | `react` | `^18.3.1` | `18.3.1` | Node `>=0.10` |
| producción | `react-dom` | `^18.3.1` | `18.3.1` | peer React `^18.3.1` |
| producción | `react-router-dom` | `^6.30.1` | `6.30.3` | Node `>=14`; peers React/DOM `>=16.8` |
| desarrollo | `@types/react` | `^18.3.8` | `18.3.28` | — |
| desarrollo | `@types/react-dom` | `^18.3.0` | `18.3.7` | peer `@types/react ^18` |
| desarrollo | `@vitejs/plugin-react` | `^4.3.3` | `4.7.0` | Node `^14.18 || >=16`; Vite `^4.2 || ^5 || ^6 || ^7` |
| desarrollo | `typescript` | `^5.6.2` | `5.9.3` | Node `>=14.17` |
| desarrollo | `vite` | `^5.4.8` | `5.4.21` | Node `^18 || >=20`; peers de preprocesadores son opcionales |

### Transitivas y duplicados relevantes

`npm ls --all` fue correcto. La cadena principal de ejecución pública es `react-router-dom 6.30.3 -> react-router 6.30.3 -> @remix-run/router 1.23.2`, más `react-dom -> scheduler 0.23.2`. La cadena de build/desarrollo es `@vitejs/plugin-react -> Babel` y `vite 5.4.21 -> esbuild 0.21.5`, `rollup 4.60.2`, `postcss 8.5.12` y `nanoid 3.3.11`. El análisis del lockfile no encontró un mismo nombre de paquete instalado en más de una versión. Los `UNMET OPTIONAL DEPENDENCY` informados por Vite (`@types/node`, preprocesadores CSS y `terser`) son peers opcionales y no hicieron fallar el árbol ni el build.

## 4. Frontend: obsolescencia y vulnerabilidades

### Resultado reproducible

`npm outdated --json` no produjo inventario: GET a `registry.npmjs.org/react-dom` devolvió HTTP 403. `npm audit --json` y `npm audit --omit=dev --json` tampoco produjeron reportes: el endpoint oficial bulk advisories devolvió HTTP 403. En consecuencia, la cantidad verificable por severidad es **crítica: desconocida; alta: desconocida; moderada: desconocida; baja: desconocida**, tanto para el árbol completo como para producción. No es correcto registrar cero.

Los rangos declarados ya resolvieron parches/minors superiores (`react-router-dom 6.30.3`, tipos React, plugin React, TypeScript y Vite), pero la consulta fallida impide afirmar si están al día a 2026-08-13 o escoger una versión nueva sólo por ser “latest”. Las migraciones React 19, React Router 7, Vite 6/7/8 y cualquier major de TypeScript quedan separadas hasta revisar sus guías oficiales, engines y peers.

### Hallazgo conocido que requiere validación del audit oficial

| Paquete/cadena | Tipo y aviso | Rango/corrección conocida | Exposición y alcanzabilidad | Decisión |
|---|---|---|---|---|
| `vite 5.4.21 -> esbuild 0.21.5` | Transitiva de desarrollo; **moderada**, GHSA-67mh-4wv8-2f99 (“development server can receive requests and read responses”) | esbuild `<=0.24.2`; corregido en `0.25.0` | Afecta al servidor de desarrollo, cuando se visita contenido atacante mientras está activo. No se incorpora como servidor al despliegue estático. La configuración/uso concreto no demuestra alcanzabilidad; debe validarse dinámicamente. | Investigar una versión de Vite/plugin que resuelva esbuild `>=0.25.0`; no añadir override. Probablemente exige major de Vite y revisión de migración. |

Referencia primaria: [advisory oficial de esbuild](https://github.com/evanw/esbuild/security/advisories/GHSA-67mh-4wv8-2f99). Para Vite se deben contrastar [advisories oficiales](https://github.com/vitejs/vite/security/advisories) y [guías de migración](https://vite.dev/guide/migration.html); para React Router, sus [notas oficiales](https://github.com/remix-run/react-router/releases).

No se identificó mediante inspección estática una vulnerabilidad demostrablemente alcanzable en el JavaScript entregado al navegador. Eso **no equivale** a una auditoría limpia: el servicio de advisories no respondió. Los riesgos de Babel/Rollup/PostCSS son de entrada de build; esbuild/Vite también pueden afectar el dev server; las transitivas no importadas directamente requieren una entrada o ruta vulnerable específica.

## 5. NuGet: inventario directo

| Proyecto/uso | Paquete | Actual | Línea compatible candidata | Major más reciente / decisión |
|---|---|---:|---:|---|
| API/runtime | `Microsoft.AspNetCore.Authentication.JwtBearer` | 8.0.6 | **8.0.29**, alineada con el parche net8 ya usado | No migrar a 9/10 |
| API/OpenAPI | `Microsoft.AspNetCore.OpenApi` | 8.0.6 | **8.0.29** | No migrar a 9/10 |
| API/runtime | `Microsoft.Extensions.Identity.Core` | 8.0.6 | **8.0.29** | No migrar a 9/10 |
| API/runtime | `Microsoft.EntityFrameworkCore` | 8.0.29 | mantener **8.0.29** hasta verificar registro | 9/10 pospuesto |
| API/build | `Microsoft.EntityFrameworkCore.Design` | 8.0.29 | mantener **8.0.29** | conserva `PrivateAssets=all` |
| API/runtime | `Microsoft.EntityFrameworkCore.SqlServer` | 8.0.29 | mantener **8.0.29** | debe alinearse con EF base |
| API/build | `Microsoft.EntityFrameworkCore.Tools` | 8.0.29 | mantener **8.0.29** | conserva `PrivateAssets=all` |
| API/runtime | `MailKit` | 4.17.0 | mantener **4.17.0** pendiente de registro | Revisar release notes antes de cualquier major |
| API/docs | `Swashbuckle.AspNetCore` | 6.6.2 | investigar último 6.x verificable | Majors posteriores se posponen: cambios OpenAPI/ASP.NET requieren migración |
| tests | `Microsoft.AspNetCore.Mvc.Testing` | 8.0.29 | mantener **8.0.29** | alineado con net8 |
| tests | `Microsoft.EntityFrameworkCore.InMemory` | 8.0.29 | mantener **8.0.29** | alineado con todo EF |
| tests | `Microsoft.NET.Test.Sdk` | 17.10.0 | **17.14.1**, sujeto a restore/tests locales | 18.x debe revisarse por separado |
| tests | `xunit` | 2.8.1 | **2.9.3**, sujeto a compatibilidad runner/tests | xUnit v3 es migración mayor; posponer |
| tests | `xunit.runner.visualstudio` | 2.8.1 | **2.8.2**, sujeto a restore/tests locales | runner v3 se evalúa junto a xUnit v3 |
| tests | `coverlet.collector` | 6.0.2 | **6.0.4**, sujeto a restore/tests locales | revisar cambios antes de otra major |

Las candidatas anteriores son objetivos conservadores conocidos, no resultados de `--outdated` de esta ejecución. Deben reconfirmarse en [NuGet Gallery](https://www.nuget.org/) el día de Prompt 118. Las líneas Microsoft/EF 8 son compatibles con `net8.0`; los cuatro paquetes EF deben permanecer exactamente alineados. No se recomienda cambiar `TargetFramework` ni adoptar paquetes Microsoft 9/10 en esta etapa.

### Transitivas, vulnerabilidades y deprecaciones

Sin SDK no fue posible materializar `project.assets.json` de forma confiable ni ejecutar `dotnet list --include-transitive`, `--vulnerable` o `--deprecated`. Transitivas esperables —pero **no verificadas en este entorno**— incluyen componentes de ASP.NET Core, `Microsoft.IdentityModel.*` por JwtBearer, `Microsoft.Data.SqlClient` por EF SQL Server, dependencias MIME/criptografía de MailKit y adaptadores/testhost de la suite. No se inventan versiones, vulnerabilidades ni estado deprecated. La galería oficial debe ser la fuente de metadatos y los [advisories de seguridad de .NET](https://github.com/dotnet/announcements/labels/Security) la fuente Microsoft.

Por la misma razón, el resultado NuGet es: vulnerabilidades **desconocidas**, deprecaciones **desconocidas** y actualizaciones transitivas **pendientes**. La diferencia de parche entre ASP.NET/Extensions 8.0.6 y EF/testing 8.0.29 justifica alinear a 8.0.29, previa restauración; no prueba por sí sola una vulnerabilidad.

## 6. Compatibilidad y soporte de .NET 8

.NET 8 es LTS y su soporte oficial termina el **10 de noviembre de 2026**, según la [política oficial de soporte de .NET](https://dotnet.microsoft.com/platform/support/policy/dotnet-core). A fecha de auditoría sigue soportado, pero queda menos de un trimestre: debe planificarse una migración futura fuera de Prompts 116–118. Mantener parches de servicing 8.0 es apropiado; mezclar paquetes ASP.NET/EF 9 o 10 con el objetivo `net8.0` no lo es. EF Core, provider SQL Server, Design, Tools e InMemory deben moverse como unidad y la suite completa debe probarse.

Swashbuckle y xUnit tienen cambios mayores que no se pueden aprobar sólo por versión: revisar respectivamente sus repositorios/notas oficiales ([Swashbuckle](https://github.com/domaindrivendev/Swashbuckle.AspNetCore/releases), [xUnit](https://xunit.net/docs/getting-started/v3/migration)) y separar las migraciones de major.

## 7. Línea base de regresión

### Frontend

`npm run build` pasó: `tsc -b` terminó sin errores ni warnings; Vite `5.4.21` transformó **106 módulos** y construyó en **3.17 s**. Artefactos generales: `dist/index.html` 0.63 kB (gzip 0.39), CSS 98.76 kB (gzip 17.39) y JS 368.25 kB (gzip 105.82). No hay script de test frontend en `package.json`; no se inventó suite.

### Backend

No se pudieron ejecutar restore, build ni tests porque `dotnet` no existe en la imagen. Por tanto, no se aprueban compilación, transitivas ni las pruebas. La referencia histórica es 231 totales, 231 correctas, 0 fallidas y 0 omitidas, pero **no fue validada** aquí.

## 8. Matriz de decisiones

| Momento | Alcance exacto | Motivo/riesgo |
|---|---|---|
| Prompt 117: actualizar | Sólo versiones frontend concretas que un `npm outdated/audit` operativo confirme compatibles con React 18, Router 6, Vite 5 y TS 5; regenerar lock exclusivamente con npm | Hoy no hay evidencia suficiente para nombrar una versión superior segura. Debe resolver advisories confirmados sin `--force`, overrides ni salto major implícito. |
| Prompt 117: investigar | Vite que incorpore esbuild `>=0.25.0`, con plugin compatible | Puede exigir major; validar engines, dev server y build. |
| Posponer por major | React 19, Router 7, Vite 6+, xUnit v3, Swashbuckle major y .NET 9/10 | Requieren guías, cambios de API/configuración o cambio de plataforma. |
| Prompt 118: actualizar | JwtBearer/OpenApi/Identity `8.0.6 -> 8.0.29`; tras reconfirmación, Test SDK `17.14.1`, xunit `2.9.3`, runner `2.8.2`, coverlet `6.0.4` | Alineación net8 y mejoras conservadoras; riesgo medio en autenticación/testing, exige suite completa. |
| Prompt 118: mantener | EF/SQL Server/Design/Tools/InMemory `8.0.29`, MVC Testing `8.0.29`, MailKit `4.17.0` | Ya alineados; mantener salvo que fuentes oficiales confirmen otro parche net8 el día del cambio. |
| Investigar antes de decidir | Swashbuckle 6.6.2 y todas las transitivas/advisories/deprecations | Registro y CLI no disponibles; no hay evidencia para una candidata exacta. |

## 9. Orden propuesto de remediación

1. En un entorno con acceso a registros, repetir audits y guardar los resúmenes; resolver primero cualquier vulnerabilidad runtime alcanzable.
2. Prompt 117: aplicar sólo upgrades frontend compatibles confirmados; resolver por actualización directa la cadena de esbuild si existe una ruta soportada; nunca mediante override aislado.
3. Prompt 118: restaurar, alinear primero Microsoft ASP.NET/Extensions en 8.0.29, mantener todo EF en una única versión y después actualizar herramientas de test una por una.
4. Tras cada grupo: build correspondiente y, para backend, las 231 pruebas históricas o una cifra nueva explicada.
5. Prompt 119: auditoría final, comparación antes/después, lockfiles y riesgos residuales.

## 10. Reproducción

### Linux/frontend (desde la raíz)

```bash
node --version
npm --version
cd frontend
npm ci
npm ls --depth=0
npm ls --all
npm outdated --json
npm audit --json
npm audit --omit=dev --json
npm run build
```

### PowerShell/backend para Franz

```powershell
cd "C:\Users\Franz\Desktop\web-ventas-generica"
dotnet --info
dotnet --list-sdks
dotnet --list-runtimes
dotnet restore ".\backend-dotnet\JemNexus.sln"
dotnet list ".\backend-dotnet\JemNexus.sln" package
dotnet list ".\backend-dotnet\JemNexus.sln" package --include-transitive
dotnet list ".\backend-dotnet\JemNexus.sln" package --outdated --include-transitive
dotnet list ".\backend-dotnet\JemNexus.sln" package --vulnerable --include-transitive
dotnet list ".\backend-dotnet\JemNexus.sln" package --deprecated
dotnet build ".\backend-dotnet\JemNexus.sln" --no-restore
dotnet test ".\backend-dotnet\JemNexus.sln" --no-build --no-restore
```

## 11. Riesgos residuales y datos pendientes

- Repetir `npm outdated` y ambos `npm audit`: el HTTP 403 impidió contar severidades, confirmar advisories y escoger versiones frontend.
- Ejecutar todos los comandos PowerShell: faltan restore, inventario transitivo, outdated/vulnerable/deprecated, build y resultado real de pruebas.
- Confirmar en NuGet las candidatas y advisories vigentes; en particular `Microsoft.IdentityModel.*`, `Microsoft.Data.SqlClient`, MailKit y Swashbuckle.
- Verificar configuración y exposición del servidor Vite para determinar alcanzabilidad del advisory de esbuild.
- Planificar antes del 10-11-2026 la migración posterior a .NET 8, fuera de esta remediación.
- La ausencia de pin de Node/.NET y de lock NuGet reduce reproducibilidad; documentarla ahora, sin introducir esos mecanismos en Prompt 116.

## 12. Alcance exacto de Prompts 117–119

### Prompt 117 — frontend

Con conectividad al registro, registrar el baseline operativo; actualizar en `frontend/package.json` y `frontend/package-lock.json` sólo las candidatas exactas confirmadas dentro de React 18/Router 6/Vite 5/TS 5. Si corregir esbuild requiere Vite major, abrir una migración separada tras revisar guía, Node y peer de `@vitejs/plugin-react`. Validar `npm ci`, `npm ls --all`, ambos audits y `npm run build` (TypeScript, 106 módulos como referencia y artefactos).

### Prompt 118 — backend net8.0

Actualizar JwtBearer, OpenApi e Identity Core juntos a `8.0.29`; mantener/alinear todos los EF y MVC Testing en `8.0.29`; reconfirmar y evaluar Test SDK `17.14.1`, xunit `2.9.3`, runner `2.8.2` y coverlet `6.0.4`. No incluir .NET 9/10, xUnit v3 ni Swashbuckle major. Ejecutar restore, listas directa/transitiva/outdated/vulnerable/deprecated, build sin restore y suite completa.

### Prompt 119 — cierre

Ejecutar `npm audit` completo y producción, auditoría NuGet vulnerable/deprecated, builds frontend/backend y tests (231 o nueva cifra justificada); comprobar que los lockfiles provienen de sus gestores, comparar versiones/advisories/artefactos antes y después y dejar documentado todo riesgo residual o major pospuesto.
