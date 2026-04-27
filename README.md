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

### Frontend

1. Copia archivo de ejemplo:
   - `frontend/.env.example` → `frontend/.env`
2. Variable disponible:
   - `VITE_API_BASE_URL` (ejemplo: `http://127.0.0.1:8001/api`)
  - `VITE_WHATSAPP_NUMBER` (ejemplo: `56912345678`)

## Comandos rápidos con `start.py`

Desde la raíz del proyecto:

```bash
py start.py setup
```
Instala dependencias del backend/frontend y ejecuta migraciones.

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
Muestra guía para levantar backend y frontend en terminales separadas.

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
```

El comando crea/actualiza categorías, marcas, proveedores, productos demo, specs técnicas y promociones sin duplicar registros principales.

> Para ver datos reales en el frontend público, ejecuta `python manage.py seed_catalog` antes de abrir la Home.

## Endpoints principales del backend

- `GET /api/health/`
- `GET /api/categories/`
- `GET /api/brands/`
- `GET /api/suppliers/`
- `GET /api/products/`
- `GET /api/products/<slug>/`
- `GET /api/promotions/`
- `POST /api/quote-requests/`

> Por defecto `GET /api/products/` devuelve solo productos publicados (`is_published=True`).

## Puertos del proyecto

- **Frontend:** `http://localhost:5174`
- **Backend:** `http://127.0.0.1:8001`

## Frontend público conectado a API (Fase 4)

- Home (`/`) consume promociones (`/api/promotions/`), categorías (`/api/categories/`) y productos destacados (`/api/products/?is_featured=true`).
- Buscador lateral usa `GET /api/products/?search=<texto>`.
- Detalle de producto (`/producto/:slug`) consume `GET /api/products/<slug>/`.
- Formulario de cotización (`/cotizar`) consume `POST /api/quote-requests/`.
- Si backend falla, Home mantiene fallback visual (hero y categorías estáticas, productos de respaldo).

## Próximas fases (preparado, no implementado aún)

- Login/JWT
- Panel vendedor personalizado
- CRUD frontend conectado a API
- Carrito y pagos

## Desarrollo recomendado en VS Code

1. Abre la carpeta raíz en VS Code.
2. Ejecuta `py start.py setup` en terminal integrada.
3. Abre dos terminales:
   - Terminal A: `py start.py backend`
   - Terminal B: `py start.py frontend`
4. Abre `http://localhost:5174`.

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
