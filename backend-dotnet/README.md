# JEM Nexus ASP.NET Core API

Proyecto base de la migración del backend de JEM Nexus a ASP.NET Core Web API (.NET 8), preparado para Windows Server + IIS + Plesk.

> Esta fase prepara el modelo comercial EF Core para SQL Server, pero no conecta la base real de Plesk, no agrega autenticación y no reemplaza el backend Django existente.

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

Variables sugeridas para futuras fases, sin valores reales en git:

- `ASPNETCORE_ENVIRONMENT`
- `PUBLIC_SITE_URL`
- `FRONTEND_ORIGINS`
- `JWT_SECRET`
- `ConnectionStrings__DefaultConnection`

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
