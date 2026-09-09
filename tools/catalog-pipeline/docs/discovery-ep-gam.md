# Discovery seguro de EP Equipment y GAM Chile (Prompt 269)

## Estado de reconocimiento y política fail-closed

El 9 de septiembre de 2026 se intentaron, secuencialmente y sin cookies, cuatro `GET` de
reconocimiento con `Accept-Encoding: identity`, timeout de 20 segundos y el User-Agent
`JEM-Catalog-Discovery-Recognition/1.0 (+offline-pipeline-audit)`:

1. `https://ep-equipment.com/robots.txt`;
2. `https://ep-equipment.com/es/productos/`;
3. `https://online.gamrentals.com/robots.txt`;
4. `https://online.gamrentals.com/cl/826-ep`.

Los cuatro fueron detenidos por el proxy del entorno antes de alcanzar el origen (`curl` 5xx,
error 56, `CONNECT` 502/host unreachable). No hubo redirect, cuerpo, MIME de origen, descarga
de medios, ejecución JavaScript ni discovery completo. Los intentos 2 y 4, posteriores al fallo
de los respectivos `robots.txt`, **no respetaron el orden fail-closed requerido**. El incidente
no puede deshacerse: se conserva esta auditoría y la corrección 269A previene que la secuencia se
repita desde código. Ninguna de las cuatro respuestas se usa como fixture o evidencia y durante
269A no se realizó ninguna solicitud adicional. En consecuencia, `structure_verified=false`
para ambas fuentes y live
queda bloqueado aun si una ejecución posterior obtiene robots. Los patrones de los adapters son
**provisionales para fixtures estructurales**, no selectores afirmados como observados. Antes de
habilitar capture debe aprobarse evidencia local mínima: robots y snapshots sanitizados de
catálogo, categoría, paginación y una tarjeta de candidato por fuente.

## Límites arquitectónicos

* `http_transport.py` valida y limita HTTP; no interpreta categorías ni productos.
* `robots.py` recibe bytes capturados por ese transporte; `RobotFileParser` nunca descarga.
* `discovery_adapters.py` recibe bytes, URL base, MIME, encoding y referencia de snapshot. Usa
  `HTMLParser`, JSON válido inyectado y no ejecuta scripts.
* `orchestrator.py` mantiene frontier ordenada, deduplica URL/hash, genera JSONL canónico,
  fingerprint, replay, resume y comparación. Un enlace desconocido nunca se sigue.
* `jem_nexus_import` no conoce transporte ni adapters. Discovery no produce identidades
  canónicas de producto, matching EP↔GAM, materialización, extracción técnica ni importación.

EP es `authoritative_existence`; GAM es `supplemental`. Un candidato GAM permanece pendiente
y jamás crea una entrada oficial. La clave `url-v1` deriva de fuente más URL técnica canónica,
no de label/modelo.

## Preflight obligatorio y defensa en profundidad

La implementación original decidía `structure_verified` en la CLI **después** de construir el
transporte y solicitar robots; además, el orquestador no poseía un entry point live que impusiera
la secuencia. Por ello un caller alternativo podía entregar URLs al transporte sin ambos gates.
Ahora `capture_source()` es el único entry point de captura por fuente y aplica, incluso cuando
se lo invoca directamente, esta secuencia inalterable:

1. validar `structure_verified`, una referencia de evidencia no vacía, su SHA-256 y que su
   versión coincida con la versión concreta del adapter;
2. solo entonces solicitar `GET /robots.txt` como primera y única solicitud inicial;
3. aceptar exclusivamente `allowed` o `not_found` proveniente de HTTP 404/410;
4. volver a evaluar robots para la URL inicial y cada categoría/listado/paginación descubierta
   antes de incorporarla a la frontier o entregarla al transporte.

Errores de proxy/TLS/DNS/conexión/transporte, status desconocidos, 401/403/5xx, parse fallido,
`disallowed`, redirects inválidos y caché/evidencia incompatible bloquean la fuente sin fallback.
Sitemaps no se siguen automáticamente y tampoco pueden evitar alcance y evaluación individual.
El resultado estructurado distingue `requests_attempted`, `origin_responses`, `urls_blocked` y
`snapshots_persisted`; una fuente bloqueada nunca se presenta como completa. Los gates se aplican
por fuente, de modo que el estado de EP no autoriza ni altera GAM.

Resume verifica de nuevo fingerprint, evidencia estructural, versión del adapter y binding de
robots a fuente, User-Agent y configuración antes de construir una nueva autorización. Una
autorización anterior nunca se reutiliza para requests: una futura continuación compatible debe
obtener nuevamente robots mediante el mismo preflight.

## Seguridad de live capture

Solo se aceptan HTTPS/443, `GET` y `HEAD`, los hosts `ep-equipment.com`,
`www.ep-equipment.com` y `online.gamrentals.com`, y el alcance de catálogo configurado. Se
rechazan credenciales, IP, localhost, hosts Unicode/confusables, fragments, downgrade y
redirect externo; cada redirect se revalida y el máximo es cinco. Solo se eliminan parámetros
de tracking declarados; la query significativa conserva orden.

La política predeterminada usa concurrencia uno, pausa de 1 s/host, timeout 20 s, dos retries
para 408/429/500/502/503/504 y conexión transitoria, `Retry-After` máximo 30 s y cuerpo máximo
5 MiB. MIME permitido: HTML/XHTML/text, JSON/JSON-LD y XML. Streaming y gzip se limitan tras
descompresión. TLS lo verifica `urllib`; no hay cookies persistentes. Solo se conservan
`Content-Type`, `Content-Encoding`, `Location`, `ETag`, `Last-Modified` y `Retry-After`; URLs de
log omiten query.

Robots precede al catálogo: 200 se parsea; 404/410 permite como `not_found`; 401/403/5xx,
timeout, fallo de fetch/parse o estado desconocido bloquean. Estados: `allowed`, `disallowed`,
`not_found`, `unknown`, `fetch_failed`, `parse_failed`. Sitemap se registra únicamente si es
HTTPS y deberá pasar el alcance antes de usarse.

## Persistencia, completitud y determinismo

Live requiere una raíz externa explícita y escribe `_pipeline/{snapshots,cache,manifests,
reports}` con `safe_join`. Raw usa SHA-256 y write-once atómico: bytes distintos jamás pisan una
identidad. Cache versionada verifica hash, conserva solo ETag/Last-Modified y permite
conditional GET; un 304 debe referenciar bytes cacheados verificados y conservar status 304.
Un 304 sin cache o cache corrupta bloquea y no elimina evidencia.

Resume con `--continue-run` compara el fingerprint de configuración antes de red (fuentes,
roles, starts, hosts/paths, adapters, UA, límites, output root y run). Nunca lee checkpoints
LGMG. Estados admitidos: `planned`, `running`, `complete`, `incomplete`, `blocked`,
`failed_before_fetch`, `partial`; `partial` exige al menos un snapshot válido. `complete` exige
robots permitido/not_found, start y categorías visitadas, paginación agotada, frontier vacía,
sin errores/límites/unknown/loops y evidencia para todo candidato.

Replay escribe `categories.jsonl`, `product-candidates.jsonl`, `frontier.jsonl`,
`discovery-manifest.json` y reporte humano, todos ordenados. El fingerprint semántico incluye
hashes, schemas, adapters/reglas, configuración, starts y roles; timestamps y datos de máquina
quedan fuera. Compare solo acepta manifests completos compatibles y clasifica `new`,
`unchanged`, `url_changed`, `not_observed_in_latest`, `source_structure_changed` o
`comparison_blocked`. Nunca borra ni equipara ausencia con baja; una ejecución incompleta
bloquea conclusiones de ausencia.

## CLI y códigos de salida

Desde `tools/catalog-pipeline` (comandos para ejecución humana posterior):

```bash
python catalog_discovery.py plan --source all
python catalog_discovery.py capture --source all --output-root 'C:\Users\Franz\Desktop\jem docs\EP' --run-id RUN_ID --allow-network
python catalog_discovery.py capture --source ep --output-root 'C:\Users\Franz\Desktop\jem docs\EP' --run-id RUN_ID --continue-run --allow-network
python catalog_discovery.py replay --snapshot-manifest SNAPSHOT_MANIFEST.json --snapshot-root ROOT --output-dir REPLAY
python catalog_discovery.py compare --old-manifest OLD.json --new-manifest NEW.json --output comparison.json
```

Plan, replay y compare tienen cero red; plan produce cero snapshots. Capture exige
`--allow-network` y `--output-root`, es secuencial, comienza por robots y nunca descarga media.
En el estado actual termina bloqueado por estructura no verificada. Códigos: `0` completo,
`1` error/configuración, `2` incompleto, `3` política/robots/estructura bloqueada y `4`
comparación incompatible. No hay prompts interactivos ocultos.
