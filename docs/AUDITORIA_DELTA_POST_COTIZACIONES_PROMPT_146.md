# Auditoría delta integral post-cotizaciones — Prompt 146

**Fecha de corte:** 2026-08-21

**Repositorio:** `/workspace/web-ventas-generica`

**Rama:** `work`

**HEAD inicial:** `551db4c1a7dc4f70270b15e08b134628c6b27457` (merge PR #279)

**Continuidad funcional comprobada:** `0a60b61374f655195f528a2fe31160a8f12dbb89` (Prompt 145) es ancestro de HEAD.

## 1. Resumen ejecutivo

La fuente de verdad inspeccionada es el sistema activo ASP.NET Core 8/EF Core/SQL Server y React/Vite/TypeScript. Se localizaron **72 mapeos de endpoints**, **41 declaraciones de ruta React**, **6 políticas de autorización** (cinco con nombre más la política CORS, contada tal como aparece mediante `AddPolicy`) y **2 roles de aplicación** (`seller`, `support_admin`). El directorio Django histórico no existe en este checkout y, de aparecer en otras revisiones, queda expresamente excluido.

No se confirmó ningún hallazgo crítico ni secreto real rastreado. Los riesgos prioritarios son la reutilización de refresh tokens sin rotación/logout servidor, la ausencia de rate limiting, la falta de garantías operativas verificables para persistencia/backups de uploads y la brecha de privacidad/retención. `/media` sirve intencionalmente imágenes comerciales públicas; no obstante, el montaje estático también omite la condición de publicación para una imagen de producto no publicado y la asociación pública para una ficha técnica si un tercero ya conoce su nombre GUID, escenario específico clasificado como riesgo medio, no como exposición alta de todo el directorio. La emisión comercial actual es una creación atómica con transacción y asignador de folio serializable; no existe edición backend de cotizaciones comerciales ni borrador persistente. PDF no está implementado: el frontend lo declara y deshabilita de forma explícita.

Esta es una fotografía **estática**. No se ejecutaron builds, tests, restore, auditorías online, navegadores, migraciones, producción ni Plesk.

## 2. Alcance, exclusiones y método

### 2.1 Alcance

- Arquitectura, endpoints, autenticación, autorización, CORS, middlewares y abuso.
- Contratos y validación, modelo EF/migraciones, flujo de solicitudes/clientes/cotizaciones/folios.
- Imágenes, fichas PDF, correo, frontend, despliegue IIS/Plesk, dependencias/CI.
- Inventario estático de pruebas, privacidad, SEO/GEO/IA, accesibilidad y responsive.

### 2.2 Exclusiones

- Backend Django retirado, producción, Plesk, base de datos y archivos subidos reales.
- Ejecución de builds/tests/restores/auditorías, comandos EF, SMTP y tráfico HTTP.
- Correcciones o cambios distintos de este documento.

### 2.3 Metodología y fuentes

Se usaron `pwd`, `find .. -name AGENTS.md`, `git status`, `git branch`, `git rev-parse`, `git log`, `git merge-base`, `rg`, `rg --files`, `find`, `sed` e inspección directa. No se encontró `AGENTS.md` aplicable. Se distinguió evidencia actual de comentarios o documentos históricos; los 123 `[Fact]`, 50 `[Theory]` y 199 `[InlineData]` son inventario declarado, **no resultados ejecutados**.

Fuentes principales: `backend-dotnet/JemNexus.Api/Program.cs`, `Endpoints/*`, `Data/JemNexusDbContext.cs`, `Data/Migrations/*`, `Models/*`, `Services/*`, `frontend/src/router/AppRouter.tsx`, `frontend/src/services/*`, páginas/componentes, `frontend/public/*`, manifiestos y `docs/*`.

## 3. Inventario y arquitectura actual

| Componente | Evidencia actual | Resultado |
|---|---|---|
| Solución/proyectos | `backend-dotnet/JemNexus.sln`; `JemNexus.Api.csproj`; `JemNexus.Api.Tests.csproj` | API .NET 8 y tests xUnit. |
| Frontend | `frontend/package.json`, `src`, `vite.config.ts` | React + Vite + TypeScript. |
| Configuración | `appsettings.json`, `appsettings.Development.json`, `frontend/.env.example` | Variables para SQL, JWT, CORS, uploads, SMTP, URL pública y GTM. |
| Datos | `JemNexusDbContext` | 16 `DbSet`: usuarios, refresh tokens, catálogo, contenido Home, solicitudes, fichas, clientes, cotizaciones, ítems y contador de folio. |
| Migraciones | `Data/Migrations` | 14 migraciones actuales más snapshot; las cuatro finales cubren seller, clientes, cotizaciones y emisión/folios. |
| Almacenamiento | `LocalProductImageStorage`, `LocalTechnicalSheetStorage` | Sistema de archivos local bajo root configurable; `/media` publica recursos comerciales y, por montaje estático, no consulta reglas de publicación por objeto. |
| Notificaciones | `SmtpQuoteNotificationService` | SMTP configurable para solicitud pública; no se localizó envío de cotización emitida. |
| Analítica | `frontend/src/utils/analytics.ts` | Carga GTM condicionada a `VITE_GTM_ID`; activación externa no verificable. |
| Despliegue | `frontend/public/web.config`; documentos Plesk | SPA rewrite IIS; publicación/configuración real pendiente externa. |
| CI | `.github` ausente | No hay workflow versionado localizado. |
| SEO público | `Seo.tsx`, `seo.ts`, `robots.txt`, `sitemap.xml` | Metadata dinámica parcial; robots/sitemap conservan dominios Render obsoletos. |

### 3.1 Superficies

- **Frontend público:** `/`, catálogo, maquinaria nueva/usada, producto por slug, cotizar, contacto, sobre nosotros, FAQ, login y diagnóstico.
- **Panel:** rutas `/admin/*` protegidas en React; usuarios añade guard visual support-only.
- **API pública:** salud, login/refresh y `/api/public/*` comercial/solicitud.
- **API autenticada:** lectura/escritura comercial, fichas, usuarios, clientes y cotizaciones. La barrera efectiva está en políticas backend.
- **SQL Server:** EF Core; conexión requerida externamente en producción.
- **Archivos:** las imágenes de productos se sirven intencionalmente desde `/media/product-images/{productId}/{guid.ext}` para el catálogo. Las fichas públicas se entregan normalmente por un endpoint que exige producto publicado y asociación válida. En paralelo, Static Files cubre también `/media/technical-sheets/{guid}`, por lo que quien ya conozca el nombre puede omitir esa comprobación; los GUID reducen enumeración, pero no son autorización.
- **Swagger:** solo Development o QA. Ocultarlo no autoriza endpoints, pero las políticas sí están aplicadas.
- **Errores:** handler no Development devuelve 500 vacío; no se observó detalle interno en esa respuesta.
- **Salud:** `/`, `/health`, `/api/health` anónimos revelan nombre, environment y timestamp; no comprueban SQL/SMTP/storage.

## 4. Inventario de rutas y endpoints

### 4.1 Conteo y agrupación de los 72 mapeos

| Grupo | Métodos / cantidad | Operación |
|---|---:|---|
| Salud | GET ×3 | `/`, `/health`, `/api/health`. |
| Auth | POST ×2, GET ×1 | login, refresh, me. No logout. |
| Público comercial | GET ×9, POST ×1 | productos/detalle/ficha, categorías, marcas, promociones, Home, imágenes, specs, solicitud. |
| Lectura comercial autenticada | GET ×17, POST ×1 | listados/detalles, solicitudes y test SMTP. |
| Escritura comercial | POST ×7, PUT ×6, PATCH ×1, DELETE ×7 | catálogo, imágenes, specs, solicitudes y Home. |
| Fichas técnicas | GET ×3, POST ×2, PATCH ×1, DELETE ×1 | CRUD, reemplazo y descarga. |
| Usuarios | GET ×2, POST ×1, PUT ×1, PATCH ×1, DELETE ×1 | Administración seller. |
| Clientes | GET ×2, POST ×1, PUT ×1 | búsqueda, detalle y guardado. |
| Cotizaciones comerciales | GET ×2, POST ×1 | listar, consultar y emitir. |

> El conteo corresponde a llamadas `MapGet/MapPost/MapPut/MapPatch/MapDelete` actuales, no a casos de prueba ni tráfico observado.

### 4.2 Rutas React (41 declaraciones)

Hay 11 rutas públicas explícitas, 25 rutas/redirects bajo guard administrativo, 3 rutas support-only (usuarios), 1 guard sin path y 1 fallback comodín. `/diagnostico-api` es público: muestra la URL base efectiva y resultados/mensajes de conectividad; tiene `noindex,nofollow`, pero eso no es control de acceso. Su utilidad es soporte técnico, con riesgo informativo bajo; decidir eliminación o protección en producción. El comodín redirige a `/`, por lo que una URL inexistente puede responder el shell con 200 y comportarse como **soft 404**. IIS reescribe rutas no físicas al SPA correctamente.

## 5. Matriz de permisos efectiva

`S` = seller; `A` = support_admin; `staff/superuser` = claims heredados aceptados solo por políticas CommercialRead/Write; `—` = no autorizado por política.

| Grupo/ruta | HTTP | Operación | Anónimo | S | A | staff/superuser | Política / observación |
|---|---|---|---:|---:|---:|---:|---|
| `/`, `/health`, `/api/health` | GET | salud | Sí | Sí | Sí | Sí | Sin auth. |
| `/api/auth/login`, `/refresh` | POST | sesión | Sí | Sí | Sí | Sí | `AllowAnonymous`; sin rate limit. |
| `/api/auth/me` | GET | identidad | No | Sí | Sí | token heredado válido | Auth básica + validación DB global. |
| `/api/public/*` lectura | GET | catálogo publicado | Sí | Sí | Sí | Sí | `AllowAnonymous`; filtros de publicación. |
| `/api/public/quote-requests` | POST | crear solicitud | Sí | Sí | Sí | Sí | Anónimo; SMTP posterior. |
| `/api/*` lectura comercial | GET | catálogo completo, solicitudes | No | Sí | Sí | Sí | `RequireCommercialRead`. |
| `/api/quote-notifications/test` | POST | prueba SMTP | No | Sí | Sí | Sí | Read policy permite efecto externo; amplitud discutible. |
| `/api/*` escrituras catálogo/Home | POST/PUT/PATCH/DELETE | administrar | No | Sí | Sí | Sí | `RequireCommercialWrite`; claims históricos amplían acceso. |
| `/api/technical-sheets/*` | varios | CRUD/descarga | No | Sí | Sí | Sí | `RequireCommercialWrite`. |
| `/api/admin/users/*` | varios | administrar sellers | No | — | Sí | — | `RequireSupportAdmin`; backend efectivo. |
| `/api/admin/customers/*` | GET/POST/PUT | datos personales | No | Sí | Sí | — | `RequireSellerOrSupportAdmin`; todos los sellers ven/buscan todos los perfiles. |
| `/api/admin/commercial-quotes` | GET | listar/ver | No | propias | todas | — | Política común + filtro por vendedor en handler. |
| `/api/admin/commercial-quotes/issue` | POST | emitir | No | Sí | — | — | Además `RequireRole(seller)` y vendedor activo en DB. |
| ficha pública asociada | GET | descargar PDF publicado | Sí | Sí | Sí | Sí | Solo producto publicado/asociación activa; respuesta inline/nosniff. |
| `/media/product-images/*` | GET | imágenes comerciales | Sí | Sí | Sí | Sí | Público por diseño; el acceso directo no comprueba si el producto continúa publicado. |
| `/media/technical-sheets/*` | GET | archivo físico de ficha | Sí, con nombre conocido | Sí | Sí | Sí | Omite el endpoint público que comprueba producto publicado y asociación; el nombre GUID dificulta descubrirlo, no lo autoriza. |

No se localizaron endpoints administrativos sin política fuera de la superficie pública intencional. Las reglas React aportan UX, pero no son la única barrera. La principal decisión pendiente es si sellers deben tener acceso global a perfiles de clientes y si los claims heredados deben conservar escritura comercial.

## 6. Autenticación JWT

| Pregunta obligatoria | Respuesta basada en código actual |
|---|---|
| ¿Rotación de refresh? | **No.** Refresh emite solo un access token; no reemplaza ni revoca el refresh. |
| ¿Puede reutilizarse hasta expirar? | **Sí**, mientras no esté revocado, no expire y el usuario siga activo. No existe ruta que marque `RevokedAt`. |
| ¿Logout backend? | **No.** `logout()` solo elimina claves locales. |
| ¿Cambio de contraseña invalida tokens? | **Access:** sí, `pwd_ver` se compara con versión derivada del estado actual. **Refresh:** el endpoint no compara versión de contraseña; sigue utilizable para obtener un access nuevo firmado con versión actual. |
| ¿Desactivar/cambiar rol invalida acceso? | Access se valida contra usuario activo y rol DB en cada request; refresh exige activo y el access nuevo toma el rol actual. Sí para acceso posterior, sujeto a DB disponible. |
| ¿Dónde guarda tokens el frontend? | `localStorage`, claves históricas para access y refresh. |
| ¿Riesgo XSS? | Sí, impacto relevante si se introduce XSS porque JavaScript puede leer ambos tokens; no se localizó sink directo (`dangerouslySetInnerHTML`, `eval`, etc.), por lo que no se confirma XSS presente. |
| ¿Evita enumerar usuario? | Login devuelve 401 uniforme para vacío, inexistente, inactivo o contraseña incorrecta. |

Issuer/audience/firma/expiración se validan; `ClockSkew` es 1 minuto; HTTPS metadata se exige fuera de Development/Test y hay redirección HTTPS fuera de Test. Producción falla al arrancar sin secreto JWT. Los refresh se almacenan hasheados y tienen expiración de 7 días por configuración; access dura 60 minutos. El frontend reintenta una vez tras 401 y limpia sesión si refresh falla. No se observaron tokens en URL o logs.

## 7. CORS, transporte, middlewares y abuso

- CORS usa lista explícita de orígenes de config/`FRONTEND_ORIGINS`, `AllowAnyHeader` y `AllowAnyMethod`, sin credenciales. `appsettings.json` incluye dominios objetivo y orígenes localhost; la conveniencia de localhost en producción es una mejora de endurecimiento, no acceso sin JWT.
- Orden: excepción/HTTPS → normalización → static `/media` → routing → CORS → authentication → authorization → endpoints. Es coherente para la API.
- No se localizó configuración explícita de `ForwardedHeaders`, HSTS, CSP, frame protection, Referrer-Policy o headers globales `nosniff`. IIS puede aportar controles, pero es pendiente externo. `RequireHttpsMetadata` no sustituye proxy forwarding correcto.
- **No existe rate limiter** global, de endpoint ni control manual/429 localizado. Afecta login, refresh, formulario público, búsquedas, uploads, downloads, test SMTP y emisión. No hay clave de partición ni tratamiento de IP de proxy que auditar. Priorizar login y solicitud pública; después operaciones costosas/efectos externos.

## 8. Validación y contratos

- Cotizaciones: backend normaliza texto y RUT, valida email, enums, vigencia, ítems, cantidad/precio positivos, descuento 0–100 a dos decimales, catálogo disponible y posiciones. Vendedor, folio, fechas, estado, IVA y totales son autoritativos del servidor.
- Clientes: normalizador y RUT canónico; índice único normalizado evita duplicidad. Debe verificarse concurrencia mediante prueba real SQL Server.
- Listados de cotizaciones validan `page >= 1`, `page_size 1..100` y enums. Otros listados aplican límites según sus handlers; no hay un filtro de validación uniforme global.
- Catálogo y uploads tienen validaciones específicas en endpoints/servicios. Extensión y cabecera de imágenes/PDF se revisan; la firma parcial reduce suplantación simple, no equivale a análisis de contenido malicioso.
- El frontend valida formularios y evita UI inválida, pero las conclusiones anteriores descansan en backend/EF, no en el cliente.

## 9. Datos, EF Core e integridad

El modelo configura índices únicos para usernames/email normalizados, slugs, RUT normalizado y folio; precisiones decimales explícitas para precios/totales/descuentos; relaciones históricas relevantes usan `NoAction` o `SetNull`. Cotizaciones guardan snapshot de cliente, vendedor, nombre/marca/modelo de producto, cantidades y valores; `ProductId` es nullable con `NoAction`, de modo que el snapshot conserva significado, aunque un borrado físico del producto referenciado puede ser rechazado por SQL hasta desvinculación.

La emisión abre transacción relacional con aislamiento definido por `CommercialQuoteFolioAllocator`, incrementa contador anual, asigna folio y guarda cabecera/ítems en una unidad. El índice único de folio es defensa adicional. El camino InMemory de tests no reproduce aislamiento SQL Server. No se localizó token de concurrencia general ni prueba de dos emisiones simultáneas contra SQL Server real. Fechas de emisión distinguen UTC y fecha local chilena. CLP/USD son etiquetas de moneda: no hay conversión; cálculo decimal backend aplica descuento, neto, IVA y total con redondeo centralizado.

## 10. Auditoría específica de cotizaciones

| Etapa | Estado y evidencia |
|---|---|
| Solicitud pública | Implementada en `/api/public/quote-requests`; persiste y luego intenta notificar. |
| Revisión administrativa | Lectura/actualización de solicitudes bajo políticas comerciales. |
| Perfil cliente | CRUD reutilizable, búsqueda/paginación y RUT normalizado/único. |
| Composición | Frontend arma datos cliente e ítems manuales/catálogo; backend reconstruye snapshots y valida catálogo. |
| Confirmación | Diálogo corporativo y estado `saving` deshabilitan acción; reduce doble clic, no reemplaza idempotencia servidor. |
| Emisión/folio | POST único, seller-only, transacción y contador anual. |
| Consulta | Lista y detalle readonly; seller ve propias, support todas. |
| PDF | **No implementado**: no hay endpoint; botones deshabilitados con texto explícito. |

Respuestas expresas:

- **Atómica:** sí en proveedor relacional, transacción cubre folio y guardado.
- **Emitir dos veces / editar emitida:** el API no emite un borrador existente; cada POST crea una nueva cotización. No hay PUT/PATCH/DELETE comercial, por lo que una emitida no se edita. Una repetición de request crea otra cotización/folio válido: falta idempotencia.
- **Folio concurrente:** contador/transacción e índice único lo protegen por diseño; queda pendiente prueba SQL Server concurrente, por lo que no se afirma imposibilidad absoluta operacional.
- **Borradores:** el enum/modelo conserva `Draft`, pero no hay endpoint de persistencia de borrador; el frontend mantiene formulario en memoria y navega a `/editar`, que carga una emitida como readonly. Es deuda semántica/ruta histórica, no edición real.
- **Permisos:** seller emite/ve propias; support ve todas pero no emite. Coherente con regla actual, pendiente confirmar decisión comercial.
- **Snapshot:** sí. Cambios posteriores de nombre/precio no alteran el snapshot; el FK puede condicionar borrado físico.
- **RUT:** normalizado/validado backend tanto en cliente como emisión; frontend también usa formato canónico.
- **Totales:** backend con `CommercialQuoteCalculator`; no acepta totales/IVA/folio/estado/fecha/vendedor del cliente.
- **Doble envío:** UI deshabilita mientras guarda, pero no hay idempotency key.
- **PDF/visor:** no hay endpoint PDF; botón deshabilitado. Sí hay vista de detalle sin edición, y editor trata cotización cargada como readonly.
- **Correo:** emisión comercial no envía correo. En solicitud pública, se guarda antes de SMTP y el fallo se captura para no revertir persistencia.
- **Logs:** servicio SMTP registra IDs/estado y errores; debe verificarse configuración/sinks externos para confirmar que excepciones no incorporen PII del proveedor.

## 11. Archivos e imágenes

| Clase | Validar | Almacenar | Optimizar | Servir/eliminar |
|---|---|---|---|---|
| Imágenes producto | Límite configurable 5 MB, extensión permitida, MIME/cabecera | Nombre GUID bajo `product-images/{productId}` | **No:** copia original; sin resize, compresión, thumbnail, WebP/AVIF automático ni límite de dimensiones/descompresión | `/media` público por finalidad comercial; la ruta estática no revalida publicación del producto. |
| Logos marca | No se localizó pipeline independiente; se tratan como URL/campo, no carga dedicada | No aplica al servicio actual | No implementado | Según URL resultante. |
| Fichas PDF | Extensión, tamaño, MIME y `%PDF-` | Nombre aleatorio; replace/delete mediante servicio local | No aplica compresión de imagen | Descarga admin autenticada y descarga pública asociada; inline y `nosniff`. |

Las rutas se componen desde identificadores/nombres GUID generados y el root se normaliza, reduciendo traversal, colisiones y enumeración casual; el GUID no sustituye una decisión de autorización. Las imágenes de productos publicados y las fichas ofrecidas por su página pública son recursos públicos intencionales. El escenario indebido concreto es más estrecho: Static Files no consulta EF, por lo que una URL ya conocida de `product-images/{productId}/{guid.ext}` sigue siendo recuperable aunque el producto no esté publicado, y una URL `technical-sheets/{guid}` puede recuperar una ficha no vinculada a un producto público sin pasar por `GetProductTechnicalSheetFileAsync`. No se localizaron otros archivos administrativos o privados en el root. No se observó staging + rename atómico ni escaneo antivirus. Errores entre escritura física y `SaveChanges` pueden dejar huérfanos; eliminación inversa puede fallar tras cambiar DB. Persistencia tras redeploy, permisos, volumen externo, backups y limpieza solo pueden confirmarse en Plesk. `loading="lazy"` encontrado en UI mejora carga, no optimiza bytes.

## 12. Correo y notificaciones

SMTP toma host, puerto, credenciales, SSL, timeout, remitente y destinatarios de configuración/opciones. Valida configuración/direcciones antes de enviar, maneja excepciones y registra fallo. La solicitud se persiste antes de invocar la notificación, por lo que SMTP fallido no pierde la solicitud; el cliente puede recibir éxito con notificación fallida según handler. Los datos del formulario se incluyen en el correo por finalidad operacional. Secretos y TLS/relay/deliverability reales son pendientes externos. El endpoint autenticado de prueba SMTP está disponible a seller/support/staff histórico y debería restringirse o limitarse.

## 13. Frontend: seguridad y confiabilidad

- Cliente central construye URL, normaliza errores y usa Bearer; refresh único después de 401 y cierre local al fallar.
- Tokens en `localStorage` elevan impacto de un eventual XSS. La búsqueda estática no halló `dangerouslySetInnerHTML`, `innerHTML`, `eval`, `new Function` ni `document.write`.
- Enlaces externos revisados incluyen `rel`; `window.open` de blob usa `noopener,noreferrer`.
- Persisten confirmaciones nativas en promociones, fichas, proveedores, categorías, imágenes, specs y cambios de cotización; hay diálogos corporativos en flujos recientes, por tanto la migración es parcial.
- Cotizaciones deshabilitan controles durante envío. Búsquedas relevantes usan estados de carga/paginación; la cobertura de `AbortController`, debounce y descarte de respuestas no es uniforme.
- `ApiDiagnostics` es público, revela base URL y mensajes saneados de conexión; ya usa `noindex,nofollow`, pero los robots no impiden acceso.
- `console.debug` de analítica está condicionado por entorno/configuración en utilidad; validar que producción no registre payloads de eventos sensibles.

## 14. Producción y operación

El repo exige secreto JWT en Production y admite conexión SQL/CORS/SMTP/uploads mediante configuración/variables. No se encontró un secreto productivo no vacío rastreado; los campos sensibles versionados están vacíos/placeholders. `AllowedHosts` es `*`. Swagger queda fuera de Production salvo environment mal configurado. Health no prueba dependencias.

El `web.config` contiene rewrite SPA, pero no headers, cache, compresión ni regla 404 de contenido. No hay evidencia versionada de publicación backend (`web.config` generado), volumen persistente, ACL de uploads, backups, rotación, migrations-at-deploy o monitoreo. Todo ello es `Pendiente externo`, no un fallo confirmado de Plesk. No se accedió al hosting.

## 15. Dependencias y CI

- .NET apunta a `net8.0`; paquetes directos están fijados en el `.csproj`. Frontend mantiene `package.json` y lockfile.
- La última evidencia documental de dependencias localizada es `AUDITORIA_DEPENDENCIAS_PROMPT_119.md`; no se reutiliza su resultado como estado de vulnerabilidades hoy.
- No se consultó internet ni se ejecutó `npm audit`, restore o herramientas equivalentes. Debe repetirse en una fase local/controlada.
- No existe `.github/workflows` en el checkout: no hay CI versionado que demuestre restore, build, tests, auditoría, frontend build o verificación de migraciones.

## 16. Cobertura estática de pruebas

Inventario: **27 archivos C#**, de los cuales 25 contienen pruebas; **123 métodos `[Fact]`**, **50 `[Theory]`** y **199 filas `[InlineData]`**. Una teoría puede expandirse a varias filas; no se calcula ni afirma cantidad ejecutada.

| Área | Evidencia localizada | Cobertura estática |
|---|---|---|
| Auth/JWT/password | `AuthEndpointTests`, `JwtTokenServiceTests`, `PasswordHasherServiceTests` | Parcial: login/refresh/me y tokens; faltan rotación/logout porque no existen. |
| Autorización/usuarios | `AdminUserEndpointTests`, tests de endpoints | Buena por roles principales; ampliar claims heredados y matriz negativa completa. |
| Lectura pública | `CommercialPublicReadEndpointTests` (22 métodos) | Amplia en contratos/filtros. |
| Productos/categorías/marcas/proveedores/promociones/Home | `CommercialModel/Read/Write/ValidationTests` | Parcial-amplia, agrupada; no todos los caminos se distinguen por recurso. |
| Imágenes | `CommercialWriteEndpointTests`, lectura pública | Parcial; faltan dimensiones, descompresión, fallos IO y huérfanos. |
| Fichas | `TechnicalSheetTests` (18) | Amplia para validación/descarga; falta malware/IO real. |
| Solicitudes/correo | `CommercialPublicQuoteEndpointTests`, `QuoteNotificationServiceTests` | Cubre persistencia/fallo SMTP en dobles; no SMTP real. |
| Clientes/RUT | `AdminCustomerEndpointTests` (14), `ChileanRutTests` | Amplia funcional; falta concurrencia SQL real por RUT. |
| Cotizaciones/cálculos | cinco archivos quote, incluidos calculator/persistence | Amplia funcional/snapshot. |
| Emisión/folios | `CommercialQuoteIssuanceTests`, migration metadata | Parcial: falta concurrencia SQL Server y retry/idempotencia. |
| Migraciones | `MigrationMetadataTests` | Metadatos estáticos; no aplicación contra SQL Server. |
| Producción/config | `HealthEndpointTests`, seeds | Limitada; sin reverse proxy/Plesk/headers/backups. |
| Frontend | No se localizaron archivos de test/config runner | No implementado. |

Ninguna prueba fue ejecutada en este prompt.

## 17. Privacidad

El sistema procesa RUT, razón social/nombre, actividad, dirección, comuna, teléfono, correo, contacto, historial de solicitudes/cotizaciones y vendedor. Solicitudes son legibles por CommercialRead; perfiles por seller/support; cotizaciones propias por seller y todas por support. No se localizó exportación masiva dedicada, endpoint de anonimización/eliminación de perfiles, configuración de retención ni borrado programado. Los emails operacionales transmiten PII a SMTP.

No existen rutas/páginas Privacy Policy o Terms, texto de información/consentimiento junto al formulario ni cookie banner. GTM es opcional y su configuración/consent mode externo no es comprobable. Esto es una brecha técnica/documental, no una conclusión legal.

## 18. Matriz SEO, GEO, buscadores e IA

### 18.1 Lista obligatoria

| Elemento | Estado | Evidencia / limitación | Prioridad | Resolución |
|---|---|---|---|---|
| Metatítulos diferentes | Implementado | `Seo` por páginas públicas; validar render final. | Media | Código/prueba. |
| Metadescripciones diferentes | Implementado | Props por página/catálogo. | Media | Código/prueba. |
| Un H1 por página | Parcial | Componentes usan encabezados, sin validación DOM ejecutada. | Media | Código/prueba. |
| H1 vs meta title | Parcial | Textos relacionados, no regla automatizada. | Baja | Contenido. |
| Intención de búsqueda | Parcial | Landing maquinaria nueva/usada y catálogo; contenido limitado. | Media | Contenido. |
| TL;DR / takeaways | No implementado | No patrón localizado. | Baja | Código/contenido. |
| Resumen tras introducción | Parcial | Intro SEO del catálogo, no uniforme. | Baja | Código/contenido. |
| CTA tras primer párrafo | Parcial | CTA presentes, posición no uniforme. | Media | Código/contenido. |
| H1/H2/H3 | Parcial | Semántica presente; auditoría DOM pendiente. | Media | Código/prueba. |
| Interlinking/clusters | Parcial | navegación, breadcrumbs/categorías; sin estrategia completa. | Media | Contenido. |
| Tablas/listas | Implementado | Catálogo/admin/FAQ usan estructuras; relevancia depende de página. | Baja | Código. |
| Página FAQ | Implementado | `/preguntas-frecuentes`. | Media | Código. |
| Schema `FAQPage` | Implementado | `FaqPage.tsx`: `faqJsonLd` usa `@type: FAQPage` y se renderiza como `JsonLd` con id `faq-page`. | Baja | Mantener y validar salida renderizada. |
| Nombres de imágenes | Parcial | assets descriptivos; uploads aleatorios por seguridad. | Baja | Código/contenido. |
| ALT imágenes | Parcial | múltiples `alt`; validación exhaustiva pendiente. | Media | Código/prueba. |
| Schema `Organization` | Implementado | `HomePage.tsx`: `organizationJsonLd` y `JsonLd` id `home-organization`. Algunos datos de negocio local siguen incompletos. | Baja | Mantener; completar solo datos públicos reales. |
| Schema `WebSite` | Implementado | `HomePage.tsx`: `websiteJsonLd` y `JsonLd` id `home-website`. | Baja | Mantener y validar salida renderizada. |
| Schema `Product` | Implementado | `ProductDetailPage.tsx` usa `buildProductJsonLd` y `JsonLd` id `product-main`. | Baja | Mantener en productos válidos. |
| Schema `BreadcrumbList` | Implementado | Catálogo y producto construyen breadcrumbs y renderizan `catalog-breadcrumb`/`product-breadcrumb`. | Baja | Mantener y comprobar URLs. |
| Schema `ItemList` | Implementado | Catálogo usa `buildItemListJsonLd` y renderiza `catalog-itemlist` cuando existen productos publicados visibles. | Baja | Mantener condición de publicación. |
| Schema `LocalBusiness` | No implementado | No se localizó este tipo específico. `Organization` sí existe, pero faltan datos locales confirmados. | Media | Definir tipo, teléfono, dirección o área atendida, horarios y enlaces oficiales reales; no inventar valores. |
| `robots.txt` | Parcial | Existe, pero sitemap apunta a backend Render antiguo. | Alta | Código. |
| URLs descriptivas/IDs | Parcial | Producto por slug; admin/entidades usan IDs apropiadamente. | Baja | Código. |
| `/page/` | No aplica | SPA comercial sin paginación indexable por esa convención. | Informativa | Decisión SEO. |
| `llms.txt` | No implementado | Archivo ausente. | Baja | Código/contenido. |
| CTA fijo móvil | Parcial | acciones responsive; verificación visual no realizada. | Baja | Código/prueba. |
| Botón compartir | No implementado | No localizado. | Baja | Código. |
| GA4 | Pendiente externo | Loader GTM configurable no prueba tag GA4 activo. | Alta | GTM/externo. |
| Google Search Console | Pendiente externo | Sin acceso/evidencia de propiedad. | Alta | Externo. |
| Sitemap | Parcial | Solo `/` y `/catalogo`, ambos con dominio Render antiguo; omite rutas/landings/productos. | Alta | Código/generación. |
| Sitemap enviado a GSC | Pendiente externo | No verificable en repo. | Alta | Externo. |

### 18.2 Publicación y UX adicional

| Elemento | Estado | Evidencia / limitación | Prioridad | Resolución |
|---|---|---|---|---|
| 404 personalizada | No implementado | comodín redirige a `/`; riesgo soft 404. | Alta | Código. |
| CTA above the fold | Parcial | Home/landings tienen CTA; requiere inspección visual. | Media | Código/prueba. |
| Favicon set | No implementado | no favicon/manifest en `public` ni referencia localizada. | Media | Código/assets. |
| Breakpoints móviles | Parcial | CSS responsive presente; no se probó viewport. | Media | Prueba/código. |
| Loading states | Implementado | páginas admin/públicas usan loading/disabled. | Media | Prueba. |
| Form error states | Implementado | mensajes y RUT con `aria-invalid`; cobertura no uniforme. | Media | Prueba/código. |
| Thank-you/confirmación | Parcial | confirmación inline de solicitud; no página dedicada. | Baja | Decisión/código. |
| Privacy Policy | No implementado | ruta/documento público ausente. | Alta | Propietario + código. |
| Terms | No implementado | ruta/documento público ausente. | Alta | Propietario + código. |
| Cookie banner | No implementado | ausente; necesidad depende de tags/cookies activos. | Alta | Decisión + código. |
| Analytics instalado | Pendiente externo | código GTM condicionado; ID vacío en ejemplo. | Alta | Externo/config. |
| Imágenes comprimidas | No implementado | storage copia original; SVG assets no prueban uploads optimizados. | Media | Implementación. |

`Seo.tsx` gestiona title, description, canonical, robots y OG. El código renderiza JSON-LD `FAQPage`, `Organization`, `WebSite`, `Product`, `BreadcrumbList` e `ItemList` donde corresponde. No se localizó un schema específico `LocalBusiness`: la Home ya implementa `Organization`, pero una ampliación orientada a negocio local requiere definir datos públicos reales como tipo de negocio, teléfono, dirección o área atendida, horarios y enlaces oficiales; no deben inventarse valores. `index.html` aporta fallback estático. `robots.txt` y `sitemap.xml` contradicen el dominio objetivo `jem-nexus.cl`. Sitemap omite maquinaria nueva/usada, producto dinámico, contacto, sobre nosotros y FAQ. `/diagnostico-api` tiene meta noindex, pero no aparece disallow específico; login/admin sí aparecen en robots. `web.config` hace fallback SPA. GTM crea `dataLayer` y eventos, pero GA4/GSC/conversiones solo pueden confirmarse externamente.

## 19. Accesibilidad y responsive

La inspección encontró labels, `aria-live`, `aria-invalid`, estados disabled, botones con tipo y diálogos corporativos recientes con manejo de Escape/foco en componentes compartidos. Persisten `window.confirm`; tablas administrativas dependen de CSS/scroll y requieren prueba de teclado/móvil. No se midieron contraste, área táctil, orden de foco ni comportamiento de lector.

Pendientes explícitos: sesión autenticada real, lector de pantalla, zoom 200/400 %, solo teclado, anchos móviles representativos, contraste medido y Lighthouse. No se infieren resultados visuales.

## 20. Documentación histórica

| Documento | Stack descrito | Vigencia | Contradicciones | Uso recomendado |
|---|---|---|---|---|
| `AUDITORIA_SEGURIDAD_BASE.md` | Django/React histórico | Histórico | Django ya no es backend activo. | Contexto de riesgos, no autoridad. |
| `AUDITORIA_SEGURIDAD_PERMISOS_ROLES.md` | etapa de permisos | Parcial/histórico | Matriz puede anteceder seller/support actual. | Comparar decisiones, validar siempre en código. |
| `AUDITORIA_SEO_GEO_ADS.md` | frontend/sitio previo | Parcial | dominios/rutas han cambiado. | Baseline de contenido. |
| `AUDITORIA_DEPENDENCIAS_PROMPT_116.md` | dependencias de ese corte | Histórico | no acredita estado actual. | Trazabilidad. |
| `AUDITORIA_DEPENDENCIAS_PROMPT_119.md` | .NET/React a Prompt 119 | Última evidencia previa | posterior a ella cambió el sistema; no equivale a auditoría actual. | Punto de partida para repetir checks. |
| `cotizador-auditoria-privacidad.md` | cotizador previo/privacidad | Histórico/parcial | flujo comercial actual incluye emisión y perfiles. | Requisitos y decisiones pendientes. |
| `MIGRACION_BACKEND_ASPNETCORE_SQLSERVER.md` | migración a .NET/SQL | Vigente como historia | planes no prueban operación. | Contexto arquitectónico. |
| `REVISION_SCHEMA_ASPNETCORE_SQLSERVER.md` | EF/SQL | Parcial | precede migraciones recientes. | Trazabilidad, no snapshot actual. |
| `PLAN_*`, `PUBLICACION_*`, `POST_DEPLOY_*` | IIS/Plesk | Procedimental | ejecución externa no demostrada. | Checklist operativo. |
| `AUDITORIA_CSS_FRONTEND.md` | React/CSS | Parcial/histórico | precede ajustes responsive recientes. | Baseline visual. |

## 21. Tabla maestra de hallazgos

| ID | Área | Severidad | Estado | Hallazgo | Evidencia | Impacto | Recomendación | Verificación |
|---|---|---|---|---|---|---|---|---|
| ARCH-001 | Arquitectura | Informativa | Cubierto | Stack activo separado y Django retirado/excluido. | `JemNexus.sln`, `frontend/package.json`; sin `backend/`. | Evita auditar stack obsoleto. | Mantener documentación alineada. | Inventario por release. |
| API-001 | Superficie | Baja | Confirmado | Health revela environment/timestamp y no comprueba dependencias. | `Program.cs`, `HealthResponse`. | Fingerprinting menor y health optimista. | Minimizar payload público y añadir readiness autenticado/controlado. | Tests de respuestas y fallo SQL. |
| API-002 | Diagnóstico | Media | Confirmado | Diagnóstico React es público y muestra URL/resultados internos; noindex no protege. | `AppRouter.tsx`; `ApiDiagnostics.tsx`. | Facilita reconocimiento/ruido en producción. | Eliminar de build prod o proteger; conservar noindex. | Acceso anónimo en build prod. |
| AUTH-001 | Refresh | Alta | Confirmado | Refresh reutilizable, sin rotación ni revocación consumida. | `Program.cs`, `RefreshAsync`; `AppRefreshToken`. | Token robado mantiene capacidad de renovar hasta expirar. | Rotación one-time con familia/reuse detection. | Tests de segundo uso y carrera. |
| AUTH-002 | Logout/password | Alta | Confirmado | No hay logout backend; cambio de password no invalida refresh existente. | `MapAuthEndpoints`; `authApi.logout`; `RefreshAsync`. | Persistencia de sesión comprometida. | Endpoint de revocación y versión en refresh. | Login→password/logout→refresh debe dar 401. |
| AUTH-003 | Access validation | Informativa | Cubierto | Usuario activo, rol y versión password se consultan por request. | `Program.cs`, `OnTokenValidated`. | Revoca access ante cambio DB. | Mantener; medir costo/availability. | Tests inactivo/rol/password. |
| AUTH-004 | Token frontend | Media | Confirmado | Access y refresh viven en `localStorage`. | `authApi.ts`, `saveTokens`. | Aumenta impacto de eventual XSS. | Evaluar cookie HttpOnly/arquitectura BFF y CSP. | Threat model + pruebas XSS/CSP. |
| AUTH-005 | Enumeración | Informativa | Cubierto | Login usa 401 uniforme. | `Program.cs`, `LoginAsync`. | Reduce enumeración directa. | Mantener mensaje/tiempo razonablemente uniformes. | Tests casos inválidos. |
| AUTHZ-001 | Backend | Informativa | Cubierto | Grupos admin tienen políticas backend; usuarios support-only y emisión seller-only. | `Endpoints/*`, `Program.cs`. | Frontend no es única barrera. | Mantener matriz automatizada. | Tests 401/403 por ruta/rol. |
| AUTHZ-002 | Claims heredados | Media | Parcial | staff/superuser amplían CommercialRead/Write, pero no roles admin nuevos. | políticas `RequireCommercialRead/Write`. | Tokens heredados pueden escribir catálogo más allá del modelo de dos roles. | Decidir retiro y migrar explícitamente. | Tests con claims sin role. |
| AUTHZ-003 | Clientes | Media | Pendiente de verificación | Todo seller puede buscar/ver/editar todos los perfiles. | `AdminCustomerEndpoints`, política de grupo. | Posible acceso excesivo a PII según regla comercial. | Propietario debe decidir alcance/ownership. | Matriz con sellers distintos. |
| OPS-001 | Rate limiting | Alta | No implementado | No hay limiter/429 para auth, solicitud, SMTP test, uploads o emisión. | ausencia de `AddRateLimiter/UseRateLimiter`. | Fuerza bruta, spam y consumo de recursos. | Límites por ruta e identidad/IP con proxy confiable. | Pruebas 429 detrás de IIS. |
| OPS-002 | Proxy/headers | Media | Pendiente externo | Sin ForwardedHeaders/HSTS/CSP/headers globales versionados. | `Program.cs`; `web.config`. | Esquema/IP/defensa navegador dependen de IIS. | Definir trust proxy y baseline de headers. | Inspección Plesk + curl controlado posterior. |
| VALID-001 | Cotización | Informativa | Cubierto | Campos autoritativos y RUT/ítems/enums se validan backend. | `AdminCommercialQuoteEndpoints.PrepareAsync`. | Evita imponer folio/totales/vendedor. | Mantener casos límite. | Tests DTO malicioso. |
| DATA-001 | Folio | Informativa | Cubierto | Transacción, contador anual e índice único protegen asignación. | `IssueAsync`; `CommercialQuoteFolioAllocator`; DbContext. | Integridad del folio por diseño. | Mantener transacción e índice. | Prueba concurrente SQL Server. |
| DATA-002 | Concurrencia | Media | Parcial | No hay prueba localizada de emisión/RUT simultáneos contra SQL Server real. | tests InMemory y `MigrationMetadataTests`. | Regresiones de aislamiento podrían escapar. | Integración efímera SQL Server. | Dos emisiones/altas RUT paralelas. |
| QUOTE-001 | Inmutabilidad | Informativa | Cubierto | API comercial solo crea/lee emitidas y conserva snapshots. | `AdminCommercialQuoteEndpoints`; modelos. | Preserva historia comercial. | Documentar invariant. | Intentos PUT/PATCH y cambios producto. |
| QUOTE-002 | Idempotencia | Alta | Confirmado | Repetir POST issue crea otra cotización/folio; UI solo bloquea doble clic local. | `IssueAsync`; `CommercialQuoteEditorPage`. | Duplicados por retry/doble request. | Idempotency key/constraint y respuesta reproducible. | Requests simultáneas con misma clave. |
| QUOTE-003 | Borrador/ruta | Baja | Parcial | Enum Draft y `/editar` persisten, pero no hay borrador backend; emitida es readonly. | modelo/status; `AppRouter`; editor. | Confusión y deuda de UX/contrato. | Decidir borrar semántica o implementar borrador. | Tests de navegación/API. |
| QUOTE-004 | PDF | Media | No implementado | Sin endpoint; botones deshabilitados y explicativos. | páginas de cotizaciones; ausencia endpoint PDF. | Flujo termina sin documento descargable. | Servicio PDF y descarga autorizada. | Snapshot/headers/roles/PDF válido. |
| FILE-001 | Reglas de publicación | Media | Confirmado | Static Files sirve directamente `product-images/{productId}/{guid.ext}` y `technical-sheets/{guid}` sin consultar publicación/asociación. | `Program.cs`, `UseStaticFiles`; ambos storages; `GetProductTechnicalSheetFileAsync`. | Con una URL GUID ya conocida, una imagen de producto no publicado o ficha no vinculada puede recuperarse omitiendo la regla que sí aplica el endpoint público; no se demostró exposición de secretos ni enumeración viable. | Mantener públicos los recursos comerciales publicados y mediar o separar los que deban respetar estado/asociación. | Crear fixtures publicado/no publicado/vinculado/no vinculado y solicitar URL directa y endpoint. |
| FILE-004 | Recursos comerciales públicos | Informativa | Cubierto | Imágenes de productos publicados y fichas asociadas ofrecidas desde la ficha pública requieren entrega anónima por diseño. | DTOs públicos, `ProductDetailPage`, `resolveMediaUrl`, `buildPublicTechnicalSheetUrl`. | Permite catálogo y descarga comercial esperados; la publicidad por sí sola no es filtración. | Conservar acceso público intencional y documentar clasificación por subcarpeta. | Pruebas anónimas positivas solo para recursos publicados/asociados. |
| FILE-002 | Optimización | Media | No implementado | Imágenes se copian sin resize/compresión/conversión/dimensiones. | `LocalProductImageStorage`. | Peso, memoria de decodificación y rendimiento. | Pipeline seguro con límites y derivados. | Fixtures grandes/bomba + métricas. |
| FILE-003 | Consistencia IO/DB | Media | Confirmado | Operaciones archivo/DB no forman transacción atómica; posibles huérfanos. | write/delete en endpoints y storages. | Consumo de disco o referencias rotas tras fallo. | Compensación, staging/rename y job de reconciliación. | Inyección de fallos IO/DB. |
| OPS-003 | Persistencia | Alta | Pendiente externo | Volumen/ACL/backups de uploads y DB no son comprobables en repo. | `Uploads.RootPath` vacío por defecto; docs Plesk. | Redeploy/fallo podría perder archivos si operación está mal configurada. | Confirmar volumen persistente, ACL y restores. | Evidencia Plesk y simulacro restore. |
| PRIV-001 | Privacidad | Alta | Confirmado | Sin Privacy/Terms/retención/eliminación/anonimización ni información del formulario. | rutas React y endpoints; ausencia de documentos. | Gobernanza insuficiente de PII y transparencia. | Decisión propietario + flujos y contenido revisado. | Revisión técnica/legal independiente. |
| SEO-001 | Dominio/sitemap | Alta | Confirmado | robots y sitemap usan dominios Render obsoletos; sitemap solo dos rutas. | `public/robots.txt`; `sitemap.xml`. | Señales de indexación erróneas y cobertura incompleta. | Regenerar para `jem-nexus.cl`, incluir rutas/productos publicados. | Validadores + GSC externo. |
| SEO-002 | 404 | Media | Confirmado | Catch-all redirige a home. | `AppRouter.tsx`, ruta `*`. | Soft 404 y UX/confusión de indexación. | Página 404 con metadata noindex y estrategia HTTP/IIS. | URL inexistente + inspección status/meta. |
| SEO-003 | Medición | Informativa | Pendiente externo | GTM está preparado, GA4/GSC/sitemap enviado no acreditados. | `analytics.ts`; `.env.example`. | No se puede afirmar medición/indexación activas. | Verificar cuentas, tags y consentimiento. | Tag Assistant/GTM/GSC por propietario. |
| SEO-004 | Datos estructurados | Media | Parcial | `FAQPage`, `Organization`, `WebSite`, `Product`, `BreadcrumbList` e `ItemList` están implementados; falta únicamente el tipo `LocalBusiness` y completar datos locales reales. | `FaqPage.tsx`; `HomePage.tsx`; `CatalogPage.tsx`; `ProductDetailPage.tsx`; `seo.ts`. | La base estructurada está cubierta, pero la señal de negocio local queda incompleta. | Definir datos locales reales antes de añadir `LocalBusiness`; no inventar teléfono, dirección, horarios, área o enlaces. | Inspección DOM y validadores Schema/Rich Results por cada ruta. |
| TEST-001 | CI/frontend | Media | Confirmado | Sin workflows ni tests frontend localizados. | ausencia `.github`; `frontend` sin tests. | Regresiones llegan sin puerta automatizada. | CI para restore/build/test/audit controlado y tests UI críticos. | Ejecución CI reproducible. |
| A11Y-001 | Verificación | Baja | Pendiente de verificación | Semántica parcial correcta, pero falta prueba teclado/lector/zoom/contraste. | componentes/formularios/CSS. | Barreras no detectables solo estáticamente. | Auditoría manual y automatizada autenticada. | Checklist WCAG/Lighthouse posterior. |
| FE-001 | Confirmaciones | Baja | Confirmado | Quedan `window.confirm` en varios CRUD. | páginas admin enumeradas por búsqueda estática. | UX/foco inconsistentes. | Migrar gradualmente a diálogo accesible compartido. | Teclado/Escape/restauración foco. |

### 21.1 Totales

**Por severidad (33):** Crítica 0; Alta 7; Media 13; Baja 4; Informativa 9.

**Por estado (33):** Confirmado 13; Cubierto 8; Parcial 4; No implementado 3; Pendiente externo 3; Pendiente de verificación 2; No aplica 0; Histórico 0.

### 21.2 Diez prioridades principales

1. AUTH-001: refresh one-time y detección de reutilización.
2. AUTH-002: revocación backend/logout/cambio de contraseña.
3. OPS-001: rate limiting en auth, solicitud y efectos costosos.
4. QUOTE-002: idempotencia de emisión.
5. OPS-003: volumen persistente, ACL y restore probado en Plesk.
6. PRIV-001: política, transparencia, retención y derechos técnicos.
7. SEO-001: dominio y sitemap correctos.
8. AUTHZ-003: decisión de acceso global a clientes.
9. FILE-001: preservar recursos públicos y cerrar bypass de publicación por URL conocida.
10. TEST-001/DATA-002: CI y concurrencia real SQL Server.

**Quick wins:** corregir dominios robots/sitemap; añadir 404/noindex; retirar/proteger diagnóstico; restringir test SMTP; documentar invariantes de emisión; favicon; eliminar logs debug productivos.

**Decisiones del propietario:** alcance de sellers sobre clientes, support sin emisión, claims heredados, retención/eliminación, textos legales/cookies, datos reales necesarios para ampliar `Organization` con `LocalBusiness` y prioridad PDF.

**Plesk/externos:** HTTPS/proxy/headers, secretos, CORS efectivo, volumen/ACL/backups, SMTP, GTM/GA4, GSC y envío sitemap.

**Implementación:** refresh/logout, limiter, idempotencia, archivos, PDF, 404, SEO/schema/legales, optimización de imágenes y CI.

**Pruebas locales:** suites existentes, SQL Server concurrente/migraciones, frontend, IO fallido, authz por rol, responsive/accesibilidad y build de publicación; ninguna se ejecutó aquí.

## 22. Comprobaciones externas pendientes

- Configuración real Plesk/IIS: variables, secretos, environment, forwarded headers, TLS/HSTS/headers, permisos y persistencia.
- Aplicación/alineación de las 14 migraciones y constraints en SQL Server productivo, sin ejecutar cambios desde esta auditoría.
- Backups y restauración de SQL/uploads; monitoreo, logs, alertas y capacidad de disco.
- SMTP TLS, relay, remitente, deliverability y tratamiento de PII en proveedor/log sink.
- GTM/GA4, consentimiento, conversiones, propiedad GSC y sitemap enviado.
- DNS/canonical/HTTP status/caching/compresión reales de `jem-nexus.cl` y `api.jem-nexus.cl`.
- Pruebas autenticadas, Lighthouse, lector de pantalla, teclado, contraste, zoom y móviles.

## 23. Plan recomendado (sin implementación)

### Fase A — Seguridad e integridad

Rotación/revocación de refresh, logout, rate limiting, idempotencia, decisión authz de clientes/claims, pruebas concurrentes SQL Server, separación de archivos, compensación IO y baseline proxy/headers.

### Fase B — SEO técnico y publicación

Corregir dominio/canonical/robots/sitemap, incluir rutas/productos publicados, 404 real/noindex, favicon, decisión sobre diagnóstico y verificación IIS.

### Fase C — Privacidad y medición

Definir Privacy Policy, Terms, información/consentimiento, retención/eliminación, cookie/GTM consent; validar GA4, Search Console y conversiones externamente.

### Fase D — GEO, contenido e imágenes

Conservar los schemas ya implementados (`FAQPage`, `Organization`, `WebSite`, `Product`, `BreadcrumbList`, `ItemList`), definir datos reales antes de añadir `LocalBusiness`, trabajar intención/clusters/interlinking/resúmenes y optimizar imágenes con límites seguros y derivados.

### Fase E — Funcionalidad y verificación pendiente

Decidir/implementar PDF autorizado, cerrar semántica de borradores/ruta editar, CI, tests frontend, publicación reproducible y auditoría autenticada de accesibilidad/responsive.

## 24. Confirmación de no intervención

Durante esta auditoría no se modificó código, frontend, backend, backend histórico, configuración, dependencias, lockfiles, migraciones ni datos; no se generaron builds. No se ejecutaron restore, build, tests, auditorías online, comandos EF, servidores, navegadores, capturas, requests a producción, SMTP, Plesk, deploy, publicación, push o merge. El único cambio preparado es este informe documental.
