# JEM Nexus ASP.NET Core API

Proyecto base de la migración del backend de JEM Nexus a ASP.NET Core Web API (.NET 8), preparado para Windows Server + IIS + Plesk.

> Este proyecto prepara la migración del backend a ASP.NET Core/SQL Server. La fase Backend .NET 3 ya agrega autenticación JWT base y auditoría hacia `AppUsers`, y el schema ya quedó aplicado en Plesk/SQL Server; todavía no reemplaza el backend Django existente ni publica la API .NET.

## Estructura

```text
backend-dotnet/
  JemNexus.sln
  JemNexus.Api/
    Data/
    Models/
  JemNexus.Api.Tests/
```

## Desarrollo local

```bash
dotnet restore backend-dotnet/JemNexus.sln
dotnet build backend-dotnet/JemNexus.sln
dotnet test backend-dotnet/JemNexus.sln
dotnet run --project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj
```

Endpoints mínimos:

- `GET /`
- `GET /health`
- `GET /api/health`
- `GET /api/health/`

Todos responden JSON con `status`, `app`, `environment` y `timestamp`.

## Tests y validación

```bash
dotnet restore backend-dotnet/JemNexus.sln
dotnet build backend-dotnet/JemNexus.sln
dotnet test backend-dotnet/JemNexus.sln
```

Los tests incluyen endpoints mínimos de health y validaciones de metadata del modelo comercial EF Core.

## Entity Framework Core

El DbContext `JemNexusDbContext` queda registrado para SQL Server y toma la cadena desde `ConnectionStrings:DefaultConnection`, que en IIS/Plesk debe configurarse como variable de entorno:

```text
ConnectionStrings__DefaultConnection
```

No guardar credenciales reales en `appsettings*.json`.

Comando local para crear la migración inicial cuando el SDK .NET 8 y `dotnet-ef` estén disponibles:

```bash
dotnet ef migrations add InitialCommercialSchema --project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj
```


## Aplicación controlada de schema en Plesk

El schema ya quedó aplicado en `jemnexusb_prod`; para cualquier nueva base o reintento, revisar y seguir el checklist `../docs/PLAN_APLICACION_SCHEMA_PLESK_SQLSERVER.md`. El flujo correcto es:

1. Diagnosticar primero el estado real de la base con queries de solo lectura.
2. Revisar `__EFMigrationsHistory` y confirmar si existen tablas comerciales o auth.
3. Elegir el script correcto según el estado detectado: acumulado desde cero para base vacía, o diferencial si `InitialCommercialSchema` ya está aplicado.
4. Nunca ejecutar `dotnet ef database update` directamente contra producción/Plesk.
5. No guardar credenciales reales, cadenas de conexión completas ni secretos JWT en archivos versionados.

`backend-dotnet/sql/AddAuthUsersAndAuditRelations.sql` es acumulado desde cero. Si la base ya tiene `InitialCommercialSchema`, se debe generar/revisar `backend-dotnet/sql/FromInitialCommercialSchemaToAddAuthUsersAndAuditRelations.sql` antes de aplicar cambios.


### Schema aplicado en Plesk

El schema ASP.NET Core / EF Core fue aplicado correctamente en Plesk SQL Server sobre la base `jemnexusb_prod` después del hotfix de cascadas. Las tablas quedaron bajo el esquema real `jmnexusb_api`.

No ejecutar nuevamente `backend-dotnet/sql/AddAuthUsersAndAuditRelations.sql` sobre la misma base sin revisar primero `__EFMigrationsHistory` y confirmar la existencia real de las tablas esperadas. El historial esperado contiene:

- `20260603182917_InitialCommercialSchema`
- `20260604020543_AddAuthUsersAndAuditRelations`

Antes de publicar la API .NET en Plesk/IIS, configurar fuera del repositorio y sin secretos reales en git:

- `ConnectionStrings__DefaultConnection`
- `Jwt__Secret` o `JWT_SECRET`
- `Jwt__Issuer`
- `Jwt__Audience`
- `SeedUsers__SellerUsername`
- `SeedUsers__SellerPassword`
- `SeedUsers__SupportUsername`
- `SeedUsers__SupportPassword`
- `FRONTEND_ORIGINS`

## Publicación para IIS/Plesk

Generar un paquete local de publicación:

```bash
dotnet publish backend-dotnet/JemNexus.Api/JemNexus.Api.csproj -c Release -f net8.0 -o backend-dotnet/publish-test
```

La carpeta de salida debe incluir, entre otros artefactos:

- `JemNexus.Api.dll`
- `JemNexus.Api.exe`
- `web.config`
- `appsettings.json`

Para despliegue manual en Plesk, subir el contenido de la carpeta publicada al sitio de la API `https://api.jem-nexus.cl` y configurar las variables de entorno desde Plesk/IIS antes de iniciar la aplicación.

## Configuración y variables de entorno

La configuración base vive en `JemNexus.Api/appsettings.json` y `JemNexus.Api/appsettings.Development.json`, con soporte para override por variables de entorno.

Variables sugeridas/necesarias, sin valores reales en git:

- `ASPNETCORE_ENVIRONMENT`
- `PUBLIC_SITE_URL`
- `FRONTEND_ORIGINS`
- `ConnectionStrings__DefaultConnection`
- `Jwt__Secret` o `JWT_SECRET`
- `Jwt__Issuer` o `JWT_ISSUER`
- `Jwt__Audience` o `JWT_AUDIENCE`
- `Jwt__AccessTokenMinutes`
- `Jwt__RefreshTokenDays`
- `SeedUsers__SellerUsername`
- `SeedUsers__SellerPassword`
- `SeedUsers__SellerEmail`
- `SeedUsers__SellerFullName`
- `SeedUsers__SupportUsername`
- `SeedUsers__SupportPassword`
- `SeedUsers__SupportEmail`
- `SeedUsers__SupportFullName`

`FRONTEND_ORIGINS` puede contener orígenes separados por coma o punto y coma y se combina con `Cors:AllowedOrigins`.

No guardar secretos reales, connection strings reales ni claves JWT en `appsettings*.json`.

## CORS

La política CORS inicial permite:

- `https://jem-nexus.cl`
- `https://www.jem-nexus.cl`
- `http://localhost:5174`
- `http://127.0.0.1:5174`

## Swagger/OpenAPI

Swagger se registra solo cuando `ASPNETCORE_ENVIRONMENT` es `Development` o `QA`. No queda expuesto obligatoriamente en `Production`.

## Compatibilidad JSON

La serialización JSON queda configurada con `JsonNamingPolicy.SnakeCaseLower`. Esta decisión prepara respuestas futuras compatibles con los contratos actuales de Django/DRF, que usan nombres de campos en `snake_case`. Los DTOs reales se migrarán en fases posteriores.

## Observaciones pre-aplicación Backend .NET 2C

### Slugs

`JemNexus.Api/Utils/SlugHelper.cs` centraliza la generación/normalización de slugs: minúsculas, remoción de tildes, separadores con guiones, eliminación de caracteres no seguros, compactación de guiones y manejo seguro de `null`/vacío.

La unicidad final de slugs debe resolverse al crear endpoints de escritura, consultando la base de datos y aplicando una política de sufijos si el índice único detecta colisión.

### Timestamps automáticos

`JemNexusDbContext` actualiza timestamps comerciales en `SaveChanges` y `SaveChangesAsync`:

- En entidades nuevas, asigna `CreatedAt` cuando viene en default y siempre asigna `UpdatedAt`.
- En entidades modificadas, actualiza `UpdatedAt` y conserva `CreatedAt`.

Esto prepara el equivalente a `auto_now`/`auto_now_add` sin agregar triggers ni cambiar el schema inicial.

### Uploads

La sección `Uploads` de `appsettings*.json` prepara la configuración de imágenes para fases futuras:

```json
"Uploads": {
  "RootPath": "",
  "PublicBasePath": "/media",
  "AllowedExtensions": [".jpg", ".jpeg", ".png", ".webp"],
  "MaxFileSizeMb": 5
}
```

En desarrollo local, `RootPath` debe apuntar a una carpeta configurable. En Plesk/IIS, debe apuntar a una carpeta del hosting/subdominio o carpeta asignada con permisos de escritura controlados para el identity del app pool. La base de datos debe guardar rutas relativas, no rutas absolutas. Los endpoints futuros deben validar extensión, content-type, firma binaria y tamaño antes de escribir archivos y nunca exponer archivos fuera de la carpeta pública.

### Auditoría y actualización de base real

`CreatedById` y `UpdatedById` se mantienen por ahora como campos base sin FK real hasta definir autenticación JWT y usuarios en Backend .NET 3. La decisión pendiente es usar una tabla propia liviana o ASP.NET Core Identity.

> Advertencia: no ejecutar `dotnet ef database update` contra Plesk/SQL Server productivo sin revisar connection string, confirmar backup de SQL Server y uploads, validar ventana de mantenimiento y confirmar explícitamente la migración a aplicar.

## Backend .NET 3: autenticación JWT y usuarios base

Esta fase agrega una base de autenticación ASP.NET Core compatible con el contrato actual del frontend/Django, sin modificar frontend, Django, Render ni Plesk.

### Modelo auth

Se usa un `AppUser` propio y liviano, no ASP.NET Core Identity completo. Identity se usa únicamente para `PasswordHasher<AppUser>`.

Roles definidos:

- `seller`
- `support_admin`

No hay multiempresa ni ownership multi-vendedor en esta fase.

### Endpoints

Endpoints implementados con y sin slash final:

- `POST /api/auth/login/`
- `POST /api/auth/refresh/`
- `GET /api/auth/me/`

Respuesta de login esperada:

```json
{
  "access": "...",
  "refresh": "...",
  "user": {
    "id": 1,
    "username": "demo",
    "email": null,
    "role": "seller",
    "is_staff": true,
    "is_superuser": false
  }
}
```

### Variables JWT

No guardar secretos reales en `appsettings*.json`. Configurar por variables de entorno o secretos locales:

```text
Jwt__Issuer=JEM Nexus API
Jwt__Audience=JEM Nexus Frontend
Jwt__Secret=<configurar-fuera-del-repo>
Jwt__AccessTokenMinutes=60
Jwt__RefreshTokenDays=7
```

También se soportan aliases de entorno simples:

```text
JWT_SECRET=<configurar-fuera-del-repo>
JWT_ISSUER=JEM Nexus API
JWT_AUDIENCE=JEM Nexus Frontend
```

En Production, `Jwt__Secret` o `JWT_SECRET` es obligatorio. El valor en `appsettings.json` queda vacío intencionalmente.

### Variables SeedUsers

El seed de usuarios no crea usuarios si no hay contraseñas configuradas. Configurar solo en entorno local/seguro:

```text
SeedUsers__SellerUsername=demo
SeedUsers__SellerPassword=<password-local-no-real>
SeedUsers__SellerEmail=
SeedUsers__SellerFullName=Vendedor Demo
SeedUsers__SupportUsername=support
SeedUsers__SupportPassword=<password-local-no-real>
SeedUsers__SupportEmail=
SeedUsers__SupportFullName=Administrador Soporte
```

No subir contraseñas reales al repositorio.

### Refresh tokens

Los refresh tokens se persisten en `AppRefreshTokens` como hash SHA-256 (`TokenHash`), nunca en texto plano, con expiración y campo opcional `RevokedAt` preparado para revocación futura.

### Auditoría

`CreatedById` y `UpdatedById` de entidades comerciales se relacionan opcionalmente con `AppUsers` mediante FKs nullable y `DeleteBehavior.NoAction`. Las requests públicas pueden dejar auditoría de usuario en `null`.

### Migración auth/auditoría generada y revisada

La migración `AddAuthUsersAndAuditRelations` fue generada localmente con el commit `5b30b07 Add auth users and audit relations migration`. Comando usado para crear la migración:

```bash
dotnet ef migrations add AddAuthUsersAndAuditRelations \
  --project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj \
  --startup-project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj \
  --output-dir Data/Migrations
```

Comando usado para generar el script SQL revisable:

```bash
dotnet ef migrations script \
  --project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj \
  --startup-project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj \
  -o backend-dotnet/sql/AddAuthUsersAndAuditRelations.sql
```

> Advertencia: no ejecutar `dotnet ef database update` contra SQL Server real/Plesk y no aplicar SQL sin backup verificado, revisión del script, confirmación del estado de `__EFMigrationsHistory`, ventana de mantenimiento y aprobación explícita. Si la base ya tiene aplicada `InitialCommercialSchema`, generar/revisar un script diferencial en vez de ejecutar un script acumulado desde cero.

Antes de producción configurar `Jwt__Secret`/`JWT_SECRET` fuera del repo y definir si `SeedUsers__SellerPassword` y `SeedUsers__SupportPassword` se usarán para crear usuarios iniciales por seed controlado o si se crearán por un procedimiento separado seguro. No subir contraseñas reales ni connection strings reales al repositorio.

## Advertencia Plesk/SQL Server: errores parciales de aplicación SQL

Si la aplicación manual de un script SQL falla en Plesk/SQL Server, detenerse antes de reintentar. Revisar siempre:

- base actual (`DB_NAME()`),
- tablas existentes,
- contenido de `__EFMigrationsHistory`,
- existencia real de tablas esperadas mediante `OBJECT_ID` o `INFORMATION_SCHEMA.TABLES`.

No confiar solo en `__EFMigrationsHistory` si hubo un error parcial: un script acumulado puede haber insertado filas de historial aunque la creación del schema haya quedado incompleta. En ese caso, limpiar o restaurar la base antes de aplicar un script corregido; no reejecutar a ciegas el script anterior.
