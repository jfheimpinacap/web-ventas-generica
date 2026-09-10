# Adquisición autorizada y reanudable (Prompt 278)

Esta etapa **solo adquiere bytes**. No valida contenedores, selecciona principales, materializa
productos ni publica en JEM Nexus. Una descarga `completed` queda `validation_pending` y se entrega
mediante el `payload-manifest` v1 al validador binario existente. Selección y materialización quedan
pendientes para el Prompt 279.

## Capas y orden fail-closed

`acquisition_plan.py` no tiene red y aplica, en orden: manifests y fingerprints; definición y
versión de fuente; `structure_verified` y evidencia estructural; evidencia de derechos; conjunto y
tipo de candidate; scope; y host/path/puerto/query. La autorización es una decisión humana externa:
Codex no aprueba derechos. Vincula identidad y fingerprint propios, política, fuente/adaptador,
manifests, conjunto exacto, ambas evidencias confinadas y hasheadas, User-Agent, solo GET/HTTPS,
scopes exactos, tipos, límites, queries y `fixture_only`. Una autorización fixture nunca abre el
transporte de la CLI. EP y GAM conservan `structure_verified=false`; por ello `plan`, `acquire` y
`resume` quedan bloqueados antes de construir transporte y producen cero requests.

`asset_http_transport.py` es el transporte separado de assets. Usa solo biblioteca estándar, TLS
del sistema, GET, `Accept-Encoding: identity`, timeout, lectura/chunks/headers acotados, sin redirects
automáticos, cookies, autenticación ni proxies ambientales. Nunca envía Authorization, Cookie o
Proxy-Authorization. Solo devuelve Content-Type, Content-Length, Content-Range, ETag, Last-Modified,
Location, Accept-Ranges y Content-Encoding; `Set-Cookie` y demás headers no se conservan.

`acquisition.py` es el único orquestador. Por cada host hace `robots.txt` y después el asset; solo
`allowed` o un 404/410 real autorizan. Robots se obtiene de nuevo en cada ejecución/resume. Cada hop
301/302/303/307/308 valida Location, HTTPS, host, path, puerto y query antes del destino; un host
nuevo exige autorización explícita y robots nuevo. Detecta loops y limita hops. No reenvía Range a
otro host.

Las URL rechazan userinfo, fragments, IP literals, localhost/nombres locales, backslashes, traversal
literal o codificado y escapes ambiguos. Los paths han de ser exactos o descendientes de un prefijo.
La query está cerrada por defecto; solo admite nombres enumerados y rechaza nombres con apariencia
de token, firma, API key, credencial, sesión o contraseña. Los receipts saneanan valores de query.

## Límites, checkpoint y resume

Se aplican conjuntamente máximos de requests, assets, bytes por asset y totales, robots, headers,
chunk, timeout y redirects, con ejecución secuencial y pausa por host inyectable. Content-Length
excesivo bloquea; streaming excesivo se corta; Content-Encoding no identity se rechaza.

Los `.part` y checkpoints pertenecen a la herramienta bajo `_operations`, usan rutas POSIX
confinadas y publicación atómica. El checkpoint vincula candidate/relation, autorización e inputs,
URL y redirects, host, parcial, tamaño/hash, total, ETag fuerte, Last-Modified, MIME, estado,
siguiente acción, contador y timestamps operativos. Resume recalcula tamaño/hash y repite todos los
gates y robots. Append requiere ETag fuerte idéntico, `206`, Content-Range empezando exactamente en
el tamaño local, total coherente e identity. Sin ETag se reinicia en otro temporal; un `200` tras
Range también se trata como descarga completa limpia; 416, ETag o range incoherentes nunca anexan.

Al finalizar se sincroniza el temporal, calcula SHA-256, comprueba tamaño y publica atómicamente.
Se escriben `acquisition-receipts.jsonl`, `payload-manifest.json`,
`acquisition-reviews.jsonl`, `acquisition-manifest.json` y `acquisition-report.txt`. Receipts guardan
secuencia, robots, redirects, status, headers permitidos, conteos, hashes y bindings, nunca bodies,
cookies, secretos ni paths absolutos. Los timestamps quedan fuera del fingerprint semántico.

La CLI separada ofrece `plan`, `acquire`, `resume` y `verify`; no crea ni aprueba autorizaciones y no
tiene bypass. `verify` es offline y solo detecta alteraciones. Durante Prompt 278 no se ejecutó red,
Python, la CLI ni tests; todos los escenarios exitosos escritos usan dominios `.test`, evidencia
sintética y transporte falso.
