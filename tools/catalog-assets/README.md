# Catalog Assets — plan B

Herramienta **independiente** en Python 3.13 para inventariar y reunir imágenes y fichas
técnicas que Franz cargará manualmente. No importa productos, no se conecta al sistema vivo
y no depende del importador anterior.

## Inicio y estructura

Desde este directorio:

```text
python -m catalog_assets --root "C:\Users\Franz\Desktop\jem docs\Maquinas" init
```

`--root` es obligatorio en todos los comandos y representa directamente `Maquinas`. `init`
crea solo lo que falte, sin sobrescribir archivos existentes:

```text
Maquinas/
├── LGMG/
│   ├── Imagenes modelos LGMG/
│   └── fichas-tecnicas LGMG/
├── EP/
│   ├── Imagenes modelos EP/
│   └── fichas-tecnicas EP/
├── JLG/
│   ├── Imagenes modelos JLG/
│   └── fichas-tecnicas JLG/
├── _pendientes/
│   ├── imagenes/
│   └── fichas-tecnicas/
├── _control/
│   ├── fuentes.csv
│   ├── modelos.csv
│   ├── candidatos.json
│   ├── manifest.json
│   ├── checksums.csv
│   ├── logs/
│   └── parciales/
├── inventario.csv
└── pendientes-revision.csv
```

No hay carpetas por modelo. Las marcas de destino son **LGMG, EP y JLG**. **GAM nunca crea una carpeta**: solo puede actuar como fuente
`fallback` con destino EP, cuando falta el mismo tipo de activo en una fuente EP primaria y
el modelo EP es inequívoco.

## Contrato de `_control/fuentes.csv`

El CSV usa UTF-8 con encabezado exacto:

| columna | contrato |
|---|---|
| `target_brand` | `LGMG`, `EP` o `JLG` |
| `model` | modelo original; vacío solo en una fila deshabilitada/incompleta |
| `source_name` | nombre de origen (`LGMG`, `EP`, `GAM`, etc.) |
| `source_role` | `primary` o `fallback`; GAM exige `target_brand=EP` y `fallback` |
| `page_url` | página pública declarada; HTTP(S), sin credenciales |
| `asset_type` | `image`, `technical_sheet` o `auto` |
| `asset_url` | URL directa opcional; HTTP(S), sin credenciales |
| `priority` | entero no negativo (menor se procesa primero) |
| `expected_language` | etiqueta informativa de idioma/revisión |
| `enabled` | estrictamente `true` o `false` |
| `notes` | procedencia, carencias y observaciones |

Una fila habilitada necesita `page_url` o `asset_url`. Las filas incompletas deben permanecer
deshabilitadas. `fixtures/fuentes-ejemplo.csv` incluye una referencia LGMG ya declarada en el
repositorio y plantillas EP/GAM vacías; no inventa rutas. Revise cada URL antes de habilitarla.

## Comandos

```text
python -m catalog_assets --root "C:\Users\Franz\Desktop\jem docs\Maquinas" inventory
python -m catalog_assets --root "C:\Users\Franz\Desktop\jem docs\Maquinas" plan
python -m catalog_assets --root "C:\Users\Franz\Desktop\jem docs\Maquinas" discover --allow-public-network
python -m catalog_assets --root "C:\Users\Franz\Desktop\jem docs\Maquinas" download --allow-public-network --dry-run
python -m catalog_assets --root "C:\Users\Franz\Desktop\jem docs\Maquinas" download --allow-public-network
python -m catalog_assets --root "C:\Users\Franz\Desktop\jem docs\Maquinas" verify
python -m catalog_assets --root "C:\Users\Franz\Desktop\jem docs\Maquinas" verify --strict
python -m catalog_assets --root "C:\Users\Franz\Desktop\jem docs\Maquinas" status
```

* `inventory`: valida firmas, calcula SHA-256 y recrea los reportes deterministas; preserva
  nombres, ubicaciones y bytes existentes.
* `plan`: valida y ordena `fuentes.csv`, y deja el plan en `candidatos.json`; no usa red.
* `discover`: consulta únicamente páginas declaradas y extrae enlaces; no descarga los
  binarios finales. Exige consentimiento de red explícito.
* `download`: procesa candidatos inequívocos. `--dry-run` no escribe activos.
  `--download-pending` permite bajar ambiguos, pero únicamente a `_pendientes`, nunca a una
  marca. Admite `--max-bytes`, `--timeout`, `--retries` y `--pause`.
* `verify`: comprueba integridad binaria, rutas y hashes sin convertir una clasificación
  pendiente o un duplicado válido en un fallo.
* `verify --strict`: añade la exigencia de clasificación completa y falla ante pendientes.
* `status`: resume cobertura y enumera modelos sin imagen o PDF, motivos pendientes y cada
  duplicado con su SHA-256, tamaño y sus dos rutas, sin decidir cuál conservar.

Solo `discover` y `download` contienen operaciones de red, y se niegan a ejecutarlas sin
`--allow-public-network`. Se rechazan esquemas no HTTP(S), credenciales, localhost, IP privadas,
loopback, link-local, multicast y redirects prohibidos. No se envían cookies ni tokens.

## Asociación, nombres y revisión

El inventario trabaja en dos pasadas: primero reúne modelos fiables de nombres canónicos,
`fuentes.csv`, asociaciones del manifest y reglas manuales; después busca coincidencias exactas
completas en archivos heredados, prefiriendo el modelo completo más largo. La comparación normaliza mayúsculas, espacios, guiones y puntuación superficial, pero conserva
el modelo original. Un prefijo no basta: `A09JE`, `A09JE-2`, `A09J` y `A09JE-LI` son candidatos
distintos. Un enlace con más de un modelo queda `MODEL_AMBIGUOUS`; logos, iconos, banners,
favicons y navegación se excluyen.

Los nombres finales son `<MARCA>-<MODELO>.<ext>` para imágenes y
`Ficha-tecnica-<MARCA>-<MODELO>.pdf` para fichas. Los adicionales reciben `-2`, `-3`, etc.
La extensión procede de los bytes. Se sanitizan caracteres y nombres reservados de Windows.

No se sobrescribe. Antes de publicar se valida JPEG, PNG, WebP o PDF, MIME y límite de tamaño;
HTML, JSON/texto, cuerpos vacíos y truncados no se aceptan. Un SHA-256 repetido se registra como
duplicado sin crear otra copia. Los parciales viven en `_control/parciales`; una repetición usa
HTTP Range y reinicia con seguridad si el servidor no lo admite. El cierre usa reemplazo atómico.

Los existentes dudosos permanecen exactamente donde estaban y aparecen en
`pendientes-revision.csv`. Los motivos normalizados incluyen `MODEL_UNKNOWN`,
`MODEL_AMBIGUOUS`, `SOURCE_MISSING`, `ASSET_MISSING`, `DOWNLOAD_FAILED`, `INVALID_BINARY`,
`MIME_CONFLICT`, `DUPLICATE`, `NAME_CONFLICT` y `FALLBACK_REQUIRES_REVIEW`.

Todas las rutas se resuelven bajo `--root`; los escapes `..` y por enlaces simbólicos se
rechazan. Los CSV se escriben como UTF-8 con BOM para Excel y los reportes se ordenan y
actualizan atómicamente.

`JLG/Maquinas JLG` y las variantes heredadas de fichas LGMG (mayúsculas, tildes, espacios o
guiones) se inventarían en su ubicación real y se marcan como `legacy`. Nunca se mueven,
renombran, copian ni sobrescriben; solo las nuevas descargas van a las carpetas canónicas.

`_control/modelos.csv` es opcional y `init` lo crea vacío con las columnas `brand`,
`canonical_model`, `alias`, `enabled`, `notes`. `enabled` admite únicamente `true` o `false`;
las marcas se limitan a LGMG, EP y JLG, y los aliases activos duplicados o contradictorios se
rechazan. No se incluye ninguna regla implícita `1930` → `1930ES`: esa decisión sigue siendo
manual.

## Pruebas offline

```text
python3 -m unittest discover -s tests -v
python3 -m compileall catalog_assets tests
```

Usan `TemporaryDirectory` y transporte falso: no abren sockets ni consultan páginas reales.

## Recolección local EP/GAM

`harvest-ep` prepara fuentes para los 39 productos observados en GAM Chile, sin descargar los
activos finales:

```text
python -m catalog_assets --root <RUTA_MAQUINAS> harvest-ep --allow-public-network
```

El comando admite `--request-delay` (1 s), `--max-pages` (100), `--max-models` (39),
`--max-bytes` (5 MiB por HTML) y `--timeout` (20 s). Consulta únicamente la entrada oficial EP
y las cuatro páginas GAM declaradas, escribe un checkpoint reanudable en
`_control/research/ep-harvest-checkpoint.json` y actualiza atómicamente el inventario, candidatos,
auditoría y `_control/fuentes.csv`. EP es primaria y GAM solo fallback del tipo ausente. Las URLs
de activos quedan deshabilitadas hasta su validación binaria controlada; el comando no escribe
en las carpetas de imágenes o fichas.

## Descarga validada del harvest EP

`download-ep-harvest` es la etapa final especializada. A diferencia de `harvest-ep` (que
recolecta evidencia), `discover` (que descubre candidatos genéricos) y `download` (que conserva
su política de filas aprobadas), este comando consume exclusivamente el checkpoint compatible
(`format_version=2`, parser 4 y matcher 2), el inventario, los candidatos seleccionados y
`_control/fuentes.csv` publicados atómicamente por el último harvest satisfactorio. Es el único
comando autorizado a validar las filas `VALIDATION_DEFERRED` que permanecen deshabilitadas.

La inspección estructural, sin red ni escrituras, se ejecuta así:

```text
python -m catalog_assets --root <RUTA_MAQUINAS> download-ep-harvest --dry-run
```

La descarga posterior requiere consentimiento explícito y permite limitar tipo, cantidad,
tamaño, espera y timeout:

```text
python -m catalog_assets --root <RUTA_MAQUINAS> download-ep-harvest --allow-public-network \
  --only all --request-delay 1 --max-files 65 --max-bytes 50000000 --timeout 30
```

Cada URL y redirect se valida contra destinos públicos y contra la procedencia EP/GAM aprobada
por el harvest. Los bytes pasan primero por `_control/parciales`; solo firmas JPEG, PNG y WebP
pueden llegar a `EP/Imagenes modelos EP/`, y solo un PDF completo puede llegar a
`EP/fichas-tecnicas EP/`. La extensión se obtiene de la firma, no del nombre ni de Content-Type.
La firma binaria continúa siendo la autoridad: para imágenes, una diferencia entre subtipos
`image/*` declarados por el servidor se normaliza de forma segura y también se admiten MIME
ausente u `application/octet-stream`. HTML, texto, JSON, PDF y cualquier MIME no gráfico se
rechazan aunque la URL parezca una imagen; declarar `image/*` tampoco permite bytes sin una
firma JPEG, PNG o WebP válida. Las fichas mantienen sin cambios la exigencia de firma PDF.
Los nombres son `EP-<MODELO>.<ext>` y `Ficha-tecnica-EP-<MODELO>.pdf`, con sufijos estables si
otro contenido ocupa el nombre.

El reporte atómico `_control/ep-download-results.csv`, el manifest, checksums y pendientes
permiten reanudar sin sobrescribir. Los resultados ya confirmados se verifican por ruta y hash,
por lo que una reanudación aprovecha los 52 archivos existentes sin volver a solicitarlos. Si
modelos diferentes comparten exactamente los mismos bytes, cada modelo recibe una copia
ordinaria atómica con su propio nombre canónico (sin enlaces); el SHA-256 repetido representa
esa asociación intencional. El dry-run informa cuántos archivos omitiría, materializaría desde
una copia compartida o reintentaría, sin modificar el reporte anterior.

Las fichas de CBY 30II, CQD15SD, EFL1003-HV-6, EFL703-HV-6 y
EFS151 se registran como `MISSING_SOURCE`; no bloquean los demás activos. Las familias SERIE F,
SERIE X2, SERIE X3 y SERIE X5 se excluyen por no ser modelos. LGMG y JLG están completamente
fuera del alcance de esta operación; GAM solo es procedencia fallback con destino EP.

## Importación EP al Nexus local

`import-ep-local` es un importador deliberadamente pequeño y separado del pipeline canónico.
Su única fuente es `_control/ep-download-results.csv`: no recorre `Maquinas`, ignora la carpeta
heredada `EP/Fichas tecnicas EP`, `_pendientes` y cualquier ruta LGMG/JLG, y acepta solamente
imágenes de `EP/Imagenes modelos EP/` y fichas de `EP/fichas-tecnicas EP/` cuyo hash y firma
coincidan. Los 35 productos resultantes son borradores, sin precio visible, specs ni datos
técnicos o comerciales. Las cinco fichas declaradas como ausentes son válidas y no se buscan.

La secuencia obligatoria es **dry-run → apply → verify**. Los tres modos exigen una URL HTTP
loopback con puerto explícito. Dry-run y verify leen `JEM_NEXUS_LOCAL_READ_TOKEN`; apply lee
exclusivamente `JEM_NEXUS_LOCAL_MUTATION_TOKEN`. El dry-run escribe el plan y su fingerprint
en `_control/ep-local-import`; apply exige ese fingerprint mediante
`--confirm-plan-fingerprint`. El plan estable versión 2 calcula de nuevo SHA-256 sobre toda su
representación canónica (sin el propio fingerprint) al cargarlo; por tanto, un plan v1 o una
edición de payload, operaciones, rutas, hashes, root, URL o snapshot se rechaza antes de mutar.

El preflight usa exactamente las seis colecciones de categorías, marcas, productos, imágenes,
fichas y especificaciones (`GET /api/product-specs` incluido). Interpreta el contrato real:
`category.parent`, `product_image.product`, `product.technical_sheet_id` y
`product_spec.product`. Las imágenes se envían a `/api/product-images` con el archivo multipart
`image` y los campos `product_id`, `alt_text`, `is_main` y `order`; las fichas conservan el
archivo multipart `file` y se asocian al producto mediante `technical_sheet`. Los binarios ya
existentes se descargan solamente desde `/api/product-images/{id}/file` y
`/api/technical-sheets/{id}/file`, sin redirects, y se validan por firma, tamaño aplicable y
SHA-256 antes de considerarlos idempotentes.

Apply repite el preflight antes de la primera escritura. Antes de cada POST/PATCH persiste una
intención y cada receipt confirmado permite reanudar sin repetir esa mutación. HTTP 400, 401,
403, 404, 409, 422 y 429 son resultados definitivos: limpian la intención (429 conserva solo
un `Retry-After` numérico). Timeouts, desconexiones, respuesta perdida y 5xx no reconciliados
son ambiguos: conservan la intención y exigen reconciliación por GET. Verify vuelve a consultar
las seis colecciones, exige cero specs y compara los 35 binarios de imagen y las 30 fichas por
SHA-256 sin escribir. Los tokens nunca forman parte de planes, checkpoints, reportes o hashes.

Este importador todavía no se ha ejecutado contra un Nexus real. LGMG y JLG siguen excluidos y
no se inspeccionan, planifican ni modifican.
