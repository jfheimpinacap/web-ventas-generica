# Cierre de auditoría de dependencias — Prompt 119

**Fecha:** 2026-08-15 (UTC)
**Repositorio/rama:** `/workspace/web-ventas-generica`, `work`

## 1. Alcance

Este cierre comprende el frontend React/Vite, el backend activo ASP.NET Core sobre .NET 8 y el proyecto de pruebas xUnit. Django queda expresamente excluido. No se actualizaron dependencias ni se efectuaron cambios funcionales, de producción, contratos, autenticación, datos o interfaz visual.

## 2. Continuidad

- El Prompt 116 permanece como línea base histórica en `docs/AUDITORIA_DEPENDENCIAS_PROMPT_116.md`, sin modificaciones.
- El Prompt 117 está integrado mediante la actualización frontend (`chore: update frontend dependencies`) y el contenido del manifiesto y lockfile confirma sus versiones finales.
- El Prompt 118 está integrado mediante `chore: update backend dependencies`; los dos proyectos conservan `net8.0` y sus referencias directas aprobadas.
- El Prompt 119 cierra la auditoría y corrige únicamente las tres advertencias nuevas de los analizadores xUnit 2.9.3.

## 3. Frontend: comparación antes/después

“Antes” corresponde a la línea base del Prompt 116; “después” es el lockfile conservado al cerrar el Prompt 119.

| Paquete | Antes | Después |
|---|---:|---:|
| React | 18.3.1 | 18.3.1 |
| React DOM | 18.3.1 | 18.3.1 |
| React Router DOM | 6.30.3 | 7.18.2 |
| Vite | 5.4.21 | 6.4.3 |
| `@vitejs/plugin-react` | 4.7.0 | 5.2.0 |
| esbuild | 0.21.5 | 0.25.12 |
| PostCSS | 8.5.12 | 8.5.26 |
| nanoid | 3.3.11 | 3.3.18 |
| `@babel/core` | 7.29.0 | 7.29.7 |
| `@remix-run/router` | 1.23.2 | ausente |

El manifiesto sigue declarando `react-router-dom ^7.18.2`, `@vitejs/plugin-react ^5.2.0` y `vite ^6.4.3`. El Prompt 119 no modificó `package.json` ni `package-lock.json`.

## 4. Backend: referencias directas antes/después

“Antes” corresponde al Prompt 116 y “después” al estado final aprobado en el Prompt 118 y conservado por el Prompt 119.

### API

| Referencia directa | Antes | Después |
|---|---:|---:|
| Microsoft.AspNetCore.Authentication.JwtBearer | 8.0.6 | 8.0.29 |
| Microsoft.AspNetCore.OpenApi | 8.0.6 | 8.0.29 |
| Microsoft.Extensions.Identity.Core | 8.0.6 | 8.0.29 |
| MailKit | 4.17.0 | 4.17.0 |
| Microsoft.EntityFrameworkCore | 8.0.29 | 8.0.29 |
| Microsoft.EntityFrameworkCore.Design | 8.0.29 | 8.0.29 |
| Microsoft.EntityFrameworkCore.SqlServer | 8.0.29 | 8.0.29 |
| Microsoft.EntityFrameworkCore.Tools | 8.0.29 | 8.0.29 |
| Swashbuckle.AspNetCore | 6.6.2 | 6.9.0 |

### Pruebas

| Referencia directa | Antes | Después |
|---|---:|---:|
| coverlet.collector | 6.0.2 | 6.0.4 |
| Microsoft.AspNetCore.Mvc.Testing | 8.0.29 | 8.0.29 |
| Microsoft.EntityFrameworkCore.InMemory | 8.0.29 | 8.0.29 |
| Microsoft.NET.Test.Sdk | 17.10.0 | 17.14.1 |
| xunit | 2.8.1 | 2.9.3 |
| xunit.runner.visualstudio | 2.8.1 | 2.8.2 |

Ambos proyectos permanecen en `net8.0`; no se cambió ninguno de los `.csproj`.

## 5. Vulnerabilidades y procedencia de la evidencia

### Ejecutado por Codex en este cierre

- `npm ci` y `npm ls --depth=0` finalizaron correctamente.
- `npm audit` y `npm audit --omit=dev` se intentaron, pero el endpoint oficial de advisories respondió HTTP 403. Por tanto, Codex no obtuvo un resultado dinámico de vulnerabilidades y no interpreta el 403 como fallo del código ni como auditoría limpia.
- `command -v dotnet` confirmó que el SDK no está disponible; no se intentaron comandos .NET destinados a fallar y Codex no ejecutó auditorías NuGet.

### Evidencia local anterior proporcionada por Franz

- Prompt 117: auditoría npm total con 0 vulnerabilidades y auditoría de producción con 0 vulnerabilidades.
- Prompt 118: API y pruebas sin paquetes NuGet vulnerables directos ni transitivos.

Estos resultados pertenecen al entorno Windows de Franz y no se presentan como ejecuciones de Codex. La auditoría dinámica npm y toda validación NuGet posterior a las correcciones quedan pendientes de repetición local.

## 6. Deprecaciones y actualizaciones pospuestas

xUnit 2.9.3 aparece como `Legacy`, con xUnit v3 como alternativa; la migración a v3 se pospone deliberadamente. También quedan fuera de alcance .NET 9 y .NET 10, majors superiores de Swashbuckle, Microsoft.NET.Test.Sdk 18 y majors superiores de Coverlet y del runner xUnit. El listado de paquetes desactualizados es informativo y no autoriza actualizaciones automáticas. Las transitivas sin vulnerabilidades no deben forzarse con referencias directas, overrides ni resolutions.

## 7. Advertencias xUnit

La compilación local anterior de Franz detectó exactamente:

1. `MigrationMetadataTests.cs(39,9)`, xUnit2029: `Assert.Empty` filtraba grupos para verificar que no existieran IDs de migración duplicados. Se sustituyó por `Assert.DoesNotContain(collection, predicate)`, conservando la agrupación ordinal y el predicado `Count() > 1`.
2. `CommercialWriteEndpointTests.cs(349,9)`, xUnit2031: `Assert.Single(collection.Where(predicate))` se sustituyó por `Assert.Single(collection, predicate)`.
3. `CommercialWriteEndpointTests.cs(358,9)`, xUnit2031: se aplicó la misma transformación directa, conservando colección y predicado.

No se tocaron otros usos válidos de `Assert.Empty` o `Assert.Single`, ni datos, rutas, payloads, resultados, escenarios o aserciones posteriores. La intención y cobertura de las pruebas permanecen iguales. Codex no pudo compilar el backend por ausencia de `dotnet`; la desaparición efectiva de xUnit2029/xUnit2031 requiere la validación local final.

## 8. Build y pruebas

### Evidencia local anterior de Franz

Antes de estas correcciones: restore y build correctos; 231 pruebas ejecutadas, 231 correctas, 0 fallidas y 0 omitidas, en aproximadamente 35 segundos. Los mensajes `fail:` y `warn:` de escenarios simulados son intencionales y no contradicen ese resultado. En frontend, Franz había obtenido `npm ci` correcto, ambas auditorías con 0 vulnerabilidades y build Vite 6.4.3 correcto con 111 módulos.

### Resultado de Codex en Prompt 119

- Frontend: `npm ci` correcto (124 paquetes), árbol directo válido, build correcto con Vite 6.4.3 y 111 módulos transformados. Ambas auditorías npm quedaron sin resultado por HTTP 403.
- Backend: no ejecutado; `dotnet` no está instalado. No se atribuyen a Codex restore, build, tests ni listados NuGet.

### Validación local final pendiente

Franz debe ejecutar restore, build, las 231 pruebas y los tres listados NuGet después de integrar este commit. Se espera build con 0 errores, ausencia de xUnit2029/xUnit2031 y 231/231 pruebas correctas, pero ese resultado posterior aún no se declara realizado.

## 9. Estado final y reproducción

Las versiones directas finales son exactamente las enumeradas en las tablas; las migraciones mayores indicadas permanecen pospuestas. Sólo se modificaron las dos pruebas afectadas y este informe. No hubo cambios en código productivo, frontend, manifiestos ni lockfile.

Comandos PowerShell exactos para la validación final de Franz:

```powershell
cd "C:\Users\Franz\Desktop\web-ventas-generica"

dotnet restore ".\backend-dotnet\JemNexus.sln"

dotnet build ".\backend-dotnet\JemNexus.sln" --no-restore

dotnet test ".\backend-dotnet\JemNexus.sln" --no-build --no-restore

dotnet list ".\backend-dotnet\JemNexus.sln" package --vulnerable --include-transitive

dotnet list ".\backend-dotnet\JemNexus.sln" package --deprecated

dotnet list ".\backend-dotnet\JemNexus.sln" package --outdated --include-transitive

cd ".\frontend"

npm ci
npm audit
npm audit --omit=dev
npm run build

cd ".."

git status --short --branch
```

Resultado esperado después del merge: build .NET con 0 errores y sin xUnit2029/xUnit2031; 231/231 pruebas correctas; NuGet sin vulnerabilidades; xUnit v2 `Legacy` aceptado temporalmente; npm con 0 vulnerabilidades; build frontend correcto; árbol Git limpio.

No se ejecutaron push, merge, despliegue, publicación, SQL ni migraciones de base de datos durante este cierre.
