# Auditoría CSS Frontend

**Fecha:** 2026-05-22  
**Repositorio auditado:** `web-ventas-generica` (raíz: `/workspace/web-ventas-generica`)

## 1) Confirmación del repo auditado
Se confirma que la auditoría corresponde al repositorio **web-ventas-generica** y su frontend en `frontend/`.

## 2) Archivos CSS revisados
Se revisaron los siguientes archivos en `frontend/src/styles/`:

- `admin-forms.css`
- `admin-layout.css`
- `admin-tables.css`
- `base.css`
- `buttons.css`
- `catalog.css`
- `forms.css`
- `hero.css`
- `home-sections.css`
- `product-card.css`
- `responsive.css`
- `topbar.css`
- `variables.css`

## 3) Resumen general del estado del CSS
Con base en los hallazgos del registro de auditoría previo:

- **Total de clases detectadas:** `311`
- **Clases potencialmente unused:** `35`
- Se detectó uso localizado de `!important` (principalmente en pricing, admin y ajustes puntuales de layout).
- Se observó concentración de media queries en ciertos archivos de alto tráfico visual (`home-sections.css`, `catalog.css`, `topbar.css`).

> Estado general: CSS funcional, pero con oportunidades claras de consolidación y reducción de deuda técnica **sin cambios inmediatos de borrado**.

## 4) Reglas con `!important` detectadas

### `frontend/src/styles/home-sections.css`
- Línea 1230: `color: var(--color-accent) !important;`
- Línea 1231: `font-size: clamp(0.72rem, 1.45vw, 0.96rem) !important;`
- Línea 1232: `font-weight: 900 !important;`
- Línea 1233: `line-height: 1.08 !important;`

### `frontend/src/styles/admin-forms.css`
- Línea 119: `display: flex !important;`
- Línea 122: `font-weight: 500 !important;`

### `frontend/src/styles/catalog.css`
- Línea 800: `display: flex !important;`

### `frontend/src/styles/product-card.css`
- Línea 151: `margin-top: auto !important;`
- Línea 159: `color: #111827 !important;`
- Línea 160: `font-size: clamp(1.35rem, 1.9vw, 1.95rem) !important;`
- Línea 161: `font-weight: 700 !important;`
- Línea 163: `line-height: 1.1 !important;`
- Línea 250: `font-size: clamp(1.2rem, 5.4vw, 1.5rem) !important;`

## 5) Riesgo por grupos de `!important`

- **Precios públicos:** riesgo **medio**. Puede estar resolviendo conflictos de especificidad entre `product-card`, catálogo y bloques de home. Borrarlo sin plan puede romper jerarquía visual de precio.
- **Preview admin:** riesgo **medio-alto**. El preview suele combinar estilos del frontend + contenedor admin; retirar `!important` puede desalinear vista previa.
- **Layout mobile:** riesgo **alto** si se toca junto con media queries. El layout responsivo depende de orden + especificidad.
- **Filtros:** riesgo **medio**. Cambios en `display`/alineación pueden romper flujo visual en ancho intermedio.
- **Checkboxes admin:** riesgo **medio**. Son sensibles a estilos de formularios base y utilidades.

## 6) Media queries detectadas por archivo

Conteo de `@media` por archivo:

- `home-sections.css`: **14**
- `catalog.css`: **5**
- `topbar.css`: **2**
- `admin-forms.css`: 2
- `forms.css`: 2
- `hero.css`: 2
- `admin-layout.css`: 1
- `admin-tables.css`: 1
- `base.css`: 1
- `product-card.css`: 1
- `buttons.css`: 0
- `responsive.css`: 0
- `variables.css`: 0

## 7) Evaluación de concentración de media queries

- **`home-sections.css` (14):** principal foco de complejidad responsiva. Alto riesgo de regresión visual si se reordena sin matriz de breakpoints.
- **`catalog.css` (5):** densidad media. Buen candidato para consolidar reglas repetidas de grid/filtros/cartas.
- **`topbar.css` (2):** concentración baja-moderada; revisar por interacción con navegación móvil y estados de menú.

## 8) Clases potencialmente no usadas
Del registro de auditoría previo, existen **35 clases potencialmente no usadas**. Deben tratarse como **hipótesis**, no como borrado directo.

## 9) Advertencia crítica
**No borrar automáticamente** clases marcadas como unused sin revisar previamente:

- referencias en TSX/JSX,
- clases dinámicas/condicionales,
- variantes de preview admin,
- comportamiento responsive por breakpoint.

## 10) Candidatas aparentes a limpieza futura
Candidatas mencionadas para validación manual de uso real:

- `hero-section__actions`
- `hero-section__badges`
- `hero-section__tag`
- `quote-cta`
- `quote-cta__actions`
- `benefits-grid`
- `category-card`
- `category-grid`

## 11) Propuesta de limpieza por fases

1. **Fase 1: eliminar CSS de bloques ya removidos visualmente** (solo tras confirmación en TSX + QA visual).
2. **Fase 2: consolidar precios** (normalizar tipografía, pesos y tamaños en catálogo/product card/home).
3. **Fase 3: consolidar botones** (unificar variantes y jerarquía visual).
4. **Fase 4: revisar media queries** (reducir duplicidad y ordenar breakpoints por responsabilidad).
5. **Fase 5: limpiar clases no usadas confirmadas** (eliminación final con checklist y validación responsive).

## 12) Recomendación de esta auditoría
**No borrar nada todavía.**

Primero validar cobertura real de clases en componentes, estados condicionales y vistas admin/mobile.

## 13) Próximo prompt sugerido para limpieza segura

> "Realiza limpieza CSS faseada en `frontend/src/styles` empezando por Fase 1 (bloques removidos visualmente), validando uso en TSX y clases condicionales. No tocar backend. No cambiar comportamiento funcional. Después de cada bloque: ejecutar `npm run build`, documentar diff y justificar cada eliminación."

---

### Nota de alcance
Esta tarea documenta formalmente la auditoría previa y **no elimina CSS**, **no modifica diseño funcional**, **no toca backend**, **no toca deploy** y **no altera datos**.

## Limpieza Fase 1

**Fecha:** 2026-05-22  
**Referencia:** limpieza conservadora inicial (bloques públicos removidos visualmente).

### Clases eliminadas (confirmadas sin uso en TSX/TS/JSX/JS)
- `home-block`
- `home-block--light`
- `category-grid`
- `category-card` (incluye `h3`, `span`, `:hover`)
- `benefits-grid` (incluye `li`)
- `quote-cta` (incluye ajuste responsive en `@media (max-width: 900px)`)
- `quote-cta__actions`
- `hero-section__badges`
- `hero-section__tag`
- `topbar__nav` (incluye `topbar__nav a` y estado activo en `buttons.css`)
- `topbar__seller-access`
- `topbar__whatsapp-mobile-only`
- `sidebar__meta`
- `hero-section__actions` (selector auxiliar en `buttons.css`)

### Clases revisadas pero conservadas
- `hero-badge`: se conserva por uso en preview admin (`.admin-promo-preview__badges .hero-badge`) y por posible reutilización de badges en contenido promocional.

### Motivo de conservación / pendientes
- Se evitó eliminar clases con posible impacto en preview admin o en rutas no incluidas en la Fase 1 cuando no eran parte de bloques públicos removidos.

### Confirmación de alcance seguro
- No se modificaron reglas con `!important`.
- No se tocaron estilos de precios públicos.
- No se alteró responsive complejo fuera de la remoción puntual de un bloque ya eliminado (`quote-cta`).
- No se tocaron componentes React, backend, auth, endpoints, cotizaciones ni deploy/Render.


## Limpieza Fase 2

**Fecha:** 2026-05-22  
**Objetivo:** consolidar estilos de precios públicos, botones y variables visuales sin rediseño ni cambios de layout.

### Reglas consolidadas
- Se consolidó el color de precios públicos usando `--color-public-price` y se mantuvo la base de pricing en `frontend/src/styles/product-card.css` para `.price--public`, `.home-product-price`, `.promo-product-card__price` y `.product-card__price` con `!important` en color/tamaño/peso/line-height.
- Se reutilizó la jerarquía textual con variables (`--color-primary-text`, `--color-secondary-text`) en cards y secciones home para evitar redefinir hex equivalentes.
- Se consolidó estilo visual de botones WhatsApp en variables (`--color-whatsapp`, `--color-whatsapp-hover`).
- Se normalizó la variante `.btn--secondary` para que reutilice la misma base visual de `.btn--ghost` sin alterar apariencia.

### Duplicados eliminados / reducidos
- Se reemplazaron valores hex repetidos en reglas de títulos/textos y botones por variables en `variables.css`.
- Se evitó replicar color de precio público en secciones individuales, manteniendo la fuente de verdad en `product-card.css`.

### Variables nuevas o reutilizadas
- Nuevas: `--color-primary-text`, `--color-secondary-text`, `--color-whatsapp`, `--color-whatsapp-hover`, `--color-public-price`.
- Reutilizadas: `--color-primary`, `--color-accent`, `--radius-button`, `--radius-block`, `--radius-card`.

### Reglas `!important` revisadas
- **Conservadas** en precios públicos de `product-card.css` (color/tamaño/peso/line-height y ajuste mobile de tamaño) para no arriesgar regresiones de especificidad en catálogo/home/preview admin.
- **Eliminadas:** ninguna en esta fase, por criterio de seguridad visual.

### Alcance y exclusiones confirmadas
- No se tocaron media queries complejas ni layout mobile de topbar/catálogo.
- No se tocaron previews admin estructuralmente, slots de promociones, drawers ni panel vendedor.
- No se modificó backend, auth, endpoints, deploy Render ni lógica funcional React.

## Limpieza Fase 3

**Fecha:** 2026-05-22  
**Objetivo:** consolidar media queries repetidas/conflictivas de forma segura en frontend público, sin rediseño.

### Media queries revisadas
- `home-sections.css`: `max-width: 640px`, `max-width: 768px`, `max-width: 900px`.
- `catalog.css`: `max-width: 560px` (equivalente de tramo mobile dentro del archivo; se mantuvo el resto de breakpoints propios del componente).
- `topbar.css`: `max-width: 768px` y `max-width: 1120px` (sin consolidación por no detectar duplicados seguros en esos bloques).

### Reglas consolidadas
- En `home-sections.css` se unificaron los dos bloques separados de `@media (max-width: 640px)` en un solo bloque para evitar fragmentación del tramo móvil.
- En `home-sections.css` se unificaron los dos bloques separados de `@media (max-width: 768px)` en un único bloque manteniendo el mismo contenido y orden lógico del componente.
- En `catalog.css` se consolidaron en un solo bloque `@media (max-width: 560px)` reglas que estaban distribuidas en tres bloques distintos (grid mobile, breadcrumb mobile y toolbar/paginación mobile), sin alterar valores.

### Reglas conservadas por riesgo
- Se conservaron sin cambios los bloques de `max-width: 900px` en `home-sections.css` por su interacción progresiva con `768px` y `640px`.
- Se conservaron sin cambios las media queries de `topbar.css` (`1120px` intermedio y `768px` móvil) por sensibilidad del layout fijo de navegación.
- No se movieron reglas de responsive de estos componentes a `responsive.css`; cada bloque se mantiene en su archivo dueño.

### Confirmación de no rediseño
- No se cambiaron colores, tamaños tipográficos, espaciados intencionales ni estructura visual.
- La intervención se limitó a agrupar bloques repetidos y mantener el mismo comportamiento responsive.
- No se tocó backend, deploy/Render, ni lógica funcional.
