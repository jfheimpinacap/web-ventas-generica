# Frontend React/Vite

El frontend usa exclusivamente la API ASP.NET Core .NET 8. La URL se configura mediante Vite y no está hardcodeada en componentes.

## Configuración local

```env
VITE_API_BASE_URL=http://localhost:5000
VITE_WHATSAPP_NUMBER=56912345678
VITE_PUBLIC_SITE_URL=http://localhost:5174
VITE_GTM_ID=
```

`VITE_API_BASE_URL` puede contener el origen del backend o una base terminada en `/api`. El cliente evita duplicar ese prefijo.

## Contrato de API

- Las lecturas públicas de productos, categorías, marcas, proveedores, promociones y secciones Home usan `/api/public/*`.
- Administración y autenticación usan `/api/*` y, cuando corresponde, `Authorization: Bearer`.
- El health check usa `/health`.
- Marcas y promociones se escriben mediante JSON; los flujos de archivo que admite la API .NET, como imágenes de producto y fichas técnicas, mantienen `FormData`.

## Diagnóstico controlado

La ruta directa `http://localhost:5174/diagnostico-api` permite comprobar health, login y `/auth/me` contra la API configurada. No tiene enlace en la navegación pública principal.

1. Configura manualmente `frontend/.env.local` (no versionado) con `VITE_API_BASE_URL`.
2. Ejecuta `npm run dev` desde `frontend/`.
3. Abre `/diagnostico-api` y usa las pruebas necesarias.

El login diagnóstico conserva el access token solo en memoria. No muestres ni guardes passwords, tokens o headers `Authorization` completos en consola, capturas o Git. La pantalla diagnóstica no reemplaza el flujo normal de `/login`.

## Panel vendedor

Los listados y escrituras administrativas consumen la API .NET mediante Bearer. Las rutas vigentes incluyen:

- `/admin/productos`
- `/admin/categorias`
- `/admin/marcas`
- `/admin/proveedores`
- `/admin/promociones`
- `/admin/cotizaciones`

No uses validaciones manuales para alterar datos reales sin autorización expresa.

## Rutas comerciales de maquinaria

Las rutas públicas `/maquinaria-nueva` y `/maquinaria-usada` reutilizan el catálogo con filtros fijos `product_type=machinery` y, respectivamente, `condition=new` o `condition=used`. Esos valores definidos por la ruta tienen prioridad sobre parámetros manipulables de la URL; las subcategorías, marcas, disponibilidad, búsqueda y ordenamiento siguen disponibles.

Estas líneas comerciales no son categorías de base de datos. Las ilustraciones locales reemplazables están en `public/images/maquinaria-nueva.svg` y `public/images/maquinaria-usada.svg`. El arriendo de maquinaria queda fuera de alcance.
