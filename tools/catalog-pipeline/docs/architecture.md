# Arquitectura, políticas y límites — v1

## Componentes y artefactos

`catalog_acquisition` trabaja solo con snapshots/bytes inyectados: discovery, evidencia raw,
identidad, normalización, auditoría y empaquetado. `jem_nexus_import` depende solo de schemas y
del paquete aprobado. No contiene transporte, consulta, planificación, dry-run, mutación,
checkpoint, resume ni verify. Un adaptador futuro implementa `SourceAdapter` y recibe evidencia
capturada; nunca se importa desde `jem_nexus_import`.

Flujo: `raw -> source identity -> discovered entry -> canonical candidate -> resolved canonical
product -> normalized -> audit -> package`. Una observación es una captura histórica; no es un
producto. `DiscoveredProductEntry` es el hallazgo estable acreditado por una fuente de existencia y
permanece aunque su identidad canónica sea null, tenga varios candidatos o esté bloqueado.

## Identidades v1

`source-identity-v1` identifica un registro observado usando solo namespace estable, estrategia de
clave versionada y clave estable del adaptador. Excluye URL, modelo/variante presentados, textos,
fecha y versión del adaptador. Sin clave nativa, un adaptador futuro deberá declarar otra estrategia
versionada; aquí no se define ninguna específica de proveedor.

`canonical-identity-v1` calcula un **candidato** determinista usando marca canónica, modelo exacto,
variante y discriminador. Excluye fuente, clave/URL de fuente, adaptador y filesystem. Calcular el
hash no lo adopta ni lo vuelve importable. Variantes cercanas permanecen separadas; familia/serie
emite varios candidatos. `IdentityLink` conserva correspondencia, evidencia, regla y versión,
resolución y decisión humana. Una adopción automática exige ID+versión de regla; una manual exige
`human_decision_id`. `assert_importable` comprueba además tipo/categoría y ausencia de bloqueos.
`supersedes_canonical_identity` permite correcciones sin recalcular en silencio.

## Autoridad y universos

El rol cerrado se declara en el manifiesto de ejecución y evidencia: `authoritative_existence`
puede crear una entrada descubierta; `supplemental` solo aporta observaciones/evidencia o se enlaza
a una entrada existente. Nunca se infiere desde el nombre del adaptador y no hay marcas codificadas.

`discovered_universe` se clavea por `discovered_entry_id`; `blocked` usa la misma clave incluso sin
identidad canónica. `canonical_candidate_universe` contiene hashes calculados aún no adoptados;
`resolved_canonical_universe` contiene productos adoptados, deduplicados por identidad canónica;
`importable_universe` es su subconjunto con resolución auditable, tipo/categoría aprobados, readiness
y cero bloqueos. Una entrada no resuelta nunca desaparece ni recibe carpeta definitiva.

## Filesystem

Categorías: NFKD -> ASCII -> minúsculas -> guiones. Modelos: NFC, caracteres Windows inválidos a
`_`, recorte de espacio/punto final, prefijo `_` para reservados incluso con extensión. Segmentos
largos se acortan con sufijo SHA-256 determinista (no aleatorio). **La clave física no es
autodecodificable**: la recuperación exacta requiere el par `original_name`/`materialized_name`
conservado en el manifiesto. Comparación de colisión siempre NFC + casefold +
recorte Windows. Una colisión aborta, incluidos dos nombres transliterados iguales.
`create_layout` exige un `LayoutRegistry`: las colisiones se planifican antes de escribir. Cada
carpeta definitiva de producto se crea solo después de adoptar `canonical_identity_value`, nunca para
una entrada descubierta no resuelta, una identidad de fuente ni
a una identidad de negocio derivada de la clave física.

Layout portable: `<marca>/catalogo/<categoria>/<modelo>/{imagenes,fichas-tecnicas,documentos}` y
`<marca>/_pipeline/{snapshots,cache,manifests,mappings,reports,packages}`. Las rutas manifestadas usan
`/`; `safe_join` rechaza traversal, absolutas, UNC y unidades, y verifica confinamiento bajo raíz.
Nombres futuros: `<MARCA>-<MODELO>-<ORDEN>[-principal].<ext>` y
`<MARCA>-<MODELO>-ficha-tecnica-<idioma>[-revision].pdf`; sus metadatos están en package-manifest.

## JSON y fingerprints

JSON canónico: UTF-8, NFC, LF final, claves ordenadas, separadores compactos, sin NaN. Listas con
orden semántico se preservan; solo `aliases`, `blocking_issue_codes` y
`additional_source_categories` se ordenan canónicamente. Rutas son POSIX. El fingerprint SHA-256
incluye todo salvo `created_at`, `updated_at`, `captured_at`, `run_started_at` y `absolute_path`;
requiere `schema_version` y `rules_version`, por lo que cambios de reglas cambian el hash. Los
timestamps operativos, incluido `observed_at` del vínculo, quedan excluidos. Nunca se
debe incluir una ruta absoluta o dato de máquina en contenido aprobado.

## Persistencia local

El temporal se crea en el directorio destino, se hace `fsync` y `os.replace`; siempre se limpia.
El hash esperado se verifica antes de aceptar bytes. Evidencia raw es write-once: mismos bytes son
idempotentes; otros bytes para la misma ruta producen `RAW_EVIDENCE_IMMUTABLE` sin sobrescribir.
Errores poseen códigos estables. No existe acceso de red.

## Schemas y evolución

JSON Schema Draft 2020-12, versión `1.0.0`, IDs estables, referencias relativas, enums cerrados y
`additionalProperties: false` excepto `extensions`. Patch conserva compatibilidad; minor solo añade
opciones retrocompatibles; major rompe contrato y usa nuevo directorio/ID. Un consumidor rechaza
versiones desconocidas, schemas inválidos y propiedades silenciosas. Los estados de procedencia son:
`exact`, `normalized`, `derived_by_approved_rule`, `conflict`, `missing`,
`manual_approval_required`, `manual_approved`; no hay score numérico de confianza.

## Auditoría y revisión humana

Ambigüedad de identidad/alias, correspondencia tipo-categoría, colisión, conflictos, unidad o enum
desconocidos y reglas nuevas requieren decisión trazada. AuditIssue conserva código, etapa, sujeto,
severidad, bloqueo, mensaje, evidencia, acción, resolución y decisión. Un error inesperado nunca
produce readiness. Schemas, mapeos, identidad, reglas comerciales o resolución de conflictos
requieren aprobación humana antes de paquete `approved`.

## Alcance

Prompt 267 no obtiene datos, no implementa EP/GAM/LGMG, no descarga medios, no llama APIs, no
planifica ni muta JEM Nexus. El binding futuro distingue `external` y `produced`; lo demás pertenece
a prompts posteriores.
