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

La familia, una traducción sugerente y el sufijo del modelo no bastan. La clasificación usa evidencia estructural de cada ficha (por ejemplo, fuente de potencia, batería o voltaje). Primero se descubren las fichas y después se analizan individualmente. Con `--electric-only`, los eléctricos confirmados quedan en catálogo, los no eléctricos se contabilizan aparte y los inciertos permanecen en `review.csv` con `needs_review=true`. No se inventan equivalencias métricas/imperiales.

Antes de cualquier carga manual, el usuario debe revisar modelos, pares métrico/imperial, familias, especificaciones, clasificación y derechos. Los borradores conservan `published=false`, `featured=false`, `show_price=false` y `price=null`; no deben importarse directamente.

## Salidas

El directorio validado contiene:

- `discovery.json`: mecanismo, módulo, endpoint, parámetros, familias, páginas, enlaces rechazados, estado y motivo de detención;
- `discovery.csv`: una fila por hallazgo con orden, familia, página, procedencia, duplicado y rechazo;
- `families.csv`: familias, conteos, páginas, estado y advertencias;
- `catalog.json`, `catalog.csv`, `review.csv`, `errors.json` y `manifest.json`;
- `cache/` e `images/` (esta última puede permanecer vacía).

Las escrituras son atómicas y confinadas al output. El manifest 1.2.4 registra descubrimiento, clasificación y contadores; `jem_nexus_called=false` y `content_published=false` siempre. Las imágenes no se descargan por defecto. `--download-images` y `--download-datasheets` continúan separados del descubrimiento y requieren `--confirm-image-rights`; las fichas técnicas permanecen solo como metadatos.

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
