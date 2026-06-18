# Lógica de categorías jerárquicas — Prompt 043

## Modelo conceptual

La administración comercial queda organizada como una jerarquía simple de dos niveles:

1. **Categoría principal**: categoría con `ParentId` nulo.
2. **Subcategoría**: categoría con `ParentId` apuntando a una categoría principal.
3. **Producto**: se clasifica visualmente seleccionando primero una categoría principal y luego una subcategoría.

El modelo existente `Category.ParentId` se mantiene como la fuente de la jerarquía. No se agregan columnas ni se eliminan datos existentes.

## Administración en el panel vendedor

La pantalla de Categorías separa la operación en dos secciones:

- **Categorías principales**: permite ver, editar, inactivar y crear categorías raíz como Maquinaria, Repuestos, Servicios o futuras categorías como Logística.
- **Subcategorías**: al seleccionar una categoría principal, permite crear, editar e inactivar subcategorías dentro de esa raíz.

Los formularios de categorías muestran solo:

- Nombre.
- Activa/Inactiva.

Los campos técnicos `ProductType`, `ParentId`, `Order` y `Description` se conservan para compatibilidad, pero no se muestran como campos visuales genéricos del flujo simplificado.

## Productos

El formulario de productos deja de presentar el campo visual **Tipo de producto**. El flujo visible es:

1. Categoría principal.
2. Subcategoría dependiente de la categoría principal.
3. Datos comerciales y técnicos del producto.

Si el usuario cambia la categoría principal, la subcategoría seleccionada se limpia. Si una categoría principal no tiene subcategorías activas, el formulario muestra el mensaje para crearlas desde Categorías.

## Menú público y catálogo

El menú público de Categorías usa solo categorías principales en el primer nivel y muestra las subcategorías dentro de su categoría principal.

El catálogo acepta el filtro `category` tanto para una categoría principal como para una subcategoría:

- Si `category` apunta a una categoría principal, se incluyen los productos asociados directamente a esa categoría o a sus subcategorías inmediatas.
- Si `category` apunta a una subcategoría, se muestran los productos de esa subcategoría.

Las rutas directas `/catalogo` y `/producto/:slug` se mantienen.

## ProductType

`ProductType` queda como campo técnico/legacy por compatibilidad con datos, filtros y endpoints existentes.

- En categorías nuevas, si el panel no envía un tipo explícito, el backend conserva un valor técnico por defecto.
- En subcategorías, el backend deriva `ProductType` desde la categoría principal padre.
- En productos, el panel deriva `ProductType` desde la categoría principal cuando envía el formulario y el backend también puede derivarlo desde la categoría seleccionada.
- El usuario ya no administra visualmente `ProductType` en Categorías ni Productos.

Para categorías principales dinámicas futuras, el sistema permite crearlas como categorías raíz. Si no corresponden a Maquinaria, Repuestos o Servicios, quedan compatibles con el campo técnico legacy sin bloquear la creación de la jerarquía.

## Migración

No se creó migración EF Core en este prompt.

Motivo: el modelo actual ya tenía `Category.ParentId`, `Category.ProductType` y `Product.CategoryId`, suficientes para representar la jerarquía de dos niveles sin cambios de esquema.

No se aplicó ninguna migración y no se ejecutó `dotnet ef database update`.

## Compatibilidad de datos existentes

- No se borran categorías, productos ni migraciones anteriores.
- Las categorías raíz existentes siguen funcionando como categorías principales.
- Las subcategorías existentes con `ParentId` se muestran dentro de su categoría principal.
- Productos antiguos con `CategoryId` y `ProductType` siguen funcionando.
- El catálogo mantiene compatibilidad con filtros por categoría y `product_type`.
