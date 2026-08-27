# Extractor seguro del catálogo público LGMG

Herramienta aislada en Python 3 (solo biblioteca estándar) para preparar una muestra pequeña de metadatos públicos de LGMG para **revisión humana**. No importa a JEM Nexus, no publica, no consulta su API y no afirma precio, stock ni disponibilidad.

## Límites y robots.txt

- Solo acepta HTTPS, el host exacto `www.lgmglifts.com` y páginas `pro-list-*`/`pro-detail-*` bajo `/es/product/`.
- Opera secuencialmente, con pausa predeterminada de 1,5 s (mínimo 1,0), timeout de 20 s (5–60), dos reintentos, `Retry-After`, tres redirects y documentos HTML de hasta 5 MiB.
- El máximo predeterminado es cinco productos y el límite duro es 25. No rastrea el dominio.
- Cada ejecución registra que el operador debe verificar `robots.txt`. Si robots no está disponible por timeout/5xx, trabaje offline; ante 401/403 o una prohibición de `/es/product/`, no rastree.
- La falla de robots **no** concede autorización para reutilizar imágenes.

## Validación local en Windows PowerShell (solo metadatos)

El listado público depende de JavaScript. `--start-url` solo acepta enlaces dentro de la sección estructural `section.channel_content.pro_list` y nunca sustituye un listado vacío con enlaces globales, de navegación o relacionados. Si el contenedor estático está vacío, la ejecución registra `dynamic_listing_requires_seed`, recomienda `--seed-file` y termina con código distinto de cero. Mientras no exista descubrimiento estático confiable, use semillas revisadas manualmente:

```powershell
Set-Location "C:\Users\Franz\Desktop\web-ventas-generica"

$SeedPath = Join-Path $env:TEMP "jem-nexus-lgmg-seeds.txt"

@(
    "https://www.lgmglifts.com/es/product/pro-detail-2818.htm"
    "https://www.lgmglifts.com/es/product/pro-detail-1941.htm"
    "https://www.lgmglifts.com/es/product/pro-detail-4870.htm"
    "https://www.lgmglifts.com/es/product/pro-detail-5038.htm"
) | Set-Content -LiteralPath $SeedPath -Encoding utf8

$OutputPath = Join-Path $env:TEMP (
    "jem-nexus-lgmg-corrected-" + (Get-Date -Format "yyyyMMdd-HHmmss")
)

py -3 ".\tools\lgmg-catalog-extractor\extract_lgmg.py" `
    --seed-file $SeedPath `
    --output-dir $OutputPath `
    --max-products 4 `
    --electric-only

Write-Host "Resultados: $OutputPath"
```

Este ejemplo no descarga imágenes ni PDFs. La validación real de las cuatro fichas queda pendiente de ejecución local en Windows 11.

## Imágenes y fichas

Las imágenes se descargan únicamente si se entregan **ambas** opciones, y solo cuando exista autorización comercial suficiente:

```powershell
py -3 ".\tools\lgmg-catalog-extractor\extract_lgmg.py" `
  --start-url "https://www.lgmglifts.com/es/product/pro-list-377.htm" `
  --output-dir $OutputPath `
  --max-products 5 `
  --electric-only `
  --download-images `
  --confirm-image-rights
```

Se verifica firma del archivo, límite de 15 MiB, SHA-256, duplicados, nombre sanitizado y redirects. No se hotlinkea, transforma ni publica. `--download-datasheets` exige la misma confirmación, pero en esta versión la descarga continúa deshabilitada: solo se registran URL, nombre, formato, idioma aparente y revisión pendiente.

## Parsing, nomenclatura y clasificación

`HTMLParser` mantiene una pila estructural. Separa el `<title>` documental del título visible `.pro_detail01 .infor .tit`; contrasta este último con `table.datalist` y el `span` final de `crumbs`. La categoría procede exclusivamente del último enlace `pro-list-*` válido del breadcrumb. Los pares métrico/imperial, incluidos números romanos Unicode, se conservan como una sola entidad y cualquier discrepancia estructurada exige revisión. Solo recoge imágenes de `.pro_detail01 .right_r .ul_box` y `.pro_detail02 .right_b.imgZoom`, y PDFs del bloque `new_box` titulado `Ficha técnica`. Nunca se usa el identificador numérico de la URL como modelo.

La clasificación eléctrica requiere texto o estructura sobre electricidad, batería, voltaje o fuente de potencia; el sufijo `E` por sí solo no sirve. Las especificaciones conservan nombre y valores fuente, y solo reciben una de las claves controladas documentadas en el código. No se convierten unidades ni se copian descripciones comerciales largas.

Las imágenes siguen sin descargarse por defecto. No existe integración con JEM Nexus y ningún resultado debe importarse sin revisión humana.

El borrador JEM Nexus siempre usa `published=false`, `featured=false`, `show_price=false`, `price=null` y `stock_status=on_request`. No incluye categoría interna, proveedor, año, SKU, capacidad inferida ni certificaciones no confirmadas. **Está prohibido importar estos resultados directamente a producción.**

## Salidas y seguridad

El directorio solicitado contiene `catalog.json`, `catalog.csv`, `review.csv`, `manifest.json`, `errors.json`, `cache/` e `images/`. JSON conserva la estructura completa; `catalog.csv` facilita comparación y `review.csv` prioriza ambigüedades. El manifest registra procedencia, UTC, límites, conteos, errores, hashes y las confirmaciones de que no hubo llamada a JEM Nexus ni publicación.

Las escrituras usan temporales y reemplazo atómico; rechazan destinos amplios, la raíz del repositorio y symlinks. El caché usa SHA-256 de la URL. Una interrupción conserva únicamente archivos ya completos. Use un output dedicado vacío o generado previamente por esta herramienta; no lo mezcle con archivos ajenos.

## Pruebas y solución de problemas

Las pruebas usan exclusivamente HTML sintético y no hacen red:

```powershell
py -3 -m unittest discover ".\tools\lgmg-catalog-extractor\tests" -v
```

- `URL rechazada`: compruebe HTTPS, host exacto y patrón oficial.
- Sin enlaces: revise la advertencia de JavaScript y use `--seed-file` revisado manualmente.
- 401/403/429: detenga la ejecución; no intente evadir el bloqueo.
- Clasificación nula o `needs_review=true`: contraste encabezado y ficha oficial antes de cualquier importación.
- Caché desactualizado: use `--refresh-cache`, manteniendo los límites de red.
- `Ctrl+C`: vuelva a ejecutar con el mismo output para reutilizar la caché y archivos completos.

Opciones completas: `--start-url`, `--seed-file`, `--output-dir`, `--max-products`, `--electric-only`, `--delay-seconds`, `--timeout-seconds`, `--download-images`, `--download-datasheets`, `--confirm-image-rights`, `--refresh-cache` y `--user-agent`.
