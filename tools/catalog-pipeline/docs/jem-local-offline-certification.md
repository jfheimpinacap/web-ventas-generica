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
dry-run, autorización fixture-only, snapshot fresco con raíz `maquinarias`, preflight, executor,
checkpoint/receipts, reconciliación de resume y verifier. Reader y mutator son los únicos límites
inyectados. No se sustituyen planificación, bindings, preflight, ejecución, checkpoint,
reconciliación ni verificación.

El fake privado `_SyntheticBackend` es `fixture_only`, determinista, stateful y vive en memoria y
temporales propiedad de cada prueba. Asigna enteros positivos crecientes, actualiza colecciones tras
cada operación, registra lecturas, dispatches, payloads y bytes, y permite fallar antes del dispatch
o perder la respuesta después del commit. No crea servidor, no abre sockets, no consulta variables
de entorno, no guarda credenciales y no importa transportes concretos. Las reglas de negocio siguen
en los módulos productivos.

## Correspondencia con el contrato inspeccionado

| operation kind | endpoint/método | DTO request | respuesta de creación | colección GET | identidad observable | campos verificables |
| --- | --- | --- | --- | --- | --- | --- |
| `category` | `POST /api/categories` | `CategoryWriteDto` JSON | `201 CategoryReadDto`, `id` entero | `categories` | `slug`, `parent_id` | nombre, slug, padre, tipo, descripción, activo, orden |
| `brand` | `POST /api/brands` | `BrandWriteDto` JSON | `201 BrandReadDto`, `id` entero | `brands` | `slug` | nombre, slug, logo, descripción, activo |
| `supplier` | `POST /api/suppliers` | `SupplierWriteDto` JSON | `201 SupplierReadDto`, `id` entero | `suppliers` | `name` | contacto, teléfono, email, notas, activo |
| `product` | `POST /api/products` | `ProductWriteDto` JSON | `201` detalle de producto, `id` entero | `products` | clave natural y `id` | campos estructurados y relaciones `_id` |
| `spec` | `POST /api/product-specs` | `ProductSpecWriteDto` JSON | `201 ProductSpecReadDto`, `id` entero | `product_specs` | request `product_id` + `key`; response `product` + `name` | valor, unidad y orden; lectura denomina `Name` a la key |
| `image` | `POST /api/product-images` multipart | form fields + archivo | `201 ProductImageReadDto`, `id` entero | `product_images` | request `product_id`; response `product` (y `id` confirmado) | URL/imagen, alt, principal y orden; no hash binario |
| `technical_sheet` | `POST /api/technical-sheets/` multipart | `name` + `file` | `201 TechnicalSheetResponse`, `id` entero | `technical_sheets` | nombre (y `id` confirmado) | nombre, filename, content type, tamaño y file URL; no hash binario |

Las rutas proceden de `CommercialWriteEndpoints`, `CommercialReadEndpoints` y
`TechnicalSheetEndpoints`; los nombres proceden de sus DTOs. El fake no añade campos al modo que
representa los DTO reales para hacer verificable lo que JEM no expone.

## Dos modos de observabilidad

* `real_dto_shape` omite `sha256` en imágenes y fichas, como los DTO GET actuales. El resultado
  obligatorio es `manual_verification_required` y el checkpoint permanece
  `local_apply_completed_pending_verify`; jamás se declara un falso verified.
* `observable_binary_fixture` añade el hash exclusivamente como evidencia sintética del fixture.
  Solo ese modo permite certificar el camino `local_apply_verified` y la conservación exacta de los
  bytes y hashes.

## Dataset y garantías

El paquete contiene una categoría física sintética, una marca ficticia, un proveedor sintético ya
observable en el snapshot base, un producto, dos especificaciones, imagen primaria/secundaria y
una ficha PDF. Los bytes son constantes pequeños generados en el helper; tamaños y SHA-256 se
calculan sobre esos bytes. Ningún nombre, modelo o archivo representa equipos reales. El producto
se persiste con `price=null`, `price_visible=false`, `is_featured=false` e `is_published=false`.

Las 30 pruebas certifican orden topológico, propagación de IDs, hashes/bytes, fingerprints,
contadores, receipts y prefijo completado; checkpoint inicial e `in_flight` persistidos antes de
cada mutación; receipt/checkpoint antes de continuar; staging propio, destino idéntico idempotente
y conflicto fail-closed. También cubren pérdida de respuesta: el snapshot fresco reconcilia el
recurso exacto, crea receipt `snapshot_reconciliation` y continúa sin un segundo dispatch.
Ausencia, divergencia, duplicado, identidad no observable, deriva ajena y error de persistencia no
provocan retry automático. Verify repetido es determinista y no repara ni publica.

La composición CLI continúa ofreciendo exactamente `snapshot-local`, `plan`, `dry-run`,
`apply-local`, `resume-local` y `verify-local`. Sus factories permiten el fixture únicamente en
proceso; sin mutator inyectado, una autorización fixture-only es rechazada por el límite concreto.
El snapshot fresco y el preflight se completan antes de crear el mutator.

## Límites y pasos posteriores

Esta es evidencia de integración del código local, no evidencia de compatibilidad runtime con una
instancia real. No contiene outputs runtime, tokens, autorizaciones `local_development`, datos de
EP/GAM ni otros catálogos congelados. Conserva el inventario de 79 schemas. El total proyectado es
584 pruebas previamente confirmadas + 30 nuevas = 614; debe ejecutarse después en Windows con
Python 3.13.5.

Solo tras ese retest podrá solicitarse por separado el nivel 2: una captura GET read-only del
backend local real. Esa inspección deberá seguir siendo explícitamente autorizada y no habilitará
mutaciones. Los niveles 3 y 4 necesitan autorizaciones posteriores independientes; el nivel 5
permanece prohibido.
