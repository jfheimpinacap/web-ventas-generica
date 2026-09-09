# Contrato estático actual de JEM Nexus

**Commit inspeccionado:** `7746250d05d6ed7d90d20b5fdc380457c6418f0a`.
La fuente machine-readable completa es `schemas/v1/jem-nexus-contract.json`.

## Fuentes inspeccionadas

- `backend-dotnet/JemNexus.Api/Models/{Product,Category,Brand,Supplier,ProductImage,ProductSpec,TechnicalSheet}.cs`.
- `backend-dotnet/JemNexus.Api/Dtos/{CommercialWriteDtos,CommercialReadDtos,CommercialPublicReadDtos,TechnicalSheetDtos}.cs`.
- `backend-dotnet/JemNexus.Api/Validation/CommercialValidation.cs`.
- `backend-dotnet/JemNexus.Api/Endpoints/{CommercialWriteEndpoints,CommercialReadEndpoints,CommercialPublicReadEndpoints,TechnicalSheetEndpoints}.cs`.
- `backend-dotnet/JemNexus.Api/Data/JemNexusDbContext.cs`, model snapshot y migraciones comerciales,
  de datos técnicos, fichas y asociación de fichas.
- `backend-dotnet/JemNexus.Api/Program.cs` (JSON web defaults/case-insensitive).

## Confirmaciones

`Product` estructura `Name`, `Slug`, categoría obligatoria, marca/proveedor/ficha opcionales,
`ProductType`, `Condition`, descripciones, `Model`, `Sku`, `WorkingHeightM`, `TerrainType`, `Year`,
`HoursMeter`, `MaximumLoadCapacityKg`, `MachineWeightKg`, `PowerSource`, tres beneficios incluidos,
precio/moneda/impuesto/visibilidad, stock, destacado y publicación. `ProductImage` y `ProductSpec`
son colecciones uno-a-muchos con cascade; Brand y Supplier son opcionales; TechnicalSheet es una
ficha reutilizable por varios productos y se pone null al eliminar. Category tiene jerarquía
`Parent`/`Children` y `ProductType`.

Creación requiere efectivamente nombre, slug y categoría; el DTO usa nullable para soportar PUT
parcial y el endpoint aplica defaults al crear. Longitudes relevantes: nombre 220, slug 240,
modelo/SKU 120, descripción corta 280; spec key 120/value 220/unit 40. Precio y horas admiten cero;
capacidades/peso/working height, si aparecen, deben ser mayores que cero. Año es 1900..año UTC+1.

Enums cerrados confirmados: product type `machinery|spare_part|service`; condition
`new|used|refurbished|not_applicable`; stock `available|on_request|sold|reserved`; power
`diesel|electric_24v|electric_lithium`; terrain
`indoor_smooth|outdoor|outdoor_slopes_and_ramps`; currency `CLP|USD`; tax
`plus_vat|vat_included`. Todo valor desconocido queda bloqueado.

## Discrepancias y límites

- Relaciones admiten aliases JSON (`category` y `category_id`, etc.); el endpoint debe resolver
  conflictos. La proyección canónica usa únicamente nombres `_id`.
- `TechnicalSheet` y `MachineWeightKg` son `JsonElement` en escritura, aunque entidad/lectura son
  nullable scalar; el endpoint interpreta null/número/id.
- `ProductSpec.Key` sale como `Name`; escritura acepta `Name` o `Key`. Es una asimetría real.
- `IsPublished` no aparece en DTO público; la consulta pública filtra publicados.
- Los tres flags `Includes*` son beneficios booleanos estructurados; beneficios arbitrarios deben
  ser specs y requieren revisión, no se inventan flags.
- No existe campo estructurado general “benefits/included items”. Tampoco existen
  `MaximumLiftHeightMm`, `BatteryVoltageV`, `BatteryCapacityAh` o `BatteryChemistry`.
- Public/admin no exponen exactamente el mismo conjunto (por ejemplo proveedor no es público y
  `MachineWeightKg` solo se devuelve para machinery).

## Regla crítica de altura y ProductSpec

**Altura de elevación o mástil jamás se proyecta a `WorkingHeightM`.** `WorkingHeightM` representa
altura de trabajo; cualquier altura máxima de elevación queda como `ProductSpec` hasta una decisión
humana de schema. `MaximumLiftHeightMm` es solo candidato futuro, no campo actual. Voltaje,
capacidad y química de batería también empiezan en `ProductSpec`. La utilidad de proyección aplica
esta separación explícita y no infiere equivalencias.
