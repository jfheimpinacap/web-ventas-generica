# Auditoría SEO / GEO / Ads (Fase documental)

## Alcance y contexto

- Proyecto auditado: **web-ventas-generica**.
- Frontend: React + Vite + TypeScript.
- Backend: Django + DRF.
- Objetivo comercial: generación de leads (contacto/cotización), sin carrito de compras.
- Esta fase **no implementa cambios funcionales** en backend/frontend; solo diagnóstico y hoja de ruta.

## 1) Auditoría de estructura pública actual

### Rutas detectadas

Rutas públicas detectadas en router:

- `/`
- `/catalogo`
- `/producto/:slug`
- `/cotizar`
- `/login`
- `*` (fallback que redirige a `/`)

Rutas de navegación/filtrado detectadas:

- `/catalogo?category=:id`
- `/catalogo?search=:texto`
- `/catalogo?brand=:id`
- `/catalogo?product_type=machinery|spare_part|service|other`
- `/catalogo?condition=new|used|refurbished|not_applicable`
- `/catalogo?stock_status=available|on_request|reserved|sold`
- `/catalogo?ordering=price|-price`
- combinaciones múltiples de query params.

También se observa flujo comercial desde detalle a cotización:

- `/cotizar?product=:id`

### Matriz SEO por ruta

| Ruta | ¿Indexar? | Objetivo comercial | Título SEO recomendado | Meta description recomendada | Canonical recomendado | Datos estructurados recomendados | Conversión esperada |
|---|---|---|---|---|---|---|---|
| `/` | Sí | Captar demanda general y derivar a catálogo/cotización | Maquinaria, repuestos y servicios industriales \| [Marca] | Venta y cotización de maquinaria, repuestos y servicios. Atención comercial rápida para empresas y técnicos. | `https://dominio.com/` | `Organization`, `WebSite`, `ItemList` (destacados), opcional `FAQPage` futura | Click a catálogo, click a cotizar, click WhatsApp |
| `/catalogo` | Sí | Captar búsquedas transaccionales por tipo/categoría | Catálogo de maquinaria, repuestos y servicios \| [Marca] | Explora productos y servicios por categoría, marca y disponibilidad. Solicita cotización en línea. | `https://dominio.com/catalogo` | `BreadcrumbList`, `ItemList` | `product_view`, `product_detail_click`, `quote_click` |
| `/catalogo?category=:id` (categorías principales y subcategorías clave) | Sí (selectivo) | Posicionar categorías comerciales de alta intención | [Nombre categoría] \| Catálogo [Marca] | Encuentra [categoría] con opciones por marca, condición y stock. Solicita cotización. | URL limpia ideal futura (`/catalogo/maquinaria`), mientras tanto canonical a URL normalizada por categoría | `BreadcrumbList`, `ItemList` | `category_view`, `product_detail_click`, `quote_click` |
| `/catalogo` con filtros combinados (`brand`, `condition`, `stock_status`, `ordering`, `search`) | No (en general) | UX de refinamiento, no landing SEO | Mantener UX title dinámico, pero con noindex/canonical consolidado | N/A o heredada de catálogo/categoría | Canonical hacia `/catalogo` o categoría principal normalizada | Sin obligación de schema adicional | Interacción interna, no captación orgánica directa |
| `/producto/:slug` | Sí (si publicado) | Captar intención específica de producto/solución | [Producto] \| [Categoría] \| [Marca] | Ficha técnica, condición, disponibilidad y opciones de pago para [producto]. Solicita cotización rápida. | `https://dominio.com/producto/:slug` | `Product`, `BreadcrumbList` | `product_view`, `quote_click`, `whatsapp_click`, `quote_submit` |
| `/cotizar` | Condicional (recomendado: No) | Conversión directa vía formulario | Solicitar cotización \| [Marca] | Completa el formulario para recibir una propuesta comercial según tu necesidad. | `https://dominio.com/cotizar` | Opcional `BreadcrumbList`; evitar sobreoptimizar formulario | `quote_submit` |
| `/cotizar?product=:id` | No | Prellenado de intención, página táctica de conversión | Hereda de `/cotizar` | Hereda de `/cotizar` | Canonical a `/cotizar` | Igual que `/cotizar` | `quote_submit` |
| `/login` | No | Acceso privado vendedor/admin | Acceso vendedor \| [Marca] | Acceso al panel interno de gestión comercial y soporte. | `https://dominio.com/login` con `noindex, nofollow` | Ninguno | Login interno, sin conversión comercial pública |

## 2) Estrategia de indexación

### Indexar

1. Home `/`.
2. Categorías principales (Maquinaria, Repuestos, Servicios).
3. Subcategorías con volumen/intención comercial real.
4. Productos publicados (`/producto/:slug`).
5. Servicios publicados (como producto tipo `service` o landing dedicada futura).

### No indexar

1. `/login`.
2. Todo `/admin/*` y rutas protegidas.
3. Rutas internas operativas.
4. `/cotizar` cuando predomina formulario y poco contenido SEO (recomendación actual).
5. URLs de filtro combinadas (alto riesgo de duplicación por query params).

### Decisión

- Se prioriza indexar páginas con **demanda de búsqueda** y contenido útil para descubrimiento.
- Se evita indexar páginas de **flujo interno, autenticación** o variantes con bajo valor semántico.
- Para filtros, se recomienda consolidar señales con canonical y política de indexación selectiva (indexar solo categorías estratégicas normalizadas).

## 3) SEO técnico actual y brechas

Estado observado:

- **Title dinámico**: No implementado; se detecta un único `<title>` estático en `frontend/index.html`.
- **Meta description dinámica**: No implementada.
- **Canonical**: No implementado.
- **Open Graph**: No implementado.
- **Twitter Card**: No implementado.
- **robots.txt**: No detectado en `frontend/public`.
- **sitemap.xml**: No detectado en `frontend/public`.
- **Structured data JSON-LD**: No detectado.
- **Alt text en imágenes**: Parcialmente implementado (detalle y cotización usan `alt` con fallback).
- **Breadcrumbs SEO**: Hay breadcrumbs visuales en catálogo/detalle, sin marcado JSON-LD.
- **Headings H1/H2**: Existen H1 en páginas clave; requiere auditoría de consistencia por plantilla.
- **URLs amigables**: Producto usa slug (positivo); categorías dependen de query params (mejorable a futuro).
- **Rendimiento mobile básico**: Build OK; falta medición formal con Lighthouse/Core Web Vitals.

## 4) Datos estructurados recomendados (JSON-LD)

### Home

- `Organization`
  - nombre comercial, logo, URL, redes, `ContactPoint` (cuando exista teléfono/soporte público).
- `WebSite`
  - URL principal y `SearchAction` (si se decide exponer búsqueda interna con endpoint estable).

### Categorías y listados

- `BreadcrumbList`
  - Inicio > Categoría > Subcategoría.
- `ItemList`
  - Listado paginado de productos/servicios visibles.

### Producto (`/producto/:slug`)

- `Product`
  - nombre, descripción, imagen, SKU/modelo, marca, categoría, estado, disponibilidad, oferta/precio cuando aplique.
- `BreadcrumbList`
  - Inicio > Categoría > Producto.

### Servicios

- Si se modelan como servicios de reparación/soporte con entidad propia:
  - `Service`.
- Si se mantienen como item de catálogo comparable a producto:
  - `Product` (con tipo/atributos de servicio).

### Contacto

- `ContactPoint` dentro de `Organization` cuando se publique teléfono/canales formales.

## 5) GEO (local) + Generative Engine Optimization (IA)

### 5.1 SEO geográfico/local

Recomendaciones:

- Definir zonas de atención explícitas (ciudad/comuna/región).
- Publicar datos NAP consistentes cuando el negocio defina versión pública:
  - Name (nombre comercial)
  - Address (si aplica atención física)
  - Phone (canal comercial principal)
- Preparar alta futura de Google Business Profile (cuando haya dirección/cobertura consolidada).
- Incluir referencias geográficas en contenido de categorías/servicios y en página de contacto.

### 5.2 GEO para motores generativos (LLM/AI Overviews)

Enfoque recomendado:

- Contenido claro, verificable y específico por categoría y servicio.
- FAQs con preguntas de intención real (precio, tiempos, stock, compatibilidad, despacho, soporte).
- Descripciones comerciales + técnicas de productos/servicios.
- Estructura semántica consistente (H1/H2 + datos estructurados).
- Señales de confianza: experiencia, marcas trabajadas, casos de uso, políticas de atención y tiempos de respuesta.

### Contenidos futuros sugeridos

1. Página **Sobre nosotros** (experiencia, propuesta de valor, rubros atendidos).
2. Página **Contacto** (canales, horarios, cobertura geográfica, tiempos de respuesta).
3. Página **FAQs** transversal.
4. Bloques SEO por categoría principal (texto introductorio útil, no relleno).
5. Landings/textos por servicio (mantenimiento, reparación, asesoría, etc.).
6. Página o secciones de **zonas de atención**.

## 6) Google Ads y medición (plan, sin implementación)

### Conversiones a medir

- Envío exitoso de cotización (`quote_submit`) — conversión principal.
- Clic en WhatsApp (`whatsapp_click`).
- Clic en botón Cotizar (`quote_click`).
- Clic en Ver detalle (`product_detail_click`).
- Clic en teléfono (si se publica) (`phone_click`).
- Visita a producto (`product_view`).
- Visita a categoría (`category_view`).
- Clic en oferta hero (`hero_offer_click`).

### Stack recomendado

1. **Google Tag Manager (GTM)** como capa de orquestación.
2. **GA4** para analítica de eventos y embudos.
3. **Google Ads Conversion Tracking** importando/conectando eventos clave desde GA4 o etiqueta directa.
4. **dataLayer** estandarizado para eventos con parámetros:
   - `product_id`, `product_slug`, `product_type`, `category_id`, `category_name`, `lead_origin`, etc.

## 7) Plan de implementación por fases

### Fase SEO 1 (base técnica mínima)

- Helmet/meta dinámico por ruta.
- Títulos y meta descriptions por plantilla.
- Canonical por página indexable.
- `robots.txt`.

### Fase SEO 2 (descubrimiento + rich results)

- `sitemap.xml` dinámico/automatizado.
- JSON-LD inicial: `Organization`, `WebSite`, `BreadcrumbList`, `Product`.

### Fase SEO 3 (contenido comercial escalable)

- Contenido SEO por categoría/servicio.
- FAQs.
- Páginas Sobre nosotros y Contacto.

### Fase SEO 4 (medición y gobierno)

- Alta y validación en Google Search Console.
- Implementación GA4 + GTM.
- Eventos de conversión y panel básico de leads.

### Fase SEO 5 (activación Ads)

- Google Ads por categorías prioritarias.
- Campañas de búsqueda y potencial remarketing (si volumen lo permite).
- Medición de CPL/lead de calidad y optimización continua.

## 8) Confirmación de no intervención funcional

Durante esta fase:

- No se realizaron cambios funcionales en backend o frontend.
- No se alteraron rutas, modelos, settings, estilos ni despliegue.
- Se generó únicamente documentación de auditoría y roadmap.

## 9) Evidencia de tests/build ejecutados

1. `python backend/manage.py check` → OK.
2. `python backend/manage.py test core catalog -v 2` → OK (79 tests).
3. `cd frontend && npm run build` → OK (build producción completado).

## 10) Riesgos y prioridades

### Riesgos actuales

- Baja controlabilidad de indexación por depender de query params en categorías.
- Ausencia de metadatos por ruta limita CTR orgánico.
- Ausencia de sitemap/robots dificulta rastreo óptimo.
- Sin capa de medición de eventos no hay atribución sólida para Ads futuros.

### Prioridades inmediatas recomendadas

1. Resolver SEO técnico base (Fase SEO 1).
2. Definir taxonomía indexable de categorías/subcategorías (canónicas).
3. Incorporar structured data de alto impacto comercial.
4. Preparar instrumentación analítica antes de activar inversión Ads.

## Implementación Fase SEO 1

### Qué se implementó

- Componente reutilizable `Seo` en frontend para gestionar `title`, `description`, `canonical`, `robots`, Open Graph y Twitter Card en runtime.
- Metadatos SEO aplicados en rutas públicas clave (`/`, `/catalogo`, `/producto/:slug`, `/cotizar`, `/login`).
- Política `noindex` aplicada para login y rutas admin vía `ProtectedRoute`.
- Soporte de `VITE_PUBLIC_SITE_URL` con fallback a `window.location.origin` para construir canonical y `og:url`.
- `robots.txt` agregado en frontend con `Disallow` para `/login` y `/admin`.
- `frontend/index.html` actualizado con title/description base como fallback estático.

### Rutas cubiertas

- `/` (index,follow)
- `/catalogo` (index,follow; `noindex,follow` cuando hay `search`)
- `/catalogo?category=:id` (title/description/canonical por categoría)
- `/producto/:slug` (index,follow por defecto; `noindex,nofollow` si `is_published=false`)
- `/cotizar` (`noindex,follow`)
- `/login` (`noindex,nofollow`)
- `/admin/*` (`noindex,nofollow` desde capa protegida frontend)

### Variables nuevas

- `VITE_PUBLIC_SITE_URL` en frontend (`.env.example`) para URL pública base de canonical/OG.

### Pendientes para Fase SEO 2

- `sitemap.xml` dinámico o automatizado por entorno.
- JSON-LD inicial (`Organization`, `WebSite`, `BreadcrumbList`, `Product`).
- Estrategia de canonical/indexación más granular para más combinaciones de filtros del catálogo.
- Validación en Google Search Console y pruebas de rich results.



## Implementación Fase SEO 2A

### Sitemap creado

- Se creó `frontend/public/sitemap.xml` como sitemap inicial estático para descubrimiento básico en buscadores.
- URL pública resultante (Vite public root): `https://web-ventas-ps62.onrender.com/sitemap.xml`.

### Rutas incluidas

- `https://web-ventas-ps62.onrender.com/`
- `https://web-ventas-ps62.onrender.com/catalogo`

### Rutas excluidas (decisión actual)

- `/cotizar`: excluida por estrategia actual de `noindex` al ser página principalmente transaccional de formulario.
- `/login` y `/admin`: excluidas por ser rutas privadas/no públicas para SEO.
- URLs con filtros o búsqueda (`/catalogo?search=...`, combinaciones de query params): excluidas para evitar duplicación y canibalización.
- Productos (`/producto/:slug`): excluidos en esta fase por no existir aún generación dinámica/automatizada del sitemap.

### Limitaciones

- Este sitemap es **inicial y estático**.
- No incorpora inventario dinámico (productos publicados) ni cambios automáticos de catálogo.
- No incluye categorías por query param (`/catalogo?category=<id>`) porque no son rutas limpias estables y los IDs pueden variar.

### Pendientes para Fase SEO 2B

- Generar sitemap dinámico desde backend o script de build-time.
- Incluir productos publicados (`/producto/:slug`) de forma automática.
- Incluir categorías principales con URLs SEO limpias cuando existan rutas dedicadas (ej.: `/maquinaria`, `/repuestos`, `/servicios`).
- Mantener sincronización automática entre dominio público y referencias en `robots.txt`/`sitemap.xml` en cambios de entorno.
