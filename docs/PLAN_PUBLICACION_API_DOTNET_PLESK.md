# Plan de publicación controlada API .NET en Plesk/IIS

## A. Alcance

Este plan prepara la publicación manual y controlada de la API ASP.NET Core de JEM Nexus en Plesk Windows/IIS para `https://api.jem-nexus.cl`.

Incluye documentación, checklist operativo, variables requeridas, comandos locales de publicación, smoke tests, diagnóstico y rollback.

Fuera de alcance para este plan:

- No aplicar schema de base de datos.
- No ejecutar `dotnet ef database update`.
- No ejecutar SQL real.
- No conectar a Plesk desde Codex.
- No publicar ni subir archivos desde Codex.
- No crear usuarios reales desde SQL.
- No guardar secretos reales en git, docs, README ni `appsettings*.json` versionados.
- No cambiar el frontend para consumir la API .NET todavía.
- No tocar Django ni Render.

## B. Estado previo requerido

Antes de publicar la API, confirmar que el estado previo de Plesk/SQL Server ya está completo:

- El schema EF Core ya fue aplicado en SQL Server/Plesk.
- La base de datos es `jemnexusb_prod`.
- Los objetos quedaron bajo el esquema real `jmnexusb_api`.
- `__EFMigrationsHistory` contiene estas dos migraciones:
  - `20260603182917_InitialCommercialSchema`.
  - `20260604020543_AddAuthUsersAndAuditRelations`.
- El subdominio `api.jem-nexus.cl` ya existe en Plesk.
- SSL Let's Encrypt está activo para `api.jem-nexus.cl`.
- La redirección HTTP -> HTTPS está activa.
- HSTS permanece desactivado por ahora para facilitar rollback durante las primeras publicaciones controladas.

## C. Checklist de Plesk/IIS antes de publicar

Revisar en Plesk antes de reemplazar archivos:

- [ ] Confirmar que `api.jem-nexus.cl` apunta a la carpeta correcta del subdominio de API, no a `httpdocs` del frontend principal.
- [ ] Confirmar soporte de ASP.NET Core/.NET 8 en el hosting o que el ASP.NET Core Hosting Bundle compatible esté disponible en el servidor.
- [ ] Confirmar configuración de Application Pool / hosting settings si Plesk la muestra.
- [ ] Confirmar permisos de escritura si se usará carpeta de uploads en IIS.
- [ ] Confirmar la ruta final para uploads si `Uploads__RootPath` se configura en producción.
- [ ] Respaldar la carpeta actual de `api.jem-nexus.cl` antes de reemplazar archivos.
- [ ] Confirmar que no se sobreescribe el `web.config` generado por `dotnet publish` con un `web.config` viejo.
- [ ] Confirmar que `appsettings.Production.json`, si existe fuera del repo, no contiene secretos versionados.
- [ ] Confirmar que variables de entorno y secretos se configuran en Plesk/IIS o en un `web.config` transformado fuera de git.
- [ ] Confirmar que no se ejecutará `dotnet ef database update` durante la publicación.
- [ ] Confirmar que existe una ventana de publicación y una persona responsable de rollback.

## D. Variables requeridas sin secretos reales

Configurar fuera del repositorio. Usar placeholders en documentación y ejemplos; nunca guardar valores reales en git.

Variables mínimas/recomendadas:

- `ASPNETCORE_ENVIRONMENT=Production`.
- `ConnectionStrings__DefaultConnection`.
- `JWT_SECRET` o `Jwt__Secret`.
- `Jwt__Issuer`.
- `Jwt__Audience`.
- `SeedUsers__SellerUsername`.
- `SeedUsers__SellerPassword`.
- `SeedUsers__SupportUsername`.
- `SeedUsers__SupportPassword`.
- `FRONTEND_ORIGINS`.
- `Uploads__RootPath`, si aplica.
- `Uploads__PublicBasePath`, si aplica.

Aclaraciones:

- No guardar contraseñas reales, connection strings con password real ni claves JWT reales en README, docs ni `appsettings*.json` versionados.
- `SeedUsers__*` solo debe configurarse si se desea crear usuarios iniciales mediante seed controlado.
- Si no se configuran passwords, `SeedData` no crea usuarios.
- En `Production`, la aplicación exige `JWT_SECRET` o `Jwt__Secret`; si falta, el arranque debe fallar de forma explícita.
- `FRONTEND_ORIGINS` puede listar `https://jem-nexus.cl,https://www.jem-nexus.cl`.

## E. Cadena de conexión esperada

Formato de referencia sin password real:

```text
Server=190.107.176.16;Database=jemnexusb_prod;User Id=jemnexusb_api;Password=***;TrustServerCertificate=True;Encrypt=True;
```

Notas:

- El servidor real puede requerir la IP o el host indicado por Plesk.
- En la validación con SSMS se conectó usando `190.107.176.16` y Trust Server Certificate.
- No incluir password real en commits, documentación, tickets, capturas ni mensajes de PR.
- La variable esperada para ASP.NET Core es `ConnectionStrings__DefaultConnection`.

## F. Comandos locales de publicación

Ejecutar en Windows PowerShell desde la raíz del repo antes de subir archivos:

```powershell
dotnet restore backend-dotnet\JemNexus.sln
dotnet build backend-dotnet\JemNexus.sln -c Release
dotnet test backend-dotnet\JemNexus.sln -c Release

dotnet publish backend-dotnet\JemNexus.Api\JemNexus.Api.csproj `
  -c Release `
  -o backend-dotnet\publish\JemNexus.Api
```

La carpeta `backend-dotnet\publish\JemNexus.Api` es la carpeta local que se comprime/sube manualmente a Plesk. No publicar desde la carpeta de código fuente.

`backend-dotnet\publish\` es un artefacto local de despliegue y no se versiona en Git. Si se necesita regenerar el paquete, ejecutar:

```powershell
.\backend-dotnet\scripts\publish-plesk.ps1
```

Antes de commitear, revisar `git status --short`; no usar `git add .` sin confirmar que `backend-dotnet\publish\`, binarios publicados, archivos locales y secretos no serán agregados.

También se puede usar el script seguro del repo desde PowerShell:

```powershell
backend-dotnet\scripts\publish-plesk.ps1
```

El script solo restaura, compila, prueba y publica localmente. No conecta a Plesk, no sube archivos, no ejecuta SQL y no ejecuta `dotnet ef database update`.

## G. Archivos esperados en `publish`

Después de `dotnet publish`, la carpeta de salida debe incluir, entre otros:

- `JemNexus.Api.dll`.
- `web.config`, generado por el SDK Web para IIS/ASP.NET Core Module.
- `appsettings.json`.
- Dependencias `.dll`.
- `wwwroot`, si existe en la app.
- `runtimes`, si aplica por dependencias/plataforma.

Si `web.config` no aparece, revisar que el proyecto use `Microsoft.NET.Sdk.Web` y que se esté publicando el `.csproj` de `JemNexus.Api`.

## H. Subida a Plesk

Opciones manuales válidas:

- Crear un ZIP con el contenido de `backend-dotnet\publish\JemNexus.Api`, subirlo con File Manager de Plesk y extraerlo en la carpeta del subdominio `api.jem-nexus.cl`.
- Subir los archivos con File Manager de Plesk.
- Usar FTP/SFTP si está disponible y autorizado.

Reglas de seguridad operacional:

- Respaldar la carpeta anterior antes de reemplazar.
- No tocar `httpdocs` del frontend principal.
- No mezclar archivos publicados con fuentes del repo.
- No subir archivos de desarrollo, `.git`, `obj`, `bin` de build intermedio ni secretos locales.
- Configurar variables de entorno antes de iniciar o reiniciar la app en `Production`.
- Confirmar que el `web.config` final corresponde al publish actual, no a un archivo viejo.

## I. Smoke tests post-publicación

Ejecutar manualmente después de subir, configurar variables y reiniciar la aplicación.

Health checks:

```http
GET https://api.jem-nexus.cl/health
GET https://api.jem-nexus.cl/api/health
```

Resultado esperado:

- `200 OK`.
- JSON con `status` igual a `ok`.
- `app` identificando `JEM Nexus API`.
- `environment` igual a `Production`.

Auth, solo si se configuró seed de usuarios con credenciales temporales/controladas:

```http
POST https://api.jem-nexus.cl/api/auth/login
Content-Type: application/json

{
  "username": "<SELLER_OR_SUPPORT_USERNAME>",
  "password": "<TEMPORARY_PASSWORD>"
}
```

Resultado esperado:

- `200 OK` si el usuario existe y la contraseña es correcta.
- Respuesta con `access`, `refresh` y `user`.

Luego probar el token:

```http
GET https://api.jem-nexus.cl/api/auth/me
Authorization: Bearer <ACCESS_TOKEN>
```

Resultado esperado:

- `200 OK`.
- Datos del usuario autenticado.

CORS:

- Probar desde `https://jem-nexus.cl` cuando el frontend apunte a la API .NET en una fase posterior.
- No cambiar URLs ni funcionalidad del frontend durante esta publicación controlada.

## J. Rollback

Si falla la publicación:

1. Guardar evidencia mínima del error: hora, URL probada, status HTTP y extracto breve de logs sin secretos.
2. Restaurar la carpeta anterior respaldada de `api.jem-nexus.cl`.
3. Quitar o revertir variables nuevas si causan conflicto de arranque.
4. Reiniciar el sitio/app pool si aplica.
5. Repetir smoke tests contra la versión restaurada.
6. No tocar la base de datos si el error es de publicación/app/IIS.
7. Revisar logs antes de reintentar otra publicación.

No ejecutar scripts SQL ni `dotnet ef database update` como parte de rollback de publicación.

## K. Logs y diagnóstico

Lugares a revisar si la app no arranca o responde 5xx:

- Logs del dominio/subdominio en Plesk.
- IIS logs del sitio.
- Event Viewer de Windows, si se tiene acceso.
- Logs de stdout del ASP.NET Core Module, solo si se habilitan temporalmente.

Sobre stdout:

- `stdoutLogEnabled="true"` en `web.config` debe usarse solo para diagnóstico temporal.
- Definir una ruta con permisos de escritura para los logs si se habilita.
- Desactivar `stdoutLogEnabled` después de diagnosticar para evitar crecimiento de archivos y exposición de datos sensibles.
- No commitear un `web.config` modificado con stdout permanente ni secretos.

## L. Riesgos conocidos

- El esquema real de SQL Server es `jmnexusb_api`; confirmar que el usuario `jemnexusb_api` usa permisos correctos sobre ese esquema.
- La cadena de conexión debe usar la misma base `jemnexusb_prod` y usuario con permisos correctos.
- Variables JWT son obligatorias en `Production`; falta de `JWT_SECRET`/`Jwt__Secret` debe impedir el arranque.
- El seed de usuarios puede no crear usuarios si faltan passwords; esto es esperado y seguro.
- No reejecutar scripts SQL ya aplicados.
- No ejecutar `dotnet ef database update` contra producción durante publicación.
- Uploads en IIS requieren permisos de escritura explícitos y ruta controlada.
- `HSTS` desactivado por ahora reduce fricción de rollback inicial; reevaluarlo cuando la publicación esté estable.
- CORS ya contempla `https://jem-nexus.cl` y `https://www.jem-nexus.cl`, pero el frontend no debe cambiarse a la API .NET hasta una fase posterior.

## Confirmaciones técnicas del estado actual

- El proyecto `JemNexus.Api` apunta a `net8.0`.
- `dotnet publish` del proyecto Web SDK debe generar `web.config` para IIS.
- La API expone `/health`, `/api/health`, `/api/auth/login`, `/api/auth/refresh` y `/api/auth/me`.
- Swagger se habilita solo en `Development` o `QA`.
- En `Production`, la app exige `JWT_SECRET` o `Jwt:Secret`.
- CORS incluye `https://jem-nexus.cl` y `https://www.jem-nexus.cl`, y además acepta `FRONTEND_ORIGINS` por variable.
- La conexión SQL se lee desde `ConnectionStrings__DefaultConnection` mediante la configuración estándar de ASP.NET Core.
- `SeedData` omite creación de usuarios cuando faltan passwords configuradas.
