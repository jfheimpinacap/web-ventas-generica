# Plan de integración frontend con API .NET en Plesk

## A. Estado actual

- El frontend React/Vite mantiene el flujo actual y no se hizo un corte total hacia la API .NET.
- La API .NET ya está publicada y validada manualmente en Plesk en `https://api.jem-nexus.cl` según el hito post-deploy documentado.
- El backend Django sigue existiendo y no fue eliminado ni reemplazado.
- El frontend público todavía no queda forzado a usar la API .NET; la selección se controla por variables de entorno Vite.
- No se conectó a Plesk, no se ejecutó SQL real y no se aplicaron migraciones desde este workspace.

## B. Variables frontend

El frontend usa variables Vite seguras, sin secretos, para decidir el backend objetivo:

| Variable            | Uso                                                                                                                                                         | Valores esperados                                                                |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `VITE_API_BASE_URL` | URL base del backend configurado. Puede incluir `/api` por compatibilidad con configuraciones anteriores, pero se recomienda apuntar al origen del backend. | `http://localhost:8000`, `http://127.0.0.1:8001/api`, `https://api.jem-nexus.cl` |
| `VITE_API_PROVIDER` | Selector controlado de proveedor para pequeñas diferencias de rutas, principalmente health y trailing slash.                                                | `django`, `dotnet`                                                               |

Ejemplo Django local actual:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_PROVIDER=django
```

Ejemplo API .NET en Plesk, para activar manualmente cuando corresponda:

```env
VITE_API_BASE_URL=https://api.jem-nexus.cl
VITE_API_PROVIDER=dotnet
```

La configuración de ejemplo vive en `frontend/.env.example`. Para cambiar la API no se debe tocar código: se debe crear o actualizar el `.env` correspondiente del entorno de ejecución/build.

## C. Auth

La API .NET validada en Plesk responde al login con esta forma:

```json
{
  "access": "...",
  "refresh": "...",
  "user": {}
}
```

El frontend normaliza respuestas de autenticación hacia una forma interna estable:

```ts
{
  ;(accessToken, refreshToken, user)
}
```

La normalización acepta las variantes de access token `access`, `accessToken`, `access_token` y `token`, además de las variantes de refresh token `refresh`, `refreshToken` y `refresh_token`. Los tokens se siguen guardando en `localStorage` con las claves internas existentes para no romper el flujo actual.

Las llamadas autenticadas usan `Authorization: Bearer <accessToken>`. Esto permite validar `/api/auth/me` contra la API .NET cuando `VITE_API_PROVIDER=dotnet` y `VITE_API_BASE_URL=https://api.jem-nexus.cl`, sin imprimir tokens en consola ni registrar secretos.

## D. Estrategia de migración por fases

### Fase 1: base controlada

- Preparar el cliente API centralizado y variables de entorno.
- Validar health contra la API configurada.
- Validar login contra .NET en un entorno controlado.
- Mantener Django disponible durante la verificación.

### Fase 2: login y panel vendedor

- Migrar login y `/api/auth/me` de forma controlada.
- Validar roles `seller` y `support_admin` con usuarios reales ya rotados o reemplazados.
- Confirmar CORS desde el dominio real del frontend.

### Fase 3: catálogo público y endpoints comerciales

- Migrar gradualmente productos, categorías, marcas, proveedores, promociones, secciones de home y cotizaciones.
- Mantener compatibilidad de payloads o adaptar servicios por endpoint.
- Evitar cambios masivos hasta tener smoke tests post-build.

### Fase 4: imágenes y gestión desde panel vendedor

- Implementar o validar subida de imágenes/productos desde el panel vendedor usando API .NET.
- Verificar almacenamiento, URLs públicas, límites de tamaño y permisos.
- Agregar pruebas específicas antes de activar el flujo en producción.

### Fase 5: convivencia o retiro gradual de Django

- Definir si Django queda como backend paralelo temporal o si se retira por etapas.
- Documentar endpoints retirados y fecha de corte.
- Mantener rollback claro mientras existan operaciones comerciales críticas.

## E. Pendientes

- Rotación controlada de credenciales provisorias usadas en validaciones manuales.
- Módulo `support_admin` para reset de contraseña vendedor.
- Carga de imágenes desde panel con API .NET.
- Validación CORS desde el frontend real.
- Smoke test post-build contra el backend configurado.
- SEO/IA SEO posterior, fuera de esta fase.
- Migración controlada de catálogo y cotizaciones cuando la API .NET tenga contratos confirmados para esos flujos.

## Validación controlada desde frontend

La ruta directa `/diagnostico-api` permite validar la API configurada por variables Vite sin cambiar la navegación pública ni migrar catálogo.

1. Crear `frontend/.env.local` manualmente, no versionado:

   ```env
   VITE_API_BASE_URL=https://api.jem-nexus.cl
   VITE_API_PROVIDER=dotnet
   ```

2. Ejecutar:

   ```bash
   cd frontend
   npm run dev
   ```

3. Abrir:

   ```text
   http://localhost:5174/diagnostico-api
   ```

   Si `start.py` o Vite usan otro puerto en el entorno local, abrir la misma ruta en ese puerto.

4. Presionar **Probar health** y confirmar que el proveedor, la base URL y el endpoint resuelto coincidan con la configuración esperada.
5. Probar login con el usuario vendedor validado manualmente en el entorno correspondiente.
6. Presionar **Probar /auth/me** para confirmar que el access token normalizado funciona como Bearer token.
7. Confirmar CORS desde el origen del frontend usado en la prueba.
8. No dejar passwords, tokens ni respuestas sensibles en capturas públicas o registros compartidos.
9. Volver a configuración Django/local cuando corresponda:

   ```env
   VITE_API_BASE_URL=http://127.0.0.1:8001/api
   VITE_API_PROVIDER=django
   ```

Esta validación no conecta a Plesk desde Codex, no ejecuta SQL, no aplica migraciones, no crea usuarios reales y no publica cambios. Tampoco hace corte total del frontend a .NET ni migra catálogo.

## Migración controlada del login real

- El login real de `/login` usa el servicio centralizado `authApi`, por lo que la URL base y el proveedor salen de `VITE_API_BASE_URL` y `VITE_API_PROVIDER` en lugar de quedar hardcodeados en componentes.
- El modo Django/local sigue disponible con `VITE_API_PROVIDER=django`; el modo .NET se activa de forma explícita con `VITE_API_PROVIDER=dotnet` y una base como `https://api.jem-nexus.cl`.
- La respuesta del login se normaliza internamente a `{ accessToken, refreshToken, user }`, aceptando la forma .NET `{ access, refresh, user }` y las variantes históricas de Django (`accessToken`, `access_token`, `token`, `refreshToken`, `refresh_token`).
- Los tokens del login real sí se guardan según el flujo normal del panel vendedor, usando las claves históricas de `localStorage` (`ventas_access_token` y `ventas_refresh_token`). No se guardan passwords ni se muestran tokens.
- El usuario actual del flujo real se valida con `/auth/me` usando `Authorization: Bearer <accessToken>` mediante `authApi`, con normalización de campos Django/.NET como `first_name`/`firstName`, `is_staff`/`isStaff` y `role`/`userRole`.
- El guard del panel vendedor mantiene bloqueo para usuarios anónimos y valida que el usuario autenticado pueda operar como vendedor/staff/superuser o tenga rol compatible (`seller`, `support_admin`, `admin`, `staff`).
- La pantalla `/diagnostico-api` sigue separada: usa las mismas utilidades de login y `/auth/me`, pero conserva el token solo en memoria del componente y no toca `localStorage`.
- El catálogo público y los servicios comerciales todavía no fueron migrados a .NET; el panel vendedor queda como siguiente validación funcional manual antes de avanzar con productos, categorías, marcas, proveedores, promociones, imágenes o cotizaciones.

## Migración controlada de lectura del panel vendedor

### Alcance aplicado

- Se prepararon los servicios de lectura del panel vendedor para usar el cliente centralizado, `VITE_API_BASE_URL`, `VITE_API_PROVIDER` y `authFetch` con Bearer token.
- Los listados revisados/preparados son productos, categorías, marcas, proveedores, promociones/ofertas Hero, cotizaciones y secciones administrables de Home.
- No se implementó escritura .NET nueva: crear, editar, eliminar, cambiar estado, subir imágenes y editar especificaciones siguen como flujos existentes/pendientes según el backend configurado.
- El catálogo público no fue migrado en esta fase; solo se tocaron helpers compartidos de API y servicios admin.

### Endpoints Django usados por listados admin

| Listado                 | Endpoint actual        | Parámetros detectados                                                                                                                                              |
| ----------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Productos               | `/products/`           | `include_unpublished`, `search` local en página, filtros locales por categoría/marca/tipo/condición/stock/publicación; Home envía `product_type` e `is_published`. |
| Categorías              | `/categories/`         | `include_inactive`.                                                                                                                                                |
| Marcas                  | `/brands/`             | `include_inactive`.                                                                                                                                                |
| Proveedores             | `/suppliers/`          | `include_inactive`.                                                                                                                                                |
| Promociones Hero legacy | `/promotions/`         | `include_inactive`.                                                                                                                                                |
| Cotizaciones            | `/quote-requests/`     | `status`, `search`, `ordering`, `product` soportado por servicio.                                                                                                  |
| Home section admin      | `/home-section-items/` | `include_inactive`, `section`; además lee productos disponibles por sección desde `/products/`.                                                                    |

### Endpoints .NET detectados

La revisión de `backend-dotnet/JemNexus.Api/Program.cs` detectó endpoints reales para:

- `GET /`, `GET /health`, `GET /api/health`.
- `POST /api/auth/login`.
- `POST /api/auth/refresh`.
- `GET /api/auth/me`.

No se detectaron controladores ni endpoints Minimal API reales para estos listados comerciales en la API .NET actual:

- `GET /api/products`.
- `GET /api/categories`.
- `GET /api/brands`.
- `GET /api/suppliers`.
- `GET /api/promotions`.
- `GET /api/quote-requests`.
- `GET /api/home-section-items`.

Por eso, con `VITE_API_PROVIDER=dotnet`, el frontend queda preparado para consumir esos paths cuando existan, pero mostrará un mensaje claro de endpoint pendiente si la API responde `404` o `501`. Con `VITE_API_PROVIDER=django`, los listados conservan compatibilidad con Django/local.

### Normalización de shapes

Los adaptadores admin normalizan respuestas de lista como arreglo directo o contenedores `{ results }`, `{ items }` y `{ data }`. También normalizan diferencias esperadas entre Django y .NET, principalmente:

- Campos `snake_case` Django y `camelCase` .NET (`is_active`/`isActive`, `created_at`/`createdAt`, `product_type`/`productType`, etc.).
- Relaciones anidadas de producto, categoría, marca, proveedor y producto de cotización.
- Imágenes principales de producto desde `main_image`/`mainImage` o desde la colección `images`.
- Fechas y campos opcionales nulos para mantener un shape interno estable en las páginas admin.

### Manejo seguro de errores

El helper central de errores del frontend entrega mensajes seguros para:

- `401`: sesión expirada/no válida.
- `403`: acceso no autorizado.
- `404` con proveedor .NET: endpoint pendiente para este listado.
- `501`: endpoint pendiente de implementación.
- errores de red/CORS: revisar URL configurada, CORS o conectividad.
- `5xx`: error interno seguro sin exponer stack traces, tokens ni headers.

### Pendientes explícitos

- Implementar endpoints comerciales de lectura en .NET antes de validar datos reales de productos, categorías, marcas, proveedores, promociones, cotizaciones y Home section contra `https://api.jem-nexus.cl`.
- Migrar escritura del panel vendedor solo en una fase posterior y con contratos .NET confirmados.
- Implementar carga real de imágenes en una fase posterior.
- Migrar catálogo público en una fase posterior; esta fase no cambia el comportamiento público de catálogo.
