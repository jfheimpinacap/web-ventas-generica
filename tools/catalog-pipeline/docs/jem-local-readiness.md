# Certificación offline de una captura GET local

## Continuidad y evidencia de Prompt 299

Esta corrección continúa la línea de Prompts 294–298 sobre la base fusionada `55c5a41` (contenido
funcional `81d89db`). El retest confirmado externamente antes de este cambio fue **661 pruebas OK**.
La captura GET read-only aprobada `prompt-296-run-07` tuvo 98.576 bytes y SHA-256
`466d535971de62c8a4da2845e1bbcc7a5c66e63b4112794a9196befb7af28dee`; su assessment offline
terminó `read_incompatible`/exit 3 únicamente por `ROOT_CATEGORY_MISSING`, además del warning
`BINARY_CONTENT_NOT_OBSERVABLE`, con cero solicitudes y cero mutaciones en el manifiesto.

Las diez categorías observadas incluían las raíces `maquinaria`/`machinery`,
`repuestos`/`spare_part` y `servicios`/`service`, y siete hijas machinery apuntaban a la primera.
Este repositorio no incorpora ni modifica esa evidencia: solo corrige el consumidor contractual.
Se agregan 8 métodos offline (incluidos cinco subcasos de forma inválida), para un total Windows
proyectado entonces de **669**; la ejecución posterior autoritativa en Windows corrigió
ese inventario inflado en un caso y confirmó **668**. No se ejecutaron aquí por la
restricción expresa de validación estática.

Esta certificación separa estrictamente **captura** y **assessment**. La captura existente es el
único paso con red y usa exclusivamente GET loopback; el assessor nuevo solo abre archivos locales,
no recibe URL ni credenciales, no autoriza mutaciones y declara cero solicitudes propias.

## Contrato de lectura observado

La tabla deriva de `local_readiness.collections` en `jem-nexus-contract.json` y de los DTOs .NET
inspeccionados. Un campo desconocido se ignora de forma segura; ausencia y tipo incorrecto de un
campo consumido son blockers. `null` solo se acepta donde el tipo contractual lo permite.

| colección | GET | campos recibidos/consumidos para readiness | identidad | relaciones | compatibilidad |
|---|---|---|---|---|---|
| categories | `/api/categories` | `id`, `name`, `slug`, `parent`, `product_type` | `slug` Unicode NFC/case-insensitive | `parent` → category | planning compatible |
| brands | `/api/brands` | `id`, `name`, `slug` | `slug` | productos → brand opcional | compatible |
| suppliers | `/api/suppliers` | `id`, `name` | `name` | productos → supplier cuando observable | compatible |
| products | `/api/products` | `id`, `name`, `slug`, `category`, `brand`, `model`, `product_type` | `slug` | DTOs anidados category/brand; supplier opcional | compatible |
| product_images | `/api/product-images` | `id`, `product`, `image`, `alt_text`, `is_main`, `order` | ID | `product` → product | estructura compatible; binario no verificable |
| product_specs | `/api/product-specs` | `id`, `product`, `name`, `value`, `unit`, `order` | ID | `product` → product | compatible; `name` es la key leída |
| technical_sheets | `/api/technical-sheets/` | `id`, `name`, `original_file_name`, `content_type`, `size_bytes`, `file_url` | ID | relación solo si el GET la expone | estructura compatible; binario no verificable |

### Relación de categoría y seguimiento del Prompt 296

La captura read-only del Prompt 296 terminó con `ORPHAN_RELATION` en
`product.category_id`: el validador buscaba exclusivamente esa forma estructurada y trataba su
ausencia como `None`, antes de interpretar el campo `category` realmente observado. La inspección
estática del repositorio confirma además que `GET /api/products` construye `ProductListReadDto`,
cuyo `category` obligatorio es un `CategoryReadDto` (objeto con `id` entero). La captura local
observada expuso el mismo nombre como ID entero escalar; ninguna de las dos formas es nullable. En
cambio, `ProductWriteDto` admite los IDs enteros
`category` y `category_id`; los snapshots estructurados históricos conservan `category_id`.

La validación de snapshots admite de forma cerrada solo esas dos representaciones contractuales:
`category: <entero>` para la captura GET, `category: {"id": <entero>}` para el DTO GET actualmente
materializado en el repositorio y `category_id: <entero>` para la forma histórica. No admite
`categoryId`, nombres ni slugs. Si aparecen ambas claves, sus IDs
deben ser idénticos; ausencia, `null`, booleanos, strings numéricos, objetos sin ID entero,
contradicciones o IDs fuera de la colección `categories` producen `ORPHAN_RELATION`. La validación
solo lee el objeto: no añade, elimina ni normaliza campos, por lo que el fingerprint continúa
representando exactamente la forma observada y mantiene su independencia del orden.

El mismo resolver fail-closed audita `product_images` y `product_specs`, donde los DTO GET exponen
el entero `product` y la forma estructurada admite `product_id`; ambas claves simultáneas deben
coincidir. Para categorías padre se aceptan de manera cerrada `parent` (GET) y `parent_id`
(histórica), incluido el `null` contractual, y todo padre no observable sigue bloqueado. No se
amplió `technical_sheets` ni ninguna otra relación.

Esta corrección no valida los valores observados en la instancia: la captura real debe repetirse,
en un destino nuevo, únicamente después del merge y del retest completo en Windows/Python 3.13.5.
No se deben reutilizar `prompt-296-run-05` ni `prompt-296-run-06`. Readiness permanece pendiente
hasta obtener un snapshot válido. No se autorizó ninguna mutación, reparación, publicación ni
acceso adicional al backend.

El contrato vigente distingue expresamente **Etiqueta visible: Maquinarias**, **Slug persistido:
maquinaria** y **Tipo: machinery**. La migración canónica del backend, sus DTO/GET, filtros y pruebas
son la autoridad estática del slug singular; ni la etiqueta humana ni las rutas comerciales cambian.
El falso `ROOT_CATEGORY_MISSING` de `prompt-296-run-07` fue causado exclusivamente por el plural
contractual anterior.

El assessor exige exactamente una raíz física que cumpla a la vez `slug=maquinaria`, ID entero
positivo (no booleano ni string), `parent=null` y `product_type=machinery`. Repuestos, servicios,
posición, orden e ID conocido no son fallbacks. La misma metadata cerrada de
`jem-nexus-contract.json` alimenta planning: el binding externo es `root:maquinaria` y una categoría
hija recibe el ID observado por ese binding, nunca el literal `1`. Ausencia, duplicidad o forma
inválida bloquean; no se crea ni se propone reparar la raíz.

El cambio de contrato altera su fingerprint canónico y por ello invalida fail-closed snapshots,
planes, dry-runs y autorizaciones ligados al fingerprint histórico
`6da3fd64c4180bf1f19dacaa10ea14dafa8633db0d02dd8fb76b7196560d7daf`. No se incrementa
`jem-local-readiness-v2`: las reglas de evaluación no cambiaron y el contrato completo ya es la
entrada versionada y fingerprinted que liga todos esos artefactos. `prompt-296-run-07` permanece
evidencia histórica inmutable y no es aceptable bajo el contrato nuevo.

Los GET de imágenes y fichas ofrecen metadatos, pero la captura de colecciones no obtiene bytes ni
SHA-256. Filename, URL, MIME o tamaño aislado no prueban igualdad. Por ello el resultado realista de
una captura estructuralmente válida es `read_compatible_manual_binary_verification`; imágenes y
fichas se informan por separado y `mutation_authorized` permanece `false`.

## Ejecución posterior (no ejecutada durante la implementación)

1. Arranque el backend en el perfil local ya configurado y determine su URL loopback con puerto
   explícito desde esa configuración; no se presupone ningún puerto.
2. Exporte únicamente `JEM_NEXUS_LOCAL_READ_TOKEN`. No defina
   `JEM_NEXUS_LOCAL_MUTATION_TOKEN`.
3. Después del merge y del retest completo, calcule el fingerprint canónico del contrato mediante
   la función productiva y capture en el destino nuevo `prompt-296-run-08` con la interfaz existente:

   ```text
   catalog_import.py snapshot-local --base-url <URL_LOOPBACK_CON_PUERTO> --contract-fingerprint <FINGERPRINT_CONTRATO> --output <DIRECTORIO_SNAPSHOT>
   ```

4. Ya sin dependencia del backend, ejecute:

   ```text
   catalog_readiness.py assess --snapshot <DIRECTORIO_SNAPSHOT>/jem-state-snapshot.json --contract schemas/v1/jem-nexus-contract.json --output-dir <DIRECTORIO_REPORTE>
   ```

5. Revise `local-readiness-report.json` (decisión canónica) y
   `local-readiness-report.txt` (proyección humana). Copie ambos completos para revisión, nunca el
   token ni el entorno.
6. Interprete `read_compatible` como estructura y binarios observables;
   `read_compatible_manual_binary_verification` como planning/dry-run permitido tras revisión
   binaria manual; y `read_incompatible` como blocker que debe corregirse en captura o contrato.
7. Elimine el secreto de la sesión con el mecanismo del shell correspondiente (por ejemplo,
   `unset JEM_NEXUS_LOCAL_READ_TOKEN` en bash). Confirme también que la variable mutante sigue sin
   definirse.

`snapshot-local` realiza exclusivamente los siete GET locales allowlisted y ningún POST. El
assessment realiza cero solicitudes de red, cero POST, cero create/update/delete y ninguna
publicación. No habilita producción, EP/GAM live ni cambios LGMG.

La advertencia `BINARY_CONTENT_NOT_OBSERVABLE` permanece: los GET no exponen bytes y SHA-256
verificables. Una captura nueva válida puede derivar
`read_compatible_manual_binary_verification`, pero ese resultado no se fuerza. El siguiente paso
permitido es solamente la captura GET read-only nueva y su assessment offline; no autoriza apply,
resume, verify mutante, reparación, importación ni publicación.

## Salidas, resultados y errores

Los dos archivos se escriben como UTF-8/LF mediante staging propio, flush/fsync, rename y sync
portable del directorio. Repetir bytes idénticos es idempotente; un destino divergente bloquea sin
overwrite ni `--force`. El fingerprint excluye tiempos volátiles y el texto nunca decide.

Los resultados cerrados son `read_compatible`,
`read_compatible_manual_binary_verification` y `read_incompatible`. La CLI devuelve 0 para los dos
primeros, 2 para input/schema inválido, 3 para incompatibilidad y 4 para conflicto de outputs.

## Regeneración posterior al merge

La lectura local v2 sella los targets administrativos exactos (incluidas sus queries), la vista normalizada y las rutas comerciales protegidas. Después del merge deben regenerarse el snapshot, el reporte readiness, el plan de observación binaria y toda su descendencia sintética o local. Los artefactos históricos sellados no se reescriben ni se aceptan como evidencia completa v2.
