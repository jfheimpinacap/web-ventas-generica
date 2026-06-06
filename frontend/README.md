# Frontend React/Vite

## Configuración controlada de API

El frontend no tiene hardcodeada la API productiva en componentes. La URL y el proveedor se controlan con variables Vite:

```env
# API Django local actual
VITE_API_BASE_URL=http://localhost:8000
VITE_API_PROVIDER=django

# API .NET Plesk, activar manualmente cuando corresponda
# VITE_API_BASE_URL=https://api.jem-nexus.cl
# VITE_API_PROVIDER=dotnet
```

`VITE_API_BASE_URL` puede apuntar al origen del backend o mantener `/api` por compatibilidad con configuraciones anteriores. `VITE_API_PROVIDER` acepta `django` o `dotnet` y permite ajustar diferencias controladas como trailing slash y health check.

## Health check

El servicio `src/services/healthApi.ts` permite probar la API configurada sin mostrar secretos:

- `django`: usa `/api/health/` cuando la base no incluye `/api`.
- `dotnet`: usa `/health` contra la base configurada.

## Autenticación

`src/services/authApi.ts` normaliza respuestas de login Django/.NET y acepta `access`, `accessToken`, `access_token` o `token` para el access token, además de `refresh`, `refreshToken` o `refresh_token` para refresh. Las llamadas autenticadas usan Bearer token.
