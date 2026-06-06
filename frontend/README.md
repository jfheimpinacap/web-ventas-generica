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

## Diagnóstico controlado de API

Existe una ruta directa, sin enlace público principal, para validar la API configurada por variables Vite:

```text
http://localhost:5174/diagnostico-api
```

Uso recomendado para probar la API .NET en Plesk de forma controlada:

1. Crear manualmente `frontend/.env.local` (no versionado):

   ```env
   VITE_API_BASE_URL=https://api.jem-nexus.cl
   VITE_API_PROVIDER=dotnet
   ```

2. Ejecutar el frontend:

   ```bash
   cd frontend
   npm run dev
   ```

3. Abrir `/diagnostico-api` en el puerto Vite del proyecto (`5174` por defecto).
4. Usar **Probar health** para confirmar URL base, proveedor, endpoint resuelto y respuesta de health.
5. Usar **Probar login** con un usuario válido solo para validación manual.
6. Usar **Probar /auth/me** para validar el Bearer token normalizado recibido en memoria.

La pantalla no muestra tokens, passwords ni headers `Authorization` completos. El login diagnóstico mantiene el access token solo en memoria del componente y no reemplaza el flujo normal del sistema.
