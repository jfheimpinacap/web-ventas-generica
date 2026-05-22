# Web Ventas Genérica (Base Full Stack)

Base reutilizable para una web comercial tipo catálogo (maquinaria, elevadores tipo tijera, brazos articulados y repuestos), con monorepo `backend + frontend`.

## Stack

- **Backend:** Python + Django + Django REST Framework
- **Base de datos (dev):** SQLite
- **Frontend:** React + Vite + TypeScript
- **Estructura:**
  - `/backend`
  - `/frontend`
  - `/.env.example` (puertos del launcher `start.py`)

## Estructura de carpetas

```text
.
├── backend/
│   ├── catalog/          # Catálogo comercial (modelos, API, seed)
│   ├── config/           # Settings, urls, wsgi/asgi
│   ├── core/             # App base con endpoint de health
│   ├── manage.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   └── router/
│   ├── package.json
│   └── .env.example
└── start.py              # Script de arranque rápido
```

## Requisitos (Windows + VS Code)

- Python 3.11+
- Node.js 20+
- npm
- VS Code (opcional pero recomendado)

> En Windows se asume uso de `py` launcher.

## Variables de entorno

### Launcher (`start.py`)

1. Copia archivo de ejemplo:
   - `.env.example` → `.env`
2. Variables disponibles:
   - `APP_OPEN_URL` (default: `http://localhost:5174`)
   - `FRONTEND_PORT` (default: `5174`)
   - `BACKEND_PORT` (default: `8001`)

### Backend

1. Copia archivo de ejemplo:
   - `backend/.env.example` → `backend/.env` (opcional para desarrollo)
2. Variables disponibles:
   - `DJANGO_DEBUG`
   - `DJANGO_SECRET_KEY`
   - `DJANGO_ALLOWED_HOSTS`
   - `CORS_ALLOWED_ORIGINS`
   - `DEFAULT_FROM_EMAIL`
   - `QUOTE_NOTIFICATION_EMAIL`
   - `EMAIL_BACKEND` (por defecto consola en desarrollo)



### Backend (Render producción)

Configurar estas variables en Render para endurecimiento de seguridad:

- `SECRET_KEY`
- `DEBUG=false`
- `DATABASE_URL`
- `ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`
- `CSRF_TRUSTED_ORIGINS`
- `SECURE_SSL_REDIRECT`
- `SECURE_HSTS_SECONDS`
- `QUOTE_NOTIFICATION_EMAIL`
- `DEFAULT_FROM_EMAIL`
- `EMAIL_BACKEND`

Notas:
- Mantener `CORS_ALLOW_ALL_ORIGINS=false` (solo emergencia local).
- En Render, `SECURE_PROXY_SSL_HEADER` se configura en settings para respetar `X-Forwarded-Proto` y evitar loops HTTPS.

### Frontend

1. Copia archivo de ejemplo:
   - `frontend/.env.example` → `frontend/.env`
2. Variable disponible:
   - `VITE_API_BASE_URL` (ejemplo: `http://127.0.0.1:8001/api`)
  - `VITE_WHATSAPP_NUMBER` (ejemplo: `56912345678`)
  - `VITE_PUBLIC_SITE_URL` (ejemplo local: `http://localhost:5174`, producción: `https://web-ventas-ps62.onrender.com`)

## Comandos rápidos con `start.py`

Desde la raíz del proyecto:

```bash
py start.py
```
Flujo recomendado (comando maestro): prepara backend/frontend y luego inicia el entorno completo. Este comando:
- instala dependencias Python (`pip install -r backend/requirements.txt`)
- aplica migraciones (`python manage.py migrate`)
- carga catálogo demo (`python manage.py seed_catalog`)
- crea/actualiza usuario demo (`python manage.py seed_demo_user`)
- verifica backend (`python manage.py check`)
- instala dependencias frontend (`npm install`)
- levanta backend + frontend y abre navegador en `APP_OPEN_URL` (default `http://localhost:5174`)

```bash
py start.py setup
```
Ejecuta preparación completa sin abrir servidores (equivale a `py start.py prepare`).

```bash
py start.py prepare
```
Alias de `setup`: prepara todo el entorno sin abrir backend/frontend.

```bash
py start.py backend
```
Levanta Django en `http://127.0.0.1:8001`.

```bash
py start.py frontend
```
Levanta Vite en `http://127.0.0.1:5174`.

```bash
py start.py dev
```
Abre backend y frontend en terminales separadas y abre navegador, sin instalar dependencias ni correr migraciones.

## Base de datos y migraciones

Desde `backend/`:

```bash
python manage.py makemigrations
python manage.py migrate
```

## Seed de catálogo demo

Desde `backend/`:

```bash
python manage.py seed_catalog
python manage.py seed_demo_user
```

- `seed_catalog` crea/actualiza categorías, marcas, proveedores, productos demo, specs técnicas y promociones sin duplicar registros principales.
  - dataset demo ampliado a ~50 productos (maquinaria, repuestos, servicios/accesorios y algunos no publicados para validar filtros).
  - crea/actualiza 5 promociones demo activas para probar carrusel Hero y CTAs.
- `seed_demo_user` crea (o actualiza) el usuario vendedor demo de forma idempotente:
  - username: `vendedor`
  - password: `vendedor123`
  - email: `vendedor@example.com`
- `generate_demo_products` genera productos demo variables por tipo (maquinaria y repuestos), incluyendo especificaciones técnicas por producto.

Uso interactivo:

```bash
python manage.py generate_demo_products
```

Uso no interactivo (ideal para pruebas/CI):

```bash
python manage.py generate_demo_products --tijeras 10 --brazos 8 --baterias 20 --ruedas 20 --controles 15 --no-input
```

> Para ver datos reales en el frontend público, ejecuta `python manage.py seed_catalog` antes de abrir la Home.

## Endpoints principales del backend

Públicos:
- `GET /api/health/`
- `GET /api/categories/`
- `GET /api/brands/`
- `GET /api/suppliers/`
- `GET /api/products/`
- `GET /api/products/<slug>/`
- `GET /api/promotions/`
- `POST /api/quote-requests/`
- `GET /api/product-images/?product=<id>`
- `GET /api/product-specs/?product=<id>`

Auth JWT:
- `POST /api/auth/login/`
- `POST /api/auth/refresh/`
- `GET /api/auth/me/`

Privados (requieren token):
- Escritura (`POST/PUT/PATCH/DELETE`) de productos, categorías, marcas, proveedores y promociones.
- Gestión de imágenes de producto (`/api/product-images/`) con upload `multipart/form-data`.
- Gestión de especificaciones técnicas (`/api/product-specs/`).
- `GET /api/quote-requests/` (listado para panel vendedor, con filtros `status`, `product`, `search` y `ordering`).
- `GET /api/quote-requests/<id>/` (detalle privado para gestión comercial).
- `PATCH /api/quote-requests/<id>/` (actualizar estado, notas internas y respuesta comercial).
- `DELETE /api/quote-requests/<id>/` (eliminar cotización desde panel privado).
- `GET /api/products/?include_unpublished=true` para ver productos no publicados en panel.
- `GET /api/categories|brands|suppliers|promotions/?include_inactive=true` para que panel admin vea entidades activas e inactivas (requiere token).

> Por defecto `GET /api/products/` devuelve solo productos publicados (`is_published=True`).

## Puertos del proyecto

- **Frontend:** `http://localhost:5174`
- **Backend:** `http://127.0.0.1:8001`

## Frontend público conectado a API (Fase 11 visual pública)

- Home (`/`) ahora incluye hero comercial con carrusel de promociones (`/api/promotions/`) y fallback estático cuando no hay datos.
- Catálogo (`/catalogo`) consume `GET /api/products/` con filtros públicos por `search`, `category`, `brand`, `product_type`, `condition`, `stock_status` y `ordering`.
- Topbar pública fija con navegación visible (`Inicio`, `Catálogo`, `Cotizar`), teléfono/WhatsApp y acceso a login.
- Si existe sesión de vendedor activa, la topbar pública muestra acceso rápido **`Volver al panel`** hacia `/admin`.
- Sidebar pública reforzada con buscador comercial y categorías reales/fallback que redirigen a `/catalogo?...`.
- Detalle de producto (`/producto/:slug`) consume `GET /api/products/<slug>/` y sugiere productos relacionados de la misma categoría.
- Formulario de cotización (`/cotizar`) consume `POST /api/quote-requests/` y puede preseleccionar producto vía query param (`?product=<id>`).
- Si backend falla, Home mantiene fallback visual (hero/categorías estáticas y productos de respaldo), y catálogo muestra estado de error claro.

### Flujo público recomendado

`Inicio → Catálogo → Producto → Cotizar / WhatsApp`

## Panel vendedor (Fase 8)

Rutas privadas frontend:
- `/login`
- `/admin`
- `/admin/productos`
- `/admin/productos/nuevo`
- `/admin/productos/:slug/editar`
- `/admin/cotizaciones`
- `/admin/cotizaciones/:id`
- `/admin/promociones`
- `/admin/promociones/nueva`
- `/admin/promociones/:id/editar`
- `/admin/categorias`
- `/admin/categorias/nueva`
- `/admin/categorias/:id/editar`
- `/admin/marcas`
- `/admin/marcas/nueva`
- `/admin/marcas/:id/editar`
- `/admin/proveedores`
- `/admin/proveedores/nuevo`
- `/admin/proveedores/:id/editar`

El panel vendedor ahora permite:
- CRUD de productos (crear, editar, publicar/despublicar, destacar y eliminar).
- CRUD inicial de categorías, marcas, proveedores y promociones desde rutas privadas del panel vendedor.
- Gestión de imágenes por producto en la vista de edición:
  - agregar imagen
  - editar `alt_text`, `order` y bandera `is_main`
  - eliminar imagen
- Gestión de especificaciones técnicas por producto en la vista de edición:
  - agregar especificación (`name`, `value`, `unit`, `order`)
  - editar especificación
  - eliminar especificación
- Interfaz compactada visualmente para reducir espacios vacíos, mostrar más contenido arriba y facilitar la operación diaria.

Flujo recomendado:

```bash
py start.py
```

Luego inicia sesión en `http://localhost:5174/login` con el usuario demo y accede al panel vendedor.


### Flujo de cotizaciones (Fase 10)

- Público (`/cotizar`): el cliente puede enviar nombre, teléfono, email, mensaje y opcionalmente empresa, ciudad y método preferido (WhatsApp/teléfono/email).
- Backend guarda la solicitud en `QuoteRequest` con estado inicial `new`.
- Al crear una cotización pública se dispara un servicio de notificación por email:
  - aviso al vendedor (`QUOTE_NOTIFICATION_EMAIL`)
  - comprobante al cliente (`customer_email`)
- En desarrollo, los correos se ven en consola usando `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`.
- Privado (`/admin/cotizaciones`): el vendedor puede filtrar/buscar/ordenar, revisar resumen por estado y abrir el detalle comercial.
- Privado (`/admin/cotizaciones/:id`): editar estado, notas internas y respuesta comercial.

Reglas de fecha por estado:
- `contacted` completa `contacted_at` (solo si estaba vacío).
- `quoted` completa `quoted_at` (solo si estaba vacío).
- `closed` completa `closed_at` (solo si estaba vacío).

## Próximas fases (preparado, no implementado aún)

- Carrito y pagos

## Desarrollo recomendado en VS Code

1. Abre la carpeta raíz en VS Code.
2. Ejecuta `py start.py` en terminal integrada.
3. Espera a que el launcher termine preparación y abra backend/frontend.
4. Abre `http://localhost:5174` (o la URL configurada en `APP_OPEN_URL`).

## Ejecutar en paralelo con `market-trading-bot`

Este proyecto queda configurado para no colisionar con `market-trading-bot`:

- `market-trading-bot` (ocupado): frontend `5173`, backend `8000`
- `web-ventas-generica` (este repo): frontend `5174`, backend `8001`

Pasos recomendados:

1. Mantén `market-trading-bot` ejecutándose sin tocar sus procesos.
2. En este repo, ejecuta:
   - `py start.py backend` → `http://127.0.0.1:8001`
   - `py start.py frontend` → `http://127.0.0.1:5174`
3. Navega a `http://localhost:5174`.


## Archivos media en desarrollo

- `MEDIA_URL` está configurado como `/media/`.
- `MEDIA_ROOT` apunta a `backend/media/`.
- En modo `DEBUG=True`, Django sirve archivos media automáticamente desde `config/urls.py`.
- Para carga de imágenes de productos en API admin usa `multipart/form-data` contra `POST /api/product-images/`.

## Deploy en Render (backend + frontend)

### 1) Backend Django/DRF como **Web Service**

- **Root Directory:** `backend`
- **Build Command:** `./build.sh`
- **Start Command:** `gunicorn config.wsgi:application`

> `build.sh` instala dependencias y ejecuta `collectstatic`. No ejecuta seeds automáticos para evitar duplicación de datos demo.

Variables de entorno recomendadas para el backend:

- `SECRET_KEY` (obligatoria en producción)
- `DEBUG=False`
- `ALLOWED_HOSTS=tu-backend.onrender.com`
- `DATABASE_URL` (entregada por Render PostgreSQL)
- `CORS_ALLOWED_ORIGINS=https://tu-frontend.onrender.com,http://localhost:5174`
- `CSRF_TRUSTED_ORIGINS=https://tu-backend.onrender.com,https://tu-frontend.onrender.com`
- `DEFAULT_FROM_EMAIL` (opcional)
- `QUOTE_NOTIFICATION_EMAIL` (opcional)
- `EMAIL_BACKEND` (opcional)

Comandos manuales post-deploy (Shell de Render en backend):

```bash
python manage.py migrate
python manage.py seed_catalog
```

- `seed_catalog` es idempotente y puede ejecutarse manualmente.
- **No** usar `generate_demo_products` en cada deploy automático.

### 2) Base de datos como **Render PostgreSQL**

- Crear una instancia PostgreSQL en Render.
- Vincular su `DATABASE_URL` al servicio backend.
- En local, si `DATABASE_URL` no existe, el proyecto sigue usando SQLite.

### 3) Frontend React/Vite como **Static Site**

- **Root Directory:** `frontend`
- **Build Command:** `npm install && npm run build`
- **Publish Directory:** `dist`

Variable de entorno del frontend:

- `VITE_API_BASE_URL=https://TU-BACKEND.onrender.com/api`
- `VITE_WHATSAPP_NUMBER=<tu_numero>`

El frontend ya consume la API desde `VITE_API_BASE_URL` (con fallback local para desarrollo).


## Uploads de imágenes
- Formatos permitidos: `.jpg`, `.jpeg`, `.png`, `.webp`.
- MIME permitidos: `image/jpeg`, `image/png`, `image/webp`.
- Tamaño máximo configurable en backend con `MAX_UPLOAD_IMAGE_SIZE_MB` (default: 5 MB).


### Nota SEO técnica

- `frontend/public/robots.txt` usa temporalmente el dominio Render actual en la línea `Sitemap`. Si cambia el dominio productivo, actualizar ese valor manualmente.


## SEO técnico público (estado actual)

- Sitemap público disponible en `/sitemap.xml` (producción actual: `https://web-ventas-ps62.onrender.com/sitemap.xml`).
- Robots público disponible en `/robots.txt` (producción actual: `https://web-ventas-ps62.onrender.com/robots.txt`).
- Si cambia el dominio de Render, actualizar las URLs absolutas referenciadas en `frontend/public/robots.txt` y `frontend/public/sitemap.xml`.
