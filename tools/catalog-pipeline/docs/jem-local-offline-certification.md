# Certificación offline del importador local JEM Nexus (nivel 1)

## Alcance y niveles

| Nivel | Alcance | Estado |
| --- | --- | --- |
| 1 | Ensayo sintético end-to-end sin sockets | Implementado por esta certificación |
| 2 | Captura GET read-only del backend local real | Posterior al retest |
| 3 | Mutación local de dataset sintético aislado | Requiere autorización posterior |
| 4 | Importación EP real en JEM local | Fuera de este prompt |
| 5 | Producción/publicación | Prohibido |

Superar un nivel no autoriza el siguiente. En particular, esta entrega no autoriza requests contra
una API, POST reales, publicación, producción ni uso de catálogos reales.

## Flujo certificado

La prueba `test_jem_nexus_local_integration.py` construye un ZIP canónico con el packager real, lo
verifica con el verificador real y consume sus bytes sin extraerlos. Después ejecuta planner,
dry-run, autorización fixture-only, snapshot fresco con raíz `maquinaria`, preflight, executor,
checkpoint/receipts, reconciliación de resume y verifier. Reader y mutator son los únicos límites
inyectados. No se sustituyen planificación, bindings, preflight, ejecución, checkpoint,
reconciliación ni verificación.

El fake privado `_SyntheticBackend` es `fixture_only`, determinista, stateful y vive en memoria y
temporales propiedad de cada prueba. Asigna enteros positivos crecientes, actualiza colecciones tras
cada operación y registra por `operation_id` intents, dispatches, commits y respuestas entregadas o
perdidas. `_PlannedMutator`, construido para el bundle sellado y el índice `next_operation` del
checkpoint, valida orden, operation ID, kind y endpoint antes de asociar un dispatch. Para JSON
compara el payload materializado completo con el `request_fingerprint` productivo. Para multipart
usa una validación específica del contrato descrita abajo. Así no inventa un `operation_id` en la interfaz real
`kind + payload` ni depende del anterior `current_operation`, que era estado externo inexistente en
el contrato y atribuía operaciones diferentes a un único ID. El fake permite fallar antes del
dispatch o perder la respuesta después del commit. No crea servidor, no abre sockets, no consulta variables
de entorno, no guarda credenciales y no importa transportes concretos. Las reglas de negocio siguen
en los módulos productivos.

### Descriptor multipart y causa del retest del Prompt 292

El retest de la base fusionada del Prompt 292 (`88e12a9`, cuyo cambio funcional es `3ae34aa`)
registró 614 pruebas, 596 correctas, 18 failures y cero errors. Las 18 rutas end-to-end no eran
causas independientes: todas alcanzaban por primera vez una imagen y `_PlannedMutator` reconstruía
el descriptor completo, pero lo entregaba a `_expected()` como si fuera el JSON recibido. El primer
campo diferente era la envoltura: el argumento `fields` ya era la parte estructurada interior,
mientras `_expected()` esperaba `{"multipart": ...}`; además el executor ya había separado
`file_entry`, `sha256`, `size` y `mime`.

El descriptor planificado de cada imagen es `{"multipart": {"product_id": <binding de producto>,
"file_entry": <path>, "sha256": <hash del objeto>, "size": <tamaño>, "mime": "image/png",
"alt_text": "", "is_main": <bool>, "order": <ordinal>, "source_filename": <nombre fuente>}}`.
Tras materializar bindings, `product_id` es el entero producido; todo lo demás permanece idéntico.
`execute()` calcula el fingerprint sobre ese descriptor materializado completo y el endpoint
`/api/product-images`. Luego entrega al mutator solamente los campos `product_id`, `alt_text`,
`is_main`, `order` y `source_filename`, más `upload.bin`, `image/png`, los bytes, y hash y tamaño
esperados como argumentos separados.

La ficha se planifica como `{"multipart": {"name": "Ficha sintética", "file_entry":
"products/sintetico/ficha.pdf", "sha256": <hash PDF>, "mime": "application/pdf"}}`; no contiene
binding de producto, ordinal, role, source filename ni tamaño explícito. El executor obtiene el
tamaño por defecto desde los bytes, calcula el fingerprint del descriptor completo con
`/api/technical-sheets` y entrega `{"name": "Ficha sintética"}`, `upload.pdf`, MIME, bytes, hash y
tamaño por separado. En ambos tipos el path y la metadata de integridad forman parte del payload
fingerprinted aunque no sean campos del formulario; `role` no forma parte del descriptor y, para
las imágenes, se proyecta a `is_main`.

La validación multipart test-only ahora vuelve a materializar el descriptor planificado y compara,
sin confiar solo en el fingerprint, campos estructurados, filename contractual, MIME, bytes exactos,
SHA-256 recalculado, hash esperado, tamaño real y tamaño esperado. Finalmente recalcula
`request_fingerprint(endpoint, payload_materializado_completo)` con el helper productivo —la única
fuente del algoritmo— y solo entonces avanza el cursor. El wrapper despacha al fake con el
`operation_id` seleccionado y conserva toda la evidencia multipart por operación. La cobertura
existente comprueba también alteraciones individuales de cada componente, y que las dos imágenes y
la ficha quedan asociadas a sus propias operaciones.

## Correspondencia con el contrato inspeccionado

| operation kind | endpoint/método | DTO request | respuesta de creación | colección GET | identidad observable | campos verificables |
| --- | --- | --- | --- | --- | --- | --- |
| `category` | `POST /api/categories` | `CategoryWriteDto` JSON | `201 CategoryReadDto`, `id` entero | `categories` | `slug`, `parent_id` | nombre, slug, padre, tipo, descripción, activo, orden |
| `brand` | `POST /api/brands` | `BrandWriteDto` JSON | `201 BrandReadDto`, `id` entero | `brands` | `slug` | nombre, slug, logo, descripción, activo |
| `supplier` | `POST /api/suppliers` | `SupplierWriteDto` JSON | `201 SupplierReadDto`, `id` entero | `suppliers` | `name` | contacto, teléfono, email, notas, activo |
| `product` | `POST /api/products` | `ProductWriteDto` JSON | `201` detalle de producto, `id` entero | `products` | clave natural y `id` | campos estructurados y relaciones `_id` |
| `spec` | `POST /api/product-specs` | `ProductSpecWriteDto` JSON | `201 ProductSpecReadDto`, `id` entero | `product_specs` | request `product_id` + `key`; response `product` + `name` | valor, unidad y orden; lectura denomina `Name` a la key |
| `image` | `POST /api/product-images` multipart | form fields + archivo | `201 ProductImageReadDto`, `id` entero | `product_images` | request `product_id`; response `product` (y `id` confirmado) | URL/imagen, alt, principal y orden; no hash binario |
| `technical_sheet` | `POST /api/technical-sheets` multipart | `name` + `file` | `201 TechnicalSheetResponse`, `id` entero | `technical_sheets` | nombre (y `id` confirmado) | nombre, filename, content type, tamaño y file URL; no hash binario |

Las rutas proceden de `CommercialWriteEndpoints`, `CommercialReadEndpoints` y
`TechnicalSheetEndpoints`; los nombres proceden de sus DTOs. El fake no añade campos al modo que
representa los DTO reales para hacer verificable lo que JEM no expone.

## Dos modos de observabilidad

* `real_dto_shape` elimina de la respuesta pública `sha256` y no expone bytes de imágenes o fichas,
  exactamente como los DTO GET actuales. `SnapshotObserver` no sintetiza hashes desde filename,
  URL, MIME o tamaño. El resultado obligatorio es `manual_verification_required`, enumera los IDs
  de operación binarios y el checkpoint permanece `local_apply_completed_pending_verify`; jamás
  se declara un falso verified.
* `observable_binary_fixture` conserva los bytes solo en almacenamiento privado del fake y los
  entrega a `_ObservableBinaryFixtureObserver`, un observer test-only explícito que calcula SHA-256
  desde esos bytes actuales. Solo ese modo permite certificar el camino `local_apply_verified`.

La falsa observabilidad anterior combinaba un `sha256` del payload POST guardado en los recursos
internos del fake con un observer sintético que declaraba los bytes observables mediante un booleano
sin aportar evidencia actual. `verify_managed()` confiaba en ese booleano y nunca comparaba un hash
observado. Ahora exige el SHA-256 actual del observer para cada imagen y ficha; plan, checkpoint,
receipt, source hash, filename y metadatos de carga no sustituyen esa evidencia.

## Dataset y garantías

El paquete contiene una categoría física sintética, una marca ficticia, un proveedor sintético ya
observable en el snapshot base, un producto, dos especificaciones, imagen primaria/secundaria y
una ficha PDF. Los bytes son constantes pequeños generados en el helper; tamaños y SHA-256 se
calculan sobre esos bytes. Ningún nombre, modelo o archivo representa equipos reales. El producto
se persiste con `price=null`, `price_visible=false`, `is_featured=false` e `is_published=false`.
El plan tiene por ello ocho mutaciones: categoría, marca, producto, dos ProductSpec, dos imágenes y
una ficha. El proveedor no genera la novena porque ya existe en el snapshot y se resuelve como
binding externo. Las aserciones de checkpoint, receipts y mutaciones derivan el total de
`len(bundle["operations"])` y validan por separado esta distribución, sin conservar el literal `8`.

Las 30 pruebas certifican orden topológico, propagación de IDs, hashes/bytes, fingerprints,
contadores, receipts y prefijo completado; checkpoint inicial e `in_flight` persistidos antes de
cada mutación; receipt/checkpoint antes de continuar; staging propio, destino idéntico idempotente
y conflicto fail-closed. También cubren pérdida de respuesta: el snapshot fresco reconcilia el
recurso exacto, crea receipt `snapshot_reconciliation` y continúa sin un segundo dispatch.
Ausencia, divergencia, duplicado, identidad no observable, deriva ajena y error de persistencia no
provocan retry automático. Las colisiones integrales se detienen todavía antes: `capture_snapshot()`
preserva `validate_snapshot()`, por lo que una identidad duplicada en vuelo produce
`IDENTITY_COLLISION` y un ID administrado duplicado produce `DUPLICATE_ID`, ambos antes de
reconcile/verify y sin invocar el mutator ni reintentar. Las pruebas unitarias de reconciliación
pueden seguir construyendo entradas controladas para cubrir `ambiguous`. Verify repetido es
determinista y no repara ni publica.

La composición CLI continúa ofreciendo exactamente `snapshot-local`, `plan`, `dry-run`,
`apply-local`, `resume-local` y `verify-local`. Sus factories permiten el fixture únicamente en
proceso; sin mutator inyectado, una autorización fixture-only es rechazada por el límite concreto.
El snapshot fresco y el preflight se completan antes de crear el mutator.

## Límites y pasos posteriores

La corrección posterior al falso positivo del Prompt 296 conserva los DTO observados sin
normalizarlos: la captura GET observada usa `category` como ID entero y el código inspeccionado lo
materializa como objeto `CategoryReadDto` con `id` entero, mientras snapshots históricos pueden
usar `category_id` entero. `category` y `category_id` son los únicos nombres admitidos por el
snapshot; si ambos aparecen deben identificar exactamente la misma categoría observable. Valores
ausentes, nulos, de tipo incorrecto, contradictorios o desconocidos siguen bloqueándose con
`ORPHAN_RELATION`. Imágenes y ProductSpec mantienen análogamente `product`/`product_id`, ahora con
conflictos duales explícitamente bloqueados. Los fingerprints continúan calculándose sobre el DTO
original y la validación no lo muta.

La raíz vigente conserva la etiqueta visible `Maquinarias`, pero su slug persistido es
`maquinaria` y su tipo es `machinery`. Esa identidad procede una sola vez de la metadata cerrada
del contrato; readiness y planning la comparten, y planning produce `root:maquinaria` con el ID
observado, no con un ID fijo. El plural anterior explica el falso `ROOT_CATEGORY_MISSING` sin
implicar ninguna reparación de datos.

Cambiar el contrato invalida por fingerprint la captura y toda autorización anteriores. La captura
real se repetirá solo después del merge y del retest en Windows con Python 3.13.5, en
`prompt-296-run-08`; `prompt-296-run-07` y las anteriores permanecen históricas e inmutables.
Readiness continúa pendiente y `BINARY_CONTENT_NOT_OBSERVABLE` permanece hasta aportar evidencia
manual real. Esta corrección no autoriza GET durante su implementación, mutaciones, reparación,
importación ni publicación.

Esta es evidencia de integración del código local, no evidencia de compatibilidad runtime con una
instancia real. No contiene outputs runtime, tokens, autorizaciones `local_development`, datos de
EP/GAM ni otros catálogos congelados. Conserva el inventario de 79 schemas. El total proyectado es
584 pruebas previamente confirmadas + 30 nuevas = 614; debe ejecutarse después en Windows con
Python 3.13.5.

El nivel 2 queda expresamente pendiente para el Prompt 294: una captura GET read-only del backend
local real. Esa inspección deberá seguir siendo explícitamente autorizada y no habilitará
mutaciones. Los niveles 3 y 4 necesitan autorizaciones posteriores independientes; el nivel 5
permanece prohibido.
