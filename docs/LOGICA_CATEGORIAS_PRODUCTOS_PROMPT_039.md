# Lógica de categorías y productos — Prompt 039

## Tipo vs Categoría

El **Tipo** es una línea comercial fija del sistema. Los valores permitidos son:

- `machinery` — Maquinaria
- `spare_part` — Repuestos
- `service` — Servicios

La **Categoría** es una clasificación comercial dentro de un Tipo. Una categoría no debe usarse como Tipo ni reemplazar los valores fijos anteriores.

## Categorías padre y subcategorías

Cada categoría pertenece a un Tipo mediante `product_type`. La categoría padre es opcional, pero si se define debe cumplir estas reglas:

- existir;
- estar activa;
- pertenecer al mismo `product_type` que la categoría hija;
- no ser la misma categoría que se está editando.

Ejemplo esperado:

```text
Tipo Maquinaria > Categoría Elevadores > Subcategoría Elevador tijera
Tipo Repuestos > Categoría Sistema hidráulico > Subcategoría Mangueras hidráulicas
Tipo Servicios > Categoría Gestión comercial > Subcategoría Búsqueda de proveedores
```

## Uso en Productos

En el formulario de productos se selecciona primero el Tipo. Luego el selector de Categoría muestra solo categorías activas de ese Tipo.

Si el usuario cambia el Tipo, el formulario limpia la categoría seleccionada para evitar asociaciones cruzadas. El backend también valida la coherencia: un producto `machinery` no puede guardarse con una categoría `spare_part`, y viceversa.

## Validaciones implementadas

- `Category.product_type` es obligatorio en creación.
- `product_type` solo acepta Maquinaria, Repuestos o Servicios.
- La categoría padre debe ser activa y del mismo Tipo.
- Una categoría no puede ser padre de sí misma.
- Los listados de categorías permiten filtrar por `product_type`.
- La creación y edición de productos rechaza categorías que no correspondan al Tipo seleccionado.

## Pruebas locales

Comandos previstos para validación local:

```bash
dotnet restore ./backend-dotnet/JemNexus.sln
dotnet build ./backend-dotnet/JemNexus.sln
dotnet test ./backend-dotnet/JemNexus.sln
cd frontend && npm run build
git status --short
```

> En este cambio no se debe ejecutar `dotnet ef database update` ni SQL real. La migración queda creada para aplicación controlada fuera de este prompt.
