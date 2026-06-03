# Revisión Backend .NET 2B - Schema SQL inicial EF Core/SQL Server

Fecha de revisión: 2026-06-03  
Repositorio: `web-ventas-generica`  
Alcance: revisión técnica documental del schema EF Core/SQL Server inicial antes de aplicar migraciones en Plesk.  
Base destino futura considerada: SQL Server 2022, Windows Server, IIS/Plesk, base `jemnexusb_prod`, usuario `jemnexusb_api`.

> Importante: esta revisión **no ejecutó** `dotnet ef database update`, **no conectó** a `jemnexusb_prod`, **no tocó** la base real, **no regeneró** migraciones, **no modificó** frontend y **no eliminó** Django.

## 1. Resumen ejecutivo

El schema inicial EF Core/SQL Server reproduce de forma amplia el dominio comercial actual de Django: categorías, marcas, proveedores, productos, imágenes, especificaciones, promociones, secciones de home y solicitudes de cotización. La migración genera claves primarias `IDENTITY`, relaciones equivalentes a las relaciones principales Django, índices para filtros públicos y administrativos, unicidad en slugs y unicidad de posiciones/items de home.

La conclusión de esta revisión es: **APTO CON OBSERVACIONES**.

No se detectan bloqueos críticos para una base nueva/vacía en SQL Server 2022. Sin embargo, antes de aplicar en Plesk conviene resolver o aceptar explícitamente algunas observaciones: no existen claves foráneas reales hacia usuarios/auditoría, `UpdatedAt` no se actualiza automáticamente por SQL Server, no hay `CHECK CONSTRAINT` para enums/choices, los slugs son obligatorios en .NET aunque en Django se autogeneran si vienen en blanco, no hay defaults SQL para `Product.PriceVisible`, `Product.IsFeatured` e `Product.IsPublished`, y varios `nvarchar(max)` podrían limitarse si se desea mayor control operativo.

## 2. Archivos revisados

- `backend-dotnet/JemNexus.Api/Data/Migrations/20260603182917_InitialCommercialSchema.cs`
- `backend-dotnet/JemNexus.Api/Data/Migrations/20260603182917_InitialCommercialSchema.Designer.cs`
- `backend-dotnet/JemNexus.Api/Data/Migrations/JemNexusDbContextModelSnapshot.cs`
- `backend-dotnet/sql/InitialCommercialSchema.sql`
- `backend-dotnet/JemNexus.Api/Data/JemNexusDbContext.cs`
- `backend-dotnet/JemNexus.Api/Models/Brand.cs`
- `backend-dotnet/JemNexus.Api/Models/Category.cs`
- `backend-dotnet/JemNexus.Api/Models/Supplier.cs`
- `backend-dotnet/JemNexus.Api/Models/Product.cs`
- `backend-dotnet/JemNexus.Api/Models/ProductImage.cs`
- `backend-dotnet/JemNexus.Api/Models/ProductSpec.cs`
- `backend-dotnet/JemNexus.Api/Models/Promotion.cs`
- `backend-dotnet/JemNexus.Api/Models/HomeSectionItem.cs`
- `backend-dotnet/JemNexus.Api/Models/QuoteRequest.cs`
- `backend/catalog/models.py`
- `backend/core/models.py`
- `backend/core/views.py` para validar sitemap futuro basado en productos/categorías.
- `frontend/src/types/catalog.ts` y servicios frontend de catálogo/admin como referencia de contratos futuros.
- `docs/MIGRACION_BACKEND_ASPNETCORE_SQLSERVER.md`

## 3. Tablas detectadas

La migración/script crea las siguientes tablas:

| Tabla | Propósito | Columnas principales | Observaciones |
| --- | --- | --- | --- |
| `__EFMigrationsHistory` | Historial EF Core | `MigrationId`, `ProductVersion` | Normal para EF Core. |
| `Brands` | Marcas | `Id`, `Name`, `Slug`, `Logo`, `Description`, `IsActive`, auditoría | Compatible con Django. |
| `Categories` | Categorías jerárquicas | `Id`, `Name`, `Slug`, `ParentId`, `Description`, `IsActive`, `Order`, auditoría | Soporta árbol padre/hijos. |
| `Suppliers` | Proveedores | `Id`, `Name`, `ContactName`, `Phone`, `Email`, `Notes`, `IsActive`, auditoría | Compatible con Django. |
| `Products` | Catálogo principal | `Id`, `Name`, `Slug`, `CategoryId`, `BrandId`, `SupplierId`, `ProductType`, `Condition`, descripciones, `Model`, `Sku`, `Year`, `HoursMeter`, `Price`, `PriceVisible`, `StockStatus`, `IsFeatured`, `IsPublished`, auditoría | Cubre filtros públicos y administración futura. |
| `HomeSectionItems` | Productos destacados por sección de home | `Id`, `Section`, `Position`, `ProductId`, `IsActive`, auditoría | Incluye restricciones únicas por sección/posición y sección/producto. |
| `ProductImages` | Imágenes de productos | `Id`, `ProductId`, `Image`, `AltText`, `IsMain`, `Order`, auditoría | `Image` es ruta/string, no binario. |
| `ProductSpecs` | Especificaciones de productos | `Id`, `ProductId`, `Key`, `Value`, `Unit`, `Order`, auditoría | Diferencia nominal frente a Django: `Key` vs `name`. |
| `Promotions` | Promociones/banner | `Id`, `Title`, `Subtitle`, `ProductId`, `Image`, `ButtonText`, `ButtonUrl`, `IsActive`, `Order`, `StartsAt`, `EndsAt`, auditoría | Compatible con promociones activas y ordenadas. |
| `QuoteRequests` | Solicitudes públicas de cotización | `Id`, `ProductId`, datos cliente, `PreferredContactMethod`, `Message`, `Status`, notas internas, fechas de gestión, auditoría | Compatible con creación pública y gestión vendedor. |

## 4. Tipos SQL Server detectados

- Identificadores: `int NOT NULL IDENTITY`.
- Textos cortos/medios: `nvarchar(N)` con longitudes alineadas en campos clave (`Slug`, `Name`, `Sku`, `Email`, `ButtonUrl`, rutas de imagen).
- Textos largos: `nvarchar(max)` para descripciones, notas y mensajes.
- Moneda/precio: `decimal(12,2)` para `Products.Price`.
- Booleanos: `bit`.
- Fechas: `datetimeoffset`, con default `SYSUTCDATETIME()` para `CreatedAt` y `UpdatedAt`.
- Relaciones: claves foráneas con `ON DELETE SET NULL`, `CASCADE` o `NO ACTION` según corresponda.

Los tipos son compatibles con SQL Server 2022 y adecuados para EF Core 8/IIS/Plesk. No se detectan tipos no soportados por SQL Server.

## 5. Claves primarias detectadas

Todas las tablas comerciales tienen PK simple por `Id`:

- `PK_Brands`
- `PK_Categories`
- `PK_Suppliers`
- `PK_Products`
- `PK_HomeSectionItems`
- `PK_ProductImages`
- `PK_ProductSpecs`
- `PK_Promotions`
- `PK_QuoteRequests`

`__EFMigrationsHistory` usa `MigrationId` como PK.

## 6. Relaciones detectadas y delete behavior

| Relación | FK | Nullable | Delete behavior SQL | Equivalente Django | Evaluación |
| --- | --- | --- | --- | --- | --- |
| `Categories.ParentId -> Categories.Id` | `FK_Categories_Categories_ParentId` | Sí | `ON DELETE SET NULL` | `parent` con `SET_NULL` | Correcta. |
| `Products.CategoryId -> Categories.Id` | `FK_Products_Categories_CategoryId` | No | `ON DELETE NO ACTION` / restrict | `category` con `PROTECT` | Correcta para evitar eliminar categorías con productos. |
| `Products.BrandId -> Brands.Id` | `FK_Products_Brands_BrandId` | Sí | `ON DELETE SET NULL` | `brand` con `SET_NULL` | Correcta. |
| `Products.SupplierId -> Suppliers.Id` | `FK_Products_Suppliers_SupplierId` | Sí | `ON DELETE SET NULL` | `supplier` con `SET_NULL` | Correcta. |
| `HomeSectionItems.ProductId -> Products.Id` | `FK_HomeSectionItems_Products_ProductId` | No | `ON DELETE CASCADE` | `product` con `CASCADE` | Correcta, pero borrar un producto elimina su presencia en home. |
| `ProductImages.ProductId -> Products.Id` | `FK_ProductImages_Products_ProductId` | No | `ON DELETE CASCADE` | `product` con `CASCADE` | Correcta. |
| `ProductSpecs.ProductId -> Products.Id` | `FK_ProductSpecs_Products_ProductId` | No | `ON DELETE CASCADE` | `product` con `CASCADE` | Correcta. |
| `Promotions.ProductId -> Products.Id` | `FK_Promotions_Products_ProductId` | Sí | `ON DELETE SET NULL` | `product` con `SET_NULL` | Correcta. |
| `QuoteRequests.ProductId -> Products.Id` | `FK_QuoteRequests_Products_ProductId` | Sí | `ON DELETE SET NULL` | `product` con `SET_NULL` | Correcta para preservar historial de cotizaciones. |

### Auditoría `CreatedById` / `UpdatedById`

Todos los modelos comerciales .NET mantienen `CreatedById` y `UpdatedById`, pero la migración inicial **no crea tabla de usuarios ni FKs** hacia una tabla de identidad. Esto evita dependencia temprana con el sistema de auth, pero deja la integridad referencial de auditoría para una fase posterior. En Django esos campos sí apuntan al `AUTH_USER_MODEL` con `SET_NULL`.

## 7. Índices detectados

### Índices únicos

- `IX_Brands_Slug` único.
- `IX_Categories_Slug` único.
- `IX_Products_Slug` único.
- `IX_HomeSectionItems_Section_Position` único.
- `IX_HomeSectionItems_Section_ProductId` único.

### Índices no únicos

- `Brands`: `IsActive`, `Name`.
- `Categories`: `IsActive`, `Order`, `ParentId`.
- `Products`: `BrandId`, `CategoryId`, `Condition`, `IsFeatured`, `IsPublished`, `ProductType`, `Sku`, `StockStatus`, `SupplierId`.
- `ProductImages`: `IsMain`, compuesto `(ProductId, Order, Id)`.
- `ProductSpecs`: compuesto `(ProductId, Order, Id)`.
- `Promotions`: `EndsAt`, `IsActive`, `Order`, `ProductId`, `StartsAt`.
- `HomeSectionItems`: `IsActive`, `ProductId`.
- `QuoteRequests`: `CreatedAt`, `ProductId`, `Status`.
- `Suppliers`: `IsActive`, `Name`.

### Evaluación de índices

Los índices cubren correctamente los filtros principales previstos: productos por categoría, marca, tipo, condición, estado de stock, publicación; marcas/categorías/proveedores activos; promociones activas y vigentes; home por sección/posición; cotizaciones por estado/fecha. Para búsquedas textuales futuras (`search` por nombre/modelo/SKU/descripción) podría evaluarse un índice adicional o full-text search si el volumen crece.

## 8. Campos nullable/requeridos y defaults

### Correctos o alineados

- `Product.CategoryId` obligatorio, equivalente al `ForeignKey(... PROTECT)` de Django.
- `BrandId`, `SupplierId`, `Promotion.ProductId`, `QuoteRequest.ProductId` opcionales, equivalentes a `null=True, blank=True`.
- Slugs únicos y `NOT NULL` en SQL Server para `Brands`, `Categories`, `Products`.
- Descripciones y campos opcionales de texto se normalizan mayoritariamente a string vacío por default.
- `CreatedAt` y `UpdatedAt` tienen default SQL `SYSUTCDATETIME()`.

### Observaciones

- En Django `slug` puede llegar en blanco y se autogenera en `save()`. En .NET el schema exige `Slug NOT NULL`; la API .NET deberá autogenerarlo antes de persistir o rechazar con validación clara.
- `UpdatedAt` tiene default de creación, pero SQL Server no lo actualiza automáticamente en cada `UPDATE`. Debe resolverse en EF Core con interceptor/override de `SaveChanges` o trigger si se desea comportamiento equivalente a `auto_now=True`.
- `PriceVisible`, `IsFeatured` e `IsPublished` son `NOT NULL`, pero en la migración SQL no tienen default explícito. EF asigna valores desde el modelo al crear entidades, pero inserts SQL manuales podrían requerir valores explícitos.
- `CreatedById` y `UpdatedById` son enteros nullable sin FK real.
- No hay `CHECK CONSTRAINT` para limitar enums (`ProductType`, `Condition`, `StockStatus`, `QuoteRequest.Status`, `PreferredContactMethod`, `HomeSectionItem.Section`). Esto replica parcialmente Django, donde los choices validan a nivel de aplicación pero no necesariamente a nivel DB.

## 9. Comparación contra Django

### Category

Django: `name(120)`, `slug(140, unique, blank, autogenerado)`, `parent SET_NULL`, `description`, `is_active`, `order`, auditoría, ordering `['order', 'name']`.

.NET/SQL Server: mismos campos principales; `Slug` obligatorio y único; relación padre `SET NULL`; índices en `Slug`, `IsActive`, `Order`, `ParentId`.

Diferencias:
- Falta autogeneración persistente del slug en el schema; debe implementarse en servicio/API.
- No hay índice compuesto `(Order, Name)`; no es crítico.
- Auditoría de usuario sin FK.

### Brand

Django: `name(120)`, `slug(140, unique, blank, autogenerado)`, `logo` archivo opcional, `description`, `is_active`, auditoría, ordering `['name']`.

.NET/SQL Server: `Logo nvarchar(500) NULL`, `Description nvarchar(max)`, `IsActive` default true, `Slug` único, índices `Name`/`IsActive`.

Diferencias:
- `Logo` queda como ruta/string; correcto para IIS/Plesk, pero falta política de storage público y validación de upload.
- Slug obligatorio en DB, con generación pendiente en API.
- Auditoría sin FK.

### Supplier

Django: `name(160)`, `contact_name(160, blank)`, `phone(40, blank)`, `email EmailField(blank)`, `notes`, `is_active`, auditoría, ordering `['name']`.

.NET/SQL Server: campos equivalentes; `Email nvarchar(254)`, strings opcionales normalizados con default vacío, índices `Name` e `IsActive`.

Diferencias:
- Validación de email dependerá de la API, no del schema.
- Auditoría sin FK.

### Product

Django: `name(220)`, `slug(240, unique, blank, autogenerado)`, `category PROTECT`, `brand/supplier SET_NULL`, `product_type`, `condition`, `short_description(280)`, `description`, `model(120)`, `sku(120, blank)`, `year`, `hours_meter`, `price decimal(12,2) nullable`, `price_visible`, `stock_status`, `is_featured`, `is_published`, auditoría, ordering `['-updated_at']`.

.NET/SQL Server: campos principales equivalentes; enum strings con longitudes equivalentes; `CategoryId` restrict/no action; `BrandId`/`SupplierId` set null; `Price decimal(12,2)`; índices para filtros públicos.

Diferencias:
- `Slug` obligatorio y único en DB; requiere generación previa.
- `Sku` no es único, solo indexado. Esto es razonable porque Django tampoco lo define como único y admite vacío.
- No hay restricciones DB para `Year` y `HoursMeter` positivos; Django usa `PositiveIntegerField`, por lo que la API .NET debe validar `>= 0` o agregar checks.
- `PriceVisible`, `IsFeatured`, `IsPublished` sin default SQL explícito.
- No existe índice compuesto optimizado para listados públicos típicos como `(IsPublished, ProductType, CategoryId, BrandId, StockStatus)`, aunque los índices simples son suficientes para fase inicial.

### ProductImage

Django: `product CASCADE`, `image FileField`, `alt_text(220, blank)`, `is_main`, `order`, auditoría, ordering `['order', 'id']`.

.NET/SQL Server: `ProductId` requerido con cascade; `Image nvarchar(500) NOT NULL`; `AltText`, `IsMain`, `Order`, timestamps, índices `IsMain` y `(ProductId, Order, Id)`.

Diferencias:
- `Image` obligatorio en .NET; Django también requiere archivo si se crea imagen, aunque permite validación a nivel serializer/form.
- Falta restricción única que limite una sola imagen principal por producto; Django tampoco la tiene, pero puede ser deseable.
- Auditoría sin FK.

### ProductSpec

Django: `product CASCADE`, `name(120)`, `value(220)`, `unit(40, blank)`, `order`, auditoría, ordering `['order', 'id']`.

.NET/SQL Server: `ProductId`, `Key(120)`, `Value(220)`, `Unit(40)`, `Order`, timestamps e índice `(ProductId, Order, Id)`.

Diferencias:
- Campo renombrado: Django usa `name`; .NET usa `Key`. Esto es aceptable internamente si la API mantiene contrato JSON `name` o documenta el cambio. Es un hallazgo medio porque afecta serializers/DTOs futuros.
- Auditoría sin FK.

### Promotion

Django: `title(180)`, `subtitle(280, blank)`, `product SET_NULL`, `image FileField optional`, `button_text(80)`, `button_url URLField`, `is_active`, `order`, `starts_at`, `ends_at`, auditoría, ordering `['order', '-created_at']`.

.NET/SQL Server: campos equivalentes; `ButtonUrl nvarchar(2048)`, imagen ruta nullable, índices por actividad, orden, fechas y producto.

Diferencias:
- Validación URL queda en API.
- `StartsAt <= EndsAt` no se valida en DB; debe validarse en API si aplica.
- Auditoría sin FK.

### HomeSectionItem

Django: `section(40 choices)`, `position`, `product CASCADE`, `is_active`, auditoría; `unique_together` en `(section, position)` y `(section, product)`; validación de límites por sección en `clean()`.

.NET/SQL Server: campos y unicidades equivalentes; `ProductId` cascade; índices por `IsActive` y `ProductId`.

Diferencias:
- No hay validación DB de límites por sección ni posición máxima. Debe implementarse en servicios/API .NET.
- No hay `CHECK` para valores permitidos de `Section`.
- Las restricciones únicas aplican también a items inactivos, igual que Django `unique_together`; puede bloquear reusar una posición aunque el registro viejo esté inactivo. Esto no es regresión, pero debe conocerse.

### QuoteRequest

Django: `product SET_NULL`, datos del cliente, `preferred_contact_method` opcional, `message`, `status` default `new`, notas internas, respuesta vendedor, fechas de gestión, auditoría, ordering `['-created_at']`.

.NET/SQL Server: campos equivalentes; `CustomerEmail` default vacío, `PreferredContactMethod` default vacío, `Status` default `new`, `Message nvarchar(max)` requerido, índices en `Status`, `CreatedAt`, `ProductId`.

Diferencias:
- No hay límite DB para `Message`; Django lo limita a nivel serializer a 2000 caracteres. Debe mantenerse en DTO/API.
- No hay validación DB de email, método de contacto ni status.
- Auditoría sin FK.

## 10. Compatibilidad con contratos futuros frontend/Django

| Caso futuro | Soporte por modelo actual | Observación |
| --- | --- | --- |
| Listado público de productos | Sí | `Products` contiene `IsPublished`, filtros e índices principales. |
| Detalle por slug | Sí | `Products.Slug` es único y obligatorio. API debe enrutar por slug. |
| Filtros por `category`, `brand`, `product_type`, `condition`, `stock_status` | Sí | Existen columnas e índices individuales. |
| Promociones/home | Sí | `Promotions` y `HomeSectionItems` modelan datos actuales. Validaciones de vigencia/límites deben vivir en API. |
| Cotización pública | Sí | `QuoteRequests` soporta producto opcional, datos cliente, mensaje y status. |
| Panel vendedor futuro | Parcial | Auditoría existe como IDs, pero falta modelo/relación de usuarios/roles en .NET y FKs reales. |
| Uploads de imágenes | Parcial | El schema guarda rutas; falta definir filesystem/storage persistente IIS/Plesk, URLs públicas y validadores de tamaño/content-type/firma. |
| Sitemap futuro | Sí | `Products.Slug`, `Products.IsPublished`, `Products.UpdatedAt`, `Categories.IsActive`, `Categories.UpdatedAt` permiten replicar sitemap. |

## 11. Riesgos SQL Server/Plesk

### Riesgos críticos

No se identifican riesgos críticos bloqueantes para una base nueva/vacía en SQL Server 2022.

### Riesgos medios

1. **Auditoría sin integridad referencial**: `CreatedById` y `UpdatedById` no apuntan a una tabla de usuarios. Si se importan datos o se implementa auth .NET, puede haber IDs huérfanos.
2. **`UpdatedAt` no es equivalente a Django `auto_now` por sí solo**: el default SQL solo aplica al insert. Debe actualizarse desde EF Core o trigger.
3. **Enums sin `CHECK CONSTRAINT`**: valores inválidos podrían entrar por SQL directo/importaciones.
4. **Slugs obligatorios en .NET**: si el API no autogenera slugs, operaciones que en Django eran válidas con `slug=''` fallarán.
5. **Validaciones de negocio no presentes en DB**: límites de home sections, mensajes de cotización de 2000 caracteres, año/horómetro positivos, URLs válidas, email válido y rangos de fechas de promociones dependen de la API.
6. **`ProductSpec.Key` vs `ProductSpec.name`**: riesgo de contrato si se expone directamente la entidad .NET sin DTO compatible.
7. **Rutas de imagen como string**: correcto para SQL Server, pero el éxito en IIS/Plesk depende de definir carpeta persistente, permisos NTFS, URL pública y limpieza de archivos al borrar registros.

### Riesgos menores

1. `nvarchar(max)` en descripciones/notas/mensajes es compatible, pero puede ser excesivo para algunos campos si se busca control estricto.
2. `Sku` indexado pero no único es compatible con Django. Si el negocio decide SKU único, debe agregarse después considerando valores vacíos/demos.
3. Las unicidades de home section aplican a registros inactivos, lo cual replica Django pero puede incomodar al panel vendedor.
4. No hay índices compuestos específicos para consultas públicas combinadas; aceptable para fase inicial, optimizable con métricas reales.
5. `PriceVisible`, `IsFeatured`, `IsPublished` sin default SQL puede afectar inserts manuales.
6. La collation de la base no está fijada por el script; la sensibilidad a mayúsculas/minúsculas dependerá de la collation de `jemnexusb_prod`. Esto afecta unicidad de slugs y búsquedas.

## 12. Hallazgos críticos

- **No se detectaron hallazgos críticos bloqueantes** para crear el schema inicial en una base SQL Server 2022 vacía.

## 13. Hallazgos medios

- `UpdatedAt` requiere lógica de actualización en EF Core para comportarse como Django `auto_now`.
- Auditoría `CreatedById`/`UpdatedById` existe como entero nullable, pero sin FK a usuarios.
- Slugs son obligatorios en SQL Server y deben autogenerarse/validarse antes de insertar.
- No hay constraints DB para choices/enums ni para rangos positivos.
- `ProductSpec.Key` debe mapearse cuidadosamente al contrato Django/frontend que usa `name`.
- Uploads de imágenes requieren diseño Plesk/IIS antes de producción.

## 14. Hallazgos menores

- Algunos campos `nvarchar(max)` podrían limitarse para reducir crecimiento accidental.
- No hay índice compuesto para listados públicos con múltiples filtros.
- Las restricciones únicas de home section no discriminan `IsActive`.
- `Sku` no único es coherente con Django, pero puede requerir decisión comercial futura.
- Defaults SQL incompletos en algunos booleans de `Products` si habrá inserts fuera de EF.

## 15. Recomendaciones antes de aplicar en Plesk

1. Confirmar que la base `jemnexusb_prod` está vacía o que no contiene tablas con los mismos nombres.
2. Definir si se mantendrán entidades comerciales en tablas pluralizadas (`Products`, `Categories`, etc.) sin esquema custom (`dbo` por default).
3. Implementar en la API .NET generación de slugs para `Category`, `Brand` y `Product`, manteniendo unicidad.
4. Implementar actualización automática de `UpdatedAt` en EF Core (`SaveChanges`/interceptor) antes de operar datos reales.
5. Decidir si se agregan `CHECK CONSTRAINT` para enums y rangos positivos o si se validará solo en DTOs/API.
6. Definir el sistema de usuarios/roles .NET y si se agregarán FKs de auditoría hacia esa tabla.
7. Definir almacenamiento de imágenes para Windows/IIS/Plesk: ruta física fuera del deploy, permisos para el application pool, URL pública, límites de tamaño y validación de firma.
8. Mantener DTOs compatibles con frontend: especialmente `product_type`, `stock_status`, `is_published`, `images`, `specs.name` vs `ProductSpec.Key`.
9. Evaluar collation de SQL Server para slugs únicos case-insensitive/case-sensitive según criterio SEO.
10. Ejecutar `dotnet build` y pruebas .NET en un entorno con SDK disponible antes de aplicar la migración.
11. Probar el script SQL primero en una base temporal SQL Server 2022, no en `jemnexusb_prod`.

## 16. Checklist previo a `database update`

- [ ] Confirmar backup/snapshot de `jemnexusb_prod` si ya existe contenido.
- [ ] Confirmar que se usará cadena de conexión de staging o producción correcta, nunca accidentalmente local/demo.
- [ ] Confirmar permisos mínimos del usuario `jemnexusb_api` para migración o usar usuario migrador separado.
- [ ] Validar que `dotnet build backend-dotnet/JemNexus.sln` pasa en ambiente con SDK .NET.
- [ ] Validar que `dotnet test backend-dotnet/JemNexus.sln` pasa en ambiente con SDK .NET.
- [ ] Ejecutar el SQL generado en base temporal SQL Server 2022 y revisar resultado.
- [ ] Confirmar estrategia de slugs automáticos.
- [ ] Confirmar estrategia de `UpdatedAt` automático.
- [ ] Confirmar estrategia de usuarios/roles/auditoría.
- [ ] Confirmar estrategia de uploads en IIS/Plesk.
- [ ] Confirmar que no se ejecutará migración desde una app con conexión a la base equivocada.
- [ ] Confirmar plan de rollback si falla la aplicación del script.

## 17. Conclusión

**APTO CON OBSERVACIONES**.

El schema es consistente con los modelos comerciales actuales y compatible con SQL Server 2022/Plesk para una primera base nueva. No obstante, no debería aplicarse a producción sin cerrar las observaciones de operación y aplicación: generación de slugs, actualización de `UpdatedAt`, validaciones equivalentes a Django, estrategia de usuarios/auditoría y almacenamiento de imágenes en Windows/IIS.

## Cierre de observaciones Backend .NET 2C

> Alcance 2C: se cerraron o prepararon observaciones sin aplicar la base real, sin ejecutar `dotnet ef database update`, sin tocar `jemnexusb_prod`, sin regenerar la migración inicial y sin modificar el frontend.

| Observación 2B | Estado | Cambio realizado | Archivos afectados | ¿Requiere migración futura? |
| --- | --- | --- | --- | --- |
| Generación/normalización de slugs | Cerrada a nivel helper; pendiente unicidad transaccional en endpoints de escritura. | Se agregó `SlugHelper` reutilizable para minúsculas, remoción de tildes, conversión de espacios/separadores a guiones, eliminación de caracteres no seguros, compactación/trim de guiones y manejo seguro de `null`/vacío. | `backend-dotnet/JemNexus.Api/Utils/SlugHelper.cs`, `backend-dotnet/JemNexus.Api.Tests/SlugHelperTests.cs` | No para el helper. La unicidad final ya existe como índice único en DB, pero la resolución de colisiones (`slug`, `slug-2`, etc.) debe implementarse en la fase CRUD/API sin cambiar el schema salvo que se decida otra política. |
| `UpdatedAt` automático | Cerrada a nivel EF Core. | `JemNexusDbContext` ahora aplica timestamps antes de `SaveChanges`/`SaveChangesAsync`: en `Added` asigna `CreatedAt` si viene en default y siempre asigna `UpdatedAt`; en `Modified` actualiza `UpdatedAt` y conserva `CreatedAt`. Aplica a `Category`, `Brand`, `Supplier`, `Product`, `ProductImage`, `ProductSpec`, `Promotion`, `HomeSectionItem` y `QuoteRequest`. | `backend-dotnet/JemNexus.Api/Data/JemNexusDbContext.cs`, `backend-dotnet/JemNexus.Api.Tests/AuditTimestampTests.cs` | No. No se agregaron triggers ni columnas; se mantiene el schema inicial. |
| Validaciones equivalentes a Django/choices | Parcialmente cerrada a nivel dominio/aplicación. | Se agregó una primera capa de validación interna con constantes permitidas y reglas para `Product`, `QuoteRequest`, `ProductImage` y `ProductSpec`, sin introducir FluentValidation ni controllers. | `backend-dotnet/JemNexus.Api/Validation/CommercialValidation.cs`, `backend-dotnet/JemNexus.Api.Tests/CommercialValidationTests.cs` | No para validación de aplicación. Si se desean `CHECK CONSTRAINT` en SQL Server para enums, sí requeriría una migración correctiva futura autorizada. |
| Uploads en IIS/Plesk | Parcialmente cerrada/preparada. | Se agregó sección `Uploads` configurable y clase `UploadOptions` para una fase futura de endpoints. Estrategia documentada: rutas relativas en DB, carpeta configurable, permisos controlados y validación de extensión/content-type/firma binaria/tamaño al implementar endpoints. | `backend-dotnet/JemNexus.Api/appsettings.json`, `backend-dotnet/JemNexus.Api/appsettings.Development.json`, `backend-dotnet/JemNexus.Api/Options/UploadOptions.cs`, `backend-dotnet/JemNexus.Api/Program.cs`, `backend-dotnet/README.md` | No. La estrategia usa campos string de ruta ya existentes (`Logo`, `Image`). No hay subida real todavía. |
| Auditoría/usuarios | Pendiente por decisión de auth; preparada documentalmente. | Se mantiene `CreatedById`/`UpdatedById` como campos base sin FK real. Se documenta que Backend .NET 3 debe decidir JWT + tabla propia liviana o ASP.NET Core Identity, considerando que habrá 1 vendedor y 1 administrador soporte y evitando multiempresa/ownership multi-vendedor. | `docs/REVISION_SCHEMA_ASPNETCORE_SQLSERVER.md`, `docs/MIGRACION_BACKEND_ASPNETCORE_SQLSERVER.md`, `backend-dotnet/README.md` | Posiblemente sí. Si se exige integridad referencial hacia usuarios antes de aplicar schema definitivo, se necesitará migración correctiva para tabla de usuarios/FKs o adopción de Identity. |
| Defaults SQL para `Product.PriceVisible`, `Product.IsFeatured`, `Product.IsPublished` | Pendiente/aceptada temporalmente. | No se cambió el schema. EF Core mantiene defaults de modelo en creación de entidades; inserts SQL manuales deberán enviar valores explícitos. | Sin cambios de código específicos. | Sí, solo si se decide agregar defaults SQL explícitos mediante nueva migración correctiva. |
| `nvarchar(max)` en textos largos | Pendiente/aceptada temporalmente. | No se cambiaron tipos ni longitudes para evitar tocar la migración inicial en esta fase. | Sin cambios de código específicos. | Sí, solo si se decide limitar columnas largas con una migración correctiva. |

### Validaciones pendientes para controllers/DTOs

- Validar payloads de entrada con DTOs antes de mapear a entidades EF Core.
- Generar slugs automáticamente cuando `Slug` venga vacío en endpoints de escritura y resolver colisiones contra la base de datos dentro de una transacción o reintento controlado.
- Validar unicidad de `ProductImage.IsMain` por producto y reglas de home sections en la capa de aplicación.
- Validar uploads por extensión, content-type, firma binaria y tamaño máximo antes de guardar archivos.
- Aplicar throttling/autorización en endpoints de cotización y panel vendedor cuando se implemente JWT.
