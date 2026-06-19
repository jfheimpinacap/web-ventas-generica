# Prompt 045 — Categorías jerárquicas y precio visual de productos

## Menú público de categorías

- El menú público debe tomar como primer nivel únicamente categorías raíz activas (`ParentId`/`parent` nulo).
- Al enfocar o pasar sobre una categoría principal, el panel derecho muestra solo subcategorías activas reales.
- Ya no se debe usar el bloque de llamada a la acción `Ver <categoría>` cuando una principal no tiene hijos; en ese caso se muestra un estado discreto de ausencia de subcategorías.
- El clic en una categoría principal navega a `/catalogo?category=<id_categoria_principal>`.
- El clic en una subcategoría navega a `/catalogo?category=<id_subcategoria>`.

## Panel Categorías

- El listado separa categorías principales y subcategorías por relación jerárquica (`ParentId`).
- Las categorías principales pueden editarse, borrarse o seleccionarse para administrar sus subcategorías.
- Las subcategorías se crean desde una categoría principal seleccionada y heredan/derivan internamente el `ProductType` de la raíz.
- El formulario visual solo expone nombre, ubicación controlada y estado activo/inactivo; no expone tipo, orden ni descripción como campos operativos.

## Borrado seguro

- El borrado de categorías es físico cuando es seguro.
- No hay borrado en cascada de productos ni subcategorías.
- Si una categoría tiene productos asociados, el backend bloquea el borrado con un mensaje claro para inactivarla o mover productos primero.
- Si una categoría tiene subcategorías, el backend bloquea el borrado con un mensaje claro para eliminar o mover subcategorías primero.

## Movimiento/corrección de categorías

- El formulario de edición incluye una ubicación controlada: categoría principal o subcategoría de una raíz.
- Una categoría raíz creada por error puede moverse bajo una categoría principal real cuando no tiene hijos que generarían un tercer nivel.
- Una subcategoría puede moverse a otra principal o convertirse en categoría principal.
- La jerarquía queda limitada a dos niveles.
- No se permite que una categoría sea padre de sí misma ni que una categoría con hijos se mueva bajo otra raíz.
- Los productos asociados se conservan en la misma categoría cuando esta se mueve.

## Producto: moneda, precio e IVA visual

- Se agregan campos persistidos al producto:
  - `PriceCurrency`: `CLP` o `USD`.
  - `PriceTaxMode`: `plus_vat` o `vat_included`.
- Los valores por defecto para productos existentes son `CLP` y `plus_vat`.
- No se calcula IVA, no se suma impuesto y no se convierte moneda.
- El texto visual esperado es:
  - `$5.500.000 + IVA`
  - `$5.500.000 IVA incluido`
  - `USD 5.500 + IVA`
  - `USD 5.500 IVA incluido`
- Si el precio no es visible o no existe, se mantiene el comportamiento `Consultar`.

## Formulario de producto

- El campo Precio se reemplaza visualmente por una fila de tres controles: Moneda, Precio e IVA.
- Se mantiene la normalización de precio chileno: `5.500.000` y `5500000` se envían como `5500000`.
- `Descripción corta` se oculta visualmente; se deriva desde `Descripción` cuando es necesario para compatibilidad técnica.
- `Descripción completa` se muestra como `Descripción`.
- El bloque de especificaciones técnicas se oculta del formulario de creación/edición sin borrar endpoints ni datos.

## Migración EF Core

- Migración creada: `AddProductPriceDisplayFields`.
- Campos agregados: `PriceCurrency` y `PriceTaxMode` en `Products`.
- La migración no fue aplicada en base de datos.
- No se ejecutó `dotnet ef database update`.

## Pendiente

- El buscador/listado de productos queda pendiente para Prompt 046.
