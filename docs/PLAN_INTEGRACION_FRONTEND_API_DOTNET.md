# Plan de integración controlada Frontend/API .NET

## A. Estado actual

- El frontend React/Vite todavía conserva el flujo actual y no hace un corte total hacia ASP.NET Core.
- La API .NET ya está publicada y validada manualmente en `https://api.jem-nexus.cl`.
- El backend Django sigue existiendo y no fue eliminado ni reemplazado.
- No se ha hecho una migración total del catálogo, panel vendedor ni endpoints comerciales.
- No se debe conectar Codex a Plesk, subir archivos, ejecutar SQL real, ejecutar `dotnet ef database update`, crear usuarios reales ni guardar secretos reales en el repositorio.

## B. Variables frontend

El frontend usa variables Vite para seleccionar la API de manera controlada:

| Variable | Uso |
| --- | --- |
| `VITE_API_BASE_URL` | Origen/base configurada de la API. Puede incluir `/api` por compatibilidad, aunque se recomienda usar solo el origen. |
| `VITE_API_PROVIDER` | Proveedor activo: `django` o `dotnet`. Controla compatibilidad de rutas y health check. |

Ejemplo Django local actual:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_PROVIDER=django
```

Ejemplo API .NET Plesk, activación manual cuando corresponda:

```env
VITE_API_BASE_URL=https://api.jem-nexus.cl
VITE_API_PROVIDER=dotnet
```

El cliente central agrega `/api` para llamadas funcionales cuando `VITE_API_BASE_URL` no lo incluye, evitando hardcodear dominios productivos en componentes.

## C. Auth

La API .NET validada devuelve login con esta forma:

```json
{
  "access": "...",
  "refresh": "...",
  "user": {}
}
```

El frontend normaliza respuestas Django/.NET hacia una forma interna estable:

```ts
{
  accessToken,
  refreshToken,
  user
}
```

Campos aceptados para access token:

- `access`
- `accessToken`
- `access_token`
- `token`

Campos aceptados para refresh token:

- `refresh`
- `refreshToken`
- `refresh_token`

El token de access se envía como `Authorization: Bearer <token>` para endpoints protegidos como `/api/auth/me`. No se deben imprimir tokens en consola ni registrarlos en logs.

## D. Estrategia de migración por fases

### Fase 1

- Preparar cliente API y variables de entorno.
- Validar health contra la API configurada.
- Validar login contra .NET en un entorno controlado.

### Fase 2

- Migrar login y panel vendedor de forma controlada.
- Confirmar compatibilidad de roles `seller` y `support_admin` con las vistas existentes.
- Validar expiración/refresh de tokens antes de exponer uso real.

### Fase 3

- Migrar catálogo público o endpoints comerciales por grupos pequeños.
- Comparar contratos JSON de productos, categorías, marcas, promociones y cotizaciones.
- Mantener fallback o ventana de rollback mientras Django siga disponible.

### Fase 4

- Subir imágenes/productos desde panel vendedor usando API .NET.
- Validar multipart/form-data, límites de tamaño, extensiones permitidas y almacenamiento definitivo.

### Fase 5

- Definir convivencia o retiro gradual de Django.
- Documentar corte final, rollback y monitoreo posterior.

## E. Pendientes

- Rotación controlada de credenciales provisorias.
- Módulo `support_admin` para reset de contraseña vendedor.
- Carga de imágenes desde panel.
- Validación CORS desde el frontend real.
- Smoke test post-build.
- SEO/IA SEO posterior.

## Health check desde frontend

No se agregó una UI de diagnóstico grande en esta fase. Para probar desde una pantalla futura o desde código temporal controlado, usar:

```ts
import { checkApiHealth } from './services/api'

const result = await checkApiHealth()
```

El helper devuelve proveedor configurado, base API configurada, URL de health, status HTTP y payload. No muestra secretos.

## Endpoints comerciales pendientes

La migración del catálogo no se ejecuta todavía. Permanecen pendientes de comparar/migrar los contratos de:

- Productos y detalle de producto.
- Categorías, marcas y proveedores.
- Promociones y secciones del home.
- Cotizaciones públicas y administración de cotizaciones.
- CRUD completo del panel vendedor.
