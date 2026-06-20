# Prompt 049 — Eliminación real de productos y columnas del listado

## Despublicación vs. eliminación física

La despublicación cambia el estado del producto para que no sea visible en el catálogo público, pero el registro sigue existiendo en la base de datos. Por eso puede seguir apareciendo en paneles administrativos que consultan productos con `include_unpublished=true`.

La eliminación física borra el registro `Product` de la base de datos. Si se elimina físicamente, el producto ya no debe aparecer en listados administrativos ni públicos, incluso cuando se solicitan productos no publicados.

## Problema detectado en Prompt 048

El flujo visual del panel mostraba el mensaje “Producto eliminado correctamente.” después de confirmar la eliminación, pero el endpoint de borrado solo cambiaba `IsPublished` a `false`. Como el listado administrativo usa `include_unpublished=true`, el producto seguía apareciendo.

## Condiciones para eliminar físicamente

Un producto se elimina físicamente solo cuando no tiene relaciones comerciales o históricas críticas asociadas. Antes de borrar se valida la existencia de cotizaciones vinculadas.

Si no existen cotizaciones asociadas, el backend elimina o desvincula relaciones técnicas dependientes y luego elimina el producto dentro de una operación transaccional cuando el proveedor de base de datos lo permite.

## Relaciones que bloquean eliminación

La eliminación se bloquea cuando el producto tiene cotizaciones o solicitudes de cotización asociadas (`QuoteRequests`). En ese caso el backend responde con conflicto y el mensaje:

> No se puede eliminar este producto porque tiene cotizaciones asociadas. Puedes despublicarlo o inactivarlo.

## Relaciones técnicas eliminadas o desvinculadas

Cuando el producto no tiene cotizaciones asociadas, se consideran seguras estas operaciones técnicas:

- eliminar imágenes del producto;
- eliminar especificaciones técnicas del producto;
- eliminar asociaciones de destacados/home que apuntan al producto;
- desvincular promociones del producto sin borrar la promoción.

No se eliminan promociones completas, marcas, proveedores, categorías, usuarios ni datos comerciales/históricos.

## Cotizaciones y datos históricos

No se eliminan cotizaciones ni datos históricos. Tampoco se modifican cotizaciones para permitir el borrado. Si existe una cotización asociada, el producto permanece intacto.

## Corrección Categoría/Subcategoría en listado

El listado administrativo separa ahora la categoría raíz real de la subcategoría:

- Si el producto pertenece a una subcategoría, “Categoría” muestra la raíz y “Subcategoría” muestra la hija.
- Si el producto pertenece directamente a una categoría raíz, “Categoría” muestra esa raíz y “Subcategoría” muestra “—”.

La lógica usa las categorías cargadas desde la API y no hardcodea nombres de categorías principales.

## Qué no se tocó

No se tocaron secretos, credenciales, SMTP, Plesk, Render, Django, migraciones anteriores, conexión productiva, `web.config` productivo, precio/IVA visual, Panel Categorías base ni datos históricos. No se ejecutó SQL real ni `dotnet ef database update`.
