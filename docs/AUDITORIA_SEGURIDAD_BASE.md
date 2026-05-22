# Auditoría de Seguridad Base — web-ventas-generica

Fecha: 2026-05-22  
Alcance: diagnóstico/documentación (sin cambios funcionales)

## 0) Confirmación de repositorio y alcance

Se confirmó que el trabajo se realizó en el repo correcto `web-ventas-generica`, con estructura esperada `backend/`, `frontend/`, `start.py`.

Comandos de verificación ejecutados:
- `git remote -v`
- `pwd`
- `ls`

## 1) Configuración Django

### Hallazgos
- `SECRET_KEY` tiene fallback inseguro (`dev-secret-key-change-me`) si no existe variable de entorno. Riesgo alto en producción si se omite configuración.  
- `DEBUG` por defecto evalúa a `true` si no se define variable (`DEBUG`/`DJANGO_DEBUG`). Riesgo alto en producción por exposición de errores y metadata interna.  
- `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` y `CSRF_TRUSTED_ORIGINS` se cargan por variables, pero con defaults de desarrollo local. Riesgo medio si se despliega sin sobrescribir valores.  
- `DATABASE_URL` usa parseo con `ssl_require=True` cuando existe variable (correcto para Render), con fallback a SQLite local (esperado).  
- `EMAIL_BACKEND` por defecto consola (correcto para dev, no para producción real de notificaciones).  
- No hay separación explícita de settings por entorno (single settings file con env vars). Riesgo operativo medio.

### Riesgo
- Alto: `DEBUG`/`SECRET_KEY` por defecto inseguros.
- Medio: defaults locales para hosts/orígenes si no se configuran en Render.

### Recomendaciones (sin implementar en esta fase)
1. En producción, forzar `DEBUG=False` (fail fast si falta variable).
2. Eliminar fallback hardcoded de `SECRET_KEY` en producción (abortar arranque si falta).
3. Establecer checklist de variables obligatorias en Render para backend.
4. Documentar “matriz de entornos” (local/staging/prod) con valores esperados.

## 2) Autenticación JWT

### Hallazgos
- Endpoints presentes:
  - `POST /api/auth/login/`
  - `POST /api/auth/refresh/`
  - `GET /api/auth/me/`
- Frontend almacena `access` y `refresh` en `localStorage`.
- En `401`, frontend intenta refresh y si falla limpia sesión (`clearSession`).
- Rutas/acciones admin consumen `authFetch` con bearer token.
- No se observa configuración explícita `SIMPLE_JWT` para TTL/rotación/blacklist en settings.

### Riesgo
- Medio: tokens en `localStorage` aumentan superficie ante XSS.
- Medio: no tener TTL explícito puede dejar dependencia en defaults no documentados.

### Recomendaciones
1. Declarar explícitamente `SIMPLE_JWT` (lifetimes, rotación y política de refresh).
2. Evaluar migración a cookies `HttpOnly` (si arquitectura y CSRF lo permiten) o endurecer XSS + CSP si se mantiene `localStorage`.
3. Mantener y ampliar manejo centralizado de 401 (ya existe base correcta).

## 3) Permisos DRF por recurso

### Hallazgos
- `Category`, `Brand`, `Supplier`, `Product`, `ProductImage`, `ProductSpec`, `Promotion`, `HomeSectionItem`: `IsAuthenticatedOrReadOnly`.
- `QuoteRequest`: `create` público (`AllowAny`), resto autenticado (`IsAuthenticated`).
- `include_unpublished` en productos solo aplica para usuario autenticado.
- `include_inactive` en categorías/marcas/proveedores/promociones solo aplica autenticado.

### Riesgo
- Bajo/medio: esquema general correcto para lectura pública + escritura autenticada.
- Medio: conviene tests adicionales de regresión por permisos en todos los endpoints sensibles.

### Recomendaciones
1. Aumentar cobertura de tests de permiso por endpoint y método HTTP.
2. Evaluar permisos por rol (staff vs no staff) en fase posterior.

## 4) Rate limiting (propuesta)

No implementado en esta fase (solo propuesta).

### Endpoints prioritarios
1. `POST /api/auth/login/` (alta criticidad brute-force)
2. `POST /api/quote-requests/` (spam/abuso)
3. `GET /api/products/`, `/api/promotions/`, `/api/categories/` (scraping y saturación)
4. Endpoints admin autenticados (protección de backend ante abuso de tokens comprometidos)

### Valores iniciales sugeridos
- **Login (estricto):** `5/min por IP` y `30/h por IP`.
- **Cotizaciones públicas (medio):** `10/min por IP` y `100/d por IP`.
- **Lecturas públicas catálogo (amplio):** `120/min por IP`.
- **Admin autenticado (amplio):** `300/min por usuario`.

## 5) Riesgo de SQL Injection

### Hallazgos
- Uso predominante de ORM/QuerySet (positivo).
- No se detecta uso de SQL raw en módulos revisados.
- `ordering` en `QuoteRequest` ya usa whitelist explícita.
- `ProductViewSet` usa `ordering_fields` de DRF (whitelist implícita), y `SearchFilter` de DRF.
- `category` en productos se convierte a `int`; inválido retorna queryset vacío.
- Persisten filtros por query params con valores directos del request (ORM parametrizado, riesgo bajo de SQLi directa).

### Riesgo
- Bajo para SQLi clásica por uso de ORM.
- Medio para abuso lógico/performance por inputs extremos en `search` y filtros.

### Recomendaciones
1. Whitelist explícita de filtros permitidos por endpoint (ya parcial en productos).
2. Límite de longitud para `search` (ej. 80-120 chars) y normalización básica.
3. Validación estricta de tipos/formato en query params (ids enteros, enums cerrados).
4. Tests con payloads maliciosos/no esperados para no-regresión.

## 6) Validación de formularios públicos (QuoteRequest)

### Hallazgos
- Campos existentes en modelo/serializer: nombre, teléfono, email, empresa, ciudad, mensaje, método de contacto, producto.
- Hay restricciones de tipo y `max_length` en modelo para múltiples campos, pero `message` es `TextField` sin límite explícito de negocio.
- No se observa anti-spam/rate-limit específico aún.

### Riesgo
- Medio: abuso por spam/inputs muy largos.
- Bajo/medio: calidad de dato inconsistente (teléfono/formato).

### Recomendaciones
1. Definir límites de negocio en serializer (ej. `message` máximo 1500-2000 chars).
2. Validación de teléfono (regex permisiva internacional) y normalización.
3. Sanitización básica (trim, colapso de espacios, bloqueo de payloads triviales vacíos).
4. Protección anti-spam gradual: throttle + honeypot invisible + opcional CAPTCHA en picos.

## 7) API keys y secretos

### Hallazgos
- No se detectaron secretos hardcodeados evidentes en `frontend/src`, `backend/config/settings.py`, `start.py`, `.env.example`, README revisado.
- El frontend usa `VITE_API_BASE_URL` y `VITE_WHATSAPP_NUMBER` (correcto: variables `VITE_*` son públicas por diseño).
- Configuración sensible esperada en variables backend (`SECRET_KEY`, `DATABASE_URL`, etc.).

### Riesgo
- Bajo actual (con la evidencia revisada).
- Medio operativo si se confunde y se agrega secreto en frontend o en repo.

### Recomendaciones
1. Política explícita: secretos solo backend/Render Environment.
2. Escaneo periódico de secretos en CI (gitleaks/trufflehog).
3. Mantener `.env.example` sin credenciales reales.

## 8) Cabeceras y hardening HTTP

### Hallazgos
- Existe `SecurityMiddleware`, pero no se observan flags adicionales de hardening explícitas en settings.

### Recomendaciones (no implementar aún)
- `SECURE_SSL_REDIRECT=True` (producción).
- `SESSION_COOKIE_SECURE=True`.
- `CSRF_COOKIE_SECURE=True`.
- `SECURE_HSTS_SECONDS` (inicial 31536000 con rollout cuidadoso).
- `SECURE_CONTENT_TYPE_NOSNIFF=True`.
- `X_FRAME_OPTIONS='DENY'` (o `SAMEORIGIN` según necesidad real).
- `SECURE_REFERRER_POLICY='strict-origin-when-cross-origin'`.

## 9) Archivos y media uploads

### Hallazgos
- Se utilizan `FileField` para logos, imágenes de producto y promociones.
- No se observan validadores explícitos de extensión MIME/tamaño en modelo/serializer revisados.

### Riesgo
- Medio: subida de archivos no imagen o payloads excesivos.

### Recomendaciones
1. Validar tipo real de archivo (MIME + verificación de imagen).
2. Whitelist de extensiones permitidas (`jpg`, `jpeg`, `png`, `webp`, `gif` según negocio).
3. Límite de tamaño por archivo (ej. 2–5 MB).
4. Normalización de nombres de archivo y almacenamiento seguro.
5. Tests negativos de upload (archivo no imagen / tamaño excesivo).

## 10) Frontend

### Hallazgos
- No se detectó uso de `dangerouslySetInnerHTML` en `frontend/src` (positivo).
- Manejo de auth central con `authFetch`; en 401 intenta refresh y limpia sesión si falla.
- Tokens guardados en `localStorage`.
- Links externos observados con `target="_blank"` y `rel="noreferrer"` (positivo).

### Riesgo
- Medio: exposición de tokens si ocurre XSS.

### Recomendaciones
1. Mantener política estricta de no inyectar HTML de usuario.
2. Fortalecer sanitización/escape en mensajes renderizados desde API.
3. Considerar CSP y evaluación de migración de estrategia de tokens.

## 11) Tests de seguridad recomendados (nuevos)

1. Throttling login: fuerza bruta corta/extendida.
2. Throttling quote requests público.
3. `include_unpublished` sin auth debe ocultar no publicados.
4. Escritura sin token en recursos admin debe devolver 401/403.
5. `ordering` inválido en cotizaciones debe ignorarse o fallback controlado.
6. `search` con caracteres especiales/extremos no debe romper ni degradar severamente.
7. Upload no imagen debe fallar con error de validación.
8. Usuario no autenticado en endpoints admin debe fallar consistentemente.

## 12) Plan de implementación por fases

### Fase Seguridad 1
- Implementar throttling DRF en login, quote requests, lecturas públicas y admin.
- Validación de query params con whitelist cerrada.
- Límites de longitud para `search`.

### Fase Seguridad 2
- Hardening de settings de producción.
- Activar headers SSL/cookies/HSTS/nosniff/frame/referrer.
- Revisión fina CORS/CSRF por dominio final de Render.

### Fase Seguridad 3
- Validación robusta de uploads (tipo/tamaño/extensión).
- Suite de tests de seguridad inicial automatizada.

### Fase Seguridad 4
- Auditoría de permisos por rol/vendedor (least privilege).
- Matriz de autorización por endpoint/acción.

---

## Conclusión ejecutiva

Estado actual: base razonable de permisos y JWT funcional, con riesgos principales en endurecimiento de configuración productiva, ausencia de throttling explícito y controles de upload/validación avanzada por reforzar.

## Implementación Seguridad Fase 1

### Qué se implementó
- Se activó throttling base en DRF con tasas centralizadas en `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES`.
- Se agregaron clases de throttle específicas para login, creación pública de cotizaciones, lecturas públicas de catálogo y tráfico autenticado/admin.
- Se incorporó validación estricta de query params en productos y cotizaciones admin (search, ordering, filtros por id/choices/boolean).
- Se reforzó validación de largo de `message` en cotizaciones públicas.
- Se agregaron tests de seguridad para throttling y validación de filtros/ordering/search.

### Endpoints protegidos
- `POST /api/auth/login/` con throttle específico de login.
- `POST /api/quote-requests/` con throttle específico de creación pública.
- Lecturas públicas de catálogo en:
  - `/api/products/`
  - `/api/categories/`
  - `/api/brands/`
  - `/api/suppliers/`
  - `/api/promotions/`
  - `/api/home-section-items/`
- Endpoints autenticados/admin bajo scope de throttle amplio para usuarios autenticados.

### Límites aplicados
- `login`: `5/minute`
- `quote_requests_create`: `20/hour`
- `public_catalog_read`: `600/hour`
- `authenticated_user`: `1000/hour`
- `admin_api`: `1000/hour`
- `anon` global: `600/hour`

### Validaciones agregadas
- `products`:
  - `search` con `strip` y máximo 120 caracteres.
  - `ordering` con whitelist (`name`, `price`, `created_at`, `updated_at`, `is_featured` y sus descendentes con `-`).
  - `category` y `brand` deben ser numéricos.
  - `product_type`, `condition`, `stock_status` validados contra choices.
  - `include_unpublished` e `is_featured` validados como booleanos permitidos.
- `quote-requests` admin:
  - `search` con máximo 120 caracteres.
  - `ordering` inválido retorna `400`.
- `quote-requests` público:
  - `message` máximo 2000 caracteres (con trim).

### Tests agregados
- Login throttling (bloqueo con 429 al superar límite configurado para test).
- Quote request throttling (bloqueo con 429 al superar límite configurado para test).
- Products:
  - ordering inválido -> 400.
  - category inválida -> 400.
  - product_type inválido -> 400.
  - search demasiado largo -> 400.
- Quote requests:
  - POST válido sigue funcionando.
  - mensaje demasiado largo falla con 400.
  - ordering admin inválido -> 400.
- Cobertura existente mantiene protección de `include_unpublished` sin autenticación.

### Pendientes para Fase 2
- Hardening de settings de producción (`DEBUG`, `SECRET_KEY`, flags `SECURE_*`, HSTS).
- Revisión de CORS/CSRF por dominio final de despliegue.
- Estrategia de tokens (rotación/blacklist y evaluación de almacenamiento más seguro).
- Validación robusta de uploads (MIME/extensión/tamaño) y tests negativos.

## Implementación Seguridad Fase 2

### Settings endurecidos
- `DEBUG` ahora se toma de entorno (`DEBUG`/`DJANGO_DEBUG`) y por defecto es `True` solo para desarrollo local.
- `SECRET_KEY` se toma de entorno (`SECRET_KEY`/`DJANGO_SECRET_KEY`).
- Si `DEBUG=False` y no existe `SECRET_KEY`, la app falla al iniciar con error claro (`RuntimeError`).
- Se agregaron helpers `env_bool`, `env_int` y se mantuvo `env_list` para parseo seguro de variables.

### Variables nuevas/actualizadas
- Variables recomendadas de producción: `SECRET_KEY`, `DEBUG`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `QUOTE_NOTIFICATION_EMAIL`, `DEFAULT_FROM_EMAIL`, `EMAIL_BACKEND`.
- `CORS_ALLOW_ALL_ORIGINS` queda soportada como variable opcional de emergencia local, con default `False`.

### Headers de seguridad configurados (producción)
Condicionados a `DEBUG=False`:
- `SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https")`
- `SECURE_SSL_REDIRECT=True` (overridable por env)
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `SECURE_HSTS_SECONDS=31536000` (overridable)
- `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`
- `SECURE_HSTS_PRELOAD=True`
- `SECURE_CONTENT_TYPE_NOSNIFF=True`
- `X_FRAME_OPTIONS='DENY'`
- `SECURE_REFERRER_POLICY='strict-origin-when-cross-origin'`

### SIMPLE_JWT explícito
Se definió configuración explícita en settings:
- `ACCESS_TOKEN_LIFETIME=30 minutos`
- `REFRESH_TOKEN_LIFETIME=7 días`
- `ROTATE_REFRESH_TOKENS=False`
- `BLACKLIST_AFTER_ROTATION=False` (sin blacklist app en esta fase)
- `AUTH_HEADER_TYPES=("Bearer",)`

### Pendientes para Fase 3
- Validaciones robustas de uploads (MIME real, extensión permitida, tamaño máximo).
- Mayor cobertura de tests de seguridad (casos negativos de archivos y estrés de payloads).
- Evaluación de estrategia de tokens más resistente a XSS (sin cambios en esta fase).
