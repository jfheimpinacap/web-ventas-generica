# Schemas v1 y validador local

## Inventario

Hay catorce schemas Draft 2020-12, versión `1.0.0`: `common-definitions`, `run-manifest`,
`raw-evidence`, `canonical-product`, `normalized-product`, `normalized-value`, `audit-issue`,
`human-decision`, `physical-mapping`, `package-manifest`, `jem-projection`, `binding-contract` e
`identity-link` y `discovered-product-entry`. Estos expresan el vínculo auditable y el hallazgo que
puede sobrevivir sin identidad canónica. El contrato
`jem-nexus-contract.json` es un inventario de inspección, no un schema de instancia.

Cada schema tiene un fixture positivo. Casos negativos pasan por el mismo validador runtime para
requeridos ausentes, tipos incorrectos, versión/enum desconocidos, extras y restricciones.

## Subconjunto runtime, no implementación completa

Los documentos declaran Draft 2020-12 con `$schema`, pero el validador de biblioteca estándar
implementa deliberadamente solo un subconjunto. El inventario real de v1 es:

- Anotación/no validación: `$schema`, `$id`, `$defs`, `title`, `description` y el miembro documental
  `schema_version`. `$id` nunca se usa para obtener recursos y `$schema` nunca dispara red.
- Validación presentes e implementadas: `$ref`, `type`, `properties`, `required`,
  `additionalProperties` (booleano o schema), `enum`, `const`, `items`, `minItems`, `uniqueItems`,
  `minLength`, `minimum`, `pattern` y `format` (`date-time` únicamente).
- El runtime también implementa `maxLength` y `maximum`, aunque ningún schema v1 actual las usa;
  permanecen en la lista explícita soportada.
- No utilizadas ni soportadas: `oneOf`, `anyOf`, `allOf`, `if`, `then`, `else`. Cualquier keyword
  ajena a ambos conjuntos falla con `SCHEMA_INVALID`; así un cambio futuro no queda ignorado.

`validate_schema_keywords` audita cada schema y los documentos referenciados. Esto no pretende
conformidad general con JSON Schema Draft 2020-12.

## `$ref` exclusivamente local

Solo se aceptan paths relativos cuyo archivo permanezca directamente en `schemas/v1` y fragments
JSON Pointer locales. Se rechazan referencia inexistente, fragment inexistente, ciclo, traversal,
path absoluto y cualquier URI con esquema (`http:`, `https:`, `file:`, etc.). La resolución no usa
`$id`, resolutores, red o librerías HTTP.

Los errores exponen código estable `SCHEMA_INVALID`, nombre de schema, ruta de instancia, keyword y
mensaje. Una instancia inválida no puede convertirse en artefacto aprobado.

## Universos

`package-manifest` separa `raw_observation_count`, `source_identity_count`,
`discovered_entry_count`, `canonical_candidate_count`, `resolved_canonical_product_count`,
`blocked_discovered_entry_count` e `importable_canonical_product_count`.
`discovered_universe` y `blocked` usan IDs de entrada descubierta; candidatos y productos adoptados
poseen colecciones distintas; `importable_universe` usa identidades canónicas adoptadas. Así dos
fuentes no duplican el producto y una fuente complementaria no crea un hallazgo oficial por sí sola.

JSON Schema valida forma, cierres y tipos, pero no igualdad aritmética entre contadores y tamaños de
colecciones ni todas las reglas de subconjunto. Esa consistencia transversal queda explícitamente
reservada para un validador de dominio posterior; el schema por sí solo no la garantiza.
