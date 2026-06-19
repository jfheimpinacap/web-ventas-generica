# Hotfix categorías principales reales administrables — Prompt 046

## Causa encontrada

El panel vendedor lee categorías reales desde `GET /api/categories/` con `include_inactive=true`, por lo que solo puede mostrar registros existentes en la tabla `Categories`.

El menú público tenía un fallback en frontend que agregaba visualmente `Maquinaria`, `Repuestos` y `Servicios` cuando faltaban como categorías raíz reales. Por eso podían aparecer en el menú público aunque no existieran como registros administrables.

## Estado de Maquinaria, Repuestos y Servicios

Según el código revisado, `Maquinaria`, `Repuestos` y `Servicios` podían ser sintéticas en el menú público por fallback frontend. El backend público y admin ya listaban categorías reales desde base de datos; el problema era que no había garantía de datos canónicos raíz para esas tres líneas comerciales.

## Solución aplicada

Se creó una migración EF Core de datos llamada `EnsureCanonicalRootCategories` para asegurar que existan como categorías raíz reales:

- `Maquinaria` con `ProductType = machinery`.
- `Repuestos` con `ProductType = spare_part`.
- `Servicios` con `ProductType = service`.

Los registros nuevos se crean con:

- `ParentId = NULL`.
- `IsActive = true`.
- `Slug` coherente (`maquinaria`, `repuestos`, `servicios`).
- `Order` 1, 2 y 3.
- `CreatedAt` y `UpdatedAt` usando `SYSUTCDATETIME()`.

## Seguridad de la migración

La migración es idempotente a nivel SQL Server mediante `IF NOT EXISTS` antes de cada `INSERT`.

Para evitar duplicados, cada inserción valida la existencia de una categoría raíz equivalente por slug, nombre o `ProductType`. Si una categoría equivalente ya existe como raíz, no se crea otra. Si existe inactiva como raíz, se conserva y no se activa automáticamente.

La migración no:

- borra categorías;
- borra productos;
- mueve categorías;
- actualiza categorías existentes masivamente;
- modifica productos;
- modifica precios;
- toca cotizaciones;
- genera cascadas destructivas.

La migración fue creada pero no aplicada. No se ejecutó `dotnet ef database update` ni SQL real.

## Endpoints admin y públicos

No se cambiaron los endpoints porque ya cumplían la separación necesaria:

- Admin: `GET /api/categories/` lista categorías reales y permite `include_inactive=true`.
- Público: `GET /api/public/categories/` lista categorías reales activas.

## Menú público

Se eliminó el fallback sintético del menú público. Ahora el menú muestra únicamente categorías raíz activas recibidas desde el endpoint público y sus subcategorías activas reales.

Si una categoría principal real no tiene subcategorías, se mantiene el estado limpio `Sin subcategorías disponibles`.

Los enlaces siguen usando:

- Categoría principal: `/catalogo?category=<id_categoria_principal>`.
- Subcategoría: `/catalogo?category=<id_subcategoria>`.

## Panel Categorías

No se modificó el panel porque ya consume `getAdminCategories()` con `include_inactive=true` y filtra localmente por `Solo activas`, `Solo inactivas` o `Todas`. Al aplicar la migración, `Maquinaria`, `Repuestos` y `Servicios` quedarán como categorías raíz reales seleccionables, editables e inactivables/borrables si no tienen relaciones.

## Qué NO se tocó

No se tocaron:

- productos;
- precios, moneda o IVA visual;
- cotizaciones;
- SMTP;
- usuarios;
- login;
- buscador/listado de productos;
- imágenes;
- Home;
- footer;
- Django;
- Plesk;
- Render;
- credenciales;
- `web.config` productivo;
- archivos `.env.local`;
- ZIPs productivos.

## Pendiente

El buscador/listado de productos queda pendiente para Prompt 047.
