# JEM Nexus

Aplicación web de ventas con un único backend vigente: **ASP.NET Core Web API .NET 8**, persistencia mediante **Entity Framework Core y SQL Server**, y frontend **React + Vite + TypeScript**.

Django fue retirado del código versionado en el Prompt 103. `docs/` conserva auditorías, planes de migración y registros históricos que pueden mencionarlo, pero no constituyen configuración ni dependencias ejecutables actuales.

## Estructura

- `backend-dotnet/`: solución .NET 8, API y tests.
- `frontend/`: aplicación React/Vite.
- `docs/`: trazabilidad técnica e histórica.

Para detalles técnicos, seguridad, publicación y operación de la API, consulta [`backend-dotnet/README.md`](backend-dotnet/README.md).

## Desarrollo local

### Backend

En PowerShell:

```powershell
cd "C:\Users\Franz\Desktop\web-ventas-generica\backend-dotnet"
.\run-local.ps1
```

El backend local canónico queda en `http://localhost:5000`.

Solo durante la primera preparación controlada de la base local, cuando corresponda:

```powershell
cd "C:\Users\Franz\Desktop\web-ventas-generica\backend-dotnet"
.\run-local.ps1 -UpdateDatabase
```

`-UpdateDatabase` está protegido para actuar exclusivamente sobre `(localdb)\MSSQLLocalDB` y la base `JemNexus_Local`. No debe usarse contra producción.

### Frontend

En otra PowerShell:

```powershell
cd "C:\Users\Franz\Desktop\web-ventas-generica\frontend"
npm run dev
```

El frontend local queda en `http://localhost:5174`.

Variables Vite disponibles en `frontend/.env.example`:

- `VITE_API_BASE_URL=http://localhost:5000`
- `VITE_WHATSAPP_NUMBER`
- `VITE_PUBLIC_SITE_URL=http://localhost:5174`
- `VITE_GTM_ID`

## Validaciones

```powershell
dotnet restore .\backend-dotnet\JemNexus.sln
dotnet build .\backend-dotnet\JemNexus.sln --no-restore
dotnet test .\backend-dotnet\JemNexus.sln --no-build --no-restore
```

```powershell
cd .\frontend
npm run build
```

## Producción y seguridad

El frontend y la API .NET se publican en Plesk/IIS conforme a las guías vigentes. No se deben guardar credenciales, tokens, cadenas de conexión reales ni archivos locales de entorno en Git.
