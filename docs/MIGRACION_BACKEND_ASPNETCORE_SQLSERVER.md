# Migración backend Django/DRF a ASP.NET Core Web API + SQL Server 2022

## 0. Confirmación de repositorio y alcance

Repositorio confirmado: `web-ventas-generica`.

Estructura esperada presente en la raíz:

- `backend/`
- `frontend/`
- `start.py`

Esta auditoría **no implementa** la nueva API .NET, **no borra** Django, **no modifica** el frontend, **no cambia** Render/deploy actual, **no toca secrets** y **no ejecuta migraciones reales**.

Contexto de destino confirmado:

- Dominio principal futuro: `https://jem-nexus.cl`
- API futura: `https://api.jem-nexus.cl`
- Hosting final: Windows Server + IIS + Plesk
- Stack backend final: ASP.NET Core Web API + SQL Server 2022
- Base SQL Server creada: `jemnexusb_prod`
- Usuario SQL Server creado: `jemnexusb_api`
- Render/Django/Python no deben usarse en la versión final de hosting.

## 1. Diagnóstico del backend Django/DRF actual

### 1.1 Apps y estructura revisada

Apps propias actuales:

| App | Rol actual | Archivos principales |
| --- | --- | --- |
| `core` | Endpoints transversales: auth JWT, usuario actual, health, sitemap XML, throttling global. | `backend/core/views.py`, `backend/core/urls.py`, `backend/core/throttles.py` |
| `catalog` | Dominio comercial: categorías, marcas, proveedores, productos, imágenes, specs, promociones, secciones home, cotizaciones, permisos, validadores, seeds. | `backend/catalog/models.py`, `backend/catalog/serializers.py`, `backend/catalog/views.py`, `backend/catalog/urls.py`, `backend/catalog/permissions.py`, `backend/catalog/validators.py`, `backend/catalog/services.py`, `backend/catalog/management/commands/*.py` |
| `config` | Configuración Django, DRF, JWT, CORS, media/static, URL root. | `backend/config/settings.py`, `backend/config/urls.py` |

Apps Django/terceros relevantes:

- `django.contrib.auth`, `admin`, `sessions`, `staticfiles`.
- `rest_framework`.
- `rest_framework_simplejwt`.
- `corsheaders`.
- `whitenoise` opcional según disponibilidad.

### 1.2 Modelos detectados

Modelos propios detectados en `catalog`:

- `TimestampedModel` abstracto con `created_at` y `updated_at`.
- `Category`.
- `Brand`.
- `Supplier`.
- `Product`.
- `ProductImage`.
- `ProductSpec`.
- `Promotion`.
- `HomeSectionItem`.
- `QuoteRequest`.

Usuarios y roles:

- Se usa el modelo estándar `AUTH_USER_MODEL` de Django.
- Los roles comerciales se resuelven con `is_superuser`, `is_staff` o pertenencia a grupos Django llamados `vendedor` y `admin_comercial`.
- Varios modelos tienen auditoría `created_by` y `updated_by` hacia `AUTH_USER_MODEL`.

### 1.3 Serializers detectados

Serializers públicos y de escritura/admin detectados:

- `CategorySerializer`, `CategoryWriteSerializer`.
- `BrandSerializer`, `BrandWriteSerializer`.
- `SupplierSerializer`, `SupplierWriteSerializer`.
- `ProductListSerializer`, `ProductDetailSerializer`, `ProductWriteSerializer`.
- `ProductImageSerializer`, `ProductImageWriteSerializer`.
- `ProductSpecSerializer`, `ProductSpecWriteSerializer`.
- `PromotionSerializer`, `PromotionWriteSerializer`.
- `HomeSectionItemSerializer`, `HomeSectionItemWriteSerializer`.
- `QuoteRequestPublicSerializer`, `QuoteRequestAdminSerializer`.
- `CurrentUserSerializer` en `core`.

Patrón importante para migrar:

- En lectura pública, varios serializers exponen objetos anidados (`Product` con `Category`, `Brand`, `Supplier`, `images`, `specs`).
- En escritura, se reciben IDs o payloads simples.
- Uploads usan `multipart/form-data` para `Brand.logo`, `ProductImage.image` y `Promotion.image`.

### 1.4 Viewsets, vistas y URLs

El router DRF registra estos recursos bajo `/api/`:

- `/api/categories/`
- `/api/brands/`
- `/api/suppliers/`
- `/api/products/`
- `/api/product-images/`
- `/api/product-specs/`
- `/api/promotions/`
- `/api/home-section-items/`
- `/api/quote-requests/`

Endpoints adicionales:

- `/api/auth/login/`
- `/api/auth/refresh/`
- `/api/auth/me/`
- `/api/health/`
- `/api/sitemap.xml`
- `/sitemap.xml`
- `/admin/`
- `/media/*` solo cuando `DEBUG=True`.

### 1.5 Permisos y endpoints públicos/privados

Permisos personalizados:

| Permiso | Regla |
| --- | --- |
| `IsPublicReadSellerWrite` | Métodos seguros (`GET`, `HEAD`, `OPTIONS`) son públicos; escrituras requieren vendedor/admin. |
| `IsQuoteCreatePublicSellerManage` | Crear cotización es público; listar/ver/editar/eliminar cotizaciones requiere vendedor/admin. |
| `IsSellerOrAdmin` | Requiere `is_staff`, `is_superuser` o grupos `vendedor`/`admin_comercial`. |

Endpoints públicos principales:

- Lectura de categorías, marcas, proveedores activos.
- Lectura de productos publicados.
- Lectura de imágenes/specs por producto.
- Lectura de promociones activas.
- Lectura de home sections activas con productos publicados.
- Creación de `quote-requests`.
- `health` y `sitemap.xml`.
- Login/refresh.

Endpoints privados/panel vendedor:

- Escritura CRUD de catálogo, marcas, proveedores, productos, imágenes, specs, promociones y home sections.
- Listado/gestión de cotizaciones.
- Inclusión de inactivos/no publicados con flags como `include_inactive=true` o `include_unpublished=true` cuando el usuario es vendedor/admin.
- `/api/auth/me/` requiere JWT.

### 1.6 Throttling

Throttles actuales:

| Scope | Clase | Rate actual |
| --- | --- | --- |
| `anon` | `AnonRateThrottle` | `600/hour` |
| `authenticated_user` | `AuthenticatedUserThrottle` | `1000/hour` |
| `login` | `LoginRateThrottle` | `5/minute` |
| `quote_requests_create` | `QuoteRequestCreateThrottle` | `20/hour` |
| `public_catalog_read` | `PublicCatalogReadThrottle` | `600/hour` |
| `admin_api` | `ScopedRateThrottle` | `1000/hour` |

Nota: `LoginRateThrottle` se desactiva cuando `settings.TESTING` es verdadero.

### 1.7 Validadores

Validador principal detectado para imágenes:

- Extensiones permitidas: `.jpg`, `.jpeg`, `.png`, `.webp`.
- Content types permitidos: `image/jpeg`, `image/png`, `image/webp`.
- Tamaño máximo configurable con `MAX_UPLOAD_IMAGE_SIZE_MB`, default 5 MB.
- Validación de firma binaria para JPEG, PNG y WEBP.

Validaciones adicionales:

- Productos: query params validados para `category`, `brand`, enums, booleans, `ordering` y largo máximo de `search`.
- Cotizaciones: `message` máximo 2000 caracteres; filtros por `status`, `product`, `search`, `ordering`.
- Home sections: límites por sección, unicidad por `(section, position)` y `(section, product)`, compatibilidad entre tipo de producto y sección.

### 1.8 Auth/JWT

- Autenticación DRF global con `JWTAuthentication` de SimpleJWT.
- Login: `TokenObtainPairView` con throttling de login.
- Refresh: `TokenRefreshView`.
- Access token: 30 minutos.
- Refresh token: 7 días.
- Header: `Authorization: Bearer <token>`.
- El frontend guarda tokens en `localStorage` con claves `ventas_access_token` y `ventas_refresh_token`.

### 1.9 Seeds/demo data

Comandos de datos demo detectados:

| Comando | Uso |
| --- | --- |
| `seed_catalog` | Crea/actualiza categorías, marcas, proveedores, productos, specs y 5 promociones demo. |
| `generate_demo_products` | Genera productos demo variables por tipo (`tijeras`, `brazos`, `baterias`, `ruedas`, `controles`). |

No se detectó seed propio para crear usuario vendedor/admin; actualmente dependería de Django admin, comandos manuales o fixtures externos no observados en esta auditoría.

### 1.10 Uploads de imágenes

Campos con archivos:

| Modelo | Campo | Ruta Django actual |
| --- | --- | --- |
| `Brand` | `logo` | `brands/logos/` |
| `ProductImage` | `image` | `products/images/` |
| `Promotion` | `image` | `promotions/` |

Configuración actual:

- `MEDIA_URL = /media/`.
- `MEDIA_ROOT = backend/media`.
- En `DEBUG=True`, Django sirve archivos media desde `config.urls`.

Para Windows/IIS/Plesk, esto debe migrarse a una carpeta persistente fuera del directorio de deploy o a un storage administrado; la API .NET debe devolver URLs públicas estables y evitar servir archivos desde una carpeta ejecutable.

### 1.11 Sitemap/SEO backend

`SitemapXmlView` genera XML con:

- Rutas estáticas: `/`, `/catalogo`, `/contacto`, `/sobre-nosotros`, `/preguntas-frecuentes`.
- Productos publicados: `/producto/{slug}` con `lastmod` desde `updated_at`.
- Categorías activas: `/catalogo?category={id}` con `lastmod` desde `updated_at`.
- Base URL desde `PUBLIC_SITE_URL`.

Existe también `frontend/public/sitemap.xml` estático y `frontend/public/robots.txt` apunta actualmente a un sitemap en Render. Esto no se cambia en esta tarea, pero es un riesgo a resolver antes del despliegue final.

### 1.12 Cotizaciones

`QuoteRequest` permite creación pública y administración privada:

- Datos cliente: nombre, teléfono, email, empresa, ciudad, método preferido, mensaje.
- Producto opcional.
- Estados: `new`, `contacted`, `quoted`, `closed`, `discarded`.
- Campos internos: notas internas, respuesta vendedor.
- Timestamps de proceso: `contacted_at`, `quoted_at`, `closed_at`.
- Al crear se llama a `send_quote_request_notifications`.
- Al cambiar estado se autocompletan timestamps según corresponda.

### 1.13 Promociones y home sections

Promociones:

- CRUD público/privado similar al catálogo.
- Lectura pública solo de activas salvo usuario vendedor/admin con `include_inactive=true`.
- Pueden vincularse opcionalmente a producto.

Home sections:

- Secciones actuales: `machinery_promotions`, `spare_parts_offers`, `repair_services`.
- Límites: 12, 6 y 12 elementos activos respectivamente.
- Cada item apunta a un producto.
- El backend valida compatibilidad de producto con sección.
- La creación calcula posición libre y activa el item.
- La edición permite reordenar/intercambiar posiciones.

## 2. Matriz de endpoints actuales

Convención: todos los endpoints bajo `/api/` salvo `/sitemap.xml` raíz y `/admin/`.

| Método | Endpoint Django actual | Uso | Público/Auth | Modelo relacionado | Debe migrar | Prioridad |
| --- | --- | --- | --- | --- | --- | --- |
| POST | `/api/auth/login/` | Login, emite `access` y `refresh`. | Público con throttling `login`. | `User` | Sí | Alta |
| POST | `/api/auth/refresh/` | Renovar access token. | Público con refresh token válido. | `User`/JWT | Sí | Alta |
| GET | `/api/auth/me/` | Obtener usuario actual para panel. | JWT requerido. | `User` | Sí | Alta |
| GET | `/api/health/` | Health check API. | Público. | N/A | Sí | Alta |
| GET | `/api/categories/` | Listar categorías activas; admin puede incluir inactivas. | Público lectura; auth escritura. | `Category` | Sí | Alta |
| POST | `/api/categories/` | Crear categoría. | Vendedor/admin. | `Category` | Sí | Alta |
| GET | `/api/categories/{id}/` | Detalle categoría. | Público lectura. | `Category` | Sí | Alta |
| PUT/PATCH | `/api/categories/{id}/` | Actualizar categoría. | Vendedor/admin. | `Category` | Sí | Alta |
| DELETE | `/api/categories/{id}/` | Eliminar categoría. | Vendedor/admin. | `Category` | Sí | Media |
| GET | `/api/brands/` | Listar marcas activas; admin puede incluir inactivas. | Público lectura; auth escritura. | `Brand` | Sí | Alta |
| POST | `/api/brands/` | Crear marca con logo opcional. | Vendedor/admin. | `Brand` | Sí | Alta |
| GET | `/api/brands/{id}/` | Detalle marca. | Público lectura. | `Brand` | Sí | Alta |
| PUT/PATCH | `/api/brands/{id}/` | Actualizar marca/logo. | Vendedor/admin. | `Brand` | Sí | Alta |
| DELETE | `/api/brands/{id}/` | Eliminar marca. | Vendedor/admin. | `Brand` | Sí | Media |
| GET | `/api/suppliers/` | Listar proveedores activos; admin puede incluir inactivos. | Público lectura; auth escritura. | `Supplier` | Sí | Alta |
| POST | `/api/suppliers/` | Crear proveedor. | Vendedor/admin. | `Supplier` | Sí | Alta |
| GET | `/api/suppliers/{id}/` | Detalle proveedor. | Público lectura. | `Supplier` | Sí | Alta |
| PUT/PATCH | `/api/suppliers/{id}/` | Actualizar proveedor. | Vendedor/admin. | `Supplier` | Sí | Alta |
| DELETE | `/api/suppliers/{id}/` | Eliminar proveedor. | Vendedor/admin. | `Supplier` | Sí | Media |
| GET | `/api/products/` | Catálogo público; filtros `category`, `brand`, `product_type`, `condition`, `stock_status`, `is_featured`, `search`, `ordering`; admin puede incluir no publicados. | Público lectura; auth escritura. | `Product` | Sí | Crítica |
| POST | `/api/products/` | Crear producto. | Vendedor/admin. | `Product` | Sí | Crítica |
| GET | `/api/products/{slug}/` | Detalle público por slug con imágenes/specs. | Público si publicado; admin puede ver no publicado. | `Product`, `ProductImage`, `ProductSpec` | Sí | Crítica |
| PUT/PATCH | `/api/products/{slug}/` | Actualizar producto. | Vendedor/admin. | `Product` | Sí | Crítica |
| DELETE | `/api/products/{slug}/` | Eliminar producto. | Vendedor/admin. | `Product` | Sí | Media |
| GET | `/api/product-images/?product={id}` | Listar imágenes de producto. | Público lectura; auth escritura. | `ProductImage` | Sí | Alta |
| POST | `/api/product-images/` | Subir imagen de producto; si `is_main=true` desmarca otras. | Vendedor/admin. | `ProductImage` | Sí | Alta |
| GET | `/api/product-images/{id}/` | Detalle imagen. | Público lectura. | `ProductImage` | Sí | Media |
| PUT/PATCH | `/api/product-images/{id}/` | Actualizar metadata/imagen. | Vendedor/admin. | `ProductImage` | Sí | Alta |
| DELETE | `/api/product-images/{id}/` | Eliminar imagen. | Vendedor/admin. | `ProductImage` | Sí | Alta |
| GET | `/api/product-specs/?product={id}` | Listar specs de producto. | Público lectura; auth escritura. | `ProductSpec` | Sí | Alta |
| POST | `/api/product-specs/` | Crear spec. | Vendedor/admin. | `ProductSpec` | Sí | Alta |
| GET | `/api/product-specs/{id}/` | Detalle spec. | Público lectura. | `ProductSpec` | Sí | Media |
| PUT/PATCH | `/api/product-specs/{id}/` | Actualizar spec. | Vendedor/admin. | `ProductSpec` | Sí | Alta |
| DELETE | `/api/product-specs/{id}/` | Eliminar spec. | Vendedor/admin. | `ProductSpec` | Sí | Alta |
| GET | `/api/promotions/` | Listar promociones activas; admin puede incluir inactivas. | Público lectura; auth escritura. | `Promotion` | Sí | Alta |
| POST | `/api/promotions/` | Crear promoción con imagen opcional. | Vendedor/admin. | `Promotion` | Sí | Alta |
| GET | `/api/promotions/{id}/` | Detalle promoción. | Público lectura. | `Promotion` | Sí | Alta |
| PUT/PATCH | `/api/promotions/{id}/` | Actualizar promoción/imagen. | Vendedor/admin. | `Promotion` | Sí | Alta |
| DELETE | `/api/promotions/{id}/` | Eliminar promoción. | Vendedor/admin. | `Promotion` | Sí | Media |
| GET | `/api/home-section-items/?section={section}` | Listar secciones home activas; admin puede incluir inactivas. | Público lectura; auth escritura. | `HomeSectionItem`, `Product` | Sí | Alta |
| POST | `/api/home-section-items/` | Crear item home section; calcula posición. | Vendedor/admin. | `HomeSectionItem` | Sí | Alta |
| GET | `/api/home-section-items/{id}/` | Detalle item. | Público lectura. | `HomeSectionItem` | Sí | Media |
| PUT/PATCH | `/api/home-section-items/{id}/` | Actualizar/reordenar item. | Vendedor/admin. | `HomeSectionItem` | Sí | Alta |
| DELETE | `/api/home-section-items/{id}/` | Eliminar item. | Vendedor/admin. | `HomeSectionItem` | Sí | Alta |
| POST | `/api/quote-requests/` | Crear solicitud de cotización pública y enviar notificación. | Público con throttling `quote_requests_create`. | `QuoteRequest` | Sí | Crítica |
| GET | `/api/quote-requests/` | Panel vendedor: listar cotizaciones con filtros. | Vendedor/admin. | `QuoteRequest` | Sí | Alta |
| GET | `/api/quote-requests/{id}/` | Panel vendedor: ver cotización. | Vendedor/admin. | `QuoteRequest` | Sí | Alta |
| PUT/PATCH | `/api/quote-requests/{id}/` | Actualizar estado/notas/respuesta y timestamps. | Vendedor/admin. | `QuoteRequest` | Sí | Alta |
| DELETE | `/api/quote-requests/{id}/` | Eliminar cotización. | Vendedor/admin. | `QuoteRequest` | Sí | Media |
| GET | `/api/sitemap.xml` | Sitemap XML desde backend. | Público. | `Product`, `Category` | Sí | Media |
| GET | `/sitemap.xml` | Alias root de sitemap XML. | Público. | `Product`, `Category` | Sí | Media |
| GET | `/admin/` | Django Admin. | Staff Django. | Todos/Django admin | No como tal | Baja |
| GET | `/media/*` | Media servida por Django en dev. | Público en `DEBUG=True`. | Archivos | Sí, con estrategia .NET/IIS distinta | Alta |

## 3. Matriz de modelos

| Modelo Django | Campos principales | Relaciones | Equivalente ASP.NET Core/EF Core | Observaciones |
| --- | --- | --- | --- | --- |
| `TimestampedModel` | `created_at`, `updated_at` | Abstracto. | Interfaz/base `AuditableEntity` o `TimestampedEntity`. | Usar `DateTimeOffset`/UTC; completar en `SaveChanges`. |
| `Category` | `id`, `name`, `slug`, `description`, `is_active`, `order`, `created_at`, `updated_at`, `created_by`, `updated_by` | `parent` self FK nullable; `children`; `products`. | `Category` con `ParentId`, `Parent`, `Children`, índice único `Slug`. | Mantener slug único y generación automática; cuidado con borrado: Django usa `SET_NULL` en parent. |
| `Brand` | `id`, `name`, `slug`, `logo`, `description`, `is_active`, timestamps, auditoría. | `products`. | `Brand` con `LogoPath`/`LogoUrl`, índice único `Slug`. | Migrar upload y validación de logo. |
| `Supplier` | `id`, `name`, `contact_name`, `phone`, `email`, `notes`, `is_active`, timestamps, auditoría. | `products`. | `Supplier`. | Aunque la lectura pública existe hoy, evaluar si proveedores deben seguir expuestos públicamente. |
| `Product` | `id`, `name`, `slug`, `product_type`, `condition`, `short_description`, `description`, `model`, `sku`, `year`, `hours_meter`, `price`, `price_visible`, `stock_status`, `is_featured`, `is_published`, timestamps, auditoría. | FK `Category` PROTECT; FK nullable `Brand`; FK nullable `Supplier`; colecciones `Images`, `Specs`, `Promotions`, `QuoteRequests`, `HomeSectionItems`. | `Product` con enums/string constants para tipo, condición y stock. | Lookup público por `slug`; filtros deben conservar compatibilidad con frontend. `decimal(12,2)` para precio. |
| `ProductImage` | `id`, `image`, `alt_text`, `is_main`, `order`, `created_at`, `updated_at`, auditoría. | FK `Product` CASCADE. | `ProductImage` con `ImagePath`/`PublicUrl`. | Mantener regla de una imagen principal por producto; ideal índice filtrado o lógica transaccional. |
| `ProductSpec` | `id`, `name`, `value`, `unit`, `order`, auditoría. | FK `Product` CASCADE. | `ProductSpec`. | El modelo actual no tiene `created_at/updated_at`; decidir si agregarlos en .NET por consistencia o preservar esquema lógico. |
| `Promotion` | `id`, `title`, `subtitle`, `image`, `button_text`, `button_url`, `is_active`, `order`, `starts_at`, `ends_at`, timestamps, auditoría. | FK nullable `Product` SET_NULL. | `Promotion` con `ProductId` nullable e imagen. | Actualmente no filtra por fecha en backend; solo por `is_active`. Decidir si aplicar ventanas de vigencia en .NET. |
| `HomeSectionItem` | `id`, `section`, `position`, `is_active`, timestamps, auditoría. | FK `Product` CASCADE; unique `(section, position)` y `(section, product)`. | `HomeSectionItem` con enum/string `Section`. | Mantener límites por sección: 12/6/12; validar compatibilidad con `ProductType`. |
| `QuoteRequest` | `id`, `customer_name`, `customer_phone`, `customer_email`, `company_name`, `city`, `preferred_contact_method`, `message`, `status`, `internal_notes`, `seller_response`, `contacted_at`, `quoted_at`, `closed_at`, timestamps, auditoría. | FK nullable `Product` SET_NULL. | `QuoteRequest` con enum/string `Status` y `PreferredContactMethod`. | Crear público; gestión privada. Implementar notificaciones por email y timestamps al cambiar estado. |
| `User`/roles Django | `id`, `username`, `email`, `first_name`, `last_name`, `is_staff`, `is_superuser`, grupos. | Grupos `vendedor`, `admin_comercial`; auditoría desde modelos catalog. | Recomendado: ASP.NET Core Identity (`ApplicationUser`, roles `Admin`, `Seller`) o entidad propia simple si se quiere menor alcance. | Para compatibilidad del frontend, `/auth/me/` debe devolver `id`, `username`, `email`, `first_name`, `last_name`, `is_staff`, `is_superuser` o adaptar frontend en una fase posterior. |

## 4. Arquitectura ASP.NET Core propuesta

### 4.1 Estructura futura recomendada

No crear todavía en esta tarea, pero se recomienda esta estructura:

```text
backend-dotnet/
  JemNexus.Api/
    Controllers/
      AuthController.cs
      HealthController.cs
      CategoriesController.cs
      BrandsController.cs
      SuppliersController.cs
      ProductsController.cs
      ProductImagesController.cs
      ProductSpecsController.cs
      PromotionsController.cs
      HomeSectionItemsController.cs
      QuoteRequestsController.cs
      SitemapController.cs
    Data/
      JemNexusDbContext.cs
      Configurations/
      Migrations/
      Seed/
    Domain/
      Entities/
      Enums/
    Dtos/
      Auth/
      Catalog/
      Quotes/
    Services/
      Auth/
      Files/
      Notifications/
      Seo/
      Slugs/
    Middleware/
    Options/
    Program.cs
    appsettings.json
    appsettings.Development.json
  JemNexus.Api.Tests/
```

Nombre recomendado: `JemNexus.Api`, porque coincide con el dominio/producto y evita nombres genéricos.

### 4.2 Stack técnico

- .NET 8 LTS.
- ASP.NET Core Web API.
- Entity Framework Core 8.
- Provider SQL Server: `Microsoft.EntityFrameworkCore.SqlServer`.
- SQL Server 2022.
- JWT Bearer Auth.
- ASP.NET Core Identity recomendado para usuarios/roles si se acepta su set de tablas.
- Swagger/OpenAPI solo para desarrollo y QA; deshabilitado o protegido en producción.
- Health checks con `/health` y, opcionalmente, `/api/health` mientras se conserva compatibilidad.
- CORS restringido a:
  - `https://jem-nexus.cl`
  - opcionalmente `https://www.jem-nexus.cl` si se usará.
  - localhost solo en `Development`.
- Configuración vía `appsettings*.json` + variables de entorno/Plesk.
- Uploads en carpeta segura y persistente, por ejemplo:
  - `D:\HostingSpaces\jem-nexus\uploads\jemnexus-api\`
  - o ruta configurable `Uploads:RootPath` fuera del binario publicado.
- URLs públicas de media con `Uploads:PublicBaseUrl`, por ejemplo `https://api.jem-nexus.cl/media/` o subcarpeta estática configurada en IIS.

### 4.3 Contratos de compatibilidad sugeridos

Para reducir cambios simultáneos en el frontend, la API .NET debería replicar inicialmente:

- Prefijo `/api`.
- Slashes finales tolerados (`/products/` y `/products`).
- Nombres de campos snake_case en JSON, o configurar DTOs con `JsonPropertyName` para mantener el contrato actual.
- Login response `{ "access": "...", "refresh": "..." }`.
- Refresh response `{ "access": "..." }`.
- Auth header `Authorization: Bearer`.
- List responses como array simple; el frontend ya soporta array o `{results: []}`.
- Lookup de productos por `slug`.

### 4.4 Capas recomendadas

- **Controllers**: HTTP, binding, status codes, autorización.
- **Services**: reglas de negocio, uploads, notificaciones, slugs, sitemap.
- **Data/EF Core**: `DbContext`, configuraciones por entidad, migraciones.
- **Dtos**: separar lectura pública, detalle, escritura/admin.
- **Options**: `JwtOptions`, `CorsOptions`, `UploadsOptions`, `PublicSiteOptions`, `SeedOptions`, `SmtpOptions`.

### 4.5 Seguridad y operación

- No guardar connection string ni JWT secret en git.
- Variables en Plesk/IIS para:
  - `ConnectionStrings__DefaultConnection`.
  - `Jwt__Issuer`, `Jwt__Audience`, `Jwt__SigningKey`.
  - `Cors__AllowedOrigins__0=https://jem-nexus.cl`.
  - `Uploads__RootPath`.
  - `Uploads__PublicBaseUrl`.
  - SMTP/notificaciones.
- Rate limiting con middleware de .NET (`System.Threading.RateLimiting`) para login, cotizaciones, lectura pública y admin.
- Validación de uploads por extensión, content-type, tamaño y firma/magic bytes.
- Logs con Serilog o logging estándar hacia archivos compatibles con Plesk/IIS.
- Respuestas de error consistentes; idealmente ProblemDetails.

## 5. Fases recomendadas de migración

### Fase Backend .NET 1: proyecto base ASP.NET Core

Prompt sugerido:

> Crear `backend-dotnet/JemNexus.Api` en .NET 8 con ASP.NET Core Web API, configuración por ambiente, CORS para `jem-nexus.cl`, health endpoint `/health` y `/api/health`, logging básico, Swagger solo en Development, sin tocar Django ni frontend.

Entregables:

- Solución/proyecto .NET.
- `Program.cs` mínimo.
- `appsettings.example` o documentación de variables.
- Health funcionando localmente.

### Fase Backend .NET 2: modelos EF Core + DbContext + migraciones SQL Server

Prompt sugerido:

> Crear entidades EF Core equivalentes a `Category`, `Brand`, `Supplier`, `Product`, `ProductImage`, `ProductSpec`, `Promotion`, `HomeSectionItem`, `QuoteRequest`, usuarios/roles, auditoría, configuraciones de índices/relaciones y primera migración SQL Server. No conectar frontend aún.

Entregables:

- Entidades y `JemNexusDbContext`.
- Configuraciones EF.
- Primera migración.
- Script SQL revisable antes de aplicar.

### Fase Backend .NET 3: auth JWT + usuario vendedor/admin

Prompt sugerido:

> Implementar JWT Auth compatible con frontend actual: `/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/me/`, roles `Admin` y `Seller`, seed inicial configurable de vendedor/admin, y políticas de autorización equivalentes a `IsPublicReadSellerWrite` e `IsQuoteCreatePublicSellerManage`.

Entregables:

- Auth controllers/services.
- Seed seguro por variables de entorno.
- Tests de login/me/roles.

### Fase Backend .NET 4: catálogo base

Prompt sugerido:

> Migrar endpoints de categorías, marcas, proveedores y productos a ASP.NET Core manteniendo contratos JSON, filtros, ordenamiento, búsqueda, lookup por slug, auditoría y visibilidad pública/admin.

Entregables:

- CRUD de `categories`, `brands`, `suppliers`, `products`.
- Filtros compatibles.
- Validaciones de query params.
- Tests de API.

### Fase Backend .NET 5: imágenes, specs, uploads y validaciones

Prompt sugerido:

> Migrar `product-images`, `product-specs`, uploads de `Brand.logo`, `ProductImage.image`, `Promotion.image`, validaciones de extensión/content-type/tamaño/firma binaria, carpeta segura configurable y URLs públicas en IIS/Plesk.

Entregables:

- Upload service.
- Validaciones equivalentes.
- Regla de imagen principal única.
- Tests con archivos simulados.

### Fase Backend .NET 6: promociones, home sections y hero

Prompt sugerido:

> Migrar promociones y home section items, incluyendo secciones `machinery_promotions`, `spare_parts_offers`, `repair_services`, límites por sección, unicidad, compatibilidad por tipo de producto, reordenamiento y lectura pública compatible.

Entregables:

- CRUD de promociones.
- CRUD/reordenamiento home sections.
- Validaciones de sección.
- Tests de reglas de negocio.

### Fase Backend .NET 7: cotizaciones

Prompt sugerido:

> Migrar `quote-requests` con creación pública, throttling/rate limit, gestión privada, filtros, búsqueda, ordenamiento, estados, timestamps automáticos y servicio de notificaciones SMTP configurable.

Entregables:

- Endpoints públicos/admin de cotizaciones.
- Notificación por email.
- Rate limiting.
- Tests de flujo de estado.

### Fase Backend .NET 8: sitemap y SEO backend

Prompt sugerido:

> Migrar sitemap XML a ASP.NET Core con `/sitemap.xml` y `/api/sitemap.xml`, `PUBLIC_SITE_URL=https://jem-nexus.cl`, rutas estáticas, productos publicados, categorías activas y `lastmod`.

Entregables:

- Sitemap XML compatible.
- Config de base URL.
- Tests de contenido XML.

### Fase Backend .NET 9: conectar frontend a `api.jem-nexus.cl`

Prompt sugerido:

> Cambiar configuración de frontend para apuntar a `https://api.jem-nexus.cl/api` mediante variables de entorno, validar login, catálogo, admin, uploads, cotizaciones y URLs media. No eliminar aún Django hasta completar smoke test.

Entregables:

- Variables frontend para producción.
- Build validado.
- Checklist funcional end-to-end.

### Fase Backend .NET 10: deploy en Plesk/IIS

Prompt sugerido:

> Preparar publicación ASP.NET Core para Plesk/IIS: `dotnet publish`, web.config, variables de entorno, conexión SQL Server, carpeta uploads, permisos NTFS, health check, logs, CORS, HTTPS y smoke tests productivos.

Entregables:

- Paquete publish.
- `web.config` adecuado.
- Checklist Plesk completado.
- Smoke test en `https://api.jem-nexus.cl/health` y endpoints críticos.

### Fase Backend .NET 11 opcional: migración de datos desde Django

Agregar esta fase si existe base de datos productiva con datos relevantes.

Prompt sugerido:

> Crear estrategia de migración de datos desde Django/PostgreSQL/SQLite actual hacia SQL Server 2022: export JSON/CSV, normalización de slugs, usuarios/roles, archivos media, carga idempotente y validación de conteos.

## 6. Riesgos detectados

| Riesgo | Impacto | Mitigación |
| --- | --- | --- |
| Contrato JSON snake_case actual del frontend. | Si .NET devuelve PascalCase/camelCase distinto, se rompe frontend. | Usar DTOs con `JsonPropertyName` o política snake_case compatible. |
| Lookup de productos por `slug`. | Si se usa ID en .NET, rutas de detalle fallan. | Mantener `GET /api/products/{slug}/`. |
| Slashes finales. | Frontend llama endpoints con `/`. | Tolerar ambos formatos o mantener rutas equivalentes. |
| Uploads en hosting Windows/Plesk. | Pérdida de archivos al publicar o permisos insuficientes. | Carpeta externa configurable, permisos NTFS al app pool, backup. |
| URLs media. | Imágenes rotas si cambia `/media/`. | Definir `Uploads:PublicBaseUrl`; probar con frontend. |
| CORS final. | API bloqueada desde `jem-nexus.cl`. | Config explícita para dominio principal y www si aplica. |
| Auth/roles distintos entre Django e Identity. | Panel vendedor inaccesible. | Mapear roles `Seller/Admin` y mantener respuesta `/auth/me/` compatible. |
| Rate limiting no replicado. | Login/cotizaciones vulnerables a abuso. | Implementar políticas .NET por endpoint/scope. |
| `Supplier` público. | Puede exponer datos internos. | Decidir si se mantiene por compatibilidad o se separa DTO público/admin. |
| Sitemap duplicado backend/frontend. | SEO inconsistente; robots apunta a Render. | En fase SEO/deploy actualizar robots/sitemap final. |
| Render aún presente. | Config obsoleta puede confundir despliegue. | No tocar ahora; planificar retiro en fase deploy. |
| Datos existentes. | Pérdida o inconsistencias si no se migra. | Crear fase de migración de datos idempotente. |
| Fechas de promociones. | Hoy no se filtra por `starts_at`/`ends_at`. | Decidir si .NET debe preservar comportamiento o corregirlo. |

## 7. Decisiones pendientes

1. ¿Usar ASP.NET Core Identity completo o usuarios propios livianos?
2. ¿Mantener JSON `snake_case` estrictamente o adaptar frontend durante la fase 9?
3. ¿`Supplier` seguirá siendo público o solo admin?
4. ¿Dónde quedará físicamente la carpeta de uploads en Plesk y cómo se respaldará?
5. ¿La API servirá media desde `api.jem-nexus.cl/media` o se usará otra ruta/subdominio?
6. ¿Se migrarán datos reales existentes o solo se iniciará con seed limpio?
7. ¿Se requiere conservar IDs de Django para productos/categorías o basta con slugs/nuevos IDs?
8. ¿Se deben aplicar ventanas de fecha de promociones (`starts_at`, `ends_at`) en lectura pública?
9. ¿Qué SMTP definitivo se usará para notificaciones de cotización?
10. ¿Se habilitará Swagger en producción protegido o solo en Development/Staging?
11. ¿Se usará `www.jem-nexus.cl` además del dominio raíz en CORS?
12. ¿Qué política de backup de SQL Server y uploads se aplicará en Plesk?

## 8. Checklist de despliegue Plesk/IIS

### 8.1 Pre-deploy

- [ ] Confirmar runtime/hosting bundle de .NET 8 instalado en Windows Server.
- [ ] Confirmar app pool/IIS para `api.jem-nexus.cl`.
- [ ] Confirmar HTTPS válido para `api.jem-nexus.cl`.
- [ ] Confirmar SQL Server 2022 accesible desde el sitio.
- [ ] Configurar base `jemnexusb_prod` y usuario `jemnexusb_api` con permisos mínimos necesarios.
- [ ] Definir connection string sin guardarla en git.
- [ ] Definir JWT signing key fuerte en variable de entorno.
- [ ] Definir CORS para `https://jem-nexus.cl`.
- [ ] Definir carpeta uploads externa y permisos NTFS para el identity del app pool.
- [ ] Definir SMTP/notificaciones.

### 8.2 Publicación

- [ ] Ejecutar tests .NET.
- [ ] Ejecutar `dotnet publish -c Release`.
- [ ] Revisar `web.config` generado.
- [ ] Subir artefactos publicados a Plesk.
- [ ] Configurar variables de entorno en Plesk/IIS.
- [ ] Ejecutar migraciones EF Core de forma controlada o aplicar script SQL revisado.
- [ ] Ejecutar seed inicial vendedor/admin solo una vez o idempotente.
- [ ] Configurar logs y rotación.

### 8.3 Smoke tests backend

- [ ] `GET https://api.jem-nexus.cl/health`.
- [ ] `GET https://api.jem-nexus.cl/api/health` si se mantiene compatibilidad.
- [ ] `POST /api/auth/login/`.
- [ ] `GET /api/auth/me/` con JWT.
- [ ] `GET /api/categories/`.
- [ ] `GET /api/products/`.
- [ ] `GET /api/products/{slug}/`.
- [ ] Upload de imagen desde panel vendedor.
- [ ] `POST /api/quote-requests/` público.
- [ ] `GET /sitemap.xml`.

### 8.4 Frontend y SEO

- [ ] Configurar `VITE_API_BASE_URL=https://api.jem-nexus.cl/api`.
- [ ] Build frontend productivo.
- [ ] Validar CORS desde `https://jem-nexus.cl`.
- [ ] Validar catálogo, detalle, login admin, CRUD admin, uploads y cotizaciones.
- [ ] Actualizar `robots.txt` para sitemap final, no Render.
- [ ] Validar sitemap en producción.
- [ ] Revisar enlaces a media.

### 8.5 Post-deploy

- [ ] Monitorear logs IIS/app.
- [ ] Confirmar backup SQL Server.
- [ ] Confirmar backup de uploads.
- [ ] Documentar rollback.
- [ ] Mantener Django/Render disponible solo durante ventana de transición si se requiere rollback.
- [ ] Retirar referencias a Render cuando la migración sea estable.

## 9. Archivos revisados en esta auditoría

Backend:

- `backend/catalog/models.py`
- `backend/catalog/serializers.py`
- `backend/catalog/views.py`
- `backend/catalog/urls.py`
- `backend/catalog/permissions.py`
- `backend/catalog/validators.py`
- `backend/catalog/services.py`
- `backend/catalog/admin.py`
- `backend/catalog/tests.py`
- `backend/catalog/management/commands/seed_catalog.py`
- `backend/catalog/management/commands/generate_demo_products.py`
- `backend/core/views.py`
- `backend/core/urls.py`
- `backend/core/throttles.py`
- `backend/core/tests.py`
- `backend/config/settings.py`
- `backend/config/urls.py`

Frontend/API consumers revisados solo para confirmar contrato actual:

- `frontend/src/services/api.ts`
- `frontend/src/services/authApi.ts`
- `frontend/src/services/catalogApi.ts`
- `frontend/src/services/adminApi.ts`
- `frontend/public/robots.txt`
- `frontend/public/sitemap.xml`

## 10. Resultado de checks de esta tarea

Registrar aquí el resultado observado al ejecutar los comandos requeridos:

- `dotnet build backend-dotnet/JemNexus.sln`: no ejecutable en este contenedor porque el SDK `dotnet` no está instalado (`dotnet: command not found`). Se intentó instalar .NET 8 con `apt-get` y `dotnet-install.sh`, pero la red/proxy del entorno devolvió HTTP 403.
- `dotnet test backend-dotnet/JemNexus.sln`: no ejecutable en este contenedor porque el SDK `dotnet` no está instalado (`dotnet: command not found`).
- `dotnet publish backend-dotnet/JemNexus.Api/JemNexus.Api.csproj -c Release -f net8.0 -o backend-dotnet/publish-test`: no ejecutable en este contenedor porque el SDK `dotnet` no está instalado (`dotnet: command not found`).
- `python backend/manage.py check`: OK, sin issues.
- `python backend/manage.py test core catalog -v 2`: OK, 80 tests ejecutados. Warnings observados: directorio `backend/staticfiles/` inexistente y llave HMAC dev menor a 32 bytes en entorno de test.
- `cd frontend && npm run build`: OK. Warning de npm: `Unknown env config "http-proxy"`.

## Implementación Backend .NET 1

Se agregó la base del backend ASP.NET Core Web API en .NET 8 dentro de `backend-dotnet/`, sin eliminar ni reemplazar el backend Django existente y sin modificar contratos funcionales del frontend.

### Estructura creada

```text
backend-dotnet/
  JemNexus.sln
  README.md
  JemNexus.Api/
    JemNexus.Api.csproj
    Program.cs
    appsettings.json
    appsettings.Development.json
  JemNexus.Api.Tests/
    JemNexus.Api.Tests.csproj
    HealthEndpointTests.cs
```

### Endpoints mínimos

La API base expone endpoints de salud simples:

- `GET /`
- `GET /health`
- `GET /api/health`
- `GET /api/health/`

La compatibilidad con `GET /api/health/` se conserva mediante normalización interna hacia `GET /api/health`, evitando mapear dos endpoints que ASP.NET Core pueda considerar ambiguos. Todos responden JSON sin datos sensibles:

```json
{
  "status": "ok",
  "app": "JEM Nexus API",
  "environment": "Development",
  "timestamp": "2026-06-03T00:00:00Z"
}
```

### Configuración base

Se agregaron `appsettings.json` y `appsettings.Development.json`, más lectura estándar de variables de entorno de ASP.NET Core. En esta fase no se conecta SQL Server y los valores sensibles quedan vacíos o documentados para configuración externa.

Variables sugeridas para Plesk/IIS y futuras fases:

- `ASPNETCORE_ENVIRONMENT`
- `PUBLIC_SITE_URL`
- `FRONTEND_ORIGINS`
- `JWT_SECRET`
- `ConnectionStrings__DefaultConnection`

### CORS preparado

La política CORS inicial permite los orígenes esperados del frontend final y local:

- `https://jem-nexus.cl`
- `https://www.jem-nexus.cl`
- `http://localhost:5174`
- `http://127.0.0.1:5174`

Además, `FRONTEND_ORIGINS` permite agregar orígenes por variable de entorno, separados por coma o punto y coma.

### Compatibilidad JSON

La API queda configurada con `JsonNamingPolicy.SnakeCaseLower` para respuestas JSON futuras. Esto prepara compatibilidad con el backend Django/DRF actual, que expone campos en `snake_case`. Los DTOs y contratos reales todavía no se migran en esta fase.

### Swagger/OpenAPI

Swagger/OpenAPI se habilita solo cuando el ambiente es `Development` o `QA`. No queda expuesto obligatoriamente en `Production`.

### Publish para IIS/Plesk

El comando previsto para validar publicación manual es:

```bash
dotnet publish backend-dotnet/JemNexus.Api/JemNexus.Api.csproj -c Release -f net8.0 -o backend-dotnet/publish-test
```

La salida esperada para Plesk/IIS debe incluir `JemNexus.Api.dll`, `JemNexus.Api.exe`, `web.config` y `appsettings.json`. El contenido publicado debe subirse manualmente al sitio `https://api.jem-nexus.cl`, configurando variables de entorno en Plesk/IIS. Codex no sube artefactos a Plesk.

### Tests agregados

Se agregó un proyecto xUnit `JemNexus.Api.Tests` con pruebas mínimas para validar que:

- `GET /health` retorna HTTP 200.
- `GET /api/health` retorna HTTP 200.
- La respuesta contiene `status = ok`.
- La respuesta contiene `app = JEM Nexus API`.

### Pendientes Backend .NET 2

- Crear entidades EF Core equivalentes a los modelos Django.
- Crear `DbContext` y configuraciones de relaciones/índices.
- Agregar provider SQL Server y migraciones iniciales.
- Generar scripts SQL revisables antes de aplicar en Plesk.
- Mantener sin cambios el frontend hasta que los contratos estén replicados.
