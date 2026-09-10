# Selección y materialización offline (v1)

Esta etapa consume exclusivamente manifests, relaciones, receipts, identidad, mapping físico y objetos SHA-256 locales. Sus gates separan validación técnica, autorización, asociación, elegibilidad, selección y materialización; `selected` nunca significa publicación, importación ni aprobación comercial. Cualquier schema, versión, hash, fingerprint, receipt, objeto o relación inconsistente bloquea el preflight antes de escribir.

La política categórica elige como principal una única imagen oficial EP específica: primero señal `hero`/`primary`, luego ordinal de galería 1 y finalmente la única EP elegible. Relations diferentes del mismo SHA-256 son un objeto; objetos distintos en un nivel empatan y requieren review. El host CDN no concede autoridad: esta procede de la relation y autorización EP. GAM nunca es primary automático y solo puede ser secundaria mediante aprobación externa auditable.

Tras excluir primary, se conservan hasta cuatro secundarias EP, deduplicadas por hash. Más de cuatro requieren ordinales completos, únicos y explícitos; sin ellos no se corta arbitrariamente. La ficha principal debe ser PDF EP seguro y `technical_sheet`, con precedencia explícita `es-419`, `es`, `en-001`/`en`. Empates o revisiones incomparables requieren review. GAM, brochures, manuales, otras fichas y documentos adicionales se conservan como supplemental/adicionales, nunca se reclasifican por filename.

Las aprobaciones son artefactos externos cerrados y ligados a policy, fingerprints, identidad, object, relation y evidencia. La CLI no ofrece `approve`; fixtures sintéticos no habilitan decisiones live y una aprobación jamás vuelve válidos bytes inválidos.

La categoría física es el árbol del catálogo fuente, no una categoría JEM Nexus. Se exige una primaria resuelta; las adicionales quedan en el manifest. El naming es una política genérica por brand code, filesystem model key Windows-safe, idioma y revisión probados. El source filename es solo metadata. No se inventan categorías ni sufijos de colisión.

El plan calcula todos los paths y colisiones case-insensitive antes de copiar. `materialize` exige fingerprint exacto, usa staging hermano, conserva bytes, revalida hash/tamaño y publica el árbol nuevo con rename. Un destino idéntico es idempotente; uno incompleto o distinto se bloquea sin reparar ni mezclar. `verify` detecta faltantes, extras y cambios, pero no repara ni borra. Los estados contemplados son `planned`, `blocked`, `staged`, `completed`, `already_complete`, `verification_failed` y `publish_failed`.

`catalog_select.py plan|select|materialize|verify` no importa transporte ni usa red/API. EP/GAM live siguen imposibles mientras sus contratos estén bloqueados. No se crea `producto.json`; normalización, categoría JEM, importación y publicación quedan pendientes para Prompt 280.
