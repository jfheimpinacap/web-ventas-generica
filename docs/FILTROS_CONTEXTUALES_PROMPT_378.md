# Filtros contextuales del catálogo — PROMPT 378

## Contexto y fuente de datos

`CatalogPage` resuelve un contexto mediante `resolveCatalogContext` y entrega a
`Layout`/`Sidebar` las mismas selecciones, categorías y facetas que usa el listado.
La configuración comercial recibida desde `AppRouter` conserva la prioridad para
el tipo y la condición fija. El panel no vuelve a inferirlos desde el pathname.

En `/catalogo`, una categoría por ID o slug se resuelve hasta su raíz activa. Se
mantienen las subcategorías hermanas en el árbol, independientemente de qué hojas
estén seleccionadas. Sin categoría ni tipo se conserva el catálogo general.
También se admite el enlace legado `product_type`. Categorías incompatibles con
el contexto o no disponibles públicamente no se convierten en opciones laterales.

Se usa exclusivamente `GET /api/public/products/` mediante `getProducts`, junto
con las lecturas públicas existentes de categorías y marcas. La consulta de
productos contiene tipo, condición fija y búsqueda; no envía las selecciones de
checkboxes ni la ordenación. La API ya devuelve la lista completa antes de paginar.
La búsqueda sigue en el backend para preservar sus coincidencias en descripción
completa y SKU de repuestos, datos que no están en el DTO público del listado.

`useCatalogProducts` espera las categorías antes de descargar datos, comparte
promesas en curso y conserva hasta ocho consultas durante el montaje del catálogo.
Cambiar checkboxes u ordenación no descarga productos de nuevo. Cambiar la
búsqueda o las restricciones fijas puede requerir una consulta pública nueva.
Las respuestas de efectos anteriores no actualizan el estado actual y un cambio
de clave oculta sincrónicamente el conjunto anterior antes del siguiente efecto.

No hay cambios de backend, contratos HTTP, esquema ni migraciones.

## Selección y URL

Los grupos discretos son `category`, `brand`, `condition` y `stock_status`.
Dentro de un grupo se aplica OR; entre grupos, AND. Un grupo vacío no restringe.
La condición fija del contexto se aplica siempre, fuera de las selecciones.

Se escribe una sola clave por grupo, con valores separados por comas:

```text
/maquinaria-nueva?category=61,62&brand=1,2&stock_status=available,on_request
/catalogo?catalog_root=6&category=611,612&brand=1
```

Los IDs de estos ejemplos son ilustrativos. `URLSearchParams` puede serializar
las comas como `%2C`; ambas formas tienen el mismo significado. La lectura acepta
una selección individual, listas y claves repetidas (`brand=1&brand=2`), elimina
duplicados y admite los slugs individuales existentes de categorías y marcas.
Las categorías y marcas reconocidas se normalizan a IDs al editar su grupo.

`catalog_root` identifica el contexto de `/catalogo`, no una subcategoría marcada.
Se agrega al cambiar o limpiar filtros cuando la entrada original tenía una
categoría raíz implícita. Al desmarcar la última hoja se conserva esa raíz y sus
alternativas. Un enlace individual a la propia raíz abre ese contexto sin
restringir el grupo; una raíz incluida junto con otras categorías sigue formando
parte del OR y abarca todos sus descendientes válidos.

Se mantienen los parámetros ajenos y los demás grupos. Se elimina `page` al
cambiar filtros; la paginación local vuelve a uno ante cambios de ruta/query.
La URL es la fuente de selección para recarga y navegación atrás/adelante.
`min_price` y `max_price`, si están presentes, se aplican a precios visibles tanto
en resultados como en contadores. No se agregan controles de rango decorativos.

Limpiar elimina selecciones, búsqueda, rangos y página. Conserva ordenación,
parámetros ajenos, contexto anclado y el tipo legado. Las restricciones comerciales
se vuelven a obtener de la configuración, aunque la URL intente contradecirlas.
Las vistas con `catalog_root` o rangos se marcan como filtradas para SEO.

## Cantidades

`contextProducts` aplica las restricciones del contexto, deduplica por ID y
conserva las reglas de visibilidad pública: publicado, categoría activa, marca
activa o ausente y stock distinto de vendido. La API pública ya impone esas reglas.

`filterCatalogProducts` es el mismo filtro usado por resultados y facetas. Para
contar una opción se omite el grupo al que pertenece, se mantienen los demás
grupos y rangos, y se cuenta su coincidencia sobre el conjunto completo recibido
para contexto y búsqueda. La paginación se realiza después, en `CatalogPage`.
Una categoría incluye sus descendientes activos con conjuntos de IDs y recorridos
que terminan ante ciclos. Los productos se cuentan una sola vez.

Las categorías pertenecen al árbol del contexto. Las marcas, condiciones y estados
se obtienen del conjunto público base para contexto y búsqueda, no de las tarjetas
paginadas ni del resultado ya filtrado por checkboxes. Las selecciones permanecen
como opciones desmarcables aunque otro grupo reduzca su contador a cero. Una marca
seleccionada sin productos en el contexto conserva su etiqueta pública si existe.

Durante carga/error se muestran mensajes y `…`, sin presentar ceros como cantidades
válidas ni reutilizar cantidades de un contexto anterior.

## Panel, movimiento y accesibilidad

El título contextual se muestra en escritorio y móvil. Maquinarias empieza en
«Tipo de maquinaria», sin ramas de Repuestos/Servicios, texto «Vista» ni sección
editable de condición fija. Las filas usan checkbox, etiqueta y cantidad; las
flechas de expansión tienen botones independientes.

Se conserva el reductor del PROMPT 377 para una sección principal y una rama por
nivel. La inicialización admite el ID normalizado después de la carga de datos,
se hace una sola vez y no sobrescribe las decisiones manuales. El panel se reinicia
al cambiar el contexto principal, no al marcar opciones del mismo contexto.

`Collapsible` mantiene los hijos montados y anima una pista de CSS Grid de `0fr`
a `1fr` durante 200 ms. No usa una altura máxima de lista. El contenido cerrado
recibe `inert` y `aria-hidden` inmediatamente; la visibilidad se retrasa durante
el cierre. El contenedor interior recorta la transición sin crear otro scroll
visible. Solo `.sidebar__panel` desplaza verticalmente y sus secciones no encogen.

Se mantienen labels, `aria-controls`/`aria-expanded`, foco visible, Escape y
retorno del foco al cerrar en móvil. El cajón móvil usa opacidad/desplazamiento
durante 200 ms y queda inerte cuando está cerrado. `prefers-reduced-motion`
desactiva las transiciones y usa desplazamientos inmediatos.

## Validación pendiente en Windows

Por instrucción del PROMPT 378, en Codex no se ejecutaron instalaciones, restore,
pruebas, compilaciones ni servidores. La revisión realizada es estática y con
`git diff --check`; esto no demuestra que la aplicación compile o pase pruebas.

Se conservaron sin cambios los ocho casos de `tests/sidebar-menu.test.mjs` y se
añadieron diecinueve casos de comportamiento en `tests/catalog-filters.test.mjs`.
El script existente `test:sidebar-menu` incluye ambos archivos, sin dependencias
nuevas. Con las dependencias locales disponibles, ejecutar desde `frontend`:

```powershell
npm run test:sidebar-menu
npm run test:api-url
npm run build
```

En el entorno local de Windows, verificar visualmente y con la pestaña Network:

1. Las cuatro rutas comerciales, `/catalogo` general, categoría por ID/slug y
   selección profunda; confirmar títulos, exclusiones y restricciones al limpiar.
2. Marcar varias subcategorías y marcas, mezclar stock/condición editable, llegar
   a cero resultados y recuperar al desmarcar; contrastar cantidades con todo el
   conjunto público, incluyendo más de doce productos y categorías profundas.
3. Paginación seguida de un cambio de filtro/rango; recarga y atrás/adelante;
   parámetros ajenos, slugs y enlaces individuales existentes.
4. Confirmar que marcar checkboxes no crea nuevas peticiones de productos y que
   resultados/contadores no retroceden por respuestas fuera de orden al cambiar
   rápidamente de búsqueda/contexto, usando latencia artificial del navegador.
5. Interceptar fallos de las lecturas públicas; verificar mensajes, ausencia de
   cantidades antiguas/ceros ficticios y selecciones todavía desmarcables.
6. Escritorio y móvil, listas largas, nombres extensos, zoom, una sección abierta,
   hermanos por nivel, cierre suave, un solo scroll y acceso a Limpiar filtros.
7. Teclado, foco, Escape y retorno al botón móvil; confirmar que los controles
   cerrados no reciben Tab, también durante el cierre y con movimiento reducido.

No se realizó validación visual ni conexión al entorno publicado.
