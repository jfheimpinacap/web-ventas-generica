# Frontend JEM Nexus

Aplicación React/Vite del sitio público y panel vendedor.

## Configuración de API

El frontend usa variables Vite para elegir la API sin tocar código:

```env
# API Django local actual
VITE_API_BASE_URL=http://localhost:8000
VITE_API_PROVIDER=django

# API .NET Plesk, activar manualmente cuando corresponda
# VITE_API_BASE_URL=https://api.jem-nexus.cl
# VITE_API_PROVIDER=dotnet
```

Notas:

- `VITE_API_BASE_URL` debe apuntar al origen de la API, sin secretos.
- El cliente central agrega el prefijo `/api` para las llamadas funcionales cuando la URL no lo trae incluido, por compatibilidad con configuraciones antiguas como `https://backend.example.com/api`.
- `VITE_API_PROVIDER=django` conserva endpoints con slash final, por ejemplo `/api/auth/login/`.
- `VITE_API_PROVIDER=dotnet` normaliza endpoints sin slash final, por ejemplo `/api/auth/login`.
- Para health check se puede importar `checkApiHealth` desde `src/services/api.ts`; reporta proveedor, URL base configurada, URL de health, status y payload sin exponer secretos.

## Auth controlada Django/.NET

`src/services/authApi.ts` normaliza respuestas de login con cualquiera de estas formas:

- Access: `access`, `accessToken`, `access_token` o `token`.
- Refresh: `refresh`, `refreshToken` o `refresh_token`.
- Usuario: `user` cuando exista.

La forma interna es estable: `accessToken`, `refreshToken` y `user`. Los tokens se siguen guardando en `localStorage` con las claves existentes del panel vendedor.

## Build

```bash
npm run build
```
