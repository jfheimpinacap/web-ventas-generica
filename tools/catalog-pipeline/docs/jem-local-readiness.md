# Certificación offline de una captura GET local

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

El assessor exige la raíz física única `maquinarias`, con ID entero positivo, `parent=null` e
identidad contractual exacta, y valida descendientes por `parent`. No crea ni propone reparar la
raíz y no la confunde con categorías normalizadas o futuras categorías de producto.

Los GET de imágenes y fichas ofrecen metadatos, pero la captura de colecciones no obtiene bytes ni
SHA-256. Filename, URL, MIME o tamaño aislado no prueban igualdad. Por ello el resultado realista de
una captura estructuralmente válida es `read_compatible_manual_binary_verification`; imágenes y
fichas se informan por separado y `mutation_authorized` permanece `false`.

## Ejecución posterior (no ejecutada durante la implementación)

1. Arranque el backend en el perfil local ya configurado y determine su URL loopback con puerto
   explícito desde esa configuración; no se presupone ningún puerto.
2. Exporte únicamente `JEM_NEXUS_LOCAL_READ_TOKEN`. No defina
   `JEM_NEXUS_LOCAL_MUTATION_TOKEN`.
3. Calcule el fingerprint canónico del contrato con una herramienta aprobada por su procedimiento
   local y capture con la interfaz existente:

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

## Salidas, resultados y errores

Los dos archivos se escriben como UTF-8/LF mediante staging propio, flush/fsync, rename y sync
portable del directorio. Repetir bytes idénticos es idempotente; un destino divergente bloquea sin
overwrite ni `--force`. El fingerprint excluye tiempos volátiles y el texto nunca decide.

Los resultados cerrados son `read_compatible`,
`read_compatible_manual_binary_verification` y `read_incompatible`. La CLI devuelve 0 para los dos
primeros, 2 para input/schema inválido, 3 para incompatibilidad y 4 para conflicto de outputs.
