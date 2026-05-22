# Auditoría de Seguridad Fase 4: Permisos, Roles y Ownership

Fecha: 2026-05-22
Alcance: **solo auditoría/documentación** (sin cambios funcionales en backend/frontend).

## 1) Auditoría de endpoints y permisos actuales

Base de rutas observada:
- Prefijo API: `/api/`.
- Auth/Core: `/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/me/`.
- Catálogo/Panel: `/api/categories/`, `/api/brands/`, `/api/suppliers/`, `/api/products/`, `/api/product-images/`, `/api/product-specs/`, `/api/promotions/`, `/api/quote-requests/`, `/api/home-section-items/`.

### Tabla de permisos actuales (backend real)

| Endpoint | Lectura pública | Escritura pública | ¿Auth requerida? | ¿Staff/Superuser requerido? | Observación de riesgo |
|---|---|---|---|---|---|
| `POST /api/auth/login/` | N/A | Sí (credenciales válidas) | No para llamar; sí credenciales correctas | No | Riesgo bajo/moderado: endpoint sensible a fuerza bruta mitigado por `LoginRateThrottle`; no hay MFA. |
| `POST /api/auth/refresh/` | N/A | Sí (con refresh token válido) | No header auth, sí refresh válido | No | Si se compromete refresh token, permite renovar acceso. |
| `GET /api/auth/me/` | No | N/A | Sí (`IsAuthenticated`) | No | Cualquier usuario autenticado puede consultar su perfil (esperado). |
| `GET /api/products/`, `GET /api/products/{slug}/` | Sí (solo publicados por defecto) | N/A | No | No | Público ve catálogo publicado; autenticados pueden consultar no publicados con flags/lógica de acción. |
| `POST/PATCH/DELETE /api/products/` | No | No | Sí (`IsAuthenticatedOrReadOnly`) | **No** | Riesgo alto: cualquier usuario autenticado podría crear/editar/borrar productos. |
| `GET /api/product-images/` | Sí | N/A | No | No | Exposición pública de metadatos de imágenes; usual para catálogo. |
| `POST/PATCH/DELETE /api/product-images/` | No | No | Sí (`IsAuthenticatedOrReadOnly`) | **No** | Riesgo alto: cualquier autenticado podría alterar imágenes de cualquier producto. |
| `GET /api/product-specs/` | Sí | N/A | No | No | Lectura pública de especificaciones. |
| `POST/PATCH/DELETE /api/product-specs/` | No | No | Sí (`IsAuthenticatedOrReadOnly`) | **No** | Riesgo alto: cualquier autenticado puede modificar specs globales. |
| `GET /api/categories/` | Sí (activas por defecto) | N/A | No | No | Lectura pública esperada. |
| `POST/PATCH/DELETE /api/categories/` | No | No | Sí (`IsAuthenticatedOrReadOnly`) | **No** | Riesgo alto: taxonomía editable por cualquier autenticado. |
| `GET /api/brands/` | Sí (activas por defecto) | N/A | No | No | Lectura pública esperada. |
| `POST/PATCH/DELETE /api/brands/` | No | No | Sí (`IsAuthenticatedOrReadOnly`) | **No** | Riesgo alto: marcas editables por cualquier autenticado. |
| `GET /api/suppliers/` | Sí (activos por defecto) | N/A | No | No | Riesgo de exposición de datos de proveedor si se considera interno. |
| `POST/PATCH/DELETE /api/suppliers/` | No | No | Sí (`IsAuthenticatedOrReadOnly`) | **No** | Riesgo alto: proveedores editables por cualquier autenticado. |
| `GET /api/promotions/` | Sí (activas por defecto) | N/A | No | No | Lectura pública esperada para home/campañas. |
| `POST/PATCH/DELETE /api/promotions/` | No | No | Sí (`IsAuthenticatedOrReadOnly`) | **No** | Riesgo alto: promociones manipulables por cualquier autenticado. |
| `GET /api/home-section-items/` | Sí (solo activos + producto publicado para público) | N/A | No | No | Lectura pública controlada, pero con impacto visual directo en home. |
| `POST/PATCH/DELETE /api/home-section-items/` | No | No | Sí (`IsAuthenticatedOrReadOnly`) | **No** | Riesgo alto: cualquier autenticado puede alterar composición del home. |
| `POST /api/quote-requests/` | Sí (público puede crear) | Sí | No | No | Riesgo moderado: spam/abuso mitigado parcialmente por throttle de creación. |
| `GET/PATCH/DELETE /api/quote-requests/` | No | No | Sí (`IsAuthenticated`) | **No** | Riesgo alto: cualquier autenticado puede listar/editar/borrar todas las cotizaciones. |
| `/api/admin/` (Django admin `/admin/`) | No | No | Sí + permisos admin Django | Sí (staff/permisos) | Correcto para panel admin Django; separado de DRF catálogo. |

### Hallazgos puntuales
- En catálogo predomina `IsAuthenticatedOrReadOnly`: protege escritura frente a anónimos, pero **no separa vendedor vs usuario autenticado común**.
- En cotizaciones (`quote-requests`) solo `create` es público; resto usa `IsAuthenticated`, sin filtro por rol ni ownership.
- No se observan permisos custom DRF por rol (`seller`, `admin_comercial`, etc.) en endpoints auditados.

---

## 2) Matriz de roles propuesta (inicial)

### Rol 1: Público / Visitante
**Puede**
- Ver productos publicados.
- Ver categorías, marcas y promociones públicas.
- Enviar solicitudes de cotización.
- Usar canal WhatsApp comercial.

**No puede**
- Crear/editar/eliminar productos.
- Ver listado interno de cotizaciones.
- Subir imágenes o editar especificaciones.
- Ver no publicados/inactivos.

### Rol 2: Vendedor
**Puede**
- Acceder al panel vendedor.
- Crear/editar productos.
- Subir/editar imágenes del producto.
- Administrar especificaciones.
- Revisar y gestionar cotizaciones.
- Administrar promociones y home-section-items.

**No debería poder**
- Administrar usuarios/grupos/permisos globales.
- Cambiar política de seguridad.
- Acceder a información interna de otros vendedores (escenario multi-vendedor futuro).

### Rol 3: Admin / Superuser
**Puede**
- Todo lo del vendedor.
- Administrar usuarios, grupos y permisos.
- Configuración avanzada, auditoría y soporte.

### Rol 4 (futuro): Proveedor
- Pendiente de definición funcional.
- Recomendado evaluar acceso limitado a productos asignados, inventario o estados de oferta según modelo comercial final.

---

## 3) Ownership actual y futuro

## Estado actual (observado)
- `Product` **no** tiene `owner`, `created_by`, `updated_by`.
- `QuoteRequest` **no** tiene `assigned_to`, `owner` ni `handled_by`.
- Entidades auxiliares (`Promotion`, `HomeSectionItem`, `ProductImage`, `ProductSpec`, `Category`, `Brand`, `Supplier`) tampoco registran autor/último editor.
- Con permisos actuales, los usuarios autenticados operan sobre datos globales compartidos.

## Implicación
- Si mañana hay múltiples vendedores, **todos verían y podrían modificar todo** (productos, promociones, cotizaciones), salvo que se cambie lógica de permisos/querysets.

## Riesgo multi-vendedor
- Contaminación cruzada de datos.
- Dificultad para trazabilidad de acciones por usuario.
- Riesgo de cambios no autorizados entre equipos/comerciales.

## Recomendaciones (fase posterior, sin implementar ahora)
- Agregar ownership explícito por entidad crítica (`created_by`, `updated_by`, `assigned_to`, eventualmente `seller_owner`).
- Aplicar filtro de queryset por rol + ownership cuando no sea admin.
- Mantener excepción para `Admin/Superuser` con visión global.

---

## 4) Riesgos actuales principales

1. **Escritura protegida solo por autenticación** (`IsAuthenticatedOrReadOnly` / `IsAuthenticated`) en recursos críticos.
2. **Escalada horizontal**: cualquier usuario con token válido podría editar/borrar datos globales del panel.
3. **Sin permisos granulares por rol** (vendedor vs admin_comercial vs usuario común).
4. **Sin campos de auditoría de autoría** (`created_by`, `updated_by`) en entidades clave.
5. **Sin historial de cambios** (quién cambió qué/cuándo, más allá de timestamps básicos en algunos modelos).
6. **Sin ownership por vendedor** para futuro escenario multi-vendedor.
7. **Frontend no es autoridad**: aunque UI oculte acciones, backend actualmente aceptaría escrituras de cualquier autenticado en muchos endpoints.

---

## 5) Recomendaciones técnicas (futura implementación)

### Permisos DRF custom recomendados
- `IsSellerOrAdmin`: escritura solo para grupo vendedor o admin/staff.
- `IsAdminOnly`: endpoints sensibles de administración de usuarios/permisos.
- `IsPublicReadSellerWrite`: lectura pública, escritura restringida por rol vendedor/admin.

### Modelo de roles en Django
- Grupos sugeridos:
  - `vendedor`
  - `admin_comercial`
- `is_staff` como condición base para acceso a panel interno.
- Permisos específicos por modelo para ajustes finos cuando aplique.

### Campos de trazabilidad/auditoría
- En modelos operativos: `created_by`, `updated_by`.
- En cotizaciones: `assigned_to` (y opcionalmente `handled_by`).
- Mantener `created_at`, `updated_at` y reforzar persistencia de `updated_by`.

### Testing recomendado
- Tests de permisos por rol para cada endpoint crítico (lectura/escritura).
- Tests de ownership (cuando se implemente): vendedor A no modifica recursos de vendedor B.
- Tests de regresión para no romper panel vendedor existente.

---

## 6) Plan Seguridad Fase 4 (subfases)

### Fase 4A (base de acceso)
- Formalizar y aprobar matriz de roles.
- Implementar permisos custom DRF mínimos.
- Limitar panel vendedor a `is_staff` o pertenencia a grupo `vendedor`.

### Fase 4B (trazabilidad)
- Agregar `created_by`/`updated_by` en modelos críticos.
- Registrar automáticamente usuario creador/editor en productos/promociones y recursos administrativos.

### Fase 4C (ownership multi-vendedor)
- Introducir ownership por vendedor para productos y cotizaciones.
- Ajustar querysets/permisos para aislamiento por vendedor (excepto admins globales).

### Fase 4D (administración de permisos desde panel)
- UI/flows para gestión de usuarios, grupos y permisos.
- Mantener backend como autoridad final de autorización.
- Añadir auditoría de acciones administrativas.

---

## 7) Alcance de esta tarea (confirmación)

- ✅ Se realizó **solo auditoría y documentación**.
- ✅ No se modificaron permisos funcionales ni lógica de backend/frontend.
- ✅ No se cambiaron modelos, migraciones, deploy ni seeds.


## Implementación Seguridad Fase 4A

### Permisos creados
- `IsSellerOrAdmin`: habilita escritura para usuarios autenticados que sean `is_staff`, `is_superuser` o pertenezcan a grupos `vendedor` / `admin_comercial`.
- `IsPublicReadSellerWrite`: permite lectura pública (`SAFE_METHODS`) y restringe escrituras a vendedor/admin.
- `IsQuoteCreatePublicSellerManage`: permite `POST` público para cotización y restringe gestión (`list/retrieve/update/destroy`) a vendedor/admin.

### Endpoints ajustados
- Aplicado `IsPublicReadSellerWrite` en: `categories`, `brands`, `suppliers`, `products`, `product-images`, `product-specs`, `promotions`, `home-section-items`.
- Aplicado `IsQuoteCreatePublicSellerManage` en `quote-requests`.
- Ajuste de visibilidad `include_inactive` / `include_unpublished`: ahora requiere rol vendedor/admin (ya no cualquier autenticado).

### Alcance
- Se endurece autorización de escritura comercial sin introducir ownership por objeto.
- Se mantiene lectura pública de catálogo publicado/activo.
- Se mantiene `POST` público de cotizaciones.

### Pruebas agregadas
- Cobertura para anónimo: lectura de productos públicos, bloqueo de escritura comercial, `POST` cotización permitido y bloqueo de listado de cotizaciones.
- Cobertura para autenticado no staff/no vendedor: bloqueo de `POST/PATCH/DELETE` en productos y bloqueo de listado de cotizaciones.
- Cobertura para vendedor/staff: permiso de `POST/PATCH/DELETE` en productos, listado de cotizaciones y creación de imagen/spec.
- Cobertura de `include_unpublished`: visible solo para vendedor/staff.

### Pendientes Fase 4B
- `created_by` / `updated_by` en entidades críticas.
- ownership por vendedor para aislamiento multi-vendedor.
- administración de usuarios/grupos/permisos desde panel.
- auditoría de cambios y trazabilidad operativa.
