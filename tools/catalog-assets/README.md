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
├── _pendientes/
│   ├── imagenes/
│   └── fichas-tecnicas/
├── _control/
│   ├── fuentes.csv
│   ├── candidatos.json
│   ├── manifest.json
│   ├── checksums.csv
│   ├── logs/
│   └── parciales/
├── inventario.csv
└── pendientes-revision.csv
```

No hay carpetas por modelo. **GAM nunca crea una carpeta**: solo puede actuar como fuente
`fallback` con destino EP, cuando falta el mismo tipo de activo en una fuente EP primaria y
el modelo EP es inequívoco.

## Contrato de `_control/fuentes.csv`

El CSV usa UTF-8 con encabezado exacto:

| columna | contrato |
|---|---|
| `target_brand` | `LGMG` o `EP` |
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
* `verify`: vuelve a calcular firmas/hashes y compara contra el inventario sin red.
* `status`: resume cobertura, faltantes, fallos, pendientes y duplicados sin red.

Solo `discover` y `download` contienen operaciones de red, y se niegan a ejecutarlas sin
`--allow-public-network`. Se rechazan esquemas no HTTP(S), credenciales, localhost, IP privadas,
loopback, link-local, multicast y redirects prohibidos. No se envían cookies ni tokens.

## Asociación, nombres y revisión

La comparación normaliza mayúsculas, espacios, guiones y puntuación superficial, pero conserva
el modelo original. Un prefijo no basta: `A09JE`, `A09JE-2`, `A09J` y `A09JE-LI` son candidatos
distintos. Un enlace con más de un modelo queda `MODEL_AMBIGUOUS`; logos, iconos, banners,
favicons y navegación se excluyen.

Los nombres finales son `LGMG-<MODELO>.<ext>` / `EP-<MODELO>.<ext>` para imágenes y
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

## Pruebas offline

```text
python3 -m unittest discover -s tests -v
python3 -m compileall catalog_assets tests
```

Usan `TemporaryDirectory` y transporte falso: no abren sockets ni consultan páginas reales.
