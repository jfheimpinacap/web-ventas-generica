# Normalización determinista y matriz EP → JEM Nexus — v1

## Límite y artefactos

La etapa consume exclusivamente artefactos locales versionados de identidad, productos/variantes,
observaciones raw, evidencia suplementaria, relaciones y decisiones de assets. Cada referencia
declara tipo, schema, path relativo, SHA-256, tamaño, fingerprint productor, versión de policy y
scope. No vuelve a interpretar HTML, PDF ni imágenes. `raw` es la captura inmutable; `canonical`
resuelve identidad; `normalized` aplica reglas; `audit` decidirá si el resultado es aceptable; el
`package` canónico y cualquier importación pertenecen al prompt siguiente.

`plan` valida gates y calcula bytes/fingerprint sin escribir outputs definitivos. `normalize` exige
ese fingerprint, escribe en staging hermano, relee bytes y hace rename atómico; un árbol idéntico es
idempotente y uno incompleto, alterado o con extras bloquea. `verify` recalcula hashes/tamaños,
referencias e inventario, rechaza symlinks y escapes, y nunca repara ni normaliza.

## Reglas, decimal y procedencia

Las reglas declarativas tienen `rule_id`/versión. El parsing utiliza `Decimal`, locale y separadores
declarados, unidad explícita, conversión exacta, escala y redondeo configurado. Un decimal ambiguo,
rango, límite, múltiple valor o configuración no se colapsa. Vacío, guiones, N/A, “no aplica”,
“opcional”, “según configuración” y “a consultar” jamás son cero. Unidad ausente o desconocida se
preserva y revisa; no se infiere por magnitud.

Cada conclusión conserva raw value/unit, source field/label, modelo/variante, source y URL solo como
metadata, documento/página/sección, extraction rule, evidence/relation refs, locale, qualifiers,
regla, policy fingerprint, estado cerrado, conflict group y reviews. Coincidencias deduplican la
conclusión conservando toda evidencia. EP establece existencia y prevalencia técnica; GAM solo
complementa ausencias permitidas y jamás autoriza stock/precio. Diferencias EP↔GAM y HTML↔PDF EP
son conflictos visibles; una precedencia oficial exige aprobación comparable explícita.

## Proyección JEM y ProductSpec

La allowlist deriva del backend inspeccionado: `WorkingHeightM`, `MaximumLoadCapacityKg`,
`MachineWeightKg`, `PowerSource`, `TerrainType`, `Year` y `HoursMeter`. Solo source keys, magnitudes,
contextos, variantes y aliases aprobados enrutan. **Lift/fork/mast height nunca es
`WorkingHeightM`**: queda en `ProductSpec` y puede proponer `MaximumLiftHeightMm`. Capacidad de
batería/remolque/eje no es carga nominal; peso de batería/accesorio/mástil no es peso de máquina.
Voltaje no implica energía; los únicos valores actuales son `diesel`, `electric_24v` y
`electric_lithium`. Terreno no se deduce de neumáticos, tracción, fotos o marketing. Year no sale
del snapshot/PDF/copyright y HoursMeter no recibe cero por ser catálogo nuevo.

Lo no representable es candidato `ProductSpec` compatible con key/value/unit/order, manteniendo
qualifiers, variantes, condiciones, evidencias y conflictos. Las propuestas separadas
`MaximumLiftHeightMm`, `BatteryVoltageV`, `BatteryCapacityAh` y `BatteryChemistry` no cambian el
backend: agregan cobertura y exigen aprobación.

## Categorías, decisiones y readiness

La matriz versionada usa claves/path durables, nunca IDs DB ni similitud. Solo un target presente en
el catálogo JEM local y una primaria explícita aprobada resuelve la categoría. `proposed`, múltiples
primarias, target ausente o aprobación fixture bloquean. Baterías, EP Energy, aeropuerto y elementos
fuera de Maquinarias permanecen descubiertos pero no importables hasta decisión humana. Las
aprobaciones de assets no se reutilizan semánticamente; no existe comando `approve`.

Readiness deriva estados `normalized_ready_for_audit`, `manual_review_required`,
`category_mapping_required`, `schema_gap_review_required`, `upstream_blocked`, `identity_blocked`,
`conflict_blocked` y `unsupported_for_import`; nunca declara ready-for-import. Falta de imagen/ficha
no borra el producto, aunque policy puede crear review.

Cada `producto.json` es **solo proyección normalizada para auditoría**, referencia assets ya
seleccionados y conserva fingerprints/reviews/gaps. No contiene bytes, paths absolutos ni texto
promocional. Precio y proveedor no se inventan; `price=null`, `is_published=false`,
`price_visible=false`, `is_featured=false`, mientras condition/stock/supplier quedan pendientes.

Todo es UTF-8/NFC/LF, ordenado, sin reloj en fingerprint, red, API, credenciales, descarga,
importación ni publicación. EP/GAM live continúan fail-closed. El siguiente paso es auditoría
integral, decisiones humanas y construcción de un paquete canónico aprobado para un importador
separado.
