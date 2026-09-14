# Planificación local de observación binaria (Prompt 301)

## Alcance y procedencia

Prompt 301 es una tarea nueva, posterior a Prompt 300, sobre el estado integrado que
restauró los contratos de categoría raíz. La validación dinámica autoritativa de ese
estado fue realizada externamente en Windows: **668 pruebas** con resultado OK. No se
repitió aquí: esta entrega admite exclusivamente validaciones estáticas y debe probarse
posteriormente en Windows con Python 3.13.5.

`prompt-296-run-07` y `prompt-296-run-08` son evidencia operacional externa e
inmutable. No se accedió a ellos ni se copiaron URLs, nombres de archivo o datos
comerciales. De run-08 solo se usa como evidencia de diseño el resumen sanitizado
proporcionado: snapshot local completo de 98.576 bytes, 57 referencias de imagen y 55
de ficha, todas candidatas root-relative, sin duplicados ni caracteres inseguros; las
imágenes exponen relación y las fichas no. Estos números y sus fingerprints **no** son
constantes productivas ni fixtures.

## Tres fases estrictamente separadas

1. **Prompt 301 (ahora):** valida archivos locales y construye un plan determinista.
2. **Prompt 302 (futuro):** podrá implementar captura GET local, acotada y autenticada,
   con límites, receipts, MIME y hashes obtenidos de bytes.
3. **Paso posterior:** podrá integrar observaciones con readiness. No se cambia todavía
   `BINARY_CONTENT_NOT_OBSERVABLE`, no se reconcilian fichas y no se autoriza apply.

El núcleo puro `jem_nexus_import/binary_observation.py` recibe objetos ya cargados. No
lee entorno, filesystem, reloj ni red. Valida el snapshot completo
`local_development`, sus siete colecciones, fingerprint semántico y contrato; valida
el reporte readiness, su fingerprint, enlace al mismo snapshot/contrato, cero blockers,
cero mutaciones y la advertencia binaria. Los hashes SHA-256 de ambos archivos de
entrada quedan registrados por la CLI.

## URL, referencias, targets y bindings

La base admite únicamente HTTP con puerto explícito y host exacto `localhost`,
`127.0.0.1` o `[::1]`, sin credenciales, path, query ni fragmento. Esto describe una
futura ubicación local; construir el plan no efectúa requests.

Solo se extraen `product_images[*].image` y
`technical_sheets[*].file_url`. Las referencias deben ser root-relative. Se rechazan
URLs, scheme-relative, credenciales, query, fragmento, controles, NUL, backslash,
segmentos vacíos, puntos/espacios finales, colon, formas drive/UNC/namespace,
traversal literal o codificado, separadores codificados y doble decoding ambiguo. No
se reparan entradas y no se resuelven contra el filesystem.

Un **target** es una futura solicitud única, identificada establemente por clase y
path. Un **binding** conserva cada fila, campo, ID, relación y declaración DTO. Las
referencias duplicadas producen un target con todos sus bindings ordenados; nunca se
elige uno. El mismo path entre clases incompatibles bloquea con
`MEDIA_CLASS_CONFLICT`: la extensión no desempata.

Las imágenes conservan el producto observado exclusivamente por `product` o
`product_id`, más la extensión declarada; la extensión no prueba contenido. Las fichas
conservan MIME, tamaño y extensión visible (posiblemente nula). Sin relación DTO se
marcan `manual_relation_verification_required`, pero siguen siendo observables en una
fase futura. Nunca se infiere producto por nombre, filename, URL, ordinal, proximidad,
cantidad, coincidencia de ID ni posición. `application/pdf` declarado no prueba `%PDF-`,
estructura, seguridad, tamaño real o SHA-256.

## Estado, determinismo y publicación atómica

El contrato usa schema `1.0.0` y reglas
`jem-local-binary-observation-plan-v1`. El estado global es `planned` solo con todos
los gates satisfechos; errores fail-closed no publican plan. Los bindings pueden quedar
`manual_relation_verification_required`. Todo plan declara:

```text
network_executed=false
bytes_observed=false
capture_supported=false
mutation_authorized=false
content_published=false
```

El fingerprint semántico incluye fingerprints de contrato/snapshot, hashes de los
archivos de entrada, base normalizada, política, reglas, targets, bindings, contadores
y estados manuales. No depende de timestamp, cwd, locale, orden de JSON/filesystem,
random, UUID ni identidad de objetos.

La CLI independiente solo ofrece:

```text
catalog_binary_observation.py plan --snapshot <json> --readiness <json> \
  --contract <json> --base-url http://localhost:5000 --output-dir <nuevo>
```

Publica `binary-observation-plan.json` canónico y un resumen TXT. Exige destino nuevo,
rechaza symlinks/conflictos, crea staging hermano propio, escribe UTF-8 con
`flush`/`fsync`, sincroniza directorios cuando el sistema lo permite y renombra el
directorio completo. Solo limpia su staging. No sobrescribe destinos parciales,
alterados, completos ni con extras.

El schema cerrado `local-binary-observation-plan.schema.json` contiene `$defs` para
targets y bindings; su fixture es inequívocamente sintético (`fixture_only=true`) y no
habilita captura. El inventario queda exactamente en **81** archivos
`*.schema.json` y **82** JSON bajo `schemas/v1` al contar el contrato JEM.

## Riesgos y siguiente paso

El plan no demuestra disponibilidad, MIME, tamaño, firma, estructura, seguridad o hash
del contenido. Tampoco aporta transporte, token, retry, resume o receipts. Prompt 302
deberá diseñar esos límites antes de cualquier GET; una fase aún posterior decidirá
cómo incorporar evidencia a readiness. POST, PUT, PATCH, DELETE, publicación y toda
mutación permanecen fuera de alcance.
