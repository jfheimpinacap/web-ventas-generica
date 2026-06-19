# Filtros de productos y eliminación segura — Prompt 048

## Causa del problema

El listado del Panel Vendedor aplicaba filtros en frontend sobre una carga local de productos y mantenía criterios en `sessionStorage`. Además, el filtro visible **Tipo** dependía del `ProductType` legacy (`machinery`, `spare_part`, `service`) y el filtro visible **Categoría** se armaba desde los productos ya cargados, no desde categorías raíz reales. Por eso una categoría raíz nueva, como **Transporte**, no tenía por qué aparecer si no estaba en los productos cargados o si el filtro legacy seguía activo.

## Nueva lógica de filtros

- **Categoría** representa una categoría raíz real (`ParentId = null`).
- **Subcategoría** representa una categoría hija real (`ParentId = id de la categoría raíz`).
- `ProductType` queda como campo técnico/legacy para compatibilidad, pero ya no es el filtro visible principal del listado.

El filtro Categoría consume las categorías reales desde `GET /api/categories/` con `include_inactive=true` y muestra raíces activas. Esto incluye **Maquinaria**, **Repuestos**, **Servicios**, **Transporte** y cualquier futura categoría principal real creada por el usuario.

El filtro Subcategoría depende de la categoría raíz seleccionada. Si no hay categoría seleccionada, queda deshabilitado con el texto “Selecciona una categoría primero”. Al cambiar de categoría raíz se limpia una subcategoría previa si ya no pertenece a esa raíz.

## Buscar y Limpiar filtros

El botón **Buscar** envía los filtros visibles al backend:

- texto de búsqueda;
- categoría raíz o subcategoría seleccionada;
- marca;
- condición;
- stock;
- estado de publicación.

El botón **Limpiar filtros** borra texto, categoría, subcategoría, marca, condición, stock y vuelve al filtro por defecto de publicados, recargando el listado sin restricciones adicionales.

## Filtro por categoría principal

El endpoint admin de productos ya soporta filtrar por una categoría raíz incluyendo productos asociados directamente a esa raíz y productos asociados a sus hijas inmediatas. Si se selecciona una subcategoría, se envía el id de esa subcategoría y el resultado queda limitado a esa subcategoría.

## Búsqueda de texto

La búsqueda admin conserva nombre, slug, SKU, modelo y descripción corta, y ahora también considera nombre de categoría, marca y proveedor cuando existen esas relaciones.

## Eliminación segura de producto

La eliminación disponible en `DELETE /api/products/{idOrSlug}/` se mantiene como eliminación segura por **soft delete funcional**: el producto no se borra físicamente, sino que se marca `IsPublished = false`.

Decisión técnica:

- No se borra físicamente el producto.
- No se eliminan cotizaciones.
- No se eliminan imágenes, especificaciones, promociones ni historial comercial por cascada.
- El producto desaparece del listado publicado por defecto y de las vistas públicas que solo muestran publicados.
- Si se necesita verlo, el panel permite cambiar el filtro de publicación a “Todos” o “Solo no publicados”.

La eliminación se movió a la pantalla de edición, en una zona de peligro, con segunda confirmación visual y botones “Sí, eliminar” y “Cancelar”. No hay eliminación rápida en la tabla.

## Qué NO se tocó

No se tocaron:

- Django/DRF;
- `start.py`;
- Plesk;
- Render;
- credenciales;
- SMTP;
- `web.config` productivo;
- migraciones anteriores;
- precio, moneda o IVA visual;
- Panel Categorías base;
- cotizaciones salvo la revisión de relación para protegerlas.

## Pendiente

- Validar manualmente en el panel real que **Transporte** aparezca cuando exista como categoría raíz activa.
- Validar manualmente el flujo de eliminación/despublicación con un producto real de prueba.
