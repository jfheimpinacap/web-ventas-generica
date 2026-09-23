# Plan 351 — traslado controlado de datos y multimedia local a producción

## 1. Propósito, límites y estado

Este documento es **solamente un diseño técnico auditable**. No contiene SQL ejecutable, exportaciones, credenciales, hashes de contraseña, tokens, cadenas de conexión, herramientas ni paquetes de traslado. Tampoco autoriza conectarse a LocalDB, producción, Plesk o APIs, ejecutar migraciones, publicar ni alterar datos o archivos.

**Decisión de este documento: NO-GO para aplicar en producción y GO para diseñar el implementador en el Prompt 352.** Ese implementador deberá quedar inerte por defecto, incorporar preflight, dry-run y pruebas sintéticas, y bloquear cualquier aplicación productiva hasta completar los controles técnicos y operativos de este plan. El GO de diseño no autoriza importar, reemplazar ni eliminar datos.

### 1.1 Base verificada en el repositorio

- Rama de trabajo observada antes de editar: `work`; `HEAD` integrado `65f4d78976c4ff29f2f83c54d600c941723830ef`; árbol inicialmente limpio.
- Se contaron 22 clases de migración (sin `Designer` ni snapshot), desde `20260603182917_InitialCommercialSchema` hasta `20260922000000_AddCommercialQuoteIssuedBy`. Producción ya tiene las 22: **no se deben volver a ejecutar**.
- El modelo vigente declara 18 tablas de aplicación, la secuencia `SellerCodeSequence` y el historial EF. Los nombres de tabla no fijan esquema; local resuelve a `dbo` y producción debe resolver a `jemnexusb_api` mediante el esquema predeterminado/configuración ya desplegada.
- La evidencia de volúmenes local/productiva que sigue fue suministrada y se acepta como evidencia confirmada del encargo; este análisis estático no se conectó a ninguna base ni servidor para volver a medirla.

## 2. Alcance resuelto, hechos por medir y controles pendientes

### 2.1 Hechos de partida

**Local (`JemNexus_Local`, `dbo`):** 3 usuarios (`jmateluna`, seller `VEN-0001`, 29 permisos; `supadmin`, `support_admin`; `fheim`, seller `VEN-0002`, 29 permisos), 122 refresh tokens y 58 permisos; 3 marcas, 10 categorías, 92 productos, 92 imágenes, 58 especificaciones y 85 fichas; 9 cotizaciones, 9 ítems, 8 registros de idempotencia, 1 contador de folios y 1 cliente. `QuoteRequests`, `HomeSectionItems`, `Promotions` y `Suppliers` están vacías. En `backend-dotnet/JemNexus.Api/uploads` hay 179 archivos/129296085 bytes; existen los 92 archivos de imágenes y 85 fichas referenciados, y existen 2 imágenes huérfanas que no deben trasladarse.

**Producción (`jemnexusb_prod`, `jemnexusb_api`):** 22 migraciones verificadas; release backend/frontend `65f4d78976c4`; 2 usuarios (`soporte` support_admin y `vendedor` seller), 29 permisos del seller, 8 `QuoteRequests` y 0 `CommercialQuotes`; health, rutas públicas y smoke autenticado GET aprobados. Hay backups SQL y web descargados, pero su restauración no ha sido ensayada.

Los conteos productivos de las demás tablas no están confirmados. La instrucción de reemplazo resuelve el resultado funcional, pero no autoriza aplicarlo ahora ni permite ignorar drift, backups, ensayo o rollback.

### 2.2 Decisiones del usuario ya resueltas

| ID | Alcance autorizado | Consecuencia que debe quedar visible |
|---|---|---|
| R-01 | `JemNexus_Local` es la fuente de verdad y reemplazará el contenido productivo. | Los conteos y relaciones locales gobiernan el resultado, sujeto a que el preflight confirme que el estado productivo no cambió desde el inventario. No habilita todavía la aplicación. |
| R-02 | Las 8 `QuoteRequests` productivas se sustituyen por las 0 locales. | Las ocho solicitudes y su información comercial dejarán de estar en la base activa. Deben quedar cubiertas por un backup recuperable justo antes de aplicar; no se vuelve a solicitar una decisión de conservación. |
| R-03 | Las cuentas `soporte` y `vendedor` se sustituyen por `jmateluna`, `supadmin` y `fheim`. | Las cuentas productivas actuales y sus sesiones dejan de otorgar acceso; el resultado tendrá un support_admin y dos sellers locales, con 29 permisos por seller. Debe verificarse acceso de `supadmin` antes de abrir tráfico. |
| R-04 | Las 9 cotizaciones locales y sus relaciones forman parte del traslado. | Se preservan cabeceras, 9 ítems, 8 registros de idempotencia, contador, cliente, seller/emisor y snapshots, sin recalcular ni reemitir. |
| R-05 | Los 122 `AppRefreshTokens` locales no se trasladan. | Las sesiones productivas existentes también deben invalidarse coherentemente con el reemplazo; después se crean únicamente sesiones nuevas mediante login. |

Si justo antes de aplicar el preflight descubre nuevas solicitudes, cuentas, cotizaciones u otros datos productivos respecto del inventario confirmado, debe **abortar sin escribir** y revisar el alcance. Esta protección contra drift no reabre las decisiones R-01 a R-05 para el estado actualmente inventariado.

### 2.3 Hechos técnicos todavía por medir

- Rutas efectivas de imágenes y fichas, `Uploads__RootPath`, `Uploads__PublicBasePath`, content root, ACL/identidad IIS, capacidad y espacio libre.
- Permisos reales de la cuenta SQL de ejecución, default schema, relación entre login de servidor y usuario de base, ownership y capacidad de transacción/staging requerida.
- Metadata y estado inmediatamente anteriores al corte: IDs, máximos identity, valor de `SellerCodeSequence`, constraints/índices confiables, colisiones y conteos completos de las tablas productivas hoy “no confirmado”.
- Correspondencia exacta entre filas, archivos, rutas y hashes; clasificación de logos de marca y cualquier medio productivo que será reemplazado.

### 2.4 Controles operativos pendientes antes de aplicar

- Backup reciente y recuperable de base y de ambas raíces multimedia, con restauración ensayada en un entorno desechable equivalente.
- Ensayo end-to-end del implementador futuro, incluidos fallos, postflight y rollback coordinado de DB/archivos.
- Ventana de mantenimiento, congelamiento verificable de todas las escrituras, responsables y criterios de aborto.
- Verificación de login/autorización de `supadmin` en el ensayo y procedimiento break-glass sin exponer secretos.
- Preflight final sin drift y capacidad de restaurar dentro del RTO acordado.

## 3. Inventario de esquema y reglas que gobiernan el traslado

### 3.1 Claves, generación y unicidad

- Las PK `Id` enteras usan identity por convención para `AppUsers`, `AppRefreshTokens`, `Brands`, `Categories`, `Suppliers`, `Products`, `ProductImages`, `ProductSpecs`, `Promotions`, `HomeSectionItems`, `QuoteRequests`, `TechnicalSheets`, `CustomerProfiles`, `CommercialQuotes` y `CommercialQuoteItems`. Al preservar IDs, el futuro implementador deberá controlar explícitamente la inserción de identity y luego verificar/resembrar cada identity por encima del máximo, sin incluir aquí comandos concretos.
- `CommercialQuoteFolioCounters.Year` es PK no generada. `AppUserPermissions` tiene PK compuesta (`UserId`, `Permission`). La idempotencia tiene PK (`ResponsibleSellerId`, `IdempotencyKey`) y unicidad de `CommercialQuoteId`.
- Unicidad relevante: `AppUsers.Username`, `SellerCode` no nulo y `Email` no nulo; `Categories.Slug`; `Brands.Slug`; `Products.Slug` y `Sku` no nulo; `HomeSectionItems` (`Section`,`Position`) y (`Section`,`ProductId`); `CustomerProfiles.NormalizedRut`; folio y (`FolioYear`,`FolioSequenceNumber`); ítem (`CommercialQuoteId`,`Position`); token hash.
- `SellerCodeSequence` comienza en 1 e incrementa de uno en uno. Los códigos ya guardados (`VEN-0001`, `VEN-0002`) no prueban por sí solos el valor actual de la secuencia: preflight debe leerlo y el ensayo debe colocar su próximo valor por encima del mayor sufijo válido y de cualquier reserva preservada. No inferirlo solo del conteo.
- El check `CK_AppUsers_Role_SellerCode` obliga código no nulo para seller y nulo para cualquier otro rol.

### 3.2 Relaciones y borrado

- Todas las relaciones de auditoría `CreatedById`/`UpdatedById` apuntan a `AppUsers` con `NO ACTION`: categorías, marcas, proveedores, productos, imágenes, specs, promociones, home, solicitudes y clientes. Por ello usuarios deben cargarse primero y no pueden desaparecer mientras sean referenciados.
- Categoría padre, producto→categoría/marca/proveedor, imagen/spec/home/promoción→producto usan `NO ACTION` (las referencias opcionales siguen debiendo existir si no son nulas).
- Producto→ficha es opcional y al borrar ficha queda `NULL`. `QuoteRequests.ProductId`, `CommercialQuoteItems.ProductId` y `CommercialQuotes.CustomerProfileId` también son opcionales con `SET NULL`.
- `CommercialQuotes.ResponsibleSellerId` e `IssuedById` son obligatorias hacia `AppUsers`, `NO ACTION`. Ítems dependen de cotización con cascada. Idempotencia depende de cotización uno-a-uno con cascada, pero su seller usa `NO ACTION`.
- Permisos y refresh tokens dependen del usuario con cascada. Esa cascada no justifica trasladar sesiones.

### 3.3 Contratos funcionales relevantes

- `support_admin` obtiene todos los permisos efectivos por rol; los sellers usan exclusivamente permisos persistidos y grantables. Deben conservarse las 29 filas por cada seller y comprobar que no reciben permisos reservados.
- Cotizaciones emitidas conservan snapshots de cliente, vendedor y precios. No “recalcular”, reemitir ni regenerar folios durante el traslado. `IssuedById` y `ResponsibleSellerId` deben apuntar al usuario local correcto incluso si coinciden en los datos actuales.
- Las claves de idempotencia y fingerprints son integridad funcional: trasladar las 8 filas junto con sus cotizaciones evita reemisión duplicada. No exponer sus valores en artefactos/logs más allá del paquete protegido futuro.
- Los 122 refresh tokens son sesiones y material sensible. **Alcance resuelto: no trasladarlos**; producción debe iniciar sin sesiones locales y las sesiones productivas anteriores deben quedar invalidadas al sustituir usuarios. Validar login nuevo, no continuidad de sesión.

## 4. Matriz completa por tabla de aplicación

“No confirmado” exige consulta read-only en un preflight futuro; no significa cero.

| Tabla | Local conocido | Producción conocida | Decisión preliminar | Dependencias / tratamiento | Validación posterior |
|---|---:|---:|---|---|---|
| `AppUsers` | 3 | 2 | **Trasladar/reemplazar (R-03)** | Preservar IDs locales; primero por auditoría, permisos y cotizaciones. No imprimir hashes. | 3 usuarios, roles/códigos/check/unicidad; cuentas anteriores sin acceso; `supadmin` login y login seller controlado. |
| `AppUserPermissions` | 58 (29+29) | 29 | **Trasladar/reemplazar** | FK a usuarios; support_admin no requiere filas; catálogo grantable vigente. | 58 total, 29 por seller, 0 para admin, sin desconocidos/reservados. |
| `AppRefreshTokens` | 122 | no confirmado | **No trasladar** | Sesiones sensibles; limpiar/inutilizar las productivas solo dentro de operación aprobada. | 0 filas tras reemplazo y refresh antiguos rechazados; login emite sesión nueva. |
| `Brands` | 3 | no confirmado | **Trasladar/reemplazar** | Auditoría→usuarios; `Logo` requiere inventario multimedia aparte. | 3; slugs únicos; FK auditoría; cada logo no vacío clasificado/verificado. |
| `Categories` | 10 | no confirmado | **Trasladar/reemplazar** | Usuarios; jerarquía autorreferente: raíces antes que hijas. | 10; sin ciclos/huérfanos; slugs y tipos válidos. |
| `Suppliers` | 0 | no confirmado | **Reemplazar por vacío** | Confirmación destructiva cubierta por fuente de verdad; referenciada opcionalmente por productos. | 0 y todo `Products.SupplierId` nulo. |
| `TechnicalSheets` | 85 | no confirmado | **Trasladar/reemplazar** | Archivos por `StorageKey`; productos pueden apuntarlas. | 85 claves simples únicas en la práctica, tamaño/tipo y 85 hashes/archivos coinciden. |
| `Products` | 92 | no confirmado | **Trasladar/reemplazar** | Categoría obligatoria; marca/proveedor/ficha/auditoría opcionales. | 92; FK íntegras; slug/SKU únicos; lectura pública de muestra y conteos por tipo/estado. |
| `ProductImages` | 92 | no confirmado | **Trasladar/reemplazar** | Producto/usuarios; `Image` es ruta pública, no blob. Solo archivos correlacionados. | 92 filas, 92 rutas canónicas, 92 archivos y hashes; ninguna ruta rota/duplicado inesperado. |
| `ProductSpecs` | 58 | no confirmado | **Trasladar/reemplazar** | Producto y usuarios. | 58; FK válidas; orden/contenido comparados con manifiesto. |
| `Promotions` | 0 | no confirmado | **Reemplazar por vacío** | Producto opcional; `Image` puede referir multimedia no administrada por servicio de imágenes. | 0; inventario confirma que no se trasladó multimedia promocional. |
| `HomeSectionItems` | 0 | no confirmado | **Reemplazar por vacío** | Producto/usuarios; dos índices únicos. | 0. |
| `QuoteRequests` | 0 | **8** | **Reemplazar por 0 (R-02)** | Producto y auditoría opcionales. La consecuencia autorizada es retirar las 8 filas de la base activa; backup recuperable y preflight sin drift son obligatorios. No convertirlas en cotizaciones. | 0 después de aplicar; evidencia de 8 antes del corte en backup/manifiesto; abortar si el preflight ya no encuentra exactamente el estado inventariado. |
| `CustomerProfiles` | 1 | no confirmado | **Trasladar/reemplazar** | Auditoría; cotización opcional; RUT normalizado único. | 1; RUT único; vínculo de cotización correcto. |
| `CommercialQuotes` | 9 | 0 | **Trasladar (R-04)** | Cliente opcional; seller/emisor obligatorios; snapshots y folios inmutables. | 9; totales/estados/timestamps/folios iguales al manifiesto; 0 FK nulas/huérfanas. |
| `CommercialQuoteItems` | 9 | no confirmado (0 inferible por 0 cabeceras, pero verificar) | **Trasladar** | Cotización obligatoria; producto opcional `SET NULL`; no recalcular. | 9; una posición única por cabecera; sumas y snapshots exactos. |
| `CommercialQuoteFolioCounters` | 1 | no confirmado | **Trasladar/reemplazar (R-04)** | PK año; debe ser ≥ máximo folio de ese año. | 1; año/último número exactos y coherentes; próximo folio no colisiona en ensayo. |
| `CommercialQuoteIssueIdempotencyRecords` | 8 | no confirmado | **Trasladar** | Seller + cotización; PK compuesta y cotización única. | 8; seller coincide con cotización; 8 cotizaciones vinculadas una sola vez; fingerprints conservados. |

`__EFMigrationsHistory` **no es dato de aplicación y no se traslada**: producción ya registra las 22 migraciones. `SellerCodeSequence` tampoco es una tabla; se ajusta/verifica de manera explícita y separada. No se ejecuta SQL de migraciones.

## 5. Diseño del traslado multimedia

### 5.1 Dos raíces distintas según el código vigente

1. **Imágenes de producto:** la ruta física es `<Uploads__RootPath>/product-images/<ProductId>/<archivo>`; solo si `Uploads__RootPath` está vacío cae en `<ContentRoot>/uploads`. La columna `ProductImages.Image` guarda la ruta pública construida con `Uploads__PublicBasePath` (por defecto `/media`), no el `StorageKey` físico.
2. **Fichas técnicas:** `LocalTechnicalSheetStorage` ignora `Uploads__RootPath` y siempre usa `<ContentRoot>/uploads/technical-sheets/<StorageKey>`. Por tanto una configuración productiva externa para imágenes **no cambia** la ubicación de fichas.

No se acepta asumir que content root, raíz de imágenes o base pública productivas coinciden con local. Antes de diseñar comandos se deben confirmar rutas absolutas, persistencia ante deploy, ACL, cuota y estrategia de backup para ambas raíces.

### 5.2 Manifiesto de correlación permitido para el futuro

El Prompt 352 deberá diseñar un manifiesto **sin contenido sensible**, generado en staging desde una fuente local autorizada, con una fila por referencia:

- imagen: `ProductImages.Id`, `ProductId`, valor `Image`, ruta relativa canónica `product-images/<ProductId>/<nombre-seguro>`, tamaño y SHA-256;
- ficha: `TechnicalSheets.Id`, `StorageKey` (nombre simple), `OriginalFileName` solo como metadata, `SizeBytes`, tipo, ruta relativa `technical-sheets/<StorageKey>` y SHA-256.

Reglas de aceptación:

1. Normalizar separadores y rechazar rutas absolutas, `..`, enlaces simbólicos/reparse points y archivos fuera de la raíz.
2. Para imágenes, validar que la base pública configurada corresponde al prefijo de cada `Image`, que el segmento de producto coincide con `ProductId`, y que el nombre es simple. Si cambia `Uploads__PublicBasePath`, definir una transformación determinista de las 92 rutas en los datos staged; **no copiar rutas locales ciegamente**.
3. Para fichas, exigir que `StorageKey` sea un nombre simple y único; comparar `SizeBytes` con disco. El nombre original nunca decide la ruta.
4. Calcular hashes en origen antes de copiar; copiar a un directorio staging productivo fuera del live; recalcular hashes allí; exigir conjuntos exactamente iguales (92 imágenes + 85 fichas) y bytes totales esperados según manifiesto. Los 129296085 bytes/179 archivos del árbol completo son control auxiliar, no el total que debe copiarse porque incluye 2 huérfanos.
5. Promover desde staging a las dos raíces efectivas solo en ventana, con operación recuperable y sin sobrescribir silenciosamente. Tras promover, recalcular hashes y probar lectura a través del backend para muestras y luego todas las rutas mediante verificación no destructiva.
6. Los dos archivos físicos de imágenes no alcanzables desde las 92 filas quedan fuera del manifiesto y fuera del traslado. Registrar únicamente su ruta relativa/razón en reporte local protegido, no copiarlos.

### 5.3 Marcas y promociones

`Brands.Logo` y `Promotions.Image` son cadenas, pero no están gestionadas por `LocalProductImageStorage`. Aunque promociones locales son cero, para las 3 marcas se debe clasificar cada `Logo` no nulo como URL externa, asset estático del frontend o archivo local. Solo el último requeriría un manifiesto y destino separado aprobado. No mezclarlo con las 92 imágenes. El preflight productivo también debe inventariar medios de marcas/promociones que serían reemplazados y asegurar su backup.

## 6. Comparación de estrategias

| Estrategia | Ventajas | Riesgos/bloqueos | Veredicto |
|---|---|---|---|
| Restauración completa de `JemNexus_Local` sobre producción | Conserva IDs y relaciones de una sola imagen DB. | Origen usa `dbo`, destino `jemnexusb_api`; podría cambiar owner/permisos/logins/default schema, historial, nombre/base y conexión del backend; destruye 8 solicitudes; incluye 122 sesiones; no mueve archivos; backups no ensayados. | **Descartada como restauración directa segura.** Solo sería replanteable mediante restauración a base desechable y transformación explícita, no sobre producción. |
| Traslado selectivo transaccional con IDs preservados | Control tabla por tabla, excluye tokens/huérfanos, aplica explícitamente el reemplazo de solicitudes/cuentas y permite validar esquema destino. | Requiere identity control/reseed, orden FK, secuencia, staging, manejo coordinado DB+archivos y SQL cuidadosamente revisado. | **Preferida para diseñar**; su aplicación queda condicionada a completar hechos técnicos y controles operativos. |
| Importación por APIs existentes | Ejecuta validaciones y storage soportado. | Cambia IDs/timestamps, puede recalcular/emitir datos, no cubre todos los agregados ni auditoría/idempotencia/folios, lenta y no atómica. | **No apta** para réplica fiel; útil solo para smoke postflight. |
| Base nueva paralela + corte de conexión | Rollback de conexión más claro y ensayo cercano. | Necesita permisos para crear DB/esquema, reproducir grants/config, corte coordinado, carga selectiva y medios siguen siendo externos. | **Alternativa respaldable** si hosting lo permite; decidir tras discovery de permisos. |

## 7. Runbook conceptual (no ejecutable)

### 7.1 Precondiciones obligatorias

- Alcance R-01 a R-05 registrado; responsables de aplicación, DBA, Plesk/IIS y dueño de datos identificados. No se requiere volver a decidir el reemplazo ya indicado.
- Exportación lógica local futura protegida y manifiestos aprobados; ninguna credencial/token en artefactos o logs.
- Confirmar mediante metadata read-only que ambas bases tienen exactamente las mismas 22 migraciones, columnas, tipos, nulabilidad, PK/FK/delete actions, checks, índices/filtros, identity y secuencia. Confirmar esquema destino `jemnexusb_api` y que toda referencia futura será calificada; no depender del `dbo` implícito.
- Levantar conteos, máximos identity, checksums lógicos por tabla, duplicados de claves naturales, huérfanos y todas las FK de auditoría en local. Repetir inventario completo de producción justo antes de la ventana; lo hoy “no confirmado” debe quedar confirmado.
- Resolver colisiones de username/email/seller code/slug/SKU/RUT/folio/idempotencia. El preflight debe exigir exactamente 8 solicitudes y las 2 cuentas productivas inventariadas; cualquier alta o cambio posterior es drift y aborta para revisar alcance.
- Confirmar rutas/ACL/capacidad y completar manifiestos de 92+85; clasificar logos. Validar que no haya escrituras fuera de las raíces respaldadas.
- Ensayar restauración de los backups SQL y de **ambas** raíces web en un entorno desechable equivalente. Un backup existente sin restore exitoso no habilita GO.
- Ejecutar ensayo end-to-end de la estrategia exacta y obtener reporte de pre/postflight y rollback dentro del RTO aprobado.

### 7.2 Ensayo desechable equivalente

Crear una base aislada con nombre no productivo, esquema `jemnexusb_api`, las 22 migraciones ya presentes y una copia sanitizada/segura del estado productivo pertinente. Replicar default schema, permisos mínimos del login de aplicación, case/collation relevantes, content root, configuración de uploads y ACL. Aplicar allí el futuro paquete revisado con la sustitución autorizada de 8 solicitudes por 0 y de 2 cuentas por 3; probar drift adicional, e interrupción antes/durante promoción de medios y antes/durante transacción DB. Descartar el entorno después de retener solo evidencias sin secretos.

### 7.3 Ventana y congelamiento

1. Anunciar mantenimiento y bloquear escrituras de usuarios, endpoints públicos de solicitudes, uploads, emisión y jobs; no basta detener el frontend. Confirmar cero writers y drenar requests.
2. Capturar preflight final y comparar con el baseline; cualquier drift cancela.
3. Tomar backup SQL consistente **justo antes** y snapshots/copias consistentes de raíz de imágenes y raíz de fichas. Descargar/verificar y registrar hash/tamaño; no reemplazar los backups previos.
4. Validar restore rápido en destino aislado si la política lo permite o exigir que el ensayo reciente cubra exactamente el mecanismo y versión.
5. Mantener backend fuera de escritura hasta completar postflight y decisión de apertura.

### 7.4 Orden lógico preferido

El futuro implementador debe usar staging y una única transacción DB para la sustitución/carga, con constraints activos y verificaciones antes de commit. Orden de carga (tras retirar destino en orden inverso respetando FK):

1. `AppUsers` (sin refresh tokens) y luego `AppUserPermissions`.
2. `Categories` raíces/hijas, `Brands`, `Suppliers`, `TechnicalSheets`.
3. `Products`.
4. `ProductImages`, `ProductSpecs`, `Promotions`, `HomeSectionItems`.
5. `CustomerProfiles`.
6. `QuoteRequests`: dejar el conjunto local vacío conforme a R-02, únicamente si el preflight confirma exactamente las 8 filas inventariadas y el backup recuperable existe.
7. `CommercialQuotes`, `CommercialQuoteItems`, `CommercialQuoteFolioCounters`, `CommercialQuoteIssueIdempotencyRecords`.
8. Verificar/resembrar identities y `SellerCodeSequence`; nunca tocar `__EFMigrationsHistory`.

Para evitar inconsistencia DB/archivos: cargar y verificar medios en staging antes de abrir la transacción; promover a ubicación versionada o reversible; cargar DB apuntando solo al layout final; ejecutar postflight técnico antes de commit cuando sea posible. Si el filesystem no permite swap/rollback atómico, conservar el conjunto anterior y un journal de archivos, y no abrir tráfico hasta que ambos lados coincidan.

### 7.5 Postflight obligatorio

- Los conteos deben coincidir con la matriz y R-01 a R-05; producción no debe tener filas inesperadas.
- Comparar checksums lógicos/campos de todas las tablas, máximos identity y timestamps; comprobar cero FK huérfanas, constraints confiables, duplicados de índices únicos y próximo valor de identities/secuencia.
- Cotizaciones: 9/9/8/1, `IssuedById` y seller válidos, folios únicos, contador ≥ máximo, snapshots/totales sin alteración. No emitir una cotización real; ensayo del próximo folio solo en base desechable.
- Seguridad: 3 usuarios, 58 permisos, 0 refresh tokens heredados; login de `supadmin` y seller con secreto introducido por custodio; autorización positiva/negativa; cuentas salientes sin acceso. No registrar tokens.
- Catálogo: 3/10/92/92/58/85 y vacías según matriz; lectura pública de listado/detalle y lectura autenticada controlada.
- Medios: hashes exactos de los 92+85, HTTP GET/HEAD exitoso y content type/tamaño esperados; ausencia de los 2 huérfanos; logos/promociones según inventario separado.
- Confirmar que `__EFMigrationsHistory` conserva exactamente 22 filas y no cambió durante la operación.
- Mantener mantenimiento hasta revisión de evidencias y firma conjunta. Health verde por sí solo no es criterio suficiente.

### 7.6 Fallos y rollback recuperable

- **Antes del commit DB:** abortar transacción, revertir cualquier promoción de medios mediante snapshot/directorio anterior, comprobar estado previo y mantener mantenimiento.
- **Después del commit, antes de abrir tráfico:** no intentar “arreglos” manuales. Volver a mantenimiento, restaurar backup preventana en base aislada para verificarlo y ejecutar el procedimiento aprobado de restauración/corte; restaurar coordinadamente ambos conjuntos de medios.
- **Después de abrir tráfico:** congelar de inmediato; capturar evidencia sin secretos y decidir entre forward-fix revisado o rollback. Un rollback DB aislado puede perder nuevas solicitudes/escrituras y quedar incompatible con medios; requiere punto de corte y conciliación explícita.
- Criterios automáticos de aborto: nuevas solicitudes, cuentas, cotizaciones u otro drift respecto del inventario; conteo/hash distinto; FK/unique/check fallido; ubicación/ACL no confirmada; espacio insuficiente; backup/restore no verificable; login admin fallido; o imposibilidad de revertir archivos.
- Conservar logs, manifiestos, hashes, conteos, tiempos y aprobaciones; excluir valores de token, hashes de contraseña y conexiones.

## 8. Riesgos residuales

1. **Sustitución autorizada de 8 solicitudes:** R-02 resuelve la decisión; el riesgo residual es no poder recuperarlas o eliminar datos nuevos no inventariados. Se mitiga con preflight exacto, aborto ante drift y backup restaurable preventana.
2. **Bloqueo administrativo:** cambiar `soporte` por `supadmin` puede dejar producción inaccesible si la credencial/hash no funciona. Exigir prueba en clon y procedimiento break-glass antes del corte.
3. **Auditoría rota o falsificada:** IDs de los usuarios locales y sus referencias requieren preservación coherente; no sustituir autores por conveniencia.
4. **Split-brain DB/archivos:** transacción SQL no incluye filesystem. Staging, promoción reversible, mantenimiento y backup coordinado son obligatorios.
5. **Rutas divergentes:** imágenes respetan `Uploads__RootPath`; fichas no. Un backup de una sola carpeta es incompleto.
6. **Restauración no ensayada:** backups descargados reducen riesgo solo después de un restore exitoso equivalente.
7. **Secuencias/identity atrasados:** causan colisiones futuras aunque el postflight de conteos pase.
8. **Datos productivos desconocidos:** antes de borrar debe confirmarse cada tabla hoy marcada “no confirmado”.
9. **PII y secretos:** usuarios, clientes, solicitudes e idempotencia requieren almacenamiento/transporte restringido; tokens no se trasladan y hashes nunca aparecen en reportes.

## 9. Decisión final y alcance propuesto para Prompt 352

### 9.1 GO/NO-GO

- **Aplicación productiva:** **NO-GO**. Este documento no aprueba ninguna operación destructiva ni traslado.
- **Diseño del implementador 352:** **GO** para crear artefactos inertes, revisables y ensayables con preflight, dry-run, pruebas sintéticas y bloqueo productivo por defecto. Este GO no autoriza ejecutar una importación. La aplicación seguirá en NO-GO hasta medir los hechos técnicos y completar todos los controles operativos.

### 9.2 Alcance verificable de Prompt 352 (sin ejecutarlo ahora)

1. Crear especificación y/o herramienta **dry-run por defecto** que lea paquetes offline/staging, nunca credenciales embebidas ni conexiones reales.
2. Generar esquema de manifiesto versionado para las 18 tablas y medios 92+85, con conteos, checksums lógicos, SHA-256, IDs/FK y exclusión demostrable de tokens y dos huérfanos.
3. Producir SQL parametrizado/revisable y calificado exclusivamente a `jemnexusb_api`, con guards de base/esquema/22 migraciones, transacción, staging, orden FK, identity/reseed, secuencia y reemplazo R-02/R-03. Debe abortar si no observa exactamente el estado productivo inventariado y permanecer imposible de aplicar a producción por omisión.
4. Incorporar preflight/postflight de solo lectura y reportes sin secretos; prohibir tocar `__EFMigrationsHistory` y prohibir ejecutar migraciones.
5. Diseñar copiador de medios offline con raíces pasadas explícitamente, path safety, staging, hash antes/después, allowlist exacta y journal reversible; fichas e imágenes como destinos distintos y logos en inventario separado.
6. Añadir pruebas unitarias con fixtures sintéticos y un runbook de ensayo desechable: colisiones, drift por nueva solicitud/cuenta, sustitución 8→0 y 2→3, fallo medio, fallo DB, login de recuperación, rollback y reejecución idempotente.
7. Entregar un paquete que el Prompt 352 **no ejecute contra producción ni LocalDB**, acompañado de revisión de diff, análisis de secretos y comandos de validación estática permitidos por su propio encargo.

La aceptación del 352 exige trazabilidad requisito→guard→prueba, revisión de dos personas y evidencia de ensayo. La autorización para producción deberá ocurrir en un prompt/ventana posterior y distinta.
