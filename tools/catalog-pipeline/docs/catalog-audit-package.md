# Auditoría integral y paquete canónico

Esta etapa es **offline** y cerrada. Consume únicamente referencias locales
allowlisted con tipo, versión, ruta relativa, SHA-256, tamaño, productor,
fingerprint de productor, policy, scope e identidad. Valida los bytes y la cadena
de fingerprints; no recorre directorios para descubrir contenido. Symlinks,
referencias huérfanas, otro run, colisiones Windows y policies incompatibles
bloquean el input.

## Auditar no es aprobar

La auditoría no normaliza otra vez, no completa supplier/condition/stock/precio,
no escribe texto comercial y no resuelve reviews. Los findings tienen ID derivado
del contenido, regla/version, scope, sujeto, severidad cerrada (`error`,
`blocking_review`, `warning`, `info`), bloqueo, message code y parámetros,
evidencia, fingerprints, approval y resolución cerrada. Solo una aprobación que
coincida exactamente en decisión, scope, sujeto, identidad, evidencia, valor,
policy e input puede resolver el finding; una aprobación sintética jamás resuelve
un live.

Se auditan identidad, asociación de observaciones, mapping por clave no numérica,
target contractual y una primary física, contrato de campos/enum/longitud,
ProductSpec y conflictos, `producto.json` con
`normalized_for_audit_not_api_payload`, defaults comerciales seguros, schema gaps
clasificados por policy y assets ya validados/seleccionados/materializados. Un CDN
no otorga autoridad. GAM requiere su aprobación exacta y nunca se promueve a
primary por host. No se descarga ni selecciona nuevamente.

Los universos permanecen separados: `discovered_universe`, `audited_universe`,
`package_eligible_universe`, `package_excluded_universe` y `package_blocked_universe`. El catálogo maestro
conserva todo producto auditable, incluso bloqueado, ordenado por identidad; la
vista importable es una allowlist explícita. Cuando el input es estructuralmente
válido se exige `audited = eligible + excluded + blocked`. `include` exige todos los
gates satisfechos; `exclude` exige una decisión explícita, versionada, vigente y con
evidencia; cualquier incertidumbre pendiente produce `blocked`, nunca una exclusión
implícita. Readiness de producto distingue
identidad, review, categoría, comerciales, schema, assets y elegibilidad; readiness
de catálogo nunca usa estados de importación, publicación o producción.

## Audit, plan, build y verify

`catalog_package.py` expone exclusivamente:

* `audit`: valida inputs y produce findings JSONL, auditorías por producto,
  decisiones, catálogo maestro, vistas eligible/excluded/blocked, manifest y reporte
  humano. El reporte no sustituye los artefactos estructurados.
* `plan`: consume un audit fingerprint exacto y enumera cada producto, mapping,
  provenance, schema y asset por source reference, hash, tamaño, rol, MIME,
  identidad y evidencia. No usa glob. Un plan vacío o bloqueado se conserva pero
  no puede ejecutarse.
* `build`: exige el plan fingerprint y gates satisfechos. Escribe un temporal
  hermano propio, crea el ZIP, lo reabre/verifica y solo entonces hace rename
  atómico. Un destino igual es `already_complete`; uno distinto nunca se borra ni
  sobrescribe.
* `verify`: inspecciona y hashea por streaming, sin extraer, reparar, completar ni
  consultar fuentes. Verifica receipt, CRC (al leer), manifest, fingerprints,
  orden, lista exacta, metadata, hashes, tamaños y límites.

Los exit codes son 0 éxito, 2 input/configuración inválido, 3 auditoría/plan con
bloqueos, 4 fingerprint incompatible y 5 paquete inseguro o alterado. La CLI no
acepta credenciales, URL, approval ni bypass.

## Formato reproducible y seguridad

La raíz lógica contiene `package-manifest.json`, `catalog/`, `mappings/`,
`provenance/`, `catalogo/<categoría>/<modelo>/` y `schemas/`. Cada incluido tiene
exactamente un `producto.json`; los assets conservan los bytes materializados. No
se incluyen raw snapshots, cache, logs, temporales, headers, datos personales,
secretos, `.git` ni assets no seleccionados.

Las entradas están ordenadas, usan `/`, UTF-8/LF, `ZIP_STORED`, fecha fija
1980-01-01, permisos regulares 0644, creator Unix y sin comment/extra fields. El
`content_fingerprint` cubre los descriptors ordenados, policy y audit; el manifest
no se incluye a sí mismo. El SHA-256 del ZIP está únicamente en el receipt externo,
que declara explícitamente que no autoriza importación.

Builder y verifier rechazan traversal, rutas absolutas/drive/UNC/backslash,
controles, segmentos ambiguos, nombres Windows reservados, duplicados y colisiones
case-insensitive, symlink/hardlink/device, cifrado, compresión no permitida,
comments, extras, límites de entradas/tamaños/total/ratio y ZIP anidado según
policy. Nunca usan una herramienta ZIP externa ni el reloj real.

EP/GAM live continúan bloqueados sin `structure_verified=true` legítimo, mappings
y assets aprobados, comerciales obligatorios, conflictos y gaps resueltos y
fingerprints compatibles. Los fixtures son sintéticos y `fixture_only=true`.
Un paquete verificado **no** es payload API, importación ni autorización. El paso
siguiente recomendado es un importador genérico separado que consuma solo este
paquete verificado, resuelva bindings y produzca primero un dry-run local.

Un catálogo con al menos una decisión `blocked` genera auditoría y un plan bloqueado,
pero nunca un ZIP. Una exclusión explícita válida no bloquea por sí sola el build.
El package plan registra `blocked_product_count`; todo manifest de un ZIP construido
declara obligatoriamente `blocked_product_count=0`, y el verifier rechaza otra cifra.
