# Auditoría de preparación para producción — Prompt 344

> Fuente de verdad estática para preparar las etapas siguientes. Fecha de auditoría: 2026-09-22. Este documento deliberadamente no contiene secretos ni confirma el estado actual de producción.

## 1. Identificación del repositorio y HEAD auditado

| Campo | Estado | Evidencia |
|---|---|---|
| Directorio | `CONFIRMADO` | `/workspace/web-ventas-generica` |
| Rama | `CONFIRMADO` | `work` |
| Árbol inicial | `CONFIRMADO` | Limpio antes de crear este informe (`git status --porcelain=v1` sin salida). |
| HEAD base | `CONFIRMADO` | `387034342ef010c17bed18b12fc5fee47ecdcca2` — `Merge pull request #470 from jfheimpinacap/codex/robustecer-prueba-de-formulario-de-usuarios`. |
| Instrucciones de agentes | `CONFIRMADO` | No se encontró ningún `AGENTS.md` aplicable en los directorios inspeccionados. |

El historial reciente integra semánticamente los Prompts 328–343 o sus implementaciones equivalentes: importación EP y correcciones de reanudación; filtros/miniaturas; permisos granulares; administración de roles, permisos y usuarios; aplicación de permisos al panel; ajustes visuales; emisión de cotizaciones por superadministrador con actor separado; toasts globales; y robustecimiento de sus pruebas. La evidencia son los merges `#450` a `#470` y sus commits funcionales, entre ellos `1e7f31d`, `4789040`, `5f39896`, `7d770f3`, `ea7264d`, `123394f`, `5b31737` y `72375bc`.

**Conclusión del precheck:** `CONFIRMADO`; no apareció una razón para detener la auditoría. Esto confirma código local, no producción.

## 2. Alcance y exclusiones

Esta fue una auditoría estática y de solo lectura operacional del repositorio. Se inspeccionaron código, configuración, documentación, migraciones, snapshot, scripts y herramientas; únicamente se creó este informe.

No se accedió a producción, Plesk, servidores ni bases; no se usó red pública, localhost, APIs o tokens; no se iniciaron servidores; no se aplicaron migraciones; no se modificaron cuentas ni datos; no se ejecutó el importador EP; no se publicaron artefactos; no se generaron ZIP, `publish` o `dist`; y no se ejecutaron restore, build, tests, TypeScript, Node, Vite, SSR ni prerender.

Las afirmaciones históricas sobre Plesk presentes en documentos anteriores son antecedentes, **no evidencia vigente**. Todo estado productivo queda `PENDIENTE DE PRODUCCIÓN` hasta comprobarlo en una ventana aprobada.

## 3. Estado confirmado del código

- `CONFIRMADO`: backend ASP.NET Core Web API sobre .NET 8, EF Core y SQL Server; frontend React 18, TypeScript y Vite.
- `CONFIRMADO`: roles `seller` y `support_admin`; catálogo fuente con 29 permisos concedibles a vendedores y `users.manage` reservado. El backend valida permisos, y las rutas administrativas de usuarios requieren `support_admin`.
- `CONFIRMADO`: administración de usuarios crea/edita y “elimina” mediante desactivación reversible; impide desactivar la sesión actual y el último superadministrador activo; cambios sensibles revocan refresh tokens.
- `CONFIRMADO`: cotizaciones guardan vendedor responsable y actor emisor por separado; `support_admin` puede seleccionar un vendedor.
- `CONFIRMADO`: UI contiene permisos por ruta/acción, menú de usuarios condicionado, filtros y miniaturas, ajustes visuales de Usuarios y toasts globales de mutaciones administrativas.
- `CONFIRMADO`: health disponible en `/`, `/health` y `/api/health`; CORS, JWT, HTTPS/HSTS en producción, rate limiting, SMTP y almacenamiento local están configurados en código.
- `RIESGO`: la cadena de conexión cae a LocalDB cuando falta configuración. En producción debe verificarse explícitamente la variable SQL antes de arrancar.
- `RIESGO`: `LocalTechnicalSheetStorage` siempre usa `<ContentRoot>/uploads/technical-sheets`, mientras imágenes sí respetan `Uploads:RootPath`; por tanto deben respaldarse y preservarse ambas ubicaciones efectivas.
- `RIESGO`: no hay workflows versionados en `.github/workflows`; generación y promoción de artefactos son manuales y requieren trazabilidad externa.

## 4. Evidencia de validaciones locales conocidas

Estado informado y aceptado como contexto del Prompt, **no reejecutado en esta auditoría**:

| Validación | Resultado conocido | Estado de esta auditoría |
|---|---:|---|
| Backend | 446/446 | `CONFIRMADO` como antecedente; no ejecutado ahora |
| Toasts administrativos | 10/10 | `CONFIRMADO` como antecedente; no ejecutado ahora |
| Permisos administrativos | 10/10 | `CONFIRMADO` como antecedente; no ejecutado ahora |
| API frontend | 6/6 | `CONFIRMADO` como antecedente; no ejecutado ahora |
| TypeScript, Vite, SSR y prerender | aprobados | `CONFIRMADO` como antecedente; no ejecutado ahora |
| Migraciones locales | aplicadas y verificadas | `CONFIRMADO` solo para local; producción desconocida |

Estas evidencias no sustituyen la reproducción controlada de artefactos ni los smoke tests productivos.

## 5. Inventario de despliegue existente

| Elemento inspeccionado | Hallazgo |
|---|---|
| Guías | `README.md`, `backend-dotnet/README.md`, `frontend/README.md` y documentos Plesk/SQL/rotación en `docs/`. Algunas secciones productivas son históricas y deben revalidarse. |
| Backend | `JemNexus.sln`, proyectos API/tests, `Program.cs`, opciones, servicios de archivos, `appsettings.json` y Development. |
| Publicación | `scripts/publish-plesk.ps1` restaura, compila, prueba y publica; `scripts/package-plesk.ps1` empaqueta y valida, excluyendo normalmente `web.config`, logs y `.env*`/`*.local`. Ninguno despliega remotamente. |
| Plesk | `env.plesk.example.txt` sin valores reales y documentación manual. No existe configuración productiva versionada ni debe existir. |
| Frontend | `package.json`, lockfile, `vite.config.ts`, `.env.example`, resolución de API y scripts de SSR/prerender/validación. |
| Persistencia | Imágenes bajo `Uploads:RootPath` o fallback `<ContentRoot>/uploads`; fichas bajo `<ContentRoot>/uploads/technical-sheets`; DB conserva rutas/claves. |
| Estáticos | Medios se sirven mediante endpoints de la API, no por `UseStaticFiles`; frontend `public/` se copia a `dist`. |
| Secretos | `.env` local y outputs se ignoran; `web.config` productivo queda en Plesk y se excluye del ZIP normal. |
| Importación EP | `tools/catalog-assets` aporta importador local y `tools/catalog-pipeline` contratos/checkpoints/receipts. No es un importador productivo listo para ejecutar sin adaptación y aprobación. |
| SQL/migraciones | Migraciones EF, snapshot, SQL y guías históricas. Los SQL históricos no cubren necesariamente todas las migraciones actuales. |
| CI/CD | `RIESGO`: no se encontraron workflows; no hay despliegue automático reproducible en el repositorio. |

## 6. Matriz de configuración sin secretos

“Origen Plesk” describe dónde debe administrarse el valor, no confirma su existencia.

| Configuración | Capa | Necesidad | Entorno | Origen esperado en Plesk | Riesgo si falta/incorrecta | Validación segura |
|---|---|---|---|---|---|---|
| `ASPNETCORE_ENVIRONMENT=Production` | Backend | Obligatoria operativamente | Producción | Variable IIS/Plesk | JWT podría usar comportamiento no productivo; Swagger/excepciones/HSTS cambian | Inspeccionar nombre, no valor secreto; `/health` debe informar `Production` |
| `ConnectionStrings__DefaultConnection` | Backend | Obligatoria | Producción | Variable protegida IIS/Plesk | Fallback LocalDB, fallo de arranque/acceso o base equivocada | Revisar destino en canal seguro; consulta read-only de `DB_NAME()` e historial, sin copiar cadena |
| `Jwt__Secret` **o** `JWT_SECRET` | Backend | Obligatoria | Producción | Secreto IIS/Plesk | Arranque falla explícitamente; tokens inválidos | Confirmar presencia/longitud por operador; login/refresh controlados, sin mostrar valor |
| `Jwt__Issuer` o `JWT_ISSUER` | Backend | Obligatoria funcionalmente | Ambos | Variable o base revisada | Tokens emitidos/rechazados con issuer erróneo | Comparar metadato aprobado; login + `/api/auth/me` |
| `Jwt__Audience` o `JWT_AUDIENCE` | Backend | Obligatoria funcionalmente | Ambos | Variable o base revisada | Tokens rechazados | Igual que issuer |
| `Jwt__AccessTokenMinutes` | Backend | Opcional con default | Ambos | Variable IIS/Plesk si se sobrescribe | Sesiones demasiado cortas/largas | Revisar entero dentro de política; comprobar expiración sin registrar token |
| `Jwt__RefreshTokenDays` | Backend | Opcional con default | Ambos | Variable IIS/Plesk si se sobrescribe | Retención/sesión inadecuada | Revisar entero y política |
| `Cors__AllowedOrigins__*` / `FRONTEND_ORIGINS` | Backend | Obligatoria funcionalmente | Producción | Preferir `FRONTEND_ORIGINS` en IIS/Plesk | Bloqueo del frontend o exposición a origen no aprobado | Preflight desde dominios aprobados y uno rechazado |
| `RateLimiting__Enabled` y las diez reglas (`PermitLimit`, `WindowSeconds`) | Backend | Reglas obligatorias; defaults versionados | Ambos | `appsettings.json` o overrides Plesk | Valores ausentes/no positivos impiden arranque; límites erróneos afectan disponibilidad/abuso | Revisar claves y enteros; smoke controlado de 429, sin carga agresiva |
| `Email__SmtpHost`, `SmtpPort`, `Username`, `Password`, `FromAddress`, `FromName`, `Security`/`UseSsl`, `TimeoutSeconds` | Backend | Obligatoria solo para envío/notificación | Producción | Variables jerárquicas IIS/Plesk; password secreto | Notificaciones fallan o SMTP inseguro | Test de notificación autorizado a destinatario controlado; logs redactados |
| `QuoteNotifications__Recipients` | Backend | Obligatoria si se notifican cotizaciones | Producción | Variable IIS/Plesk | Cotizaciones sin aviso o fuga a destinatarios erróneos | Revisar lista por doble control; test controlado |
| `Frontend__BaseUrl` | Backend | Obligatoria para enlaces en correo | Producción | Variable IIS/Plesk | Enlaces ausentes o a host erróneo | Inspeccionar enlace de correo de prueba controlado |
| `Uploads__RootPath` | Backend/imágenes | Obligatoria operativamente | Producción | Ruta absoluta Plesk fuera del reemplazo | Escritura falla o publicación sobrescribe multimedia | Verificar ruta/permisos y archivo de prueba reversible; confirmar backup |
| `Uploads__PublicBasePath` | Backend/imágenes | Opcional con `/media` | Ambos | Config o variable Plesk | URLs y lookup incompatibles | Leer una imagen existente y confirmar URL relativa |
| `Uploads__AllowedExtensions`, `MaxFileSizeMb` | Backend/imágenes | Opcional con defaults | Ambos | Config/override Plesk | Rechazos inesperados o superficie de ataque | Revisar política; cargas pequeñas controladas válidas/inválidas |
| Raíz de fichas `<ContentRoot>/uploads/technical-sheets` | Backend | Obligatoria operativamente, no parametrizada | Producción | Carpeta persistente y ACL de Plesk | Pérdida/fallo de fichas al reemplazar backend | Confirmar ruta física, ACL, backup y descarga read-only |
| `SeedUsers__*` | Backend | Opcional y temporal | Local/producción solo bajo plan | Variables Plesk efímeras | Creación/reset accidental; credenciales persistentes en config | Por defecto ausentes; si se usan, doble control, reinicio, validación y retiro inmediato |
| `PUBLIC_SITE_URL` | Backend/documentación | `PENDIENTE`: documentada, no se halló consumo actual | Producción | No configurar sin confirmar necesidad | Configuración inerte/confusa | Buscar consumo en versión exacta antes de aprobar |
| `VITE_API_BASE_URL` | Frontend (build-time) | Obligatoria en producción | Build producción | Entorno de build, no runtime Plesk salvo build allí | Sin valor usa localhost y rompe producción | Inspeccionar bundle/artefacto sin solicitar localhost; smoke de API |
| `VITE_PUBLIC_SITE_URL` | Frontend (build-time) | `RIESGO`: ejemplo/documentación; canonical está fijado en lógica de prerender | Build | Entorno de build | Expectativa falsa de parametrización | Inspección estática de HTML prerender y canonicals |
| `VITE_WHATSAPP_NUMBER` | Frontend (build-time) | Opcional con fallback | Build | Entorno de build | Contacto incorrecto | Revisar UI con valor aprobado, sin exponer datos privados |
| `VITE_CONTACT_EMAIL` | Frontend (build-time) | Opcional con fallback | Build | Entorno de build | Contacto incorrecto | Revisar UI/artefacto |
| `VITE_GTM_ID` | Frontend (build-time) | Opcional | Build | Entorno de build | Analítica ausente o enviada a propiedad errónea | Revisar ID con propietario; inspección de tag, sin datos personales |
| Proxy, HTTPS, `web.config`, app pool y `stdoutLogEnabled=false` | Hosting | Obligatoria | Producción | Plesk/IIS | 500.30, loops HTTPS, secretos/logs expuestos | Inspección manual redactada; headers y `/health` |

## 7. Inventario y orden de migraciones

Orden canónico por identificador (debe contrastarse con `__EFMigrationsHistory` y objetos reales):

1. `20260603182917_InitialCommercialSchema`
2. `20260604020543_AddAuthUsersAndAuditRelations`
3. `20260616000000_AddCategoryProductType`
4. `20260619000000_AddProductPriceDisplayFields`
5. `20260619010000_EnsureCanonicalRootCategories`
6. `20260803000000_AddMachineryTechnicalData`
7. `20260803010000_AddTechnicalSheets`
8. `20260810080000_AddProductTechnicalSheetAssociation`
9. `20260811000000_AddStructuredMachineryTechnicalData`
10. `20260812000000_AddProductMachineWeight`
11. `20260816000000_AddSellerCodes`
12. `20260817000000_AddCustomerProfiles`
13. `20260817010000_AddCommercialQuotes`
14. `20260818010000_AddCommercialQuoteIssuanceAndFolios`
15. `20260822000000_AddRefreshTokenRotation`
16. `20260822010000_AddRefreshTokenPasswordVersion`
17. `20260822020000_AddCommercialQuoteIssueIdempotency`
18. `20260824010000_AddSellerContactQuoteSnapshots`
19. `20260825010000_AddCustomerProfileStatus`
20. `20260830000000_PreserveQuotesWhenDeletingProducts`
21. `20260917000000_AddGranularSellerPermissions`
22. `20260922000000_AddCommercialQuoteIssuedBy`

El snapshot actual incluye permisos por usuario e `IssuedBy`; no fue modificado.

### Riesgos y dependencias relevantes

- Auth crea `AppUsers` y refresh tokens; auditorías usan FKs `NoAction`, mientras refresh tokens dependen por cascada del usuario.
- `AddSellerCodes` crea secuencia, backfill ordenado, índice único filtrado y check rol/código. Requiere roles válidos; cambiar roles debe respetar el constraint.
- Cotizaciones dependen de clientes, usuarios y productos. Items dependen por cascada de la cotización; desde `PreserveQuotesWhenDeletingProducts`, producto queda nullable/`SetNull` para preservar historia.
- Folios e idempotencia agregan índices únicos; snapshots de contacto hacen backfill desde usuario.
- Migraciones que alteran/droppean columnas en `Down` pueden perder información. Restaurar backup es preferible a bajar schema con datos nuevos.

### `AddGranularSellerPermissions`

`CONFIRMADO`: crea `AppUserPermissions` con PK compuesta `(UserId, Permission)`, FK a `AppUsers` con `Cascade` y longitud 80. Luego inserta **los 29 permisos concedibles vigentes al compilar la migración** para cada usuario cuyo rol sea `seller`, evitando duplicados.

Precondiciones: auth aplicada, `AppUsers` existente, roles coherentes, backup, SQL generado para el intervalo exacto revisado y estado real reconciliado. Post-check: migración registrada; tabla/PK/FK presentes; exactamente el conjunto esperado por seller; ningún `users.manage`; `/api/auth/me` refleja permisos. `Down` borra toda la tabla y todas las concesiones: `RIESGO` de pérdida de personalizaciones; no usar como rollback tras cambios de permisos sin exportación/restauración.

### `AddCommercialQuoteIssuedBy`

`CONFIRMADO`: agrega `IssuedById` nullable, lo rellena desde `ResponsibleSellerId`, lo vuelve no nulo, crea índice y FK a `AppUsers` con `NoAction`. Debe ejecutarse después de todas las anteriores, particularmente cotizaciones/usuarios y permisos.

Precondiciones: cada cotización debe tener `ResponsibleSellerId` válido; backup; ausencia de filas huérfanas; SQL exacto revisado. Post-check: cero nulos/huérfanos, FK/índice presentes, historia previa conserva `IssuedById = ResponsibleSellerId`, emisiones nuevas distinguen actor y responsable. `Down` elimina la columna y destruye auditoría del emisor: `BLOQUEANTE` para rollback destructivo si ya hay nuevas cotizaciones. Ante incompatibilidad, preferir roll-forward o restauración coordinada de DB + código + archivos al mismo punto.

### Aplicación

`PENDIENTE DE PRODUCCIÓN`: no se sabe qué migraciones están pendientes. Antes de GO, consultar read-only `__EFMigrationsHistory` **y** objetos/constraints reales (documentación histórica advierte que el historial aislado pudo quedar inconsistente), generar SQL idempotencia/intervalo exacto, revisarlo por dos personas y aplicarlo bajo transacción/backup según capacidad del script. Nunca inferir desde local ni ejecutar `dotnet ef database update` directamente contra producción.

## 8. Separación entre código y datos

### A. Transportado por artefactos de código

- DLLs/dependencias/configuración base del backend y definiciones de migración (no su aplicación).
- Bundles, HTML prerender, assets públicos e interfaz del frontend.
- Lógica de JWT, permisos/validaciones, rutas y acciones administrativas, usuarios, toasts y cotizaciones con `ResponsibleSellerId`/`IssuedById`.

### B. No transportado automáticamente

- Base productiva: usuarios, roles/permisos asignados, hashes/contraseñas, sesiones, códigos de vendedor, productos EP, cotizaciones y migraciones aplicadas.
- Imágenes, fichas técnicas y cualquier multimedia persistente.
- Checkpoints, receipts, IDs, fingerprints y resultados locales de importación.
- `web.config`, secretos, variables IIS/Plesk, certificados, proxy, bindings, ACL, app pool y configuración SMTP.

**`BLOQUEANTE`: desplegar código no copiará automáticamente la base local ni sus archivos multimedia.** Tampoco debe intentarse copiar la base local como mecanismo de normalización.

## 9. Plan de usuarios de producción (no ejecutar aquí)

Objetivo aprobado por negocio, sujeto a conciliación: `supadmin` → `support_admin`; `jmateluna` y `fheim` → `seller`.

1. `PENDIENTE DE PRODUCCIÓN`: exportar inventario read-only de ID, username, rol, activo, código de vendedor, relaciones históricas y permisos; buscar explícitamente `supadmin`, `jmateluna`, `fheim` y posible `soporte`.
2. Mapear por **ID y relaciones**, no solo nombre. Si `soporte` tiene historia, preferir renombrar/cambiar rol cuando preserve identidad; crear otra cuenta solo si se demuestra que son personas distintas. Nunca borrar físicamente una cuenta relacionada.
3. Confirmar al menos dos caminos de recuperación de superadministrador durante el cambio. El backend impide desactivar la sesión actual y el último superadministrador activo; planificar un segundo admin temporal controlado si fuese necesario.
4. Para sellers, dejar que el backend asigne códigos únicos mediante la secuencia; no inventar ni reutilizar códigos. Conciliar duplicados/constraints antes del cambio.
5. Asignar solo permisos del catálogo concedible aprobado; verificar los 29 disponibles y negar `users.manage`. Un `support_admin` obtiene acceso por rol y no guarda concesiones seller.
6. Establecer contraseñas nuevas aleatorias mediante canal seguro y entrega fuera de tickets/docs; exigir cambio organizacional si aplica. No usar ejemplos reutilizables.
7. Toda modificación de contraseña, rol, permisos o estado debe revocar sesiones; confirmar refresh tokens revocados. Retirar inmediatamente variables `SeedUsers__*Password` si excepcionalmente se usaron.
8. Desactivar reversiblemente cuentas sobrantes (incluida `soporte` solo tras aprobar el mapeo), nunca delete físico; registrar responsable, motivo y hora.
9. Validar por cuenta: login, refresh y `/api/auth/me`; identidad/rol/código/permisos; `supadmin` ve Usuarios, sellers no; 401/403 esperados. Cerrar sesiones de prueba.

`BLOQUEANTE`: no proceder sin saber qué cuenta productiva existente posee las relaciones históricas y sin recuperación comprobada del superadministrador.

## 10. Plan separado del catálogo EP

Este plan es posterior e independiente del despliegue de código:

1. Backup SQL y de las dos áreas multimedia; inventario read-only del catálogo productivo, slugs/SKU/IDs, imágenes, fichas y asociaciones.
2. Preparar un **nuevo** paquete/dry-run ligado al endpoint y snapshot de producción aprobados. No reutilizar IDs, checkpoint, autorización, receipt ni fingerprint locales.
3. Generar checkpoint productivo aislado, registrar hashes/fingerprint/versión/operador y reconciliar conflictos con IDs existentes. Mantener exclusión permanente de marcas LGMG y JLG.
4. `BLOQUEANTE` ante deriva entre snapshot, plan y estado justo antes de apply; ante colisiones, duplicados, asociaciones ambiguas, fingerprint distinto o multimedia sin backup.
5. Revisión manual de operaciones, diffs, binarios/MIME y ausencias; aprobación de dos personas.
6. Apply en ventana propia y con permisos mínimos. Persistir receipts productivos; nunca sobrescribir evidencia local ni asumir reintento ciego.
7. Reanudar solo desde checkpoint productivo validado y reconciliado con receipts/estado remoto; una operación incierta se verifica antes de repetir.
8. Verify por IDs productivos, contenido, asociaciones, hashes y acceso público. Comprobar **35 productos, 35 imágenes, 30 fichas y cinco ausencias permitidas únicamente si el dry-run productivo aprobado confirma exactamente esos valores**; de otro modo detenerse y aprobar el nuevo plan.

Una importación parcial no se “deshace” eliminando por rango de IDs: detener, preservar evidencia, reconciliar receipts, restaurar backup coordinado o completar por roll-forward aprobado.

## 11. Artefactos backend y frontend

### Backend

Comando previsto (no ejecutado): `dotnet publish backend-dotnet/JemNexus.Api/JemNexus.Api.csproj -c Release -f net8.0 -o backend-dotnet/publish/JemNexus.Api`. El script `publish-plesk.ps1` además restaura, compila y prueba antes de publicar; el pipeline real debe fijar SHA, SDK y registrar hashes.

La salida debe contener al menos `JemNexus.Api.dll`, ejecutable cuando corresponda, `.deps.json`, `.runtimeconfig.json`, dependencias, `appsettings.json` y `web.config` generado. El ZIP normal creado por `package-plesk.ps1` debe contener DLL/runtime/deps y **excluir** `web.config`, logs/stdout, `.env*` y `*.local`.

No publicar: fuentes, tests, `bin/obj`, secrets, `.git`, bases, logs, outputs locales, herramientas/importadores ni ZIPs viejos. No sobrescribir: `web.config` productivo, uploads/imágenes, `uploads/technical-sheets`, logs operativos o configuración Plesk.

### Frontend

Comando previsto (no ejecutado): desde `frontend`, `npm ci` en ambiente limpio y luego `npm run build`. El script ejecuta `tsc -b`, build cliente, bundle SSR temporal, prerender y validación. `dist` debe contener `index.html`, bundles/assets con hash, contenido de `public/` (`robots.txt`, `sitemap.xml`, `llms.txt`, `web.config`, favicon/manifest/icons), diez rutas prerender y fallbacks `_spa.html`/`_noindex.html`. `.prerender-server` es temporal y no se publica.

`RIESGO`: variables `VITE_*` quedan embebidas en build. Un frontend construido sin `VITE_API_BASE_URL` usa localhost; inspeccionar el artefacto antes de promoverlo.

### Compatibilidad temporal

El backend nuevo que lee/escribe `IssuedById` requiere esquema nuevo: backend-before-migration puede no soportar UI nueva y backend-after-migration falla si la columna falta. El frontend nuevo espera endpoints/campos/permisos nuevos. Por ello usar mantenimiento, aplicar primero schema compatible, luego backend, health/API, y finalmente frontend. No mantener tráfico de escritura durante el cambio de schema.

## 12. Backup obligatorio

Antes de GO, registrar en una hoja de cambio: artefacto, ubicación cifrada, hash/tamaño, hora UTC, responsable que creó, responsable que verificó y resultado de una restauración ensayada.

- Backup SQL consistente (incluidos `__EFMigrationsHistory`, usuarios, refresh tokens, cotizaciones y catálogo) y restauración comprobada en entorno aislado.
- Backup multimedia completo de imágenes y `<ContentRoot>/uploads/technical-sheets`, con permisos/estructura y muestreo de hashes.
- Backup exacto del backend publicado, incluido `web.config` productivo protegido por acceso.
- Backup exacto del frontend publicado y reglas IIS/web.config frontend.
- Exportación o registro redactado de bindings, certificados, app pool, versión runtime, variables/nombres (no valores en informe), CORS, proxy/HTTPS, ACL, SMTP, tareas y configuración Plesk.

`BLOQUEANTE`: backup existente sin prueba de restauración, sin responsable o sin marca temporal no satisface GO.

## 13. Orden recomendado de despliegue

1. Aprobar SHA, ventana, responsables, plan de comunicación, mantenimiento y rollback; congelar escrituras/importaciones.
2. Recolectar información productiva de §17; reconciliar migraciones y generar/revisar SQL exacto.
3. Generar artefactos reproducibles fuera de esta auditoría, con variables build-time aprobadas; inspeccionar hashes/contenido y conservar versión anterior.
4. Completar y verificar backups de §12; comprobar que multimedia queda fuera de carpetas reemplazadas.
5. Activar mantenimiento evitando nuevas cotizaciones/cambios; capturar baseline `/health`, métricas y logs.
6. Aplicar migraciones aprobadas en orden; verificar historia **y** objetos/backfills/FKs/índices. Ante error, detenerse.
7. Desplegar backend preservando `web.config` y multimedia; reiniciar mediante mecanismo Plesk aprobado; validar health, DB, auth y API compatible.
8. Desplegar frontend `dist`; validar que apunta a la API productiva y que reglas SPA/prerender están presentes.
9. Ejecutar primero smoke no mutante y luego operaciones controladas/reversibles de §14.
10. Retirar mantenimiento solo tras GO operativo; observar logs/métricas. Normalización de usuarios y catálogo EP se ejecutan como cambios separados, con sus propias aprobaciones/backups.

## 14. Smoke tests post-despliegue

### No mutantes, en orden

1. `/health` (y `/api/health`) informa `ok`, app esperada y `Production`; no expone secretos.
2. Sitio público, rutas prerender/SPA, catálogo y detalle de producto cargan sin errores.
3. Muestra controlada de imágenes y fichas descarga con MIME, tamaño y contenido correctos.
4. CORS: origen oficial permitido; origen no aprobado rechazado; HTTPS/proxy no entra en loop.
5. Login controlado de `supadmin`, refresh una vez y `/api/auth/me`: rol/permisos correctos, sin registrar tokens.
6. Menú Usuarios visible para `supadmin`; listado y formulario en lectura.
7. Login de seller de prueba: `/api/auth/me`, permisos efectivos, ausencia del menú Usuarios y 403 al endpoint reservado.
8. Petición sin token obtiene 401; con usuario autenticado sin permiso obtiene 403.
9. Leer cotización histórica y PDF existente si existe una muestra aprobada; verificar responsable/emisor sin alterar datos.
10. Revisar logs: correlación suficiente, sin passwords, JWT, connection strings, PII innecesaria ni stack traces públicos.

### Mutantes, controladas y reversibles

11. Editar un campo inocuo de una cuenta **de prueba**, confirmar toast y restaurarlo; no usar cuentas objetivo sin aprobación.
12. Conceder/quitar un permiso inocuo al seller de prueba, verificar efecto/403 y restaurar conjunto original; confirmar revocación de sesión.
13. Emitir una cotización mínima de prueba como seller; validar PDF, folio, persistencia, `ResponsibleSellerId` e `IssuedById`; anular/etiquetar según política, no borrar historia.
14. Emitir como `supadmin` seleccionando seller; comprobar PDF/datos del responsable y que `IssuedBy` audita a `supadmin`; reversión según política de cotizaciones.
15. Si correo forma parte del GO, notificación a buzón controlado y limpieza conforme a retención.

Cada mutación requiere ID de cambio, datos de prueba, resultado esperado, restauración definida y evidencia sin secretos.

## 15. Rollback

| Incidente | Acción segura |
|---|---|
| Migración falla | Mantener mantenimiento, guardar error, verificar transacción/objetos/historial. No reintentar ni editar a mano. Si hubo cambios parciales, restaurar backup o roll-forward revisado. |
| Backend no saludable | Conservar DB si migración completó; evaluar compatibilidad. Restaurar backend anterior solo si soporta el schema actual; si no, roll-forward o restauración coordinada DB+backend. Preservar `web.config`. |
| Frontend incompatible | Restaurar frontend anterior; mantener backend/schema si son backward-compatible; repetir smoke. |
| Auth falla | No alterar usuarios por SQL. Revisar environment, issuer/audience, reloj, conexión y `web.config`; restaurar configuración/backend aprobado y revocar sesiones si se rotó secreto. |
| Se pierde acceso admin | Mantener mantenimiento; usar segundo superadmin/recuperación aprobada. No desactivar último admin ni insertar hash manual. Restaurar DB/config coordinadamente si no existe vía segura. |
| Importación EP parcial | Detener importador, preservar checkpoint/receipts/logs, bloquear reintento ciego, reconciliar cada operación. Reanudar desde checkpoint validado, roll-forward, o restaurar SQL+multimedia del mismo instante. |

**Advertencia:** ejecutar `Down` después de datos nuevos puede borrar concesiones, `IssuedBy` y otras columnas/tablas. Nunca se propone un rollback destructivo sin exportar esos datos y aprobar su pérdida; restauración coordinada o roll-forward son las opciones preferidas.

## 16. Puertas GO / NO-GO

### GO — todas obligatorias

- Backups SQL, multimedia, backend, frontend y Plesk confirmados y restaurables.
- Estado productivo de migraciones identificado por historia y objetos; SQL diferencial exacto revisado, sin sorpresa destructiva.
- Matriz de variables completa y validada sin revelar valores; secretos disponibles por canal seguro.
- Backend/frontend generados reproduciblemente desde el SHA aprobado, hashes/contenido verificados.
- Estrategia de cuentas aprobada, segundo acceso admin/recuperación comprobado.
- Multimedia fuera del reemplazo, respaldada y con ACL comprobadas.
- Rollback compatible con schema/datos disponible, responsables presentes y ventana definida.
- Baseline saludable y mantenimiento listo.

### NO-GO inmediato

- Estado de migraciones desconocido o discrepancia entre historia y objetos.
- Ausencia de cualquier backup o restauración no comprobada.
- Secreto/configuración obligatoria faltante, cadena SQL no verificada o frontend que referencia localhost.
- Superadministrador sin recuperación o plan que pueda dejar cero admins activos.
- Conflictos de IDs, seller codes, usuarios, productos, fingerprint o datos.
- Multimedia sin backup/protección, o ruta efectiva desconocida.
- SQL inesperado/destructivo, backfill no explicable o constraint con datos incompatibles.
- Health fallido, logs con secretos, CORS/HTTPS incorrectos.
- Árbol, lockfile, SDK o artefactos no reproducibles/trazables al SHA.

**Estado actual de la puerta:** `BLOQUEANTE / NO-GO`, porque esta auditoría no accedió a producción y, por diseño, siguen pendientes migraciones reales, backups, configuración, artefactos y recuperación de cuentas.

## 17. Información que todavía debe obtenerse de producción

Todo lo siguiente está `PENDIENTE DE PRODUCCIÓN`:

1. Versión desplegada/SHA de backend y frontend; inventario y hashes de archivos.
2. Resultado actual de `/health`, runtime .NET, app pool, bindings, certificados, proxy/HTTPS y reglas IIS.
3. Base/schema reales, `__EFMigrationsHistory`, tablas/columnas/FKs/índices/checks y cualquier deriva o aplicación parcial.
4. Conteos y validaciones precondición para cada backfill, especialmente sellers, códigos, cotizaciones, `ResponsibleSellerId` e `IssuedById`.
5. Existencia, frescura, ubicación, cifrado, responsable y prueba de restauración de backups SQL/archivos/configuración.
6. Presencia (no valores) y procedencia de variables de §6; política de rotación JWT/SQL/SMTP.
7. Orígenes CORS oficiales y URL API que debe quedar embebida en frontend.
8. Rutas físicas, volúmenes persistentes, ACL, tamaños y backups de imágenes y fichas técnicas.
9. Inventario de cuentas/IDs/roles/activo/códigos/permisos/relaciones; existencia de `soporte`; métodos de recuperación admin.
10. Inventario EP actual, marcas, IDs/slugs/SKU, asociaciones, archivos, duplicados y decisión de si el objetivo sigue siendo 35/35/30/5.
11. SMTP/remitente/destinatarios y URL frontend aprobados; destinatario de prueba.
12. Límites de rate limiting aprobados, volumen esperado, observabilidad, ubicación/retención/redacción de logs.
13. Ventana, mantenimiento, responsables técnicos/negocio, aprobadores y canal de incidente.
14. Compatibilidad del backend/frontend anterior con el schema nuevo para elegir rollback real.

## 18. Próximas etapas recomendadas

1. **Descubrimiento read-only productivo aprobado:** completar §17 sin copiar secretos al ticket/repositorio.
2. **Conciliación de schema:** determinar intervalo exacto, generar SQL revisable, auditar destructividad/backfills y aprobarlo.
3. **Plan de backup/restauración:** ejecutar y ensayar restauración aislada; firmar evidencias.
4. **Build reproducible:** en etapa separada, generar backend/ZIP y frontend `dist` desde este SHA o uno explícitamente aprobado; validar SBOM/hashes/contenido/config build-time.
5. **Ensayo en staging equivalente:** restaurar copia anonimizada si está autorizada; practicar migración, despliegue, smoke y rollback.
6. **Plan de cuentas:** resolver identidad de `soporte` y relaciones antes de normalizar `supadmin`, `jmateluna`, `fheim`.
7. **Despliegue controlado:** seguir §13 y puertas §16, con observación posterior.
8. **Catálogo EP:** cambio independiente después de estabilizar código/cuentas; nuevo dry-run/checkpoint/approval/apply/verify productivos.
9. **Cierre:** archivar hashes, resultados de smoke, migraciones aplicadas, backups retenidos, incidencias y decisión GO final sin secretos.

Hasta completar los puntos 1–4 y todos los bloqueantes de §16, JEM Nexus **no está autorizado para despliegue productivo** por esta auditoría.
