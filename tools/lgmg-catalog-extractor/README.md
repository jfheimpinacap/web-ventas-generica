# Descubrimiento y extractor seguro del catálogo público LGMG

Herramienta local e independiente en Python 3 (solo biblioteca estándar). No forma parte del frontend ni del backend, no importa productos, no llama JEM Nexus y no publica contenido. Produce metadatos para revisión humana; la disponibilidad pública de una imagen o documento **no autoriza su reutilización comercial**.

## Modos de descubrimiento

`--discovery-mode static` conserva el comportamiento anterior: `--start-url` acepta únicamente fichas del contenedor estructural `section.channel_content.pro_list`, y `--seed-file` procesa URLs previamente revisadas. El HTML inicial puede contener el contenedor vacío porque el sitio carga el catálogo mediante JavaScript; en ese caso el modo estático termina con código 2 y recomienda el modo dinámico o un seed.

`--discovery-mode dynamic` se limita al listado exacto `/es/product/pro-list-377.htm`. Detecta el único `script#seajsConfig` oficial, valida sus atributos `src` y `domain`, y detecta únicamente `seajs.use('js/pro_list')`; después obtiene la configuración SeaJS exacta del mismo host, interpreta solo literales estáticos de `base`, `paths` y `alias`, resuelve un único módulo bajo `/es/resources/` y lo analiza como texto. `seajs.root` se sustituye exclusivamente por el dominio oficial validado desde ese HTML. **Nunca ejecuta JavaScript.** El listado se selecciona estructuralmente por `flag: "pro"` en la llamada `$.post` con endpoint exacto `https://www.lgmglifts.com/es/ext/ajax_proList.jsp`; la operación `flag: "param"` que obtiene filtros queda excluida y no se consulta.

La solicitud inicial usa POST `application/x-www-form-urlencoded` y el conjunto cerrado `flag`, `min1`, `max1`, `min2`, `max2`, `min3`, `max3`, `min4`, `max4`, `catId`, `key`, `nowPage` y `gmzhi`. Los filtros y `key` se envían vacíos, `gmzhi=1`, `catId` recibe la familia actual y `nowPage` la página actual; no se envía tamaño de página. El callback se comprueba únicamente como estructura balanceada y nunca se ejecuta.

`--discovery-only` resuelve y enumera URLs y escribe los reportes, pero no visita fichas ni extrae productos y no admite descargas. Es obligatoriamente la primera ejecución real recomendada. `--max-products` es un límite estricto de URLs canónicas únicas aceptadas: las repeticiones no consumen cupo y, si una página contiene más resultados de los necesarios, el sobrante se descarta antes de construir los reportes. `--inventory-all` habilita valores solicitados de hasta 250 fichas solo junto con descubrimiento dinámico, pero no elimina ni relaja el valor indicado en `--max-products`; no se activa por defecto. Sin ese flag se conserva el máximo normal de 25. El máximo duro es 50 páginas y 250 fichas únicas.

## Fallo seguro, familias y paginación

La resolución rechaza host distinto, HTTP, credenciales, puerto alternativo, query inesperada, fragmento, traversal, HTML disfrazado de JavaScript, varios endpoints, método incierto, parámetros no literales/no controlados, autenticación, tokens, CSRF, cookies, WebSocket y JSONP. Una inspección incompleta, incluidos los errores HTTP o de red de recursos dinámicos controlados, produce diagnóstico, estado `dynamic_inspection_required` y código 3 antes de consultar un endpoint candidato.

Las familias se leen exclusivamente de `.type_box .box[data-id]` dentro de `section.channel_content.pro_list`, sin allowlist rígido; así se excluyen los controles Métrico/Imperial y se conservan ID, nombre, origen, orden, método, conteos, páginas, estado y advertencias. La respuesta oficial es HTML (también se admite `text/plain` cuando corresponda). Los enlaces deben cumplir exactamente `/es/product/pro-detail-*.htm`; se eliminan query/hash, se excluye navegación global, se conserva orden y familia, y se deduplica entre páginas y familias.

La paginación usa exclusivamente los parámetros observados en el módulo y se detiene de manera determinista ante página vacía, página o respuesta repetida, ausencia de URLs nuevas, 50 páginas, límite de fichas o errores. Se mantienen HTTPS, host exacto, robots.txt, timeout, reintentos limitados, retraso mínimo de 1 segundo, tres redirects, límites independientes de tamaño y caché SHA-256.

## Clasificación eléctrica y revisión

La clasificación es ternaria y *fail-closed*: `true` exige evidencia eléctrica positiva suficiente, `false` exige evidencia inequívoca de combustión y `null` representa evidencia ausente, débil o conflictiva. Una especificación de batería se considera positiva si contiene términos explícitos (eléctrico/electric, batería/battery, litio/lithium o plomo-ácido/lead-acid), o si combina voltaje en V y capacidad en Ah dentro de la misma especificación. Un voltaje aislado, o potencia en kW/hp sin contexto, no basta. En una fuente de potencia, diesel/diésel, gasolina/petrol, combustible/combustión y los fabricantes de motor confirmados Kubota y Deutz constituyen evidencia de combustión.

La fuente de potencia es solo una ubicación donde buscar evidencia; su mera presencia no confirma electricidad. Si coexisten señales eléctricas y de combustión, ninguna invalida silenciosamente a la otra: el resultado queda `null`, conserva ambos lados en `electric_evidence` y recibe una advertencia de conflicto. Los casos sin evidencia suficiente también quedan pendientes. La familia, una traducción sugerente y cualquier sufijo o letra del modelo (`E`, `D`, `J` o `JE`) son únicamente procedencia/nomenclatura y nunca deciden la clasificación.

Con `--electric-only`, solo los `true` quedan en `catalog.json` y `catalog.csv` y cuentan como procesados/confirmados; los `false` se omiten y cuentan como no eléctricos y omitidos; los `null` se excluyen del catálogo, cuentan como inciertos y permanecen en `review.csv` con `needs_review=true`. Esta heurística conservadora no es una certificación técnica del fabricante. Todos los resultados deben revisarse antes de importar o publicar; no se inventan equivalencias métricas/imperiales.

Antes de cualquier carga manual, el usuario debe revisar modelos, pares métrico/imperial, familias, especificaciones, clasificación y derechos. Los borradores conservan `published=false`, `featured=false`, `show_price=false` y `price=null`; no deben importarse directamente.

## Salidas

El directorio validado contiene:

- `discovery.json`: mecanismo, módulo, endpoint, parámetros, familias, páginas, enlaces rechazados, estado y motivo de detención;
- `discovery.csv`: una fila por hallazgo con orden, familia, página, procedencia, duplicado y rechazo;
- `families.csv`: familias, conteos, páginas, estado y advertencias;
- `catalog.json`, `catalog.csv`, `review.csv`, `errors.json` y `manifest.json`;
- `cache/` e `images/` (esta última puede permanecer vacía).

Las escrituras son atómicas y confinadas al output. El manifest 1.2.5 registra descubrimiento, clasificación y contadores; `jem_nexus_called=false` y `content_published=false` siempre. Las imágenes no se descargan por defecto. `--download-images` y `--download-datasheets` continúan separados del descubrimiento y requieren `--confirm-image-rights`; las fichas técnicas permanecen solo como metadatos.

## Códigos de salida

- `0`: operación solicitada completada;
- `1`: argumentos, seguridad, escritura o procesamiento general (Argparse);
- `2`: listado dinámico detectado pero no solicitado, o seed requerido en modo estático;
- `3`: inspección dinámica incompleta o ambigua; el diagnóstico se conserva y no se consulta un endpoint inseguro.

## Windows 11: validación posterior por etapas

No ejecute inventario antes de revisar el descubrimiento.

### 1. Pruebas sintéticas

```powershell
Set-Location "C:\Users\Franz\Desktop\web-ventas-generica"
py -3 -m unittest discover ".\tools\lgmg-catalog-extractor\tests" -v
```

### 2. Solo descubrimiento y ZIP diagnóstico

```powershell
Set-Location "C:\Users\Franz\Desktop\web-ventas-generica"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$OutputPath = "C:\Users\Franz\Desktop\JEM-Nexus-LGMG-Discovery-$Stamp"

py -3 ".\tools\lgmg-catalog-extractor\extract_lgmg.py" `
  --start-url "https://www.lgmglifts.com/es/product/pro-list-377.htm" `
  --discovery-mode dynamic `
  --discovery-only `
  --output-dir $OutputPath `
  --max-products 25
$ExitCode = $LASTEXITCODE
Compress-Archive -LiteralPath $OutputPath -DestinationPath "$OutputPath.zip"
Write-Host "Código: $ExitCode; diagnóstico: $OutputPath.zip"
```

Si `manifest.json` indica `dynamic_listing` y contiene fichas válidas, revise los reportes. Si indica `dynamic_inspection_required` o devuelve 3, conserve el ZIP y no adivine el endpoint ni active inventario.

### 3. Inventario completo (solo tras aprobación manual)

```powershell
Set-Location "C:\Users\Franz\Desktop\web-ventas-generica"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$OutputPath = "C:\Users\Franz\Desktop\JEM-Nexus-LGMG-Inventory-$Stamp"

py -3 ".\tools\lgmg-catalog-extractor\extract_lgmg.py" `
  --start-url "https://www.lgmglifts.com/es/product/pro-list-377.htm" `
  --discovery-mode dynamic `
  --inventory-all `
  --electric-only `
  --output-dir $OutputPath `
  --max-products 250
Compress-Archive -LiteralPath $OutputPath -DestinationPath "$OutputPath.zip"
```

No se incluyen flags de descarga; tampoco existe ninguna opción de importación, publicación o llamada a JEM Nexus.

## Preparación offline para revisión en JEM Nexus

`prepare_jem_review.py` 1.0.0 transforma una extracción ya validada y ejecutada con
`--electric-only` en un paquete de revisión humana. Es una herramienta separada del
extractor: requiere Python 3, usa solamente la biblioteca estándar y no descubre ni
consulta contenido remoto.

Uso con la carpeta `resultado` (también se admite su carpeta de sesión contenedora):

```powershell
py -3 ".\tools\lgmg-catalog-extractor\prepare_jem_review.py" `
  --input "C:\Users\Franz\Desktop\jem docs\temp\resultado" `
  --output-dir "C:\Users\Franz\Desktop\jem docs\temp\revision-lgmg"
```

Uso con un ZIP de validación:

```powershell
py -3 ".\tools\lgmg-catalog-extractor\prepare_jem_review.py" `
  --input "C:\Users\Franz\Desktop\jem docs\temp\validacion-lgmg.zip" `
  --output-dir "C:\Users\Franz\Desktop\jem docs\temp\revision-lgmg"
```

El ZIP se lee directamente mediante su directorio central, tanto si usa `/` como
si fue creado por `Compress-Archive` con `\`; no se descomprime. Solo se leen los
ocho reportes obligatorios bajo un único `resultado`. Se ignoran `cache/` e
`images/`, se rechazan traversal, rutas absolutas, letras de unidad, duplicados
normalizados, cifrado, symlinks, tipos especiales y tamaños excesivos. La entrada
no se modifica, la salida debe ser nueva o estar vacía y no existe `--force`.

El paquete contiene `review-products.csv`, `review-specifications.csv`,
`review-images.csv`, `review-datasheets.csv`,
`review-missing-datasheets.csv`, `review-categories.csv`,
`review-uncertain.csv`, `jem-review-drafts.json`, `review-summary.json`,
`review-summary.txt`, `review-manifest.json` y `README-review.txt`. Los CSV usan
UTF-8 con BOM y protección contra fórmulas para su revisión en Excel. Una persona
debe completar las selecciones, nombres y categorías aprobados, mapeos/IDs de
categoría y decisiones de medios o fichas; los registros inciertos se revisan por
separado.

La preparación valida contadores, clasificación, procedencia, unicidad y URLs
oficiales antes de escribir. Conserva el orden fuente, modelos métricos e
imperiales, aliases, evidencia y advertencias; no completa datos faltantes. Las
imágenes y PDF permanecen como referencias remotas con derechos pendientes. La
herramienta no usa red, no descarga medios, no llama la API de JEM Nexus, no crea
ni importa productos y no publica contenido. Todos los borradores permanecen
pendientes, bloqueados, sin precio, sin categoría resuelta y no publicables.

## Descarga autorizada de medios para revisión local

`download_jem_review_media.py` 1.0.0 es una herramienta complementaria, separada del extractor y del preparador. Consume directamente una carpeta `review-package`, su carpeta de sesión contenedora o un ZIP con exactamente un `review-package`. El ZIP se lee sin extraerlo y solo se leen los seis archivos necesarios; la entrada nunca se modifica.

Toda ejecución de red exige `--confirm-media-rights`. El indicador registra únicamente la decisión operativa de autorización para descarga local y su fecha UTC; no sustituye la documentación comercial o contractual que JEM Nexus deba conservar. La descarga está limitada al host HTTPS exacto `www.lgmglifts.com`, a imágenes bajo `/es/upload/images/` y a PDF bajo `/es/upload/file/`. No admite credenciales, otros puertos, query, fragmentos, subdominios, downgrade ni redirects externos.

Antes de los medios consulta una sola vez `robots.txt` y falla de forma segura si no puede interpretarlo o prohíbe las rutas. No hay concurrencia. El retraso mínimo es 1 segundo, el timeout predeterminado es 30 segundos y se permiten como máximo cinco redirects y dos reintentos adicionales únicamente para fallos transitorios controlados.

Las imágenes se validan por extensión, MIME y firmas JPEG, PNG o WebP; los PDF por MIME y `%PDF-`. `application/octet-stream` solo se acepta cuando firma y extensión coinciden. Los límites son 20 MiB por imagen, 50 MiB por PDF, 1 GiB de imágenes, 2 GiB de PDF, 3 GiB combinados, 500 URLs de imagen y 200 URLs de PDF. Los bytes se transmiten a `.part`, se hashean con SHA-256 y solo se promueven atómicamente después de validarse; no se recomprimen ni modifican.

Se deduplican primero las URLs y después el contenido por SHA-256. `--resume` exige otra vez la confirmación, el mismo fingerprint y un `media-download-state.json` creado por esta versión; comprueba existencia, tamaño y hash antes de reutilizar un medio. Sin `--resume`, la salida debe ser nueva o estar vacía.

La salida incluye `media/images/`, `media/datasheets/`, `downloaded-images.csv`, `downloaded-datasheets.csv`, `media-files.csv`, `media-failures.csv`, `media-summary.json`, `media-summary.txt`, `media-manifest.json`, `media-download-state.json` y `README-media.txt`. Es un paquete para revisión visual posterior: no llama JEM Nexus, no importa productos, no asocia fichas, no aprueba imágenes principales y no publica contenido.

Ejemplo para la validación posterior, exclusivamente bajo la carpeta temporal controlada indicada:

```powershell
py -3 ".\tools\lgmg-catalog-extractor\download_jem_review_media.py" `
  --input "C:\Users\Franz\Desktop\jem docs\temp\JEM-Nexus-LGMG-Review-Validation-20260828-093227.zip" `
  --output-dir "C:\Users\Franz\Desktop\jem docs\temp\medios-lgmg" `
  --confirm-media-rights
```

Para reanudar esa misma salida parcial, repita el comando y agregue `--resume`.

## Plan offline de importación LGMG

`prepare_jem_import_plan.py` 1.0.0 combina el `review-package` validado con el
`media-package` completo para crear un **plan** auditable. El plan no es el
preflight: este último resolverá IDs y compatibilidad contra la API local en una
etapa posterior. Tampoco es una importación y no aplica, sube ni publica nada.
Solo usa la biblioteca estándar y no tiene opciones de red, autenticación,
`apply` o `publish`.

La entrada de revisión puede ser una carpeta `review-package`, su carpeta de
sesión con exactamente un paquete o un ZIP seguro leído directamente con
`ZipFile`, sin extracción. Los medios deben proporcionarse como carpeta
`media-package` o como su carpeta de sesión; no se admite un ZIP de medios. El
plan conserva rutas relativas, tamaños, MIME, URLs y SHA-256 validados, pero no
copia ni renombra imágenes o PDF.

Las decisiones confirmadas fijan la raíz **Maquinarias**, la marca **LGMG**, la
condición `new`, el stock `on_request`, precio y moneda ausentes, precio oculto,
producto no publicado ni destacado y todos los servicios incluidos en `false`.
Cada fila queda `eligible_for_local_preflight=true` y
`ready_for_import=false`. Se conservan los nombres sugeridos, modelos métricos,
equivalencias imperiales, aliases, números romanos Unicode, evidencia y todas
las especificaciones en orden; no se crean slugs, IDs, SKU, años ni
descripciones sin evidencia inequívoca. La fuente de energía y la capacidad
máxima se derivan exclusivamente de esas especificaciones preservadas. El
mapeo energético es conservador: solo produce `electric_24v` para una única
configuración total de 24 V sin conflicto, y `electric_lithium` cuando la
tecnología de litio consta de forma explícita e inequívoca. Las configuraciones
alternativas quedan pendientes; los voltajes confirmados de 48 V, 72 V, 76,8 V
u 80 V que no sean litio inequívoco también quedan vacíos porque el contrato
actual no dispone de una opción equivalente. En todos esos casos se conserva la
evidencia original y se agrega una advertencia.

La capacidad estructurada es la mayor capacidad de carga o plataforma declarada
de forma segura en kilogramos, incluidas sus variantes con y sin restricciones
o de extensión. Se excluyen capacidades de aceite, tanques, combustible y
baterías. No se convierten libras; una etiqueta conjunta `kg/lbs` solo admite el
único valor métrico ya preservado por la fuente. Si no existe un valor métrico
seguro, el campo queda vacío y requiere revisión. Estas derivaciones no cambian
la naturaleza del paquete: continúa siendo un plan offline que no importa ni
publica productos.

El mapeo cerrado de categorías es:

| Categoría fuente | Subcategoría objetivo |
| --- | --- |
| `Elevadores de Tijera` | `Elevadores tipo tijera eléctricos` |
| `Elevador Eléctrico RT de Tijera` | `Elevadores tipo tijera todoterreno` |
| `Elevadores de Brazo Articulado` | `Elevadores tipo brazo articulado` |
| `Elevadores de Brazo Telescópico` | `Elevadores tipo brazo telescópico` |
| `Elevador Mástil Vertical` | `Elevadores tipo mástil vertical` |
| `Elevador de Tijera Sobre Orugas` | `Elevadores tipo tijera sobre orugas` |
| `Manipuladores Telescópicos` | `Manipuladores telescópicos` |

El preflight debe intentar reutilizar y renombrar `Elevador tipo tijera
electrico` como `Elevadores tipo tijera eléctricos` antes de considerar una
creación. Otra acción manual pide revisar únicamente el producto JLG usado como
ejemplo mediante el panel de vendedor; no selecciona la marca ni otros productos
JLG para eliminación. También debe resolver o crear la marca LGMG, sin inventar
ID, logo o descripción. `AR24JE` y `T38JE` permanecen incluidos con ficha
`missing_at_source`, advertencia no bloqueante y revisión humana. Los nueve
productos de clasificación incierta permanecen excluidos.

Se generan exactamente `import-products.csv`, `import-specifications.csv`,
`import-images.csv`, `import-datasheets.csv`, `import-categories.csv`,
`import-brand.csv`, `import-warnings.csv`, `manual-actions.csv`,
`import-plan.json`, `import-summary.json`, `import-summary.txt`,
`import-manifest.json` y `README-import-plan.txt`. Los CSV usan UTF-8 con BOM,
CRLF y protección contra fórmulas. JSON y CSV preservan Unicode y orden fuente.
El manifest registra hashes, tamaños, fingerprints, conteos derivados y las
garantías de cero efectos externos.

La herramienta rechaza paquetes, fingerprints, hashes, asociaciones, MIME,
conteos y rutas incoherentes; traversal, rutas absolutas o con `\`, letras de
unidad, duplicados normalizados, symlinks, tipos especiales, archivos físicos
ausentes/no declarados y relaciones peligrosas entre entrada y salida. Construye
primero en staging y solo promueve el conjunto completo. No modifica entradas.

Ejemplo PowerShell, exclusivamente bajo la carpeta temporal controlada:

```powershell
py -3 ".\tools\lgmg-catalog-extractor\prepare_jem_import_plan.py" `
  --review-input "C:\Users\Franz\Desktop\jem docs\temp\JEM-Nexus-LGMG-Review-Validation-AAAAMMDD-HHMMSS\review-package" `
  --media-input "C:\Users\Franz\Desktop\jem docs\temp\JEM-Nexus-LGMG-Media-Download-AAAAMMDD-HHMMSS\media-package" `
  --output-dir "C:\Users\Franz\Desktop\jem docs\temp\JEM-Nexus-LGMG-Import-Plan-AAAAMMDD-HHMMSS"
```

## Preflight local de importación LGMG (solo lectura)

`preflight_jem_import.py` contrasta el plan offline aprobado y su `media-package` con el inventario real de una instalación **local** de JEM Nexus. El backend debe estar levantado previamente. La herramienta no inicia sesión: requiere un access token ya existente en `JEM_NEXUS_ACCESS_TOKEN`, no acepta el token en la CLI y no lo persiste. Nunca debe apuntarse a producción.

Solo admite `http://localhost:5000` y `http://127.0.0.1:5000`. Consulta únicamente por `GET`: `/api/health`, `/api/auth/me`, `/api/categories?include_inactive=true`, `/api/brands?include_inactive=true`, `/api/products?include_unpublished=true&ordering=name` y `/api/technical-sheets`. Rechaza redirecciones y cualquier ruta u origen fuera de esa allowlist; no usa login, refresh, logout, endpoints de archivos ni escrituras.

Ejemplo para Windows (PowerShell), usando exclusivamente el área temporal local:

```powershell
$env:JEM_NEXUS_ACCESS_TOKEN = (Get-Content -Raw "C:\Users\Franz\Desktop\jem docs\temp\access-token.txt").Trim()
python "C:\Users\Franz\Desktop\jem docs\temp\preflight_jem_import.py" `
  --plan-input "C:\Users\Franz\Desktop\jem docs\temp\import-plan" `
  --media-input "C:\Users\Franz\Desktop\jem docs\temp\media-package" `
  --api-base-url "http://localhost:5000" `
  --output-dir "C:\Users\Franz\Desktop\jem docs\temp\preflight-report"
```

La salida nueva y vacía recibe `preflight-categories.csv`, `preflight-brand.csv`, `preflight-products.csv`, `preflight-specifications.csv`, `preflight-media.csv`, `preflight-warnings.csv`, `preflight-actions.csv`, `preflight-snapshot.json`, `preflight-summary.json`, `preflight-summary.txt`, `README-preflight.txt` y `preflight-manifest.json`. Se generan mediante staging y promoción final.

El informe valida hashes, tamaños, MIME, firmas, rutas, asociaciones y conteos del plan y los medios; comprueba los límites de productos y especificaciones, el máximo configurado de 5 MiB para imágenes y el máximo de 10 MiB para fichas. Los PDF ausentes de AR24JE y T38JE permanecen `missing_at_source`. Las fichas locales solo se comparan por metadatos y una coincidencia es un `reuse_candidate`, nunca una igualdad de contenido.

La resolución conserva la raíz `Maquinarias`, sus siete categorías y la marca LGMG. Reconoce de forma controlada el alias `Elevador tipo tijera electrico`, detecta duplicados y colisiones por modelo, nombre y slug —incluidos productos sin publicar—, y registra candidatos conservadores para revisar la eliminación manual del producto JLG de ejemplo, sin eliminarlo. También calcula las operaciones futuras y advierte cuando serán necesarios batching, throttling, checkpoints e idempotencia por los límites de escritura y subida.

El snapshot comercial canónico se toma al principio y se repite al final. Un cambio concurrente produce `NO_GO`; la herramienta no lo reconcilia ni atribuye. Los veredictos son: `GO` cuando todo ya está resuelto y no quedan acciones; `CONDITIONAL_GO` cuando solo quedan acciones explícitas o revisiones humanas; y `NO_GO` ante bloqueos, conflictos, incompatibilidades o cambios concurrentes. Los códigos de salida son `0` para `GO`/`CONDITIONAL_GO`, `3` para un preflight completado con `NO_GO` y `2` para errores de entrada, autenticación, red local, formato o escritura.

El preflight es estrictamente declarativo: realiza cero solicitudes API de escritura, no modifica la base de datos, no copia ni sube medios, no importa, no elimina y no publica. Incluso con `GO`, `ready_for_import`, `content_published` y `apply_performed` permanecen en `false`; las acciones propuestas siguen siendo manuales y requieren revisión posterior.

## Importador mínimo temporal de tijeras eléctricas LGMG

`import_lgmg_scissors_minimal.py` 1.1.0 es una vía local, mínima y temporal. Acepta exclusivamente los 21 modelos fuente cerrados en el código (S0607E-2 a S1413Ⅱ), conserva el modelo oficial del proveedor y su `source_key` como procedencia auditable, pero crea el modelo comercial final y el nombre `Elevador tipo tijera eléctrico LGMG {modelo final}`. No importa detalles técnicos, especificaciones, fichas, precios ni otras familias; tampoco publica productos.

La categoría y la marca son precondiciones manuales: antes de usarlo deben existir una única raíz activa `Maquinaria` (`maquinaria`, tipo `machinery`, sin padre), una única subcategoría activa con el nombre exacto `Elevadores tipo tijera eléctricos` bajo esa raíz y una única marca activa `LGMG`. Para esa subcategoría solo se admite el slug canónico `elevadores-tipo-tijera-electricos` o, exclusivamente, el slug histórico conocido `elevador-electrico`, que el panel conserva al renombrar categorías existentes; no es una coincidencia abierta. La herramienta no cambia el slug ni realiza escrituras de categorías o marcas. La eliminación del producto de ejemplo JLG también es manual y está fuera de alcance.

El modo predeterminado es una simulación de solo lectura: valida los CSV, la integridad de las 21 asociaciones/20 archivos, consulta la API local con `GET`, clasifica existentes y escribe informes. `--apply --confirm-minimal-import` habilita únicamente los `POST` para crear los productos ausentes y cargar su imagen principal. El token se lee solo desde `JEM_NEXUS_ACCESS_TOKEN`; no se pasa por CLI ni se persiste. No hay opción de publicación.

La repetición es idempotente de manera sencilla: reutiliza una coincidencia canónica exacta, omite su imagen si ya existe y carga solamente la imagen faltante. Nunca vuelve a crear los nombres o modelos anteriores. Un producto en el estado heredado produce un conflicto controlado que pide ejecutar primero el canonizador; una coincidencia ambigua o incompatible produce `NO_GO` antes de escribir. Los códigos de salida son `0` para simulación aprobada o aplicación verificada, `2` para error operativo/aplicación parcial y `3` para una precondición bloqueante o conflicto previo.

### Windows 11 (PowerShell)

Simulación bajo `C:\Users\Franz\Desktop\jem docs\temp`:

```powershell
$env:JEM_NEXUS_ACCESS_TOKEN = "PEGAR_TOKEN_LOCAL_TEMPORAL_AQUI"
py "C:\Users\Franz\Desktop\jem docs\temp\web-ventas-generica\tools\lgmg-catalog-extractor\import_lgmg_scissors_minimal.py" `
  --plan-input "C:\Users\Franz\Desktop\jem docs\temp\import-plan" `
  --media-input "C:\Users\Franz\Desktop\jem docs\temp\media-package" `
  --api-base-url "http://localhost:5000" `
  --output-dir "C:\Users\Franz\Desktop\jem docs\temp\minimal-import-dry-run"
Remove-Item Env:JEM_NEXUS_ACCESS_TOKEN
```

Aplicación explícita (solo después de revisar la simulación y preparar manualmente categoría y marca):

```powershell
$env:JEM_NEXUS_ACCESS_TOKEN = "PEGAR_TOKEN_LOCAL_TEMPORAL_AQUI"
py "C:\Users\Franz\Desktop\jem docs\temp\web-ventas-generica\tools\lgmg-catalog-extractor\import_lgmg_scissors_minimal.py" `
  --plan-input "C:\Users\Franz\Desktop\jem docs\temp\import-plan" `
  --media-input "C:\Users\Franz\Desktop\jem docs\temp\media-package" `
  --api-base-url "http://localhost:5000" `
  --output-dir "C:\Users\Franz\Desktop\jem docs\temp\minimal-import-apply" `
  --apply `
  --confirm-minimal-import
Remove-Item Env:JEM_NEXUS_ACCESS_TOKEN
```

Use un directorio de salida nuevo y vacío en cada ejecución. La validación dinámica debe realizarse manualmente en Windows 11 contra la API local, después de revisar los seis informes generados.

## Canonización cerrada del lote de tijeras eléctricas LGMG

`canonicalize_lgmg_scissors_catalog.py` implementa la decisión comercial cerrada para los productos ID 2 a 22. La fuente y las etapas de extracción y preparación continúan conservando los modelos oficiales, incluido U+2161 `Ⅱ`; **no existe una regla global para retirar números romanos**. Solo las 12 equivalencias enumeradas dentro del canonizador eliminan U+2161, mientras nueve modelos se conservan. Los 21 nombres pasan de `Elevador de tijera...` a `Elevador tipo tijera...`.

La herramienta acepta únicamente la API local HTTP en `localhost:5000` o `127.0.0.1:5000`, rechaza redirecciones y toma el token solamente de `JEM_NEXUS_ACCESS_TOKEN`. El modo predeterminado es un dry-run exclusivamente GET. La aplicación requiere conjuntamente `--apply --confirm-lgmg-scissors-canonicalization`; después del preflight completo, sus únicas escrituras son PATCH mínimos con `name` y `model` a los 21 IDs cerrados. La omisión deliberada de `slug` hace que el backend conserve cada URL existente.

El preflight es fail-closed para marca, subcategoría, publicación, destacado, imagen principal única y estado anterior/final exacto. Los estados ya finales se omiten, por lo que una ejecución interrumpida se puede reanudar y una repetición completamente aplicada hace cero escrituras. El producto JLG ID 1 queda expresamente fuera del mapeo, no bloquea por su marca actual y se verifica sin cambios antes/después. No hay rollback destructivo, creación, eliminación, publicación ni modificación de imágenes.

Dry-run en PowerShell, que debe realizarse realmente solo en Windows después del merge:

```powershell
$env:JEM_NEXUS_ACCESS_TOKEN = "PEGAR_TOKEN_LOCAL_TEMPORAL_AQUI"
py ".\tools\lgmg-catalog-extractor\canonicalize_lgmg_scissors_catalog.py" `
  --api-base-url "http://localhost:5000" `
  --output-dir "C:\Users\Franz\Desktop\jem docs\temp\lgmg-canonicalization-dry-run"
Remove-Item Env:JEM_NEXUS_ACCESS_TOKEN
```

Aplicación posterior al merge, solamente después de revisar los seis informes del dry-run:

```powershell
$env:JEM_NEXUS_ACCESS_TOKEN = "PEGAR_TOKEN_LOCAL_TEMPORAL_AQUI"
py ".\tools\lgmg-catalog-extractor\canonicalize_lgmg_scissors_catalog.py" `
  --api-base-url "http://localhost:5000" `
  --output-dir "C:\Users\Franz\Desktop\jem docs\temp\lgmg-canonicalization-apply" `
  --apply `
  --confirm-lgmg-scissors-canonicalization
Remove-Item Env:JEM_NEXUS_ACCESS_TOKEN
```
# Auditoría técnica offline de las 21 tijeras eléctricas estándar

`audit_lgmg_scissors_technical_data.py` es una herramienta **exclusivamente
offline, local y de solo lectura**. Examina el `import-plan` amplio validado y
su `media-package` para preparar evidencia técnica de las 21 tijeras de la
familia fuente `Elevadores de Tijera`. No consulta los valores actualmente
almacenados en JEM Nexus.

La selección usa conjuntamente el `source_key` estable y el modelo fuente de
la tabla cerrada del importador mínimo. La relación fuente/objetivo se obtiene,
sin ejecutar herramientas con efectos externos, de la tabla cerrada del
canonizador: se preservan modelos fuente como `S0607EⅡ`, pero el informe usa el
modelo comercial `S0607E` y el nombre `Elevador tipo tijera eléctrico LGMG
S0607E`. No se aplica una sustitución Unicode general.

## Entradas y ejecución posterior al merge

Las tres opciones aceptadas son carpetas físicas locales:

* `--plan-input`: carpeta del `import-plan` completo;
* `--media-input`: carpeta del `media-package` completo;
* `--output-dir`: carpeta nueva o vacía, separada de ambas entradas.

La ejecución real contra los paquetes conservados se realizará en Windows
después del merge. Ejemplo PowerShell con rutas placeholder:

```powershell
py -3 ".\tools\lgmg-catalog-extractor\audit_lgmg_scissors_technical_data.py" `
  --plan-input "C:\ruta\al\import-plan" `
  --media-input "C:\ruta\al\media-package" `
  --output-dir "C:\ruta\a\technical-audit"
```

La herramienta no acepta URL, API, token, credenciales, descarga, publicación
ni modo de aplicación. No llama a JEM Nexus, no usa base de datos y no crea,
actualiza o elimina productos, fichas o especificaciones. Tampoco copia,
renombra o sube PDF: solo informa rutas relativas, asociaciones, MIME, tamaño,
SHA-256, firma física y reutilización. Que un PDF esté disponible localmente no
confirma ni autoriza su publicación comercial.

## Campos y tratamiento conservador

La auditoría prepara candidatos con evidencia para `WorkingHeightM`,
`MaximumLoadCapacityKg`, `MachineWeightKg`, `PowerSource`, `TerrainType`,
`Year`, `HoursMeter` y la disponibilidad fuente relacionada con
`TechnicalSheetId`. Conserva además todas las demás filas como posibles
`ProductSpec` (por ejemplo dimensiones, velocidades, pendientes, radios,
baterías y demás atributos que no tienen un campo directo en `Product`).

Capacidad y energía reutilizan los resultados conservadores del plan. Altura y
peso solo admiten etiquetas explícitas de una allowlist y unidades métricas;
no convierten pies o libras. El terreno exige equivalencia estructurada con el
enum y nunca se infiere de familia, modelo, nombre o fotografía. Año no se
inventa, y horómetro queda no proporcionado/no aplicable. Conflictos, valores
no representables y ausencias quedan vacíos y marcados para revisión humana.
Todos los candidatos requieren revisión humana; el resultado siempre declara
`ready_for_update=false` y no prepara payloads ni IDs.

## Nueve salidas

La promoción atómica desde staging produce exactamente:

1. `technical-audit-products.csv`;
2. `technical-audit-field-candidates.csv`;
3. `technical-audit-specifications.csv`;
4. `technical-audit-datasheets.csv`;
5. `technical-audit-warnings.csv`;
6. `technical-audit-summary.json`;
7. `technical-audit-summary.txt`;
8. `technical-audit-manifest.json`;
9. `README-technical-audit.txt`.

Los CSV preservan Unicode, usan UTF-8 con BOM y CRLF, y protegen fórmulas de
hojas de cálculo. Una entrada corrupta, insegura o distinta del lote cerrado
impide cualquier paquete parcial. El estado exitoso `AUDIT_COMPLETE` significa
únicamente que la evidencia local fue inventariada: no significa que los datos
estén listos para actualizar o publicar.

## Enriquecimiento controlado posterior a la auditoría

`enrich_lgmg_scissors_catalog.py` aplica exclusivamente la decisión comercial
cerrada para las 21 tijeras LGMG. Vuelve a validar los `import-plan` y
`media-package` originales, las 21 asociaciones y PDF, y la evidencia de altura
de trabajo, capacidad, peso base y alimentación eléctrica de 24 V. La tabla
explícita conserva U+2161 en los modelos fuente y se cruza con
`MODEL_SOURCE_KEYS` y `SOURCE_TARGET_MODELS`; no existe una transformación
Unicode general ni se consumen como fuente los informes de auditoría.

La herramienta funciona únicamente en Windows y contra los orígenes locales
exactos `http://localhost:5000` y `http://127.0.0.1:5000`. El modo predeterminado
es un dry-run de solo GET. La aplicación exige conjuntamente `--apply` y
`--confirm-lgmg-scissors-enrichment`, con el token disponible solamente en
`JEM_NEXUS_ACCESS_TOKEN`. Su preflight fail-closed obtiene snapshots completos,
resuelve los 21 productos por identidad comercial y jerarquía activas, comprueba
su estado no publicado, imagen principal única y campos preservados, y termina
sin escrituras ante cualquier diferencia. Antes del primer POST o PATCH clasifica
las 21 fichas de forma inmutable como `upload_required`, `reuse_required` o
`already_associated`; la validación de los cuatro campos técnicos directos, la
resolución por metadatos y SHA-256 y la construcción del PATCH son fases
separadas. Por ello una asociación válida no es un conflicto y nunca se envía
`technical_sheet` con valor nulo.

Las únicas escrituras autorizadas son `POST /api/technical-sheets` con los
campos multipart `name` y `file`, y `PATCH /api/products/{id}` mínimo con un
subconjunto de `working_height_m`, `maximum_load_capacity_kg`,
`machine_weight_kg`, `power_source` y `technical_sheet`. No crea productos,
ProductSpecs ni variantes, no modifica imágenes, nombres, modelos, slugs,
descripciones o datos comerciales, no publica y mantiene vacíos terreno, año y
horómetro. El contrato de fichas usado es exclusivamente `GET
/api/technical-sheets`, `GET /api/technical-sheets/{id}/file` y `POST
/api/technical-sheets`; sus respuestas se validan estrictamente mediante `id`,
`name`, `original_file_name`, `content_type`, `size_bytes`, `created_at`,
`updated_at` y `file_url`, exigiendo `content_type=application/pdf`. Las fichas
existentes se descargan por `/file` y se reutilizan solo después de verificar
metadatos y SHA-256; tamaño y tipo por sí solos nunca prueban igualdad.
El tamaño máximo coincide con el backend: 10 MiB exactos. Un archivo de hasta
10 MiB es admisible y uno mayor se rechaza localmente antes de cualquier HTTP.
Las fichas previas JPEG, PNG o WebP también se descargan con su tipo contractual
para establecer la línea base física, pero nunca son candidatas PDF para LGMG.

Dry-run posterior al merge:

```powershell
$env:JEM_NEXUS_ACCESS_TOKEN = "PEGAR_TOKEN_LOCAL_TEMPORAL_AQUI"
py -3 ".\tools\lgmg-catalog-extractor\enrich_lgmg_scissors_catalog.py" `
  --plan-input "C:\ruta\al\import-plan" `
  --media-input "C:\ruta\al\media-package" `
  --api-base-url "http://localhost:5000" `
  --output-dir "C:\ruta\a\lgmg-enrichment-dry-run"
Remove-Item Env:JEM_NEXUS_ACCESS_TOKEN
```

Aplicación, únicamente después de revisar los ocho informes del dry-run:

```powershell
$env:JEM_NEXUS_ACCESS_TOKEN = "PEGAR_TOKEN_LOCAL_TEMPORAL_AQUI"
py -3 ".\tools\lgmg-catalog-extractor\enrich_lgmg_scissors_catalog.py" `
  --plan-input "C:\ruta\al\import-plan" `
  --media-input "C:\ruta\al\media-package" `
  --api-base-url "http://localhost:5000" `
  --output-dir "C:\ruta\a\lgmg-enrichment-apply" `
  --apply `
  --confirm-lgmg-scissors-enrichment
Remove-Item Env:JEM_NEXUS_ACCESS_TOKEN
```

La ejecución es secuencial, reanudable e idempotente. Nunca espera una ventana
larga: tras 20 cargas nuevas emite `PAUSED_UPLOAD_WINDOW` y código 2 antes de la
carga 21; un HTTP 429 produce `PAUSED_RATE_LIMIT`, conserva `Retry-After` y
también retorna 2. Al repetir después de la ventana, verifica y reutiliza las
fichas ya cargadas. En estado final, la repetición realiza cero POST y cero
PATCH y emite `IDEMPOTENT_VERIFIED`.

`enrichment-products.csv` y `enrichment-datasheets.csv` siempre contienen una
fila por cada uno de los 21 modelos, incluso en dry-run, pausa y reanudación.
Registran campos directos pendientes, estado de ficha, hash, tipo de contenido,
asociación y verificación final. `enrichment-actions.csv` separa y ordena cada
GET de verificación, POST de ficha y PATCH de producto, sin persistir tokens,
multipart ni bytes PDF. La verificación final compara por ID productos
seleccionados y no seleccionados, categorías, marcas, imágenes, ProductSpecs y
fichas, y rechaza cualquier modificación concurrente fuera de los cinco campos
autorizados.

Después de cada POST, la herramienta conserva primero el estado `uploaded`,
valida los metadatos, descarga inmediatamente la ficha por `/file` y solo marca
`hash_verified` al comprobar su SHA-256. Antes de cualquier PATCH vuelve a
consultar el producto (`pre_patch_revalidated`) y reconstruye el payload mínimo
desde ese detalle fresco. Los fallos posteriores a una escritura devuelven
`PARTIAL_FAILURE` sin borrar las 21 filas, IDs ni acciones acumuladas; el
producto fallido queda `partial_failure` y las filas posteriores `not_started`.

La evidencia de altura acepta valores métricos simples y, únicamente para las
etiquetas controladas de altura de trabajo, celdas explícitas `dentro/fuera`
como `9.8m/8m(dentro/fuera)`. El primer número es la altura interior aprobada;
el segundo es la altura exterior y también se interpreta y valida (debe ser
positivo y no superar al primero). Ambos valores y la celda original quedan en
la evidencia de informe. La altura nunca se infiere del nombre del modelo. La
allowlist exacta de peso incluye además la etiqueta real `Peso de Máquina (CE)`
usada por SS0607E, sin admitir pesos de componentes ni conversiones imperiales.

Los fallos controlados registran `failure_stage`, un `failure_code` estable
(por ejemplo `EVIDENCE_WORKING_HEIGHT_INCOMPATIBLE`,
`EVIDENCE_MACHINE_WEIGHT_INCOMPATIBLE`, `EVIDENCE_CAPACITY_INCOMPATIBLE` o
`EVIDENCE_POWER_24V_MISSING`) y el modelo afectado cuando corresponde. Si el
directorio de salida ya fue validado y está nuevo o vacío, el conflicto produce
los ocho informes habituales con cero POST y cero PATCH. El diagnóstico de CLI
y los informes nunca incluyen credenciales, mensajes arbitrarios, multipart,
cuerpos HTTP ni contenido binario de PDF.

## Auditoría offline del catálogo LGMG restante

`audit_lgmg_remaining_catalog.py` prepara, sin importar ni modificar productos, la
tabla de aprobación humana del plan LGMG amplio. Su alcance contractual es de 57
productos: identifica 21 tijeras eléctricas estándar mediante los pares exactos
`source_key + metric_model` leídos de `MODEL_SOURCE_KEYS` y deja 36 productos en
seis familias. `processed_closed_cohort` describe esa cohorte cerrada; **no**
significa que la herramienta haya consultado la base de datos.

Las propuestas cerradas, siempre pendientes de aprobación humana, son:

| Familia fuente | Subcategoría propuesta | Prefijo comercial propuesto |
| --- | --- | --- |
| Elevador Eléctrico RT de Tijera | Elevadores tipo tijera todoterreno | Elevador tipo tijera todoterreno eléctrico LGMG |
| Elevadores de Brazo Articulado | Elevadores tipo brazo articulado | Elevador tipo brazo articulado eléctrico LGMG |
| Elevadores de Brazo Telescópico | Elevadores tipo brazo telescópico | Elevador tipo brazo telescópico eléctrico LGMG |
| Elevador Mástil Vertical | Elevadores tipo mástil vertical | Elevador tipo mástil vertical eléctrico LGMG |
| Elevador de Tijera Sobre Orugas | Elevadores tipo tijera sobre orugas | Elevador tipo tijera sobre orugas eléctrico LGMG |
| Manipuladores Telescópicos | Manipuladores telescópicos | Manipulador telescópico eléctrico LGMG |

El modelo propuesto conserva literalmente `metric_model`, incluido Unicode como
`Ⅱ` y cualquier sufijo. El nombre es únicamente el prefijo de la tabla, un
espacio y ese modelo exacto. El modelo imperial, los aliases y el nombre original
del plan permanecen separados para comparar; no generan productos adicionales.

La auditoría vuelve a comprobar hashes, tamaños, rutas, asociaciones, MIME,
extensiones y firmas binarias de imágenes y PDF. Exige una candidata principal
única y al menos una imagen válida por producto. `AR24JE` y `T38JE` son las únicas
fichas permitidas como `missing_at_source`: no bloquean una futura importación
mínima después de aprobarla, pero dejan el enriquecimiento técnico pendiente.
La importación mínima futura (identidad, categoría, modelo, nombre e imagen) es
distinta de asociar la ficha y completar el enriquecimiento técnico.

La herramienta acepta exclusivamente `--plan-input`, `--media-input` y
`--output-dir`, todos obligatorios y directorios locales seguros. Está cerrada a
los fingerprints aprobados del plan
`75d68378dcd7bf77b19f9c7f0e60806085deaecadf2b7fa70e3102812be4bcb7` y de medios
`b16d7f40250cc9b7a1b4affe029d0a87bba4355968e289fdab99ddbb4d656c9b`.
No requiere backend, frontend ni token; no usa red, API o base de datos y no
ofrece aplicación ni publicación.

Produce exactamente nueve archivos: `remaining-catalog-scope.csv`,
`remaining-products-for-approval.csv`, `remaining-families.csv`,
`remaining-media.csv`, `remaining-conflicts.csv`, `remaining-summary.json`,
`remaining-summary.txt`, `remaining-manifest.json` y
`README-remaining-audit.txt`. Las `approval_key` y el fingerprint agregado
permitirán al importador general futuro comprobar que una aprobación no cambió.
El plan `electric-only` no necesariamente cubre el catálogo mundial: productos
no eléctricos o inciertos fuera del plan no cuentan como importados y tampoco
deben olvidarse silenciosamente.

Ejemplo para Windows (ejecutar después del merge con los paquetes reales):

```powershell
Set-Location "C:\Users\Franz\Desktop\web-ventas-generica"

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"

& "C:\Windows\py.exe" -3 `
  ".\tools\lgmg-catalog-extractor\audit_lgmg_remaining_catalog.py" `
  --plan-input "C:\Users\Franz\Desktop\jem docs\temp\JEM-Nexus-LGMG-Qualified-Power-Validation-20260828-145126\import-plan" `
  --media-input "C:\Users\Franz\Desktop\jem docs\temp\JEM-Nexus-LGMG-Media-Download-20260828-105313\media-package" `
  --output-dir "C:\Users\Franz\Desktop\jem docs\temp\JEM-Nexus-LGMG-Remaining-Audit-$Stamp"
```
## Reparación y revisión de medios del catálogo LGMG restante

`repair_lgmg_remaining_media.py` prepara, sin importar productos, un paquete completamente
nuevo para los 36 productos y las seis familias restantes. La aprobación humana literal
`APRUEBO LAS 6 FAMILIAS Y LOS 36 NOMBRES` aprueba las familias, los prefijos, los nombres
deterministas y los modelos literales (incluido `Ⅱ`), pero **no** aprueba automáticamente
imágenes ni fichas técnicas.

La interfaz tiene exactamente cinco argumentos obligatorios: `--plan-input`, `--media-input`,
`--remaining-audit-input`, `--decisions-input` y `--output-dir`. No existe modo de aplicación,
publicación o acceso a JEM Nexus. La herramienta no requiere backend, frontend ni token; no
consulta ni modifica la base de datos y no importa productos.

El JSON de decisiones usa `schema_version: "1.0"`, la aprobación literal anterior,
`datasheet_repairs` para `SR1018E-2`, `T28JE` y `H625E`, y la decisión visual cerrada
`A13JE|A14JE`. Las fichas cruzadas de `SR1018E-2` (asociada originalmente con evidencia de
`SR0818E-2`) y `T28JE` (asociada con evidencia de `T22JE`) solo pueden sustituirse desde una
URL HTTPS de LGMG declarada explícitamente. No se raspan páginas, no se adivinan enlaces y no
se descargan imágenes. Si las URLs directas están vacías no se llama a la red. Una descarga
debe ser PDF por MIME y firma, no HTML, medir como máximo 10 MiB, conservar un SHA-256 y
contener el marcador exacto cuando haya texto extraíble. Sin extracción confiable queda como
`downloaded_pending_human_content_review`.

La ficha original de `H625E` (38.610.993 bytes) se conserva solamente como metadato de
trazabilidad: el paquete corregido la marca `excluded_backend_size_limit`, impide su carga y
requiere seguimiento técnico y de ficha, sin bloquear la futura creación del producto. El
límite contractual permanece en 10.485.760 bytes; el PDF no se comprime, divide, convierte ni
reescribe. `AR24JE` y `T38JE` conservan `missing_at_source` y también pueden importarse
posteriormente sin ficha, con seguimiento.

Las imágenes físicamente compartidas por `A13JE` y `A14JE` no se interpretan mediante OCR,
visión artificial o similitud perceptual. Se genera evidencia HTML local autónoma y CSV. La
decisión debe ser uno de `approve_shared_images_for_both`, `approve_images_for_a13je_only`,
`approve_images_for_a14je_only`, `reject_shared_images_for_both` o
`pending_human_visual_review` o, como sexta opción,
`approve_separate_model_images`. Las cinco decisiones anteriores conservan su significado.
La aprobación humana exacta de esta reparación es
`APRUEBO LAS DOS FICHAS OFICIALES Y LA SEPARACIÓN DE IMÁGENES A13JE/A14JE`.

La sexta decisión distingue el archivo físico deduplicado por SHA-256 de su asociación a un
producto. A13JE conserva, en orden, `21b8e8bbb8d2b40617b01fd86aee1c8c30025e742f90cc8f4229eaea264744ce`
(principal) y `3fc3777d98efadbd36a4cc31fde58887a476e92f1b163250011128ad02f946f4`.
A14JE retira esas dos asociaciones y conserva solamente
`e3e568efc55d1f9dcadc9bdd76f80a2ec1a6fe7d88df776cc3c5b8c1b16fe9de`
(nueva principal), `b95ee211b2a20be84372f88bfb828be596fe4fce6618b4e32f0dd6dfa9a13541` y
`acb85d1fbe203d02ef7f1af42ef0e00d6f43cb643be952b8c65c85c572c9ab41`.
No se redimensiona, recomprime ni reescribe ninguna imagen.

El contrato aprobado completo, que no debe ejecutarse en Codex, es:

```json
{
  "schema_version": "1.0",
  "catalog_approval": {
    "approved": true,
    "approval_text": "APRUEBO LAS 6 FAMILIAS Y LOS 36 NOMBRES"
  },
  "datasheet_repairs": {
    "SR1018E-2": {
      "action": "replace_from_official_source",
      "product_page_url": "https://www.lgmglifts.com/product/pro-detail-5182.htm",
      "datasheet_url": "https://www.lgmglifts.com/upload/file/2025/04/lgmg-RT-scissorlift-en-SR1018E-2.pdf",
      "expected_model_markers": ["SR1018E-2", "SR3369E-2"]
    },
    "T28JE": {
      "action": "replace_from_official_source",
      "product_page_url": "https://www.lgmglifts.com/product/pro-detail-2045.htm",
      "datasheet_url": "https://www.lgmglifts.com/upload/file/2023/07/10/73e3683775884b6da85c0f265d315616.pdf",
      "expected_model_markers": ["T28JE", "T92JE"]
    },
    "H625E": {
      "action": "exclude_backend_size_limit",
      "maximum_backend_size_bytes": 10485760
    }
  },
  "shared_image_decisions": {
    "A13JE|A14JE": {
      "decision": "approve_separate_model_images",
      "notes": "A13JE conserva sus dos imágenes. A14JE elimina las dos asociaciones de A13JE y conserva sus tres imágenes propias.",
      "approved_images": {
        "A13JE": {
          "primary_sha256": "21b8e8bbb8d2b40617b01fd86aee1c8c30025e742f90cc8f4229eaea264744ce",
          "ordered_sha256": [
            "21b8e8bbb8d2b40617b01fd86aee1c8c30025e742f90cc8f4229eaea264744ce",
            "3fc3777d98efadbd36a4cc31fde58887a476e92f1b163250011128ad02f946f4"
          ]
        },
        "A14JE": {
          "primary_sha256": "e3e568efc55d1f9dcadc9bdd76f80a2ec1a6fe7d88df776cc3c5b8c1b16fe9de",
          "ordered_sha256": [
            "e3e568efc55d1f9dcadc9bdd76f80a2ec1a6fe7d88df776cc3c5b8c1b16fe9de",
            "b95ee211b2a20be84372f88bfb828be596fe4fce6618b4e32f0dd6dfa9a13541",
            "acb85d1fbe203d02ef7f1af42ef0e00d6f43cb643be952b8c65c85c572c9ab41"
          ]
        }
      }
    }
  }
}
```

Solo se autorizan las dos URL directas anteriores. Las descargas futuras exigen HTTPS y
dominio oficial también tras redirecciones, estado HTTP satisfactorio, MIME y firma PDF,
`%%EOF`, tamaño de 1 a 10 MiB, SHA-256, ausencia de HTML disfrazado y texto verificable. Se
acepta `SR1018E-2` o `SR3369E-2`, y `T28JE` o `T92JE`; los modelos cruzados se rechazan. Si
la extracción conservadora no es confiable, el estado es
`downloaded_pending_human_content_review` y el veredicto `REVIEW_REQUIRED`.

La salida cerrada es:

```text
corrected-media/
repair-summary.json
repair-summary.txt
repair-manifest.json
repair-conflicts.csv
repair-datasheets.csv
repair-images.csv
controlled-import-readiness.csv
A13JE-A14JE-visual-review.html
A13JE-A14JE-visual-review.csv
README-repaired-media.txt
```

Los CSV usan UTF-8 con BOM, CRLF y protección contra fórmulas. El manifest registra hashes y
tamaños de entradas/salidas, fingerprints aprobados, fingerprint determinista agregado,
actividad de red cerrada y efectos nulos sobre API, base de datos, productos, cargas y
publicación. No incluye el hash de sí mismo. Las entradas son inmutables; se rechazan rutas
solapadas, traversal, rutas absolutas, letras de unidad, barras invertidas, symlinks y tipos
especiales. El conjunto se construye en staging y se promueve atómicamente solamente cuando
está completo.

Los únicos veredictos son `REPAIR_COMPLETE` (dos reemplazos validados, exclusión de H625E y
decisión visual explícita), `REVIEW_REQUIRED` (preparación válida a la que aún le falta una URL,
revisión PDF o decisión visual; código de salida exitoso) y `CONFLICT` (inconsistencia o medio
inválido; código distinto de cero). Por ello se recomienda ejecutar primero con URLs vacías y
decisión pendiente, revisar las evidencias, completar el JSON y ejecutar de nuevo hacia otro
directorio vacío.

Ejemplo para ejecutar posteriormente en Windows (no se ejecuta en Codex):

```powershell
Set-Location "C:\Users\Franz\Desktop\web-ventas-generica"

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"

& "C:\Windows\py.exe" -3 `
  ".\tools\lgmg-catalog-extractor\repair_lgmg_remaining_media.py" `
  --plan-input "C:\Users\Franz\Desktop\jem docs\temp\JEM-Nexus-LGMG-Qualified-Power-Validation-20260828-145126\import-plan" `
  --media-input "C:\Users\Franz\Desktop\jem docs\temp\JEM-Nexus-LGMG-Media-Download-20260828-105313\media-package" `
  --remaining-audit-input "RUTA_A_LA_CARPETA_remaining-audit" `
  --decisions-input "RUTA_AL_ARCHIVO\remaining-media-decisions.json" `
  --output-dir "C:\Users\Franz\Desktop\jem docs\temp\JEM-Nexus-LGMG-Repaired-Media-$Stamp"
```

Con ambas fichas validadas, las 36 filas quedan listas y el veredicto esperado es
`REPAIR_COMPLETE`; una ficha pendiente conserva `REVIEW_REQUIRED`, y toda incoherencia
produce `CONFLICT`. La reparación real se ejecutará posteriormente en Windows después del
merge. La siguiente etapa (Prompt 248) será una **importación completa controlada**, no una
importación mínima estricta. Podrá representar todos los datos confiables del plan: nombre,
modelo, marca, categorías, tipo, condición, disponibilidad, descripción, especificaciones,
capacidad validada, energía representable, imágenes válidas y ficha compatible. No inventará
año, horómetro, peso, altura, terreno, precio, IVA o stock, ni atributos derivados solamente
del modelo o una fotografía. Todos comenzarán con `show_price = false`,
`is_published = false`, `is_featured = false` y `price = null`; el futuro proceso exigirá
dry-run, confirmación, lotes, checkpoint, reanudación, idempotencia, rollback y validación final.

## Importación completa controlada del catálogo LGMG restante

`import_lgmg_remaining_controlled.py` implementa la etapa cerrada posterior al plan de **57**
productos y a la cohorte procesada de **21** tijeras: importa los **36** restantes, sin filtros
de modelo, en estas seis subcategorías exactas bajo `Maquinaria`: tijera todoterreno, brazo
articulado, brazo telescópico, mástil vertical, tijera sobre orugas y manipuladores
telescópicos. La identidad se cruza mediante `source_key + metric_model + approval_key` y la
cohorte anterior se obtiene como sintaxis desde `MODEL_SOURCE_KEYS`; no se duplica una lista
manual de 36 modelos.

La herramienta exige los fingerprints aprobados del plan
`75d68378dcd7bf77b19f9c7f0e60806085deaecadf2b7fa70e3102812be4bcb7`, medios originales
`b16d7f40250cc9b7a1b4affe029d0a87bba4355968e289fdab99ddbb4d656c9b`, catálogo restante
`62230925212e866c59197a03975bb5707d40ef416b05bb071de84e43cef7ea39`, entrada de auditoría
`d2b46313a8b9219793c6f9541e383b8eef47f6d1b2f76dbf7bf7bbd984371665`, decisiones
`280811cc376c2aa480511fcfa6923e120973e252016efb74e3b89e318130d779` y paquete reparado
`f9c18b7000a93d37e69e306960da8f3e237e4cc2bbf1122f892053566c01b157`. No hay bypass.
Valida conjuntos cerrados, manifests, hashes, tamaños, tipos regulares, ausencia de symlinks,
rutas no solapadas y todos los medios antes de llamar a la API.

Se conservan nombre aprobado, modelo literal (incluidos `-2` y `Ⅱ`), marca LGMG, categoría,
tipo `machinery`, condición `new`, disponibilidad `on_request`, descripciones existentes,
especificaciones con nombre/valor/unidad/orden/Unicode, capacidad máxima validada y energía
solo si cabe en el enum. Se cargan imágenes sin alterar bytes y fichas PDF compatibles. No se
inventan año, horómetro, altura, peso, terreno, precio, IVA, stock físico ni beneficios. Todo
producto se crea con `price = null`, `price_visible = false`, `is_published = false` e
`is_featured = false`, y con los booleanos comerciales conservadores desactivados.

El paquete reparado es la única fuente de medios. A13JE conserva dos imágenes y A14JE tres,
con la primera asociación como principal. SR1018E-2 y T28JE usan sus reemplazos validados.
AR24JE y T38JE se crean sin ficha porque no existe en origen; H625E se crea sin intentar subir
su PDF de 38.610.993 bytes. Los tres generan seguimiento, no datos inventados ni un bloqueo.

Hay exactamente un modo obligatorio: `--dry-run`, `--apply`, `--verify` o `--rollback`, y los
cuatro exigen `--checkpoint`. Todos autentican exclusivamente con `JEM_NEXUS_ACCESS_TOKEN`; el token no es argumento ni se
persiste. Una API real exige HTTPS (HTTP solo se admite para loopback sintético en pruebas),
con timeout, límite de respuesta y paginación acotada. No se llama a LGMG. Dry-run y verify
son de lectura. Apply exige `--confirm-apply IMPORTAR_36_LGMG_RESTANTES`; rollback exige
`--confirm-rollback REVERTIR_IMPORTACION_36_LGMG_RESTANTES`.

El dry-run consulta identidad, categorías, marca, productos no publicados, imágenes,
especificaciones y fichas; detecta exactos, candidatos y conflictos; expone todas las
mutaciones reales: primero la ficha, después el producto asociado, después las especificaciones
separadas y las imágenes (la principal viaja como `is_main` en su propio upload). Produce
fingerprints separados para estado remoto, plan de operaciones y dry-run completo. Apply no
admite bypass: exige exactamente el checkpoint `dry_run_ready` creado por ese dry-run, misma
versión/HEAD, API, fingerprints, taxonomía, marca, tamaño de lote y snapshot remoto. El
fingerprint diagnóstico incompleto
`85bb67b06624bbbb5b7a8d102c00faa776884c9a394eaf62cd8be3e7f9e72553` queda registrado como
supersedido y nunca se acepta para apply. El lote predeterminado es 20, por lo
que la cohorte se divide **20 + 16**; `--batch-size` acepta 1–20. El checkpoint JSON externo
se crea atómicamente durante dry-run y registra plan, recursos preexistentes, IDs reales y cada
operación completada sin autorización. `--resume` es obligatorio para continuar
`apply_in_progress` o `apply_partial`, y rechaza entradas, API, herramienta, recursos, estado
remoto, plan o tamaño distintos. Los exactos se omiten, una segunda ejecución
no escribe y un conflicto ambiguo bloquea. Un fallo detiene productos posteriores y conserva
`APPLY_PARTIAL`. Verify vuelve a exigir los 36 exactos. Rollback reanudable elimina solo IDs
creados y evidenciados por este checkpoint, en orden de dependencias, preservando recursos
preexistentes.

Cada ejecución produce exactamente ocho informes: `remaining-import-summary.json`,
`remaining-import-summary.txt`, `remaining-import-products.csv`, `remaining-import-media.csv`,
`remaining-import-operations.csv`, `remaining-import-conflicts.csv`,
`remaining-import-manifest.json` y `README-remaining-import.txt`. Los CSV son UTF-8 con BOM,
CRLF y protección de fórmulas; los JSON preservan Unicode. Los veredictos son
`DRY_RUN_READY`, `APPLY_COMPLETE`, `APPLY_PARTIAL`, `VERIFY_COMPLETE`, `ROLLBACK_COMPLETE` y
`CONFLICT`. El manifest se genera al final y contiene SHA-256 y tamaño de los otros siete
informes, nunca de sí mismo, más el SHA-256 y tamaño del checkpoint externo.

Ejemplos Windows (reemplace los marcadores). El frontend puede estar en
`http://localhost:5174`, pero el origen del backend es `http://localhost:5000`, no
`http://localhost:5000/api`. Copie el valor de `ventas_access_token` a un archivo temporal y
elimínelo después de cargar la variable de entorno:

```powershell
$TokenFile = "<RUTA_TOKEN_TEMPORAL>"
$env:JEM_NEXUS_ACCESS_TOKEN = (Get-Content -Raw $TokenFile).Trim()
$Tool = ".\tools\lgmg-catalog-extractor\import_lgmg_remaining_controlled.py"
$Common = @('--plan-input','<RUTA_PLAN>','--remaining-audit-input','<RUTA_AUDITORIA>',
  '--repaired-media-input','<RUTA_PAQUETE_REPARADO>','--api-base-url','http://localhost:5000')

py $Tool @Common --output-dir '<SALIDA_DRY_RUN>' --dry-run --checkpoint '<RUTA_CHECKPOINT>'
py $Tool @Common --output-dir '<SALIDA_APPLY>' --apply --checkpoint '<RUTA_CHECKPOINT>' `
  --confirm-apply IMPORTAR_36_LGMG_RESTANTES
py $Tool @Common --output-dir '<SALIDA_VERIFY>' --verify --checkpoint '<RUTA_CHECKPOINT>'
py $Tool @Common --output-dir '<SALIDA_ROLLBACK>' --rollback --checkpoint '<RUTA_CHECKPOINT>' `
  --confirm-rollback REVERTIR_IMPORTACION_36_LGMG_RESTANTES
Remove-Item Env:JEM_NEXUS_ACCESS_TOKEN
Remove-Item -LiteralPath $TokenFile -Force
```

Dry-run crea `<RUTA_CHECKPOINT>` y apply reutiliza exactamente ese archivo; nunca se genera un
checkpoint nuevo para apply. Después del merge se debe generar un token nuevo y ejecutar un
dry-run completamente nuevo. Sus ocho informes y checkpoint deberán revisarse antes de
considerar apply; estos ejemplos no publican y no se ejecutan en Codex.
## Auditoría individual de operaciones de especificaciones LGMG

### Corrección 2.1.1 del esquema aprobado

El intento real de dry-run 2.1.0 terminó antes de crear productos o un checkpoint
aplicable con el falso conflicto `duplicate_specification_request` de SR0818E-2.
La causa exacta era que el consumidor buscaba los campos internos `name`/`spec_name`,
`key`/`spec_key`, `value`/`spec_value` y `order`/`spec_order` en filas que nunca los
contienen. En consecuencia, las dos primeras filas se adaptaban ambas a nombre,
clave y valor vacíos y orden cero. No era un defecto del detector de duplicados.

El encabezado cerrado real es
`source_key,metric_model,group_order,group_name,specification_order,source_label,source_value,normalized_label,normalized_value,unit,requires_review,maximum_load_capacity_candidate_kg`.
La versión 2.1.1 lo valida exactamente y aplica una sola correspondencia:

* `name = normalized_label` cuando no está vacío; en otro caso `source_label`;
* `value = normalized_value` cuando no está vacío; en otro caso `source_value`;
* `key = ""`, porque el plan aprobado no representa una clave y no se inventa una;
* `unit = unit` literalmente, incluido el valor vacío;
* `order = int(specification_order)`, nunca `group_order`.

`requires_review`, `group_*` y `maximum_load_capacity_candidate_kg` siguen siendo
evidencia auxiliar y no se envían al DTO. La adaptación no translitera: conserva
`MODÈLE`, `Métrica`, tildes, símbolos, mayúsculas y `Ⅱ`. El mismo objeto efectivo
alimenta el POST, `request_template`, informes, hashes, clave de operación, apply y
resume.

`specification_index` es únicamente el índice uno-basado de auditoría; `order` es
el orden aprobado enviado al backend. La firma semántica compara la referencia
estable del producto y los cinco campos efectivos `name`, `key`, `value`, `unit` y
`order`. El índice no entra en esa firma y por tanto no puede ocultar dos requests
realmente idénticos. `operation_key`, en cambio, identifica determinísticamente la
operación auditable y se deriva del contrato completo de operación, su template y
su dependencia, sin IDs futuros ni azar.

Los conteos permanecen cerrados: 33 fichas + 36 productos + 1.057 especificaciones
+ 71 imágenes = 1.197 operaciones, sin descartar ni deduplicar silenciosamente
ninguna fila. El schema del checkpoint permanece en `2.1`, pero la versión de
herramienta forma parte de su contrato: un checkpoint 2.1.0 es incompatible con
2.1.1 y se rechaza antes de cualquier mutación. Los dos fingerprints supersedidos
ya registrados no cambian; el intento fallido no produjo otro fingerprint real.

Después del merge, el dry-run real sigue pendiente en Windows y exige token nuevo,
directorio de salida nuevo y checkpoint nuevo. No debe ejecutarse apply hasta
revisar por completo el ZIP del siguiente dry-run.

La versión 2.1.0 corrige el defecto observado en el dry-run anterior: sus 1.057
filas `specification` calculaban el mismo `payload_sha256` a partir de un
placeholder genérico y usaban `association_order=0`. Ese informe demostraba el
número de POST, pero no qué `ProductSpec` correspondía a cada POST; por ello ese
dry-run no era auditable ni aplicable.

El contrato real de `POST /api/product-specs` es `ProductSpecWriteDto`: acepta
`product` o `product_id`, `name`, `key`, `value`, `unit` y `order`. Durante el
dry-run todavía no hay ID de producto. Cada operación conserva entonces un
`request_template` canónico con `product_id_ref.operation_key` apuntando a la
operación de producto y conserva literalmente nombre, clave, valor, unidad,
orden, Unicode (incluido `Ⅱ`) e índice fuente uno-basado. No contiene IDs
futuros, timestamps, azar ni inferencias técnicas nuevas. `payload_sha256` es
SHA-256 de ese JSON UTF-8, con claves ordenadas y separadores compactos;
`resolved_payload_sha256` queda vacío hasta que apply sustituye la referencia
por el ID creado y vuelve a calcular el hash del payload real.

Cada una de las 1.197 solicitudes lleva una `operation_key`, SHA-256 determinista
del contrato 2.1, approval/source key, modelo, orden fuente, fase, acción,
método, `path_template`, índice, hash de payload/archivo y clave de dependencia.
Las fichas no dependen de otra operación; cada producto depende de su ficha si
existe; especificaciones e imágenes dependen, por orden **y** clave, del producto
del mismo modelo. Una solicitud de especificación realmente duplicada dentro de
un producto es conflicto, no se distingue artificialmente. El fingerprint de
operaciones incorpora templates, claves, dependencias y todos sus campos; el
fingerprint de dry-run incorpora además las seis entradas, HEAD/versión, API,
estado remoto, recursos, taxonomía, medios y lotes.

El checkpoint usa schema `2.1` y conserva las 1.197 operaciones completas. Apply
reconstruye y compara claves, dependencias, payloads y fingerprints antes de la
primera escritura; registra después cada clave, hash de template, hash resuelto
e ID. Resume omite solo una operación cuya clave completada coincide. Verify
comprueba los productos y usa únicamente los endpoints existentes (la identidad
de especificaciones queda limitada a lo que expone su listado). Rollback recorre
en orden inverso exclusivamente operaciones completadas, por clave, eliminando
especificaciones e imágenes antes que productos y fichas, y nunca categorías,
marca, recursos preexistentes ni la cohorte anterior.

Los fingerprints cerrados `85bb67b06624bbbb5b7a8d102c00faa776884c9a394eaf62cd8be3e7f9e72553`
(`superseded_incomplete_dry_run`) y
`bda45b2889f54055332a529df141fc6abfcfa5f3e9cfe04320d5313b991cbd31`
(`superseded_unauditable_specification_dry_run`) son rechazados explícitamente
por apply, resume, verify y rollback. Debe generarse un dry-run nuevo. Los
conteos derivados y validados son 33 fichas + 36 productos + 1.057
especificaciones + 71 imágenes = 1.197 operaciones. Se mantienen exactamente
los ocho informes existentes y el checkpoint externo obligatorio.

## Diagnóstico de uso de slugs en categorías y marcas

El diagnóstico estático de entidades, DTO, endpoints, contexto EF, formularios,
hooks, navegación, filtros, rutas, enlaces, pruebas e importadores encontró lo
siguiente:

* `Category.Slug` y `Brand.Slug` se almacenan como columnas obligatorias de hasta
  140 caracteres, ambas con índice único. No son el nombre visible.
* Los endpoints administrativos aceptan el slug opcional introducido por el
  usuario; al crear sin él (o al enviarlo expresamente) el backend lo genera con
  `SlugHelper.GenerateSlug` y evita colisiones mediante sufijos. Los formularios
  de categoría y marca exponen el campo como opcional.
* Las rutas públicas de detalle usan el **slug del producto**, no el de categoría
  ni el de marca. La navegación actual construye enlaces de catálogo con IDs.
  Los filtros del backend, sin embargo, aceptan tanto ID como slug para
  `category` y `brand`; por tanto estos slugs sí participan en funcionalidad del
  catálogo aunque el frontend actual prefiera IDs.
* Las relaciones de `Product` se guardan por `CategoryId` y `BrandId`. Este
  importador resuelve una categoría y la marca LGMG por nombre exacto y valida
  jerarquía/estado; luego envía sus IDs. No resuelve la relación por slug ni
  hardcodea IDs locales.

Por esa evidencia, `CATEGORY_SLUG_POLICY = blocking_functional_filter`. El slug
observado `levadores-tipo-brazo-articulado` frente al canónico
`elevadores-tipo-brazo-articulado` produce `category_slug_mismatch`, un conflicto
bloqueante antes de cualquier mutación. No cambia el nombre o ID, no crea PATCH
y no corrige automáticamente la categoría. El contrato también exige raíz
`Maquinaria`/`maquinaria` y los seis pares canónicos declarados en el importador.

Esta tarea no elimina ningún slug. Eliminarlos en el futuro exigiría una tarea
separada para cambiar entidades, DTO/read models, validación y generación,
índices/migraciones, endpoints de filtro, formularios/tipos/hooks, pruebas e
importadores, además de definir compatibilidad de URLs y consumidores. Quitar
solo las columnas rompería el esquema y los filtros existentes.
# Recuperación del apply parcial LGMG por HTTP 429

La ejecución Windows con importador 2.1.1 terminó en `apply_partial`: el limitador rechazó
con HTTP 429 el `POST /api/products` de la operación 66. El checkpoint parcial inmutable
(`dbb5ece22d1dcaabf16e8cb9c3bba1ebb57c1acec30fde68ec8bfe40a9a25eef`, 1.825.474
bytes) registra el prefijo continuo de 65 mutaciones: SR0818E-2 y SR1018E-2 completos
(32 operaciones cada uno) y únicamente la ficha de SR1218E-2. Quedan 1.132 operaciones.
El checkpoint-before-apply es evidencia anterior, no el estado de la base de datos: **no se
debe restaurar**, repetir apply sin `--resume`, ni ejecutar rollback antes de auditar el
estado parcial.

El backend configura limitadores `fixed_window` particionados por usuario autenticado:
global 600/60 s, escritura 60/60 s y upload 20/600 s; todos tienen cola cero, rechazan
con 429 y el callback publica `Retry-After` cuando el lease lo ofrece. Autenticación se
ejecuta antes del middleware de rate limit, y éste antes de autorización y despacho de
endpoints; por ello un 429 del limitador ocurre antes del handler. El importador 2.2.0
aplica a todas las solicitudes un coordinador común con reloj monotónico y margen del
10% sobre la política más restrictiva (33 s entre solicitudes). GET, POST y DELETE
reintentan como máximo dos veces tras el intento inicial; respetan `Retry-After` en
segundos o fecha HTTP y, si falta, esperan la ventana conservadora. Un valor inválido o
excesivo detiene la ejecución. Las mutaciones jamás se reintentan tras timeout, conexión
cerrada, respuesta ambigua/inválida ni HTTP 500/502/503.

`--verify` reconoce exclusivamente el checkpoint 2.1.1 de este incidente, comprueba su
hash, tamaño, fingerprints, las 1.197 operaciones y el prefijo 1–65, y mediante GET debe
contrastar productos, fichas, especificaciones, imágenes, taxonomía, marca, ausencias y
duplicados. No modifica el checkpoint. Si todo coincide genera `PARTIAL_RESUME_READY` y
un `partial_resume_fingerprint_sha256` determinista que vincula checkpoint, evidencia
remota, operación siguiente, política de límites y versión nueva. Los CSV presentan las
65 operaciones como `completed`, la 66 como `planned`, estados de producto derivados y
un archivo de conflictos solo con encabezado.

La reanudación exige `--apply --resume --approved-partial-resume-fingerprint <sha256>`.
Tras repetir íntegramente el preflight y comparar el fingerprint, migra atómicamente el
checkpoint 2.1.1/schema 2.1 a 2.2.0/schema 2.2 mediante staging, flush, fsync y
`os.replace`. Conserva IDs, completed_operations y operation_key; omite exactamente el
prefijo completado y empieza en la operation_key de orden 66, reutilizando la ficha ya
registrada. Cada éxito se persiste inmediatamente, evitando duplicados. Los informes
separan efectos de la invocación de efectos acumulados y reflejan manifest, operations,
products y conflictos parciales. Ningún payload publica productos ni muestra precios.
Rollback sigue siendo reanudable, valida primero y borra únicamente IDs registrados, en
orden inverso y usando el mismo pacing.

Después del merge, el procedimiento Windows comienza generando un token nuevo y
ejecutando **únicamente `--verify`** contra el checkpoint `apply_partial`. Se debe adjuntar
y revisar el ZIP `PARTIAL_RESUME_READY`; no se ejecutará `--apply --resume` hasta obtener
aprobación humana explícita de ese fingerprint. Su valor futuro no se anticipa aquí.

## Plan canónico universal para checkpoints parciales (2.2.2)

La versión 2.2.2 distingue de forma temprana el checkpoint heredado del incidente
(`2.1.1`/schema `2.1`) de los checkpoints actuales (schema y contrato de operaciones
`2.2`). La clasificación cerrada diferencia una ejecución nueva, `dry_run_ready`, el
`apply_partial` heredado, `apply_partial` actual, `rollback_in_progress`,
`apply_complete`, `rollback_complete` y cualquier checkpoint inválido. Una versión,
estado, contrato, fingerprint, cohorte o modo incompatible se rechaza antes de intentar
reconstruir operaciones.

Para **todo** checkpoint parcial válido, la regla es
`canonical_planned_operations = checkpoint["planned_operations"]`. Sus 1.197
operaciones persistidas (33 fichas, 36 productos, 1.057 especificaciones y 71 imágenes)
son el plan histórico aprobado. El snapshot remoto parcial puede acreditar taxonomía,
marca, los IDs creados, identidades exactas, colisiones y evidencia para el fingerprint;
no puede regenerar ni recortar ese plan, porque ya contiene los efectos de su prefijo
completado. Esta regla se aplica al checkpoint heredado exacto, a futuros
`apply_partial` 2.2 y a `rollback_in_progress` 2.2. Un dry-run nuevo y un
`dry_run_ready`, en cambio, siguen reconstruyendo y contrastando el plan completo antes
de la primera mutación.

El `--verify` parcial usa exclusivamente GET, conserva byte por byte el checkpoint y
produce `PARTIAL_RESUME_READY`. Los informes separan las cero mutaciones de la invocación
de las 65 mutaciones históricas registradas, muestran 1.132 pendientes y derivan la
operación siguiente y los estados de producto exclusivamente por `operation_key`. El
fingerprint parcial enlaza los bytes del checkpoint, el plan canónico, el snapshot
actual, el prefijo completado, la política de rate limiting, la versión y el HEAD; no
contiene fechas, credenciales ni secretos.

Un futuro `--apply --resume` solo será admisible después de revisar el ZIP y aprobar
literalmente ese fingerprint. Al migrar el checkpoint heredado se conservan sus 1.197
operaciones, las 65 completadas, IDs, hashes y claves; la continuación comienza en la
primera clave pendiente (orden 66) sin repetir recursos. Un rollback parcial también
usa el plan y los recursos propios persistidos, recorre las completadas en orden inverso
y nunca elimina marca, categorías ni recursos preexistentes.

El checkpoint real de Windows permanece intacto: SHA-256
`dbb5ece22d1dcaabf16e8cb9c3bba1ebb57c1acec30fde68ec8bfe40a9a25eef`, tamaño
1.825.474 bytes, versión 2.1.1, 1.197 planificadas y 65 completadas. No existe todavía
un fingerprint aprobado. Está prohibido restaurar `checkpoint-before-apply.json`, editar
manualmente el checkpoint o ejecutar resume antes de revisar el próximo ZIP.

**El siguiente paso real después del merge es ejecutar solamente `--verify` contra el
checkpoint `apply_partial` original e intacto.** Después se revisará su ZIP; hasta
entonces `--apply --resume` no está autorizado.

## Finalización reducida del catálogo LGMG restante

La decisión humana vigente es **APRUEBO LA FINALIZACIÓN REDUCIDA CON 34 PRODUCTOS Y
34 IMÁGENES PRINCIPALES**. Por ello `complete_lgmg_remaining_core.py` 1.0.2 sustituye
operativamente, sin modificarlo, al intento de reanudar las 1.197 operaciones. Parte
de los dos productos históricos completos (SR0818E-2 y SR1018E-2), deriva los otros
34 de la cohorte cerrada de 36 y crea un plan nuevo de 68 operaciones: 34 productos
sin publicar, sin precio visible, seguidos por exactamente una imagen principal cada
uno, en lotes de 20 y 14 productos.

El perfil excluye deliberadamente las 999 especificaciones pendientes, 30 fichas
pendientes, todas las imágenes secundarias, precios, publicación y enriquecimientos.
SR1218E-2 reutiliza la ficha histórica validada desde la operación 65; no vuelve a
subirla y rollback nunca la elimina. Los restantes 33 payloads usan
`technical_sheet = null`. La carga futura de fichas, especificaciones y otros medios
será manual o una tarea independiente.

El DTO real de lectura de fichas no expone necesariamente `sha256`: para esta ficha,
el SHA-256 contractual está representado exactamente por `original_file_name` como
los 64 caracteres hexadecimales aprobados seguidos de `.pdf`. La validación 1.0.1
comprueba conjuntamente el ID derivado del checkpoint, nombre, nombre físico
canónico, MIME `application/pdf`, tamaño 406080 y ruta relativa segura exacta. Si el
DTO sí incluye un `sha256` no vacío, también debe coincidir. La ausencia de asociación
con producto es esperada antes de crear SR1218E-2; una asociación presente solo se
acepta si corresponde a ese producto ya clasificado por identidad. `created_at` y
`updated_at` no forman parte de la identidad. La ficha no se vuelve a subir ni se
incluye en rollback, y esta corrección no amplía las 68 operaciones aprobadas.

La causa del falso `Checkpoint vacío o inválido` de 1.0.1 fue exacta: el lector
reducido delegaba en `read_checkpoint` del importador completo, cuyo conjunto de
estados no contiene `core_dry_run_ready`. El archivo sí se abría y deserializaba, pero
ese lector clasificaba su estado reducido válido como inválido. En 1.0.2 el lector
reducido abre físicamente y valida su propio schema antes de clasificar el modo.

No hace falta repetir el dry-run ni editar el checkpoint. La compatibilidad legado es
deliberadamente cerrada al único checkpoint reducido 1.0.1 aprobado: exactamente
138358 bytes y SHA-256
`1e655c651425d543c99c650d1730849bb8a86a6fbff9b218c1022dfdbcbc4dc9`.
Además del archivo exacto se vuelven a comprobar identidad, aprobación, schema,
estado, cero efectos y recursos creados, los 68 órdenes y `operation_key`, hashes de
payload, dependencias, composición 34+34 y fingerprints. Cualquier variante se
rechaza. El checkpoint 1.0.0 sigue rechazado.

`--source-checkpoint` es evidencia inmutable de solo lectura (2.1.1,
`apply_partial`, 65 completadas). La herramienta valida sus bytes antes y después,
deriva de sus operaciones completadas los recursos preexistentes y escribe un
checkpoint reducido separado. Nunca migra, sobrescribe ni reanuda el checkpoint
histórico. Los modos son:

1. `--dry-run`: solo GET, confirma 2 existentes, 34 ausentes, la ficha histórica,
   las 34 imágenes y el plan 34+34; genera el checkpoint y los siete informes.
2. `--apply --confirm-apply CREAR_34_LGMG_CON_IMAGEN_PRINCIPAL`, **sin `--resume`**:
   carga un checkpoint existente `core_dry_run_ready`, exige cero completadas,
   vuelve a validar inputs, medios y snapshot remoto, y usa sus 68
   `planned_operations` persistidas como plan canónico (no lo reconstruye). Solo
   entonces migra atómicamente el 1.0.1 aprobado a 1.0.2, registra su procedencia,
   pasa a `core_apply_in_progress`, hace los 68 POST y verifica 36/36.
3. `--apply --resume` continúa un `core_apply_partial`, valida y omite las claves ya
   completadas, sin duplicarlas.
4. `--verify` es solo lectura tanto antes como después del apply y no modifica el
   checkpoint.
5. `--rollback --confirm-rollback REVERTIR_FINALIZACION_REDUCIDA_LGMG` (con
   `--resume` si quedó parcial) elimina primero imágenes y luego productos, solo por
   IDs registrados como nuevos. No elimina productos, imágenes, fichas,
   especificaciones, categorías ni marca históricos.

Todos los modos reutilizan el cliente HTTP, validadores de paquetes y medios,
serialización canónica, checkpoint atómico y `RequestCoordinator` del importador
controlado. Solo se admite un origen HTTP local con puerto y el token procede
exclusivamente de `JEM_NEXUS_ACCESS_TOKEN`.

El checkpoint histórico completo de 1.197 operaciones continúa sustituido, intacto y
solo se usa como procedencia. La siguiente ejecución real en Windows queda pendiente
para después del merge y debe usar el mismo checkpoint reducido aprobado, sin
editarlo y sin `--resume`:

```powershell
$env:JEM_NEXUS_ACCESS_TOKEN = '<token-efímero-nuevo>'
python .\complete_lgmg_remaining_core.py <entradas-comunes> --output-dir C:\lgmg\core-apply --apply --confirm-apply CREAR_34_LGMG_CON_IMAGEN_PRINCIPAL
```

Tras revisar ese resultado, los comandos Windows correspondientes son:

```powershell
python .\complete_lgmg_remaining_core.py <entradas-comunes> --output-dir C:\lgmg\core-apply --apply --confirm-apply CREAR_34_LGMG_CON_IMAGEN_PRINCIPAL
python .\complete_lgmg_remaining_core.py <entradas-comunes> --output-dir C:\lgmg\core-resume --apply --resume --confirm-apply CREAR_34_LGMG_CON_IMAGEN_PRINCIPAL
python .\complete_lgmg_remaining_core.py <entradas-comunes> --output-dir C:\lgmg\core-verify --verify
python .\complete_lgmg_remaining_core.py <entradas-comunes> --output-dir C:\lgmg\core-rollback --rollback --confirm-rollback REVERTIR_FINALIZACION_REDUCIDA_LGMG
```

Desplegar este código no copia datos ni archivos locales a producción. Siguen siendo
34 productos y 34 imágenes principales; no se añaden especificaciones, fichas nuevas
ni imágenes secundarias. Si el apply queda parcial, no se repite: una invocación
posterior separada usa `--apply --resume` sobre el 1.0.2 parcial.

### Reanudación progresiva 1.0.3 (incidente de la operación 44)

La causa raíz del conflicto posterior al apply parcial era que `run()` aplicaba también
a `--apply --resume` la condición inicial `exact_models == HISTORICAL_MODELS` y 34
`create_candidate`. `classify_products()` clasificaba correctamente los 22 productos
recién creados como `already_imported_exact`, pero la condición ignoraba
`completed_operations` y volvía a exigir el snapshot del dry-run (2 históricos, 34
ausentes y cero conflictos). La cohorte inicial de 34 la construye `derive_core()` a
partir de los `create_candidate`; el resume no debe reconstruirla.

La versión 1.0.3 conserva ese contrato para `--dry-run` y para el apply inicial desde
`core_dry_run_ready`. Solamente `--apply --resume` y `--verify` sobre
`core_apply_partial` usan el preflight progresivo. Este valida que las completadas sean
un prefijo continuo del plan persistido, con la misma `operation_key`, orden, modelo,
tipo e ID; exige que `resources_created`, `external_effects.writes` y `next_operation`
sean exactamente derivables del prefijo. Luego acredita cada producto e imagen remotos
por su ID registrado, identidad y asociación de dependencia, rechaza duplicados, y
exige que todo producto o imagen aún pendiente siga ausente. No adopta recursos.

Para el checkpoint del incidente, esa derivación produce 2 productos y 2 imágenes
históricos, 22 productos y 21 imágenes creados y exactos, 12 productos ausentes y 13
imágenes pendientes, sin conflictos. La operación 43 acredita T34JE-2 como producto ID
46; la 44, con clave
`2e7349beb740a1142548b233e03514a3a7a6745eceb53307216bc8132799c085`, es su imagen
principal todavía ausente. Por tanto, la primera mutación futura es únicamente esa
imagen: T34JE-2 no se vuelve a crear. Después quedan otras 24 operaciones (25 en total).

La compatibilidad 1.0.2 es deliberadamente cerrada al archivo real de 151081 bytes y
SHA-256 `3ffafe17c6d63c7dca307ae7e3385462ed7bb598a8f2e9d13588cdf34edead1d`.
Además del contrato físico se revalidan contenido, aprobación, schema, estado, los 68
órdenes, fingerprints, prefijo 43, recursos 22+21, cero publicación/errores, procedencia
1.0.1, y las operaciones 43 y 44 exactas. Su procedencia 1.0.1 se conserva separada:
138358 bytes y SHA-256
`1e655c651425d543c99c650d1730849bb8a86a6fbff9b218c1022dfdbcbc4dc9`.
Tras todos los prechecks de lectura, el resume registra aparte la migración 1.0.2,
actualiza atómicamente a 1.0.3/`core_apply_in_progress` y empieza en 44. Un fallo futuro
persiste el nuevo prefijo como `core_apply_partial` 1.0.3, reanudable semánticamente.

No se necesita otro dry-run, no se debe usar apply sin `--resume` y no se debe ejecutar
rollback para este incidente. La ejecución real queda pendiente en Windows después del
merge: generar un JWT nuevo, usar el mismo checkpoint parcial 1.0.2 y ejecutar
`--apply --resume`. Se adjuntará el ZIP final; si vuelve a quedar parcial, no se repetirá
el mismo comando hasta revisar el nuevo estado persistido.

### Validación de detalle 1.0.4 para la ficha de SR1218E-2

El listado `GET /api/products?include_unpublished=true` devuelve
`ProductListReadDto`, que no expone `technical_sheet`; por tanto, que la clave no exista
en ese JSON no significa que la asociación sea `null`. El detalle devuelve
`ProductDetailReadDto`, sí expone `technical_sheet`, y el backend carga expresamente la
relación `TechnicalSheet`. El falso conflicto de 1.0.3 fue exclusivamente la inferencia
`product.get("technical_sheet") -> None` sobre el DTO incompleto del listado: el
checkpoint y la asociación remota real no eran divergentes.

La versión 1.0.4 mantiene todas las comprobaciones seguras del listado (identidad única,
ID, modelo, nombre, categoría, marca, publicación, destacado y precio). Para cada
producto completado cuyo template persistido exige una ficha positiva pero cuya clave
no aparece en el listado, deriva el ID únicamente de `completed_operations` y consulta
el detalle con el `ApiClient` seguro. En el prefijo contractual hay exactamente una
consulta adicional, de solo lectura: `GET /api/products/25`. Se ejecuta y valida antes
de comprobar medios pendientes, antes de migrar o escribir el checkpoint y antes de
cualquier POST, PUT, PATCH o DELETE. Los templates que esperan `null` y no representan
la clave no generan consultas; si el listado sí representa la clave, su valor se exige.

El detalle debe acreditar el producto 25, modelo `SR1218E-2`, nombre aprobado,
categoría y marca esperadas, no publicado, no destacado, precio nulo y no visible. Su
objeto `technical_sheet` debe coincidir exactamente con ID 25, nombre
`Ficha técnica LGMG SR1218E-2`, archivo
`fbfb3916b94d600e19df841560bf11bdf6dee9d7dd26500da44f5894cafde409.pdf`,
MIME `application/pdf`, tamaño 406080 y ruta relativa segura
`/technical-sheets/25/file`. Se reutiliza el contrato cerrado de la ficha histórica;
los timestamps continúan fuera de su identidad.

El checkpoint físico 1.0.2 permanece intacto en 43/68 operaciones, 22 productos y 21
imágenes, con tamaño 151081 y SHA-256
`3ffafe17c6d63c7dca307ae7e3385462ed7bb598a8f2e9d13588cdf34edead1d`.
La compatibilidad sigue cerrada exclusivamente a ese archivo y al 1.0.1 aprobado; la
migración a 1.0.4 conserva la evidencia 1.0.1 y registra aparte la procedencia 1.0.2.
La siguiente operación sigue siendo la 44: subir la imagen principal de T34JE-2 (ID
46), sin recrear el producto ni repetir ninguna de las 43 claves completadas.

No hace falta otro dry-run. Después del merge se debe generar un JWT nuevo y ejecutar
`--apply --resume` con el checkpoint parcial original. Para este incidente no se debe
usar `--rollback`. El checkpoint histórico sustituido de 1.197 operaciones permanece
intacto y no se reanuda ni modifica.

### Seguimiento no bloqueante de `alt_text` en 1.0.5

La evidencia de solo lectura confirmó que las 21 imágenes del prefijo completado sí
existen, una por producto, con IDs y asociaciones coincidentes con el checkpoint,
`is_main = true`, `order = 0` y rutas administradas bajo
`/media/product-images/{product_id}/`. El único metadato divergente es
`alt_text = ""`; esto no afecta la existencia, asociación ni condición principal de
las imágenes que exige la aprobación reducida de 34 productos y 34 imágenes
principales.

La versión 1.0.5 acepta exclusivamente esa cadena exactamente vacía como
`blank_nonblocking_followup` y registra, de forma determinista, un seguimiento manual
de accesibilidad/SEO por imagen con modelo, `operation_key`, ID de imagen e ID de
producto. Un valor ausente, `null`, espacios, otro texto o cualquier tipo no textual
sigue siendo conflicto. No se recorta ni normaliza el valor, no se ejecutan PATCH ni
recargas y no cambian el template, la clave ni el payload persistidos.

Las comprobaciones estructurales siguen cerradas: ID positivo y coincidente,
dependencia de producto correcta, exactamente una imagen, principal verdadera, orden
cero y ruta relativa no vacía sin URL absoluta, credenciales, query, fragmento ni
traversal, bajo el segmento del producto y con extensión `.jpg`, `.jpeg`, `.png` o
`.webp`. Cualquier divergencia estructural bloquea antes de una mutación.

El checkpoint físico 1.0.2 continúa intacto en 43/68 operaciones (22 productos y 21
imágenes), con 151081 bytes y SHA-256
`3ffafe17c6d63c7dca307ae7e3385462ed7bb598a8f2e9d13588cdf34edead1d`;
la compatibilidad permanece cerrada a este archivo y al 1.0.1 aprobado. La migración
a 1.0.5 conserva las 43 operaciones y ambas procedencias, añade los 21 seguimientos
sin alterar el plan y pasa a `core_apply_in_progress`. La siguiente operación continúa
siendo la 44, el POST de la imagen principal de T34JE-2 para el producto ya existente
46; no se recrea ese producto ni se reenvían sus imágenes anteriores.

No se requiere otro dry-run ni debe usarse `--rollback`. Después del merge se necesita
un JWT nuevo y se debe ejecutar `--apply --resume` con el checkpoint parcial original
e intacto. El checkpoint histórico sustituido de 1.197 operaciones permanece intacto
y no debe reanudarse.
