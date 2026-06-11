# JEM Nexus ASP.NET Core API

Proyecto base de la migración del backend de JEM Nexus a ASP.NET Core Web API (.NET 8), preparado para Windows Server + IIS + Plesk.

> Este proyecto prepara la migración del backend a ASP.NET Core/SQL Server. La fase Backend .NET 3 ya agrega autenticación JWT base y auditoría hacia `AppUsers`; el schema corregido quedó aplicado en Plesk/SQL Server, pero la API .NET todavía no está publicada ni reemplaza el backend Django existente.

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

Los tests incluyen endpoints mínimos de health, validaciones de metadata del modelo comercial EF Core, autenticación/seed inicial de usuarios y timestamps de auditoría.

Los tests que usan EF Core InMemory mantienen bases aisladas por test/factory con nombres y `InMemoryDatabaseRoot` únicos. La configuración test-only deja que EF Core construya su provider interno para cada configuración; no se comparte `UseInternalServiceProvider` entre bases InMemory distintas. Para ese aislamiento intencional se ignora únicamente `ManyServiceProvidersCreatedWarning` dentro del helper de tests, sin afectar la configuración productiva ni el seed productivo.

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

Antes de aplicar SQL en `<SQL_DATABASE>`, revisar y seguir el checklist `../docs/PLAN_APLICACION_SCHEMA_PLESK_SQLSERVER.md`. El flujo correcto es:

1. Diagnosticar primero el estado real de la base con queries de solo lectura.
2. Revisar `__EFMigrationsHistory` y confirmar si existen tablas comerciales o auth.
3. Elegir el script correcto según el estado detectado: acumulado desde cero para base vacía, o diferencial si `InitialCommercialSchema` ya está aplicado.
4. Nunca ejecutar `dotnet ef database update` directamente contra producción/Plesk.
5. No guardar credenciales reales, cadenas de conexión completas ni secretos JWT en archivos versionados.

`backend-dotnet/sql/AddAuthUsersAndAuditRelations.sql` es acumulado desde cero. Si la base ya tiene `InitialCommercialSchema`, se debe generar/revisar `backend-dotnet/sql/FromInitialCommercialSchemaToAddAuthUsersAndAuditRelations.sql` antes de aplicar cambios.

## Estado Plesk SQL Server

El schema ASP.NET Core / EF Core quedó aplicado correctamente en Plesk SQL Server sobre `<SQL_DATABASE>`. Las tablas fueron creadas bajo el esquema real `<SQL_SCHEMA_NAME>` y `__EFMigrationsHistory` registra `20260603182917_InitialCommercialSchema` y `20260604020543_AddAuthUsersAndAuditRelations`.

No ejecutar nuevamente `backend-dotnet/sql/AddAuthUsersAndAuditRelations.sql` sobre la misma base sin revisar antes `__EFMigrationsHistory` y la existencia real de tablas. El script es acumulado desde cero y puede fallar o duplicar objetos si se usa sobre una base ya aplicada.

Antes de publicar la API en Plesk/IIS, configurar fuera del repositorio y sin secretos reales en git:

- `ConnectionStrings__DefaultConnection`
- `Jwt__Secret` o `JWT_SECRET`
- `Jwt__Issuer`
- `Jwt__Audience`
- `SeedUsers__SellerUsername`
- `SeedUsers__SellerPassword`
- `SeedUsers__SupportUsername`
- `SeedUsers__SupportPassword`
- `SeedUsers__UpdateExistingPasswords` solo para reset controlado temporal
- `FRONTEND_ORIGINS`

No crear usuarios reales ni iniciar la API productiva hasta que estas variables estén configuradas y exista un plan de publicación/rollback controlado.

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

Para despliegue manual en Plesk, no subir la carpeta publicada completa con wildcard. Generar el ZIP seguro con `backend-dotnet/scripts/package-plesk.ps1`, que excluye `web.config` por defecto para conservar las variables productivas configuradas en Plesk/IIS.

`package-plesk.ps1` está ajustado para Windows PowerShell 5.1 y PowerShell moderno: carga explícitamente `System.IO.Compression` y `System.IO.Compression.FileSystem`, resuelve rutas absolutas desde la ubicación del script y valida automáticamente que el ZIP normal no contenga `web.config` y sí contenga los artefactos principales de `JemNexus.Api`. Ya no es necesario inspeccionar manualmente con rutas relativas, aunque se puede hacer un doble chequeo con ruta absoluta:

```powershell
$zip = "C:\Users\Franz\desktop\web-ventas-generica\backend-dotnet\publish\JemNexus.Api-plesk.zip"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::OpenRead($zip).Entries | Select-Object FullName | Sort-Object FullName
```

### Artefacto local `backend-dotnet/publish/`

`backend-dotnet/publish/` es un artefacto local de despliegue generado por el publish de .NET. No se versiona en Git: su contenido se comprime o sube manualmente a Plesk y debe permanecer fuera de commits y pull requests.

Para regenerar el paquete local desde Windows PowerShell, ejecutar desde la raíz del repo:

```powershell
.\backend-dotnet\scripts\publish-plesk.ps1
```

Antes de preparar cualquier commit, revisar `git status --short` y evitar `git add .` sin verificar que no se estén incluyendo artefactos locales, binarios publicados ni secretos.

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

`FRONTEND_ORIGINS` puede contener orígenes separados por coma o punto y coma y se combina con `Cors:AllowedOrigins`. Para rotar credenciales expuestas manualmente, seguir `docs/ROTACION_CREDENCIALES_PRODUCCION.md`.

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

Antes de producción configurar `Jwt__Secret`/`JWT_SECRET` fuera del repo. El seed controlado de usuarios iniciales se ejecuta al arranque, también en `Production`, cuando existen pares completos no vacíos:

- Seller: `SeedUsers__SellerUsername` o `SeedUsers:SellerUsername`, junto con `SeedUsers__SellerPassword` o `SeedUsers:SellerPassword`.
- Support: `SeedUsers__SupportUsername` o `SeedUsers:SupportUsername`, junto con `SeedUsers__SupportPassword` o `SeedUsers:SupportPassword`.

El seed no ejecuta migraciones, no cambia el schema, normaliza `Username` con `Trim`, usa el hasher del backend que valida `/api/auth/login`, asigna `IsActive=true`, `IsStaff=true` e `IsSuperuser=false`, y crea roles `seller`/`support_admin` según corresponda. Es idempotente por defecto: si el `Username` ya existe, no duplica el usuario y no sobrescribe `PasswordHash`. Para resetear passwords existentes de forma controlada, configurar temporalmente `SeedUsers__UpdateExistingPasswords=true` o `SeedUsers:UpdateExistingPasswords=true` junto con el username/password correspondiente, reiniciar, validar login y luego volver a `false` o remover la bandera y las seed passwords.

Los logs esperados son seguros y no muestran passwords ni hashes: `SeedUsers seller skipped: missing username/password.`, `SeedUsers seller already exists.`, `SeedUsers seller created.`, `SeedUsers seller password updated.`, y equivalentes para `support`. Para verificar en SQL sin exponer secretos:

```sql
SELECT Username, Role, IsActive, IsStaff, IsSuperuser, CreatedAt, UpdatedAt
FROM <SQL_SCHEMA_NAME>.AppUsers
ORDER BY Username;
```

No insertar usuarios manualmente por SQL porque `PasswordHash` debe ser generado por la lógica del backend. No subir contraseñas reales ni connection strings reales al repositorio.

## Advertencia Plesk/SQL Server: errores parciales de aplicación SQL

Si la aplicación manual de un script SQL falla en Plesk/SQL Server, detenerse antes de reintentar. Revisar siempre:

- base actual (`DB_NAME()`),
- tablas existentes,
- contenido de `__EFMigrationsHistory`,
- existencia real de tablas esperadas mediante `OBJECT_ID` o `INFORMATION_SCHEMA.TABLES`.

No confiar solo en `__EFMigrationsHistory` si hubo un error parcial: un script acumulado puede haber insertado filas de historial aunque la creación del schema haya quedado incompleta. En ese caso, limpiar o restaurar la base antes de aplicar un script corregido; no reejecutar a ciegas el script anterior.

## Publicación controlada API .NET en Plesk/IIS

El plan operativo para preparar la publicación manual de la API ASP.NET Core en `https://api.jem-nexus.cl` está documentado en `docs/PLAN_PUBLICACION_API_DOTNET_PLESK.md`.

Puntos obligatorios antes de publicar:

- No ejecutar `dotnet ef database update` contra Plesk/SQL Server durante la publicación.
- No aplicar SQL ni migraciones como parte de este paso; el schema ya fue aplicado previamente.
- No incluir secretos reales, passwords, JWT secrets ni connection strings con password real en git.
- No cambiar todavía el frontend para consumir la API .NET.
- Respaldar la carpeta actual del subdominio antes de reemplazar archivos.

Variables de ejemplo sin secretos reales:

- `backend-dotnet/env.plesk.example.txt`.

Scripts locales seguros de publicación y empaquetado:

```powershell
backend-dotnet\scripts\publish-plesk.ps1
backend-dotnet\scripts\package-plesk.ps1
```

El script `publish-plesk.ps1` ejecuta restore, build, test y publish localmente; falla si los tests fallan y deja la salida en `backend-dotnet\publish\JemNexus.Api`. Luego `package-plesk.ps1` crea `backend-dotnet\publish\JemNexus.Api-plesk.zip` excluyendo `web.config` por defecto para no sobrescribir las variables productivas de Plesk. `package-plesk.ps1` carga explícitamente los assemblies de compresión requeridos por Windows PowerShell 5.1 y valida automáticamente el contenido mínimo y la ausencia de `web.config` cuando no se usa `-IncludeWebConfig`. Los scripts no conectan a Plesk, no suben archivos, no ejecutan SQL y no ejecutan `dotnet ef database update`.

Comandos equivalentes en Windows PowerShell:

```powershell
dotnet restore backend-dotnet\JemNexus.sln
dotnet build backend-dotnet\JemNexus.sln -c Release
dotnet test backend-dotnet\JemNexus.sln -c Release

dotnet publish backend-dotnet\JemNexus.Api\JemNexus.Api.csproj `
  -c Release `
  -o backend-dotnet\publish\JemNexus.Api
```

La carpeta `backend-dotnet\publish\JemNexus.Api` es la que debe comprimirse/subirse manualmente al subdominio de API en Plesk después de configurar variables de entorno fuera del repositorio.

## Estado Plesk

Estado confirmado el `2026-06-06`:

- API publicada en `https://api.jem-nexus.cl` sobre Plesk Windows/IIS.
- Endpoints de health validados:
  - `GET https://api.jem-nexus.cl/health`.
  - `GET https://api.jem-nexus.cl/api/health`.
- Login y autenticación Bearer validados:
  - `POST https://api.jem-nexus.cl/api/auth/login`.
  - `GET https://api.jem-nexus.cl/api/auth/me`.
- Las variables, connection strings y secretos productivos se administran fuera del repositorio en Plesk/IIS.
- `backend-dotnet/publish/` es un artefacto local de despliegue y no se versiona.
- Los stdout logs deben habilitarse solo temporalmente para diagnóstico; `stdoutLogEnabled` debe quedar en `false` después de revisar incidentes.
- Las contraseñas provisorias usadas durante pruebas manuales deben rotarse si fueron expuestas en pantallas, chat, capturas o tickets.

## Endpoints comerciales read-only para panel vendedor

La API .NET expone endpoints comerciales de lectura bajo `/api` para validar listados del panel vendedor con Bearer token:

- `GET /api/products/` y `GET /api/products/{id-or-slug}/`
- `GET /api/categories/` y `GET /api/categories/{id}/`
- `GET /api/brands/` y `GET /api/brands/{id}/`
- `GET /api/suppliers/` y `GET /api/suppliers/{id}/`
- `GET /api/promotions/` y `GET /api/promotions/{id}/`
- `GET /api/quote-requests/` y `GET /api/quote-requests/{id}/`
- `GET /api/home-section-items/` y `GET /api/home-section-items/{id}/`
- `GET /api/product-images/` y `GET /api/product-images/{id}/`
- `GET /api/product-specs/` y `GET /api/product-specs/{id}/`

Todos estos endpoints son solo lectura y requieren `Authorization: Bearer <access>`. La identidad debe tener rol `seller`, rol `support_admin`, `is_staff=true` o `is_superuser=true`.

Ejemplo de prueba manual controlada, sin registrar tokens en logs compartidos:

```bash
curl -H "Authorization: Bearer <access>" https://api.jem-nexus.cl/api/products/
```

Filtros principales:

- Productos: `search`, `category`, `brand`, `product_type`, `condition`, `stock_status`, `is_featured`, `is_published`, `include_unpublished`, `ordering`.
- Categorías/marcas/proveedores/promociones: `search`, `is_active`, `include_inactive`.
- Cotizaciones: `search`, `status`, `product`, `ordering`.
- Home sections: `section`, `is_active`, `include_inactive`.
- Imágenes/especificaciones: `product`.

No se implementan escrituras comerciales, eliminación, cambios de estado ni subida real de imágenes en esta fase. No ejecutar `dotnet ef database update` contra producción: los cambios son endpoints/DTOs/tests y documentación, sin schema changes. La siguiente fase recomendada es validar los listados del frontend/panel vendedor contra la API publicada y recién después planificar escritura y uploads.


## Publicación read-only Prompt 022

Para publicar en Plesk los endpoints comerciales read-only agregados en el Prompt 021, usar la guía operativa `../docs/PUBLICACION_API_DOTNET_READONLY_PLESK.md`.

Flujo de generación local desde Windows PowerShell, siempre desde la raíz del repo:

```powershell
cd C:\Users\Franz\desktop\web-ventas-generica

.\backend-dotnet\scripts\publish-plesk.ps1
.\backend-dotnet\scripts\package-plesk.ps1
```

Esta publicación es solo de archivos por ZIP manual en Plesk usando el ZIP seguro que no incluye `web.config`. `package-plesk.ps1 -IncludeWebConfig` existe solo como opción excepcional y peligrosa; no usarla en publicaciones normales. No agrega escritura comercial, no agrega uploads reales, no requiere migraciones SQL porque el Prompt 021 no modificó modelos persistidos, `JemNexusDbContext` ni migraciones EF Core, y no debe ejecutarse `dotnet ef database update` contra producción.


## Rotación y resguardo de secretos

Ver `docs/ROTACION_CREDENCIALES_PRODUCCION.md` para la rotación manual segura de JWT, usuarios seed y contraseña SQL. `backend-dotnet/scripts/package-plesk.ps1` excluye `web.config`; el `web.config` productivo se administra manualmente en Plesk, no se commitea y no debe compartirse en capturas completas.

## Escritura comercial controlada del panel vendedor

La API .NET expone una primera capa de escritura comercial para el panel vendedor, protegida por Bearer token y por la política `RequireCommercialWrite`.

### Endpoints write disponibles

- `POST /api/categories/`, `PUT/PATCH /api/categories/{id}/`, `DELETE /api/categories/{id}/`.
- `POST /api/brands/`, `PUT/PATCH /api/brands/{id}/`, `DELETE /api/brands/{id}/`.
- `POST /api/suppliers/`, `PUT/PATCH /api/suppliers/{id}/`, `DELETE /api/suppliers/{id}/`.
- `POST /api/promotions/`, `PUT/PATCH /api/promotions/{id}/`, `DELETE /api/promotions/{id}/`.
- `POST /api/products/`, `PUT/PATCH /api/products/{idOrSlug}/`, `DELETE /api/products/{idOrSlug}/` para datos base sin upload.
- `POST /api/product-specs/`, `PUT/PATCH /api/product-specs/{id}/`, `DELETE /api/product-specs/{id}/`.
- `PATCH /api/quote-requests/{id}/` para `status`, `internal_notes` y `seller_response`.
- `POST /api/home-section-items/`, `PUT/PATCH /api/home-section-items/{id}/`, `DELETE /api/home-section-items/{id}/`.

`ProductImage` permanece read-only en esta fase; no hay endpoints multipart ni carga binaria real de imágenes.

### Autorización

`RequireCommercialWrite` requiere Bearer válido y autoriza únicamente:

- rol `seller`;
- rol `support_admin`;
- claim `is_staff=true`;
- claim `is_superuser=true`.

Las lecturas comerciales siguen protegidas por `RequireCommercialRead`. No abrir endpoints write sin token.

### Prueba manual con Bearer

1. Obtener token con login:

   ```bash
   curl -s -X POST "$API_BASE/api/auth/login/" \
     -H "Content-Type: application/json" \
     -d '{"username":"<usuario>","password":"<password>"}'
   ```

2. Usar el `access` devuelto para una escritura controlada:

   ```bash
   curl -i -X POST "$API_BASE/api/categories/" \
     -H "Authorization: Bearer <access>" \
     -H "Content-Type: application/json" \
     -d '{"name":"Categoría demo","is_active":true,"order":10}'
   ```

No imprimir ni commitear tokens, passwords, connection strings ni headers `Authorization` reales.

### Producción y publicación segura

No ejecutar `dotnet ef database update` contra producción sin autorización explícita, backup validado y ventana de mantenimiento. Esta fase no requiere migraciones nuevas ni cambios de schema.

Para publicación futura en Plesk, usar el flujo existente con ZIP seguro:

```powershell
./publish-plesk.ps1
./package-plesk.ps1
```

No usar `Compress-Archive` manual con wildcard y no incluir `web.config` productivo real en el ZIP.
