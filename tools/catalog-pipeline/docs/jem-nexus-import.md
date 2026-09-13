# Importación JEM Nexus: planificación y dry-run (Prompt 284)

## Límite y autorización

`catalog_acquisition` sigue siendo el único propietario de adquisición, normalización, auditoría,
selección, materialización y verificación del ZIP canónico. `jem_nexus_import` consume esa vista
verificada y no importa adapters EP/GAM, discovery, matching ni fuentes live. Un paquete válido para
inspección puede ser válido para dry-run aun cuando `import_authorized=false`; esto **nunca** autoriza
aplicar. Esta fase fija `apply_supported=false`, `mutation_supported=false`, contadores de mutación en
cero y `publication_authorized=false`. El apply/verify local controlado se aplaza al Prompt 287;
preparación productiva permanece fuera de alcance.

Solo se admite ZIP canónico con receipt externo recalculado, manifest completo, fingerprints de
contenido/auditoría/decisión, hash y tamaño, al menos un incluido y cero bloqueados, junto con snapshot,
policy y fingerprint contractual. Se rechazan JSON sueltos, carpetas, ZIP arbitrario o LGMG, reports
confiados sin recalcular, paths externos, globbing y datos live. La lectura conserva bytes estables,
usa únicamente entries declaradas, límites del verifier y `ZipFile.open/read`; nunca extrae ni
recomprime assets.

## Snapshot y GET local

El snapshot v1 es cerrado: categorías jerárquicas, marcas, proveedores, productos, imágenes, specs y
fichas; evidencia por endpoint/página (status, MIME, hash, completitud), clasificación
`fixture_only|local_development`, contrato y fingerprint semántico. Orden y timestamp no afectan el
fingerprint. IDs duplicados, colisiones case-insensitive, relaciones huérfanas, páginas truncadas,
MIME/shape inesperado o evidencia faltante bloquean.

`jem_nexus_import/local_client.py` es núcleo puro: valida la política local y consume exclusivamente
un callable GET inyectado; sin transporte produce `LOCAL_TRANSPORT_MISSING`. La única frontera de red
es `jem_nexus_local_transport.py`, compuesta por `catalog_import.py`: GET con puerto explícito,
sin redirects/cookies/proxies/reintentos, timeout y tamaño acotados. Solo acepta `localhost`, `127.0.0.1` y
`[::1]`; prohíbe producción, DNS/IP externos, credenciales, fragmentos y queries fuera de paginación.
La autenticación protegida procede exclusivamente de `JEM_NEXUS_LOCAL_READ_TOKEN`. Su valor, hash,
prefijo o sufijo no se registra ni serializa; ausencia falla antes de consultar. Las pruebas inyectan
transporte falso y no abren sockets. La frontera vuelve a validar el target loopback aun ante uso directo.

## Proyección, reconciliación y grafo

La proyección sigue DTOs/endpoints .NET documentados en `jem-nexus-contract.md`, genera evidencia por
campo, conserva solo campos recibidos y no trata `producto.json` (`normalized_for_audit_not_api_payload`) como DTO. Una construcción separada del payload aplica con regla y evidencia precio
null y publicación/visibilidad/destacado falsos; no inventa stock, disponibilidad, proveedor,
condición ni texto comercial. Altura de elevación/mástil permanece `ProductSpec`, nunca
`WorkingHeightM`; enums desconocidos bloquean.

Categoría y parent se comparan por mapping/jerarquía exactos; marcas por clave exacta; proveedor solo
si es explícito y único. Productos usan una natural key conservadora exacta (tipo, slug/model/SKU
contractual), sin fuzzy matching, updates, merges, deletes o publish. Imágenes conservan entry,
SHA-256, tamaño, MIME, rol, identidad y ordinal: primary único, máximo cuatro secondary y hashes no
solapados. La ficha aprobada puede planificarse; todo documento adicional queda
`retained_not_imported` cuando no hay relación backend compatible.

Bindings observados son `external`; resultados futuros son `produced`. Cada referencia lleva scope,
namespace, key y tipo. Duplicados/solapamientos, tipos erróneos, productores ausentes o múltiples,
dependencias futuras inválidas y ciclos bloquean. La regresión sintética `root:maquinarias` siembra la
raíz observada para resolver una hija; si falta produce `MISSING_BINDING`, nunca `KeyError` ni
`partial`.

Operation IDs, orden topológico y fingerprints derivan solo de inputs semánticos. Categorías/marcas
preceden productos y estos preceden specs/imágenes/ficha; no hay IDs ficticios aplicables. El dry-run
reconstruye bindings, valida dependencias/payload templates y produce placeholders inequívocamente
simbólicos. Estados: `invalid_package`, `invalid_snapshot`, `preflight_failed`,
`manual_review_required`, `dry_run_ready`.

## Evidencia y CLI

Los outputs previstos son `jem-state-snapshot.json`, `import-preflight.json`, `import-bindings.json`,
`import-operations.jsonl`, `import-plan.json`, `import-reviews.jsonl`,
`import-dry-run-manifest.json` e `import-dry-run-report.txt`. Escritura UTF-8/LF canónica usa staging
hermano, flush/fsync de archivo y rename; el sync del directorio es best-effort solo ante errores
portables de operación no soportada. Los conflictos se comprueban antes de publicar, el marcador se
publica al final y un fallo intermedio revierte solo archivos nuevos del intento. Contenido idéntico
es idempotente y contenido distinto bloquea sin overwrite/force. Fingerprints excluyen paths absolutos, directorio de salida, timestamps y token.

La serialización canónica vive en la capa neutral `catalog_pipeline_common`; adquisición conserva su
API histórica mediante reexportación y el importador no depende de adquisición.

`catalog_import.py` expone únicamente `snapshot-local`, `plan` y `dry-run`; solo el primero puede hacer
GET loopback. No hay apply/resume/publish/update/delete/approve/bypass. EP/GAM live siguen bloqueados
mientras `structure_verified=false`. El checkpoint LGMG y `jem docs\\temp` permanecen congelados,
sin lectura, modificación ni reanudación.

## Controlled local apply, resume, and verify (Prompt 288)

The execution phase is **local-only** and production remains structurally unavailable. `apply-local` and
`resume-local` reverify the canonical package, exact external receipt, plan, dry-run, policy, authorization,
and a freshly captured complete snapshot before the mutation transport is constructed. An exact external
`local-apply-authorization` binds all fingerprints, target, operation count and kinds; the CLI has no approval
command. `fixture_only` authorizations are limited to injected fake mutators, while the concrete boundary
requires `local_development` and `JEM_NEXUS_LOCAL_MUTATION_TOKEN`. Tokens and authorization headers are
never serialized, fingerprinted, reported, or accepted as arguments.

The pure execution preflight seals the topological operation order, external bindings, POST endpoint and
payload templates. The concrete boundary accepts only explicit loopback origins with ports, disables proxies
and redirects, and exposes typed JSON/multipart POST operations rather than an arbitrary HTTP method.
Multipart bodies use package bytes after size/hash validation and a deterministic request-derived boundary;
`retained_not_imported` documents are never sent. Products are checked immediately before dispatch for
`price=null`, `price_visible=false`, `is_featured=false`, and `is_published=false`.

A canonical UTF-8 checkpoint is fsynced and atomically replaced before the first POST and before every
request as an `in_flight` intent. Execution is serial. Valid closed responses produce minimal receipts and
bindings before the completed prefix advances. A post-dispatch timeout, disconnect, truncated/ambiguous
response, or persistence failure retains `in_flight`, enters `local_apply_reconciliation_required`, and is
never retried automatically. Resume requires identical inputs and target; completed resources and any
in-flight resource must reconcile exactly through GET. Missing, duplicate, divergent, or incompletely
observable resources remain blocked. Complete or verified checkpoints never repeat POSTs.

`verify-local` is GET-only and compares only plan-managed entities, relationships, IDs, natural keys,
counts, duplicates, specs, media, sheet, and commercial safe defaults. Unmanaged products are ignored.
Where the backend cannot expose byte/hash evidence, the result is `manual_verification_required`, never
`local_apply_verified`; verify never repairs. The output set contains preflight, checkpoint, JSONL receipts,
apply manifest/report and verification JSON/text without secrets or unnecessary absolute paths.

This design converts the frozen LGMG partial-apply incident into regressions: intention precedes transport,
completed IDs are a strict prefix, unknown outcomes require observation, and blind replay is prohibited.
No LGMG code, historical checkpoint, `jem docs\\temp`, backend, frontend, database, publication, or production
path is changed. Prompt 289 is reserved for later Windows 3.13.5 validation and local integration. Production
preparation remains out of scope.

### Positive in-flight reconciliation (Prompt 288C)

The Prompt 288 implementation detected `in_flight` at the beginning of `execute` and
unconditionally raised `IN_FLIGHT_RECONCILIATION_REQUIRED`; it had no observer-driven
classification path. Resume now validates the sealed checkpoint and its completed-prefix,
accepts a fresh snapshot whose only additions are explained by recorded receipts or the
current intent, and classifies the intent purely as `exact_match`, `absent`, `divergent`,
`ambiguous`, or `unobservable` before a mutation transport is constructed.

Identity is contractual per entity (slug for category/brand/product, exact supplier name,
and product/key for ProductSpec). Every managed scalar is compared exactly after binding
materialization. Products must still match all four commercial defaults. Images and
technical sheets additionally require snapshot SHA-256 evidence; filename, URL, MIME, or
size alone yields manual reconciliation. Base resources must remain byte-for-byte equal as
canonical snapshot objects, completed additions must have receipt-bound IDs, and every
other addition is drift (`LOCAL_STATE_CHANGED`).

An exact observation creates a minimal receipt with
`confirmation_source=snapshot_reconciliation`, records its produced binding, extends the
completed prefix, increments `mutations_confirmed`, `operations_completed`, and
`operations_reconciled` exactly once, clears `in_flight`, and atomically stages receipts
before publishing the checkpoint marker. Existing intent/request counters are not
incremented. Only after this persistence may composition construct a mutator for the next
operation. A final reconciled operation becomes `local_apply_completed_pending_verify`;
only `verify-local` can set `local_apply_verified`. Absent, divergent, duplicate, partially
identified, drifted, or unobservable results never resend the uncertain POST.

The companion `jem-local-execution-test-matrix.md` maps exactly 95 independently
discoverable behavioral cases (21 retained plus 74 stable generated cases). The projected
suite is 489 + 95 = 584 tests; execution remains reserved for Prompt 289 on Windows with
Python 3.13.5.
