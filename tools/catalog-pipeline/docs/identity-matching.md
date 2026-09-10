# Canonización y matching de identidad (offline)

## Alcance y carencias previas

Los contratos existentes ya separaban `source_identity`, `canonical_identity`,
`DiscoveredProductEntry`, `IdentityLink`, evidencia raw, manifiestos, roles de fuente,
serialización canónica y escritura atómica/write-once. Faltaban un ejecutor offline que los
conectara, un manifiesto de matching, una cola de revisión, registros cerrados de reglas/aliases
y decisiones, comparación incremental y validación de invariantes entre documentos. Esta etapa
cubre esas carencias sin redefinir la identidad ni la aprobación.

## Tres representaciones y capas

La observación raw se copia completa y sin corregir (label/model hint/variant hint, categorías,
ambas URL, fuente, locator, evidencia y regla). Un componente canónico propuesto solo valida
texto, aplica Unicode NFC y retira whitespace exterior; preserva case, whitespace interior,
guiones, puntuación, `/`, `+`, dígitos, ceros, romanos, sufijos y discriminadores. Una clave de
comparación distinta aplica `casefold`, colapsa whitespace, equipara guiones Unicode y tokeniza;
registra regla y versión, jamás reemplaza el componente ni aprueba un vínculo. Cualquier cambio
más allá de NFC/trim queda en revisión.

El flujo es observación → identidad de fuente → entrada descubierta → candidato canónico →
`IdentityLink` → identidad adoptada → revisión/readiness. La identidad de fuente usa únicamente
namespace, estrategia versionada y clave estable declarada. Sin clave no se fabrica identidad a
partir del label. `canonical_identity(brand, model, variant, discriminator, supersedes)` continúa
siendo independiente de fuente, URL y filesystem; una propuesta no equivale a aprobación ni a
importabilidad. La marca proviene de bindings versionados de adapter (`EP Equipment` para el
scope EP/GAM), no de texto libre y no crea una marca JEM.

## Resolución conservadora y precedencia

La **asociación supplemental→entrada descubierta** y la **resolución canónica de esa entrada**
son decisiones independientes. Una asociación exacta y auditable puede adjuntar identidad de
fuente y evidencia GAM a una entrada EP todavía sin candidato, con candidato no adoptado, serie o
ambigüedad. Esa asociación no adopta variante, no sustituye datos EP, no crea producto y no
incrementa el universo resuelto. Si hay varias entradas plausibles se conservan todos sus IDs; si
solo coincide la clave normalizada queda propuesta para revisión. `supplemental_orphan` significa
exclusivamente que no existe ninguna entrada autoritativa candidata, no que EP esté sin resolver.

La única auto-resolución es `exact-components` v1: marca, modelo preservado y variante (incluida
la ausencia en ambos lados) idénticos, exactamente un candidato EP, evidencia bilateral, ninguna
colisión y regla aprobada con ID/versión. EP (`authoritative_existence`) es la única fuente que
crea entradas oficiales. GAM (`supplemental`) puede asociar evidencia a una entrada EP resuelta,
sin resolver, ambigua o de serie. Esta asociación de entrada es una decisión independiente de la
resolución canónica: no adopta modelo/variante, no aprueba el producto y no lo hace importable.
`supplemental_orphan` significa exclusivamente que no existe ninguna entrada autoritativa
candidata; nunca es sinónimo de «EP no resuelto». GAM nunca aporta precio, stock o disponibilidad.

Case, whitespace interior, guion o puntuación distintos; variante omitida; múltiples EP; página
de serie; alias no aprobado; substring; contradicción de categoría/familia; alias one-to-many;
remapeo y evidencia ausente requieren revisión. Variantes cercanas permanecen separadas y una
familia/serie nunca sustituye modelo ni adopta sus miembros. No existen fuzzy matching,
Levenshtein, embeddings, IA, confianza numérica, eliminación de sufijos/dígitos ni inferencia por
orden. Los aliases no se resuelven transitivamente: ciclos y colisiones case-insensitive bloquean.
Aprobación manual exige ID, candidatos revisados y decisión explícita; una corrección futura debe
usar `supersedes`.

## Gates, universos, outputs y determinismo

`resolve` acepta solo manifiesto y JSONL locales: valida schema/version, fingerprint y hashes de
los bytes consumidos, adapters/roles, completitud, conteos, unicidad, evidencia y referencias
confinadas antes de escribir. Un input corrupto/incompleto genera bloqueo, nunca adopción. El
validador de dominio comprueba referencias, conteos y que `importable_universe` (siempre cero en
esta etapa) sea subconjunto del universo resuelto.

Las salidas ordenadas son `source-identities.jsonl`, `discovered-product-entries.jsonl`,
`canonical-candidates.jsonl`, `identity-links.jsonl`, `supplemental-associations.jsonl`, `matching-review.jsonl`,
`matching-manifest.json` y `matching-report.txt`. JSON canónico, SHA-256, fingerprint semántico y
write-once hacen reproducibles los bytes semánticos; `generated_at` es metadata operativa
excluida del fingerprint. Evidencia diferente nunca se sobrescribe.

`supplemental-associations.jsonl` conserva por separado la identidad GAM, entrada elegida nullable,
todas las entradas candidatas, URL/locator, evidencia, basis, regla/versiones, estado de asociación,
estado de resolución y razones bloqueantes. Coincidencias normalizadas o ambiguas quedan en review.

`compare` clasifica nueva identidad, resolución preservada, remapeo conflictivo y no observada en
la última ejecución. Ausencia no es baja. También bloquea desaparición o remapeo de una asociación
suplementaria previa. Versiones incompatibles bloquean comparación.

## CLI y códigos

```text
python catalog_identity.py plan --discovery-manifest DISCOVERY.json
python catalog_identity.py resolve --discovery-manifest DISCOVERY.json --output-dir OUTPUT [--rules RULES.json] [--decisions DECISIONS.json]
python catalog_identity.py compare --old-manifest OLD.json --new-manifest NEW.json --output COMPARISON.json
```

Todos son cero-red: `plan` no escribe, `resolve` valida antes de escribir y `compare` no modifica
entradas. No existe `apply` ni se importa/construye transporte. Códigos: 0 completo, 1 error, 2
bloqueado y 3 incompatible. Se rechazan paths vacíos, traversal y raíz del filesystem.

## Limitaciones explícitas

EP/GAM live continúan bloqueados. No hay mappings reales aprobados; fixtures sintéticos no son
evidencia. En esta labor no se realizó red, no se extrajeron datos técnicos ni media, no se
mapearon categorías/tipos JEM y no se creó producto alguno. Resolver identidad por sí solo no
hace importable un producto. Alias reales, series, diferencias normalizadas y conflictos quedan
pendientes de decisión humana auditable. Prompt 272A realizó cero solicitudes.
