# Auditoría de fuentes EP y GAM — correctivo 317A

## Evidencia y alcance

Codex identificó estáticamente en el repositorio las entradas públicas ya documentadas: el catálogo oficial EP `https://ep-equipment.com/es/productos/` y la categoría EP de GAM Chile `https://online.gamrentals.com/cl/826-ep`. La investigación de Prompt 317 no alcanzó los orígenes porque el proxy devolvió 403 al túnel CONNECT; ese bloqueo no demuestra que las páginas estén caídas.

Para este correctivo, el usuario aportó una observación externa fechada 2026-09-16: GAM Chile ofrece 39 entradas EP repartidas en cuatro páginas (`/cl/826-ep` y `?page=2`, `?page=3`, `?page=4`). Esta observación es el seed auditable; Codex no la volvió a consultar por red.

## Universo inicial

El universo de venta queda limitado a esas 39 entradas de GAM Chile. EP oficial se usará localmente para confirmar cada modelo y preferir sus imágenes y fichas. Los modelos oficiales no ofrecidos por GAM quedan fuera de alcance y deberán registrarse como `OUT_OF_SCOPE_OFFICIAL`, nunca habilitarse automáticamente.

Hay 35 denominaciones concretas en `OBSERVED` y cuatro familias en `REVIEW`: `SERIE X2`, `SERIE X3`, `SERIE X5` y `SERIE F`. No se expanden a modelos. Se preservan `ESi161`, `KSi201` y las demás grafías proporcionadas. Para `EPT20-ET`, el seed conserva la evidencia de que “EPT20 ET” fue descrito en la página con guion.

## Artefactos revisables

`ep-model-inventory.csv` contiene las 39 entradas y usa `PENDING_LOCAL_HARVEST` en datos aún no observados. `ep-asset-candidates.csv` contiene una fila no habilitable por entrada para hacer explícita la recolección pendiente, sin inventar URL directa. `fuentes-ep-gam.csv` contiene 39 filas GAM deshabilitadas y contractualmente válidas; sus URLs son solo las cuatro páginas de listado proporcionadas, no activos específicos.

## Trabajo local de Franz

`harvest-ep --allow-public-network` recorrerá las cuatro páginas GAM, comparará el vivo con el seed sin borrar retirados, resolverá páginas individuales, buscará coincidencia exacta en el catálogo oficial EP y generará bajo `--root/_control` el inventario, los candidatos, la auditoría, el checkpoint y `fuentes.csv`. EP tiene prioridad 0; GAM prioridad 100 y solo se conserva para un tipo ausente en EP. Familias, coincidencias múltiples y activos sin validación quedan deshabilitados.

El checkpoint evita repetir listados y páginas de producto ya observadas; las escrituras son atómicas. La segunda ejecución sobre el mismo estado produce los mismos artefactos. La recolección no descarga activos finales: solamente HTML y, en una evolución controlada, comprobaciones binarias pequeñas permitidas.

## Seguridad y exclusiones

El comando exige consentimiento de red explícito y reutiliza validación contra credenciales, localhost y direcciones privadas, además de redirects validados, timeout, límites de página/modelo/tamaño y pausa configurable. No usa buscadores externos, cookies, login, CAPTCHA, APIs privadas ni JEM Nexus. LGMG y JLG quedan fuera de seed, consultas, destinos y salidas. GAM nunca es destino.

Durante Prompt 317A se usó exclusivamente transporte falso en pruebas: cero red real, cero imágenes o PDF descargados y cero binarios incorporados.
