# JEM Nexus ASP.NET Core API

Proyecto base de la migración del backend de JEM Nexus a ASP.NET Core Web API (.NET 8), preparado para Windows Server + IIS + Plesk.

> Esta fase no conecta SQL Server, no migra modelos, no agrega autenticación y no reemplaza el backend Django existente.

## Estructura

```text
backend-dotnet/
  JemNexus.sln
  JemNexus.Api/
  JemNexus.Api.Tests/
```

## Desarrollo local

```bash
dotnet restore backend-dotnet/JemNexus.sln
dotnet run --project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj
```

Endpoints mínimos:

- `GET /`
- `GET /health`
- `GET /api/health`
- `GET /api/health/`

Todos responden JSON con `status`, `app`, `environment` y `timestamp`.

## Tests

```bash
dotnet build backend-dotnet/JemNexus.sln
dotnet test backend-dotnet/JemNexus.sln
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
