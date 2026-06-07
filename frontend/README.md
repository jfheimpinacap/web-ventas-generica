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

## Probar login real contra API .NET

El login real del panel vendedor está en:

```text
/login
```

Para probarlo manualmente contra la API .NET, crear `frontend/.env.local` localmente (no commitear):

```env
VITE_API_BASE_URL=https://api.jem-nexus.cl
VITE_API_PROVIDER=dotnet
```

Luego ejecutar:

```bash
cd frontend
npm run dev
```

Abrir `/login`, iniciar sesión con una cuenta válida del entorno y confirmar el acceso al panel vendedor. El flujo real guarda la sesión con las claves normales del sistema, pero no debe guardar passwords, imprimir tokens en consola ni incluir tokens/passwords en capturas.

La ruta `/diagnostico-api` sigue disponible como apoyo para validar health, login y `/auth/me` con token solo en memoria. Usarla antes o después del login real si se necesita confirmar configuración de `VITE_API_BASE_URL`, `VITE_API_PROVIDER`, CORS o Bearer token sin persistir una sesión diagnóstica.

## Probar lectura del panel vendedor contra API .NET

Para probar la lectura del panel vendedor contra .NET de forma controlada, crear manualmente `frontend/.env.local` (no commitear):

```env
VITE_API_BASE_URL=https://api.jem-nexus.cl
VITE_API_PROVIDER=dotnet
```

Luego ejecutar:

```bash
cd frontend
npm run dev
```

Abrir `/login`, iniciar sesión con un usuario vendedor válido del entorno y navegar por el panel:

- `/admin/productos`
- `/admin/categorias`
- `/admin/marcas`
- `/admin/proveedores`
- `/admin/promociones`
- `/admin/cotizaciones`

Los listados admin usan el cliente API configurable y Bearer token. Si la API .NET aún no tiene un endpoint comercial de lectura, el panel debe mostrar un mensaje claro de endpoint pendiente en lugar de exponer tokens, headers o stack traces.

No commitear `.env.local`, no guardar passwords/tokens en capturas y no usar esta prueba para crear, editar, borrar, subir imágenes ni aplicar cambios reales de datos.
