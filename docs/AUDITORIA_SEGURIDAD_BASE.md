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
