# Validación offline de media y fichas técnicas (v1)

Esta etapa consume exclusivamente `extraction-manifest.json`, `media-candidates.jsonl`,
`document-candidates.jsonl`, un `payload-manifest` explícito y bytes bajo una raíz local. No
importa transporte, no accede a EP/GAM live, no descarga y no convierte una URL en evidencia.

## Contratos separados

* Un **candidate** es una referencia extraída, no la prueba de que existan bytes.
* Un **payload binding** vincula el ID del candidate con una ruta relativa confinada, tamaño y
  SHA-256 esperados, procedencia, autorización conocida y evidencia HTTP opcional inyectada.
* Un **content object** conserva exactamente los bytes y se identifica solo por su SHA-256.
* Una **relation** conserva candidate, objeto, fuente, role EP/GAM, entrada, asociación, identidad
  canónica nullable, URLs, referrer, locator, hints raw, scope, autorización y elegibilidad.
* Una **assessment** describe la validación técnica. Un hint `hero`, `gallery`, `technical_sheet`,
  idioma o revisión no constituye selección.
* La **materialización** en la carpeta pública del producto queda fuera de esta etapa.

Los nuevos contratos cerrados v1 son `payload-manifest`, `asset-record`, `asset-relation`,
`asset-review` y `asset-manifest`. Reutilizan JSON canónico UTF-8, SHA-256, `safe_join`, escritura
atómica y write-once existentes. Se necesitaban porque extracción representa referencias, no
bindings de bytes, identidad de contenido ni assessments binarios.

## Alcance real de los validadores

* **JPEG:** comprueba SOI, markers y longitudes acotadas, obtiene dimensiones desde SOF y exige
  EOI. No decodifica scan data ni afirma decodificación completa.
* **PNG:** comprueba firma, IHDR de longitud 13, dimensiones, límites de chunks, CRC e IEND. No
  descomprime IDAT.
* **WebP:** comprueba RIFF/WEBP, tamaño, chunks y variantes VP8, VP8L o VP8X, con dimensiones cuando
  su cabecera acotada las expone. No descomprime píxeles.
* **PDF:** comprueba `%PDF-`, versión aparente, `%%EOF` y coherencia básica de `startxref`. Detecta
  `/Encrypt`, `/JavaScript`, `/JS`, `/Launch`, `/EmbeddedFile`, `/OpenAction` y `/AA` sin abrir,
  renderizar, descifrar, extraer texto ni ejecutar contenido. Cifrado y contenido activo requieren
  review; corrupción o truncamiento son inválidos. Validación contenedora no es aprobación humana.
* **Identidad declarada incompatible:** si la clase de candidate, el MIME o la extensión presentan
  el payload como PDF (o como otro formato soportado), pero sus bytes carecen de la firma esperada
  o contienen HTML u otro contenido incompatible, queda `invalid`. Las señales estables
  `class_signature_mismatch`, `mime_signature_mismatch`, `extension_signature_mismatch` y la firma
  detectada conservan la contradicción para auditoría.
* **Formatos genuinamente no soportados:** `unsupported` se reserva para contenido reconocible que
  esta versión no admite y que no se presenta como un formato soportado. Por ejemplo, SVG permanece
  `unsupported`: no se renderiza ni se acepta por MIME o extensión.

La firma decide formato, MIME detectado y extensión canónica. MIME declarado, filename y extensión
aparente se conservan solo como evidencia; una discordancia material genera review/bloqueo y nunca
queda elegible. Un payload inválido puede conservarse exactamente en el cache content-addressed para
auditoría, pero no se registra como PDF válido ni se materializa en una carpeta de producto. El
filename nunca forma una ruta. Los límites configurables cubren bytes, ancho, alto y píxeles.

## Deduplicación, asociación y autorización

Solo SHA-256 de bytes completos deduplica. URLs distintas comparten objeto, pero mantienen
relaciones, locators y hints independientes; EP autoritativo y GAM supplemental nunca se sustituyen.
No se asocia por filename o similitud, no se crea identidad desde media y una identidad nullable o
asociación ambigua queda pendiente. `pending_host_review` se preserva y nunca aprueba el host.

`synthetic_fixture` siempre queda `synthetic_only`; `unverified_local_payload` queda pendiente de
autorización. La autorización no se infiere de un booleano. Solo evidencia versionada y auditable
puede permitir `eligible_for_future_selection`; esta elegibilidad no selecciona un principal.

## Almacenamiento, outputs y CLI

Los objetos write-once se publican atómicamente bajo
`_pipeline/cache/sha256/{2}/{2}/{sha256}`. No se crean nombres finales de producto ni se escribe un
objeto no resuelto en una carpeta de producto. Los outputs son:

* `asset-records.jsonl`;
* `asset-relations.jsonl`;
* `asset-reviews.jsonl`;
* `asset-manifest.json` (fuente de verdad, hashes, fingerprints y conteos);
* `asset-report.txt` (derivado).

`catalog_media.py plan` inspecciona metadata sin leer payloads ni escribir outputs; `validate` valida
y publica bytes locales; `verify` relee hashes, tamaños y referencias sin reparar. Códigos: 0
completo, 1 input/error, 2 verificación bloqueada, 3 versión incompatible. No existen flags de red,
confianza o aprobación.

Los fixtures son inventados y no son evidencia live. No hubo descargas, selección de imagen/ficha
principal ni materialización final. La adquisición autorizada/reanudable y la selección
correspondiente quedan para una etapa futura.
