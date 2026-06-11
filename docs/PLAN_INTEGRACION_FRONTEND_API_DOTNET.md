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

## Endpoints .NET de lectura comercial

### Alcance implementado

La API ASP.NET Core agrega endpoints comerciales **solo lectura** bajo `/api` para habilitar la validación del panel vendedor con `VITE_API_PROVIDER=dotnet`. Los endpoints aceptan llamadas con y sin slash final por normalización de rutas antes del routing.

Endpoints implementados:

- `GET /api/products/`
- `GET /api/products/{id-or-slug}/`
- `GET /api/categories/`
- `GET /api/categories/{id}/`
- `GET /api/brands/`
- `GET /api/brands/{id}/`
- `GET /api/suppliers/`
- `GET /api/suppliers/{id}/`
- `GET /api/promotions/`
- `GET /api/promotions/{id}/`
- `GET /api/quote-requests/`
- `GET /api/quote-requests/{id}/`
- `GET /api/home-section-items/`
- `GET /api/home-section-items/{id}/`
- `GET /api/product-images/`
- `GET /api/product-images/{id}/`
- `GET /api/product-specs/`
- `GET /api/product-specs/{id}/`

Todos los endpoints anteriores requieren `Authorization: Bearer <access>` y una identidad compatible con panel vendedor/soporte: rol `seller`, rol `support_admin`, claim `is_staff=true` o claim `is_superuser=true`. No se abrió `quote-requests` a público.

Las respuestas son listas directas para listados y objetos directos para detalle. Se mantienen campos `snake_case` por la configuración JSON global de la API .NET, compatible con los normalizadores del frontend.

### Filtros soportados

Productos (`/api/products/`):

- `search`
- `category` por id o slug
- `brand` por id o slug
- `product_type`
- `condition`
- `stock_status`
- `is_featured`
- `is_published`
- `include_unpublished`
- `ordering`: `name`, `-name`, `created_at`, `-created_at`, `updated_at`, `-updated_at`, `price`, `-price`

Categorías, marcas, proveedores y promociones:

- `search`
- `is_active`
- `include_inactive`

Cotizaciones (`/api/quote-requests/`):

- `search`
- `status`
- `product`
- `ordering`: `created_at`, `-created_at`, `updated_at`, `-updated_at`, `status`, `-status`

Home sections (`/api/home-section-items/`):

- `section`
- `is_active`
- `include_inactive`

Imágenes y especificaciones de producto:

- `product`

### Seguridad y datos expuestos

Los DTOs de lectura excluyen `PasswordHash`, hashes de refresh tokens, claims internos no necesarios, connection strings, secretos y cualquier campo de autenticación. Los endpoints de cotizaciones son de administración autenticada y conservan respuesta solo lectura para que el vendedor pueda listar/revisar solicitudes existentes.

### Pendientes fuera de esta fase

- No se implementó `POST`, `PUT`, `PATCH` ni `DELETE` para entidades comerciales.
- No se implementó subida real de imágenes.
- No se migró el catálogo público a endpoints públicos .NET.
- No se cambió el frontend público ni SEO.
- No se aplicaron migraciones productivas, no se ejecutó SQL real y no se ejecutó `dotnet ef database update`.

Siguiente validación recomendada: publicar la API .NET mediante el flujo controlado existente, confirmar Bearer/CORS desde el panel vendedor y probar listados reales con `VITE_API_PROVIDER=dotnet` antes de avanzar a escritura o uploads.


## Validación frontend después de publicar endpoints read-only

Después de publicar la API .NET en Plesk con los endpoints comerciales read-only, validar el panel vendedor localmente con `frontend/.env.local` sin commitearlo:

```dotenv
VITE_API_BASE_URL=https://api.jem-nexus.cl
VITE_API_PROVIDER=dotnet
```

Luego:

```powershell
cd frontend
npm run dev
```

Abrir `http://localhost:5174/login`, iniciar sesión con vendedor y revisar `/admin/productos` y los listados de productos, categorías, marcas, proveedores, promociones, cotizaciones y ofertas Hero section si aplica.

Resultado esperado: ya no debería aparecer “endpoint pendiente” en los listados cubiertos por endpoints read-only. Si no hay datos, debe mostrarse lista vacía o mensaje normal. No probar escritura ni carga real de imágenes en esta fase.

## Escritura controlada inicial del panel vendedor

Esta fase habilita escritura inicial del panel vendedor contra la API .NET cuando el frontend se construye/ejecuta con `VITE_API_PROVIDER=dotnet`, manteniendo compatibilidad con Django/local mediante el mismo cliente configurable.

### Endpoints write implementados en .NET

Todos los endpoints quedan bajo `/api`, requieren Bearer válido y aceptan las rutas normalizadas con slash final por el middleware existente:

- Categorías: `POST /api/categories/`, `PUT/PATCH /api/categories/{id}/`, `DELETE /api/categories/{id}/`.
- Marcas: `POST /api/brands/`, `PUT/PATCH /api/brands/{id}/`, `DELETE /api/brands/{id}/`.
- Proveedores: `POST /api/suppliers/`, `PUT/PATCH /api/suppliers/{id}/`, `DELETE /api/suppliers/{id}/`.
- Promociones: `POST /api/promotions/`, `PUT/PATCH /api/promotions/{id}/`, `DELETE /api/promotions/{id}/`.
- Productos base, sin upload: `POST /api/products/`, `PUT/PATCH /api/products/{idOrSlug}/`, `DELETE /api/products/{idOrSlug}/`.
- Especificaciones de producto: `POST /api/product-specs/`, `PUT/PATCH /api/product-specs/{id}/`, `DELETE /api/product-specs/{id}/`.
- Cotizaciones: `PATCH /api/quote-requests/{id}/` solo para `status`, `internal_notes` y `seller_response`.
- Ítems de home: `POST /api/home-section-items/`, `PUT/PATCH /api/home-section-items/{id}/`, `DELETE /api/home-section-items/{id}/`.

### Seguridad y validación

- Se agregó la política `RequireCommercialWrite` para escritura comercial.
- La política requiere usuario autenticado por Bearer y autoriza únicamente `seller`, `support_admin`, `is_staff=true` o `is_superuser=true`.
- `RequireCommercialRead` se mantiene para lecturas comerciales y no se degradó a acceso público.
- Los inputs de escritura usan DTOs específicos y no entidades EF directas.
- Se validan nombres requeridos en creación, largos máximos alineados al modelo, enums controlados (`product_type`, `condition`, `stock_status`, `status`, `section`) y existencia de relaciones (`category`, `brand`, `supplier`, `product`).
- El payload no puede escribir campos de auditoría, password, hashes, roles ni secretos.
- `created_by` y `updated_by` se asignan desde el usuario autenticado cuando el modelo tiene `CreatedById`/`UpdatedById`; no se aceptan desde el payload.

### Semántica delete

- Soft delete/desactivación: categorías (`is_active=false`), marcas (`is_active=false`), proveedores (`is_active=false`), promociones (`is_active=false`), productos (`is_published=false`) e ítems de home (`is_active=false`).
- Delete físico controlado: especificaciones de producto, porque el modelo actual no tiene campo `is_active`/`is_published` para specs.
- Cotizaciones no tienen delete admin migrado en esta fase; solo se permite PATCH de estado/notas/respuesta.
- Product images se mantienen read-only en .NET por ahora.

### Frontend conectado

- `frontend/src/services/adminApi.ts` usa `authFetch`, `VITE_API_BASE_URL` y `VITE_API_PROVIDER` para crear/editar/eliminar entidades admin sin hardcodear `https://api.jem-nexus.cl` ni duplicar `/api`.
- Las acciones de crear, editar, eliminar/desactivar y cambiar estado de cotización usan el cliente configurable y normalizadores compartidos.
- Para `VITE_API_PROVIDER=django`, marcas/promociones siguen usando `FormData` para conservar compatibilidad con uploads existentes.
- Para `VITE_API_PROVIDER=dotnet`, marcas/promociones envían JSON sin archivo; los campos `logo`/`image` binarios quedan pendientes.
- La edición de imágenes de producto muestra un mensaje claro de pendiente con .NET y las escrituras de `product-images` devuelven error seguro 501 desde el cliente.

### Pendientes explícitos

- No se implementó upload real de imágenes ni multipart en .NET.
- `ProductImage` queda read-only en .NET salvo lectura de metadata existente.
- No se cambió el catálogo público salvo helpers compartidos del cliente admin.
- No se tocó `web.config` productivo.
- No se tocaron credenciales, no se rotaron passwords y no se agregó `SeedUsers__UpdateExistingPasswords`.
- No se ejecutó SQL real, `dotnet ef database update` ni migraciones reales.
- No se conectó a Plesk, no se subieron archivos y no se publicó.
- Una publicación futura debe seguir usando `backend-dotnet/package-plesk.ps1`, que genera ZIP seguro sin `web.config` productivo.

## Lectura pública separada de lectura admin

Se agregaron endpoints públicos GET-only bajo `/api/public/*` para que Home, Catálogo y Detalle puedan leer contenido comercial publicado sin Bearer cuando el frontend usa `VITE_API_PROVIDER=dotnet`. Esto corrige el fallback público provocado por usar endpoints `/api/*` protegidos para datos que la web pública necesita consumir sin login.

### Separación de rutas

- Sitio público sin token:
  - `GET /api/public/products/`
  - `GET /api/public/products/{idOrSlug}/`
  - `GET /api/public/categories/`
  - `GET /api/public/brands/`
  - `GET /api/public/promotions/`
  - `GET /api/public/home-section-items/`
  - `GET /api/public/product-specs/?product=...`
  - `GET /api/public/product-images/?product=...`
- Panel vendedor/admin con Bearer:
  - `/api/products/`
  - `/api/categories/`
  - `/api/brands/`
  - `/api/suppliers/`
  - `/api/promotions/`
  - `/api/quote-requests/`
  - `/api/home-section-items/`
  - `/api/product-specs/`
  - `/api/product-images/`

Los endpoints públicos filtran productos publicados (`is_published=true`), categorías activas, marcas activas, promociones activas/vigentes e ítems activos de Home. Specs e imágenes públicas solo se devuelven si pertenecen a productos publicados y con relaciones públicas activas. No se agregó `include_unpublished` ni `include_inactive` a rutas públicas. En `/api/public/products/`, los filtros `category` y `brand` aceptan ID numérico o slug, los filtros públicos de tipo/condición/stock se limitan a valores conocidos y el ordering público queda restringido a `name`, `-name`, `price` y `-price`; `/api/products/` continúa protegido para el panel vendedor/admin.

### Frontend

Con `VITE_API_PROVIDER=dotnet`, los servicios públicos de Home/Catálogo/Detalle apuntan a `/api/public/*` y usan fetch público sin token. Con `VITE_API_PROVIDER=django`, se conservan las rutas históricas `/api/products/`, `/api/categories/`, `/api/brands/`, `/api/promotions/` y `/api/home-section-items/`.

El panel vendedor conserva `authFetch` y las rutas admin protegidas. Las pantallas admin de creación/edición de producto usan servicios admin para categorías, marcas y proveedores cuando requieren datos protegidos.

### Seguridad y alcance

- La escritura sigue protegida con Bearer y `RequireCommercialWrite`.
- La lectura admin sigue protegida con `RequireCommercialRead`.
- Los DTOs públicos excluyen campos de auditoría (`created_at`, `updated_at`, `created_by`, `updated_by`), proveedores/contactos internos, hashes, tokens, secretos y datos de conexión.
- No se agregaron endpoints públicos de listado de cotizaciones.
- No se implementó upload real de imágenes.
- No se cambió schema y no se crearon migraciones.
- No se tocó `web.config` productivo.
- No se tocaron credenciales.
- No se ejecutó SQL real ni `dotnet ef database update`.
- No se conectó a Plesk, no se subieron archivos y no se publicó.

Uploads reales y cualquier migración de creación pública de cotizaciones en .NET quedan pendientes para una fase posterior controlada.

## Nota UX pública post-migración

- El acceso vendedor no se enlaza desde la navegación pública del header ni del footer.
- El panel vendedor sigue disponible por ruta directa protegida (`/admin`, con login interno si no hay sesión válida).
- En esta fase no existe login ni registro de clientes.
- El registro de clientes queda como fase futura si se implementa historial de cotizaciones o cuenta cliente.

## Fallback SPA para frontend en IIS/Plesk

- El frontend publicado como sitio estático en IIS/Plesk requiere un fallback SPA para que rutas directas como `/admin`, `/login`, `/catalogo`, `/producto/<slug>`, `/cotizar`, `/contacto`, `/maquinaria`, `/repuestos` y `/servicios` sirvan `index.html` y React Router pueda resolverlas del lado cliente.
- El archivo `frontend/public/web.config` pertenece solo al build estático del frontend: Vite lo copia a `dist/web.config` y su regla de URL Rewrite reescribe únicamente requests que no correspondan a archivos ni directorios físicos hacia `/index.html`.
- Este fallback no corresponde al `web.config` productivo del backend/API, no contiene secretos, no define connection strings y no debe reemplazar la configuración de publicación de `backend-dotnet`.

## Prompt 033 - Flujo operativo de cotizaciones y aviso a vendedores

El flujo operativo de cotizaciones queda definido así:

1. El cliente solicita una cotización desde el sitio público, sin login, sin registro y sin cuenta cliente.
2. El frontend envía la solicitud a la API .NET pública mediante `POST /api/public/quote-requests`.
3. La API valida los datos básicos, guarda la solicitud en `QuoteRequests` y responde éxito si el registro quedó persistido.
4. La solicitud aparece en el panel vendedor en `/admin/cotizaciones` para revisión y gestión interna.
5. Luego de guardar, la API intenta enviar un aviso por correo a los vendedores configurados.
6. El correo es solo una notificación adicional: si la configuración SMTP falta o el envío falla, la cotización no se pierde ni se revierte.
7. El vendedor puede mantener el orden operativo marcando estados: `new`, `contacted`, `quoted`, `closed` o `discarded`.

No se crea login de clientes, registro de clientes, panel cliente, rol `customer`, carrito, checkout, pagos, PDF de cotización ni respuesta automática con precios. Tampoco se envía correo automático al cliente en esta fase.

### Configuración SMTP esperada

Las credenciales SMTP deben configurarse en Plesk/IIS para el backend API usando variables de entorno en `web.config` o configuración segura equivalente. Codex no debe editar el `web.config` productivo ni versionar contraseñas reales.

Ejemplo documentable sin secretos reales:

```env
Email__SmtpHost=smtp.jem-nexus.cl
Email__SmtpPort=587
Email__Username=notificaciones@jem-nexus.cl
Email__Password=CONFIGURAR_EN_PLESK_NO_VERSIONAR
Email__FromAddress=notificaciones@jem-nexus.cl
Email__FromName=JEM Nexus
Email__UseSsl=true
QuoteNotifications__Recipients=jmateluna@jem-nexus.cl,fheim@jem-nexus.cl
Frontend__BaseUrl=https://jem-nexus.cl
```

`QuoteNotifications__Recipients` soporta múltiples destinatarios separados por coma o punto y coma, por ejemplo:

```env
QuoteNotifications__Recipients=jmateluna@jem-nexus.cl,fheim@jem-nexus.cl
QuoteNotifications__Recipients=jmateluna@jem-nexus.cl;fheim@jem-nexus.cl
```

Correos operativos esperados:

- Cuenta emisora SMTP: `notificaciones@jem-nexus.cl`.
- Destinatarios de aviso: `jmateluna@jem-nexus.cl` y `fheim@jem-nexus.cl`.

### Contenido del aviso al vendedor

El asunto del aviso es `Nueva solicitud de cotización - JEM Nexus`.

El cuerpo incluye fecha/hora UTC, nombre del cliente, empresa si existe, correo, teléfono, producto asociado si existe, identificador/slug del producto cuando está disponible, mensaje del cliente, origen `sitio web JEM Nexus` y enlace al panel vendedor (`https://jem-nexus.cl/admin/cotizaciones` cuando `Frontend__BaseUrl` está configurado).

Si el correo del cliente existe y es válido, se configura como `Reply-To` para facilitar que el vendedor pueda responder desde su cliente de correo. Esto no implica un correo saliente al cliente desde el sistema.
