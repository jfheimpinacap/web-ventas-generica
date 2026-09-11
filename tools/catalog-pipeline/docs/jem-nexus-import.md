# Importación JEM Nexus: planificación y dry-run (Prompt 284)

## Límite y autorización

`catalog_acquisition` sigue siendo el único propietario de adquisición, normalización, auditoría,
selección, materialización y verificación del ZIP canónico. `jem_nexus_import` consume esa vista
verificada y no importa adapters EP/GAM, discovery, matching ni fuentes live. Un paquete válido para
inspección puede ser válido para dry-run aun cuando `import_authorized=false`; esto **nunca** autoriza
aplicar. Esta fase fija `apply_supported=false`, `mutation_supported=false`, contadores de mutación en
cero y `publication_authorized=false`. Prompt 285 queda reservado para un apply/verify local
controlado; preparación productiva permanece fuera de alcance.

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

`local_client.py` es la única frontera de red: lectura JSON específica mediante GET, puerto explícito,
sin redirects/cookies/reintentos, timeout y tamaño acotados. Solo acepta `localhost`, `127.0.0.1` y
`[::1]`; prohíbe producción, DNS/IP externos, credenciales, fragmentos y queries fuera de paginación.
La autenticación protegida procede exclusivamente de `JEM_NEXUS_LOCAL_READ_TOKEN`. Su valor, hash,
prefijo o sufijo no se registra ni serializa; ausencia falla antes de consultar. Las pruebas inyectan
transporte falso y no abren sockets.

## Proyección, reconciliación y grafo

La proyección sigue DTOs/endpoints .NET documentados en `jem-nexus-contract.md`, genera evidencia por
campo y no trata `producto.json` (`normalized_for_audit_not_api_payload`) como DTO. Mantiene precio
null, publicación/visibilidad/destacado falsos y no inventa stock, disponibilidad, proveedor,
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
hermano, flush/fsync y rename; contenido idéntico es idempotente y contenido distinto bloquea sin
overwrite/force. Fingerprints excluyen paths absolutos, directorio de salida, timestamps y token.

`catalog_import.py` expone únicamente `snapshot-local`, `plan` y `dry-run`; solo el primero puede hacer
GET loopback. No hay apply/resume/publish/update/delete/approve/bypass. EP/GAM live siguen bloqueados
mientras `structure_verified=false`. El checkpoint LGMG y `jem docs\\temp` permanecen congelados,
sin lectura, modificación ni reanudación.
