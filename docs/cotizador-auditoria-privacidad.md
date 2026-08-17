# Auditoría técnica y de privacidad previa al cotizador comercial

**Fecha de auditoría:** 17 de agosto de 2026
**Commit inspeccionado:** `505c398` (`Merge pull request #259 ... corrige-alineacion-visual-del-formulario-de-vendedores`)
**Alcance:** revisión estática de `backend-dotnet` y `frontend/src`; no se ejecutaron aplicaciones, pruebas, migraciones, SQL ni consultas a producción.
**Convención:** **Hecho** describe código observado; **Inferencia** identifica una conclusión razonable no garantizada en ejecución; **Recomendación** es diseño futuro; **Pendiente** requiere decisión o verificación.

> **Este documento es una preparación técnica y no reemplaza la revisión de un abogado ni de un contador tributario en Chile.**

La historia integrada confirma backend administrativo de vendedores (`18fba48`), interfaz administrativa (`f48dbd2`), códigos automáticos (`fe58bfa`), páginas completas de creación/edición (`dd9c1f7`) y corrección visual del formulario y título (`a93a88f`). El Prompt 120 continúa aplazado.

## 1. Estado actual del sistema de cotizaciones

### 1.1 Recorrido confirmado

1. **Origen y actor.** Cualquier visitante, sin autenticación, abre `/cotizar` (`frontend/src/router/AppRouter.tsx`) y `QuotePage` envía una solicitud general o asociada a un producto. El producto puede llegar en el parámetro de URL `product`; se consulta y después se envía su `id`. Los datos del formulario no se escriben en la URL.
2. **Datos recogidos.** `QuoteRequestPublicPayload` y `QuotePage` recogen nombre, teléfono, email, empresa, ciudad/comuna, método preferido (`phone`, `email`, `whatsapp`), mensaje y producto opcional (`frontend/src/types/catalog.ts`, `frontend/src/pages/QuotePage.tsx`). La UI exige nombre, teléfono y mensaje mediante validación propia; email se valida si existe. **No se encontró** casilla de consentimiento, aviso de privacidad o enlace informativo junto al formulario.
3. **API.** `createQuoteRequest` hace `POST /api/public/quote-requests` con JSON (`frontend/src/services/catalogApi.ts`). El grupo es `AllowAnonymous` (`backend-dotnet/JemNexus.Api/Endpoints/CommercialPublicReadEndpoints.cs`). `QuoteRequestPublicCreateDto` limita por anotación nombre 160, teléfono 40, email 254, empresa 160, ciudad 120 y método 20 caracteres; `CommercialValidation.ValidateQuoteRequest` exige nombre y mensaje, limita mensaje a 2.000, valida email opcional y enumeraciones. Existe una diferencia real: el backend no exige teléfono aunque el modelo/UI lo presentan como requerido.
4. **Persistencia.** Se crea `QuoteRequest`, estado `new`, timestamps UTC, y se guarda antes de notificar. La tabla `QuoteRequests` conserva los campos anteriores, `InternalNotes`, `SellerResponse`, hitos `ContactedAt`/`QuotedAt`/`ClosedAt`, `CreatedAt`/`UpdatedAt`, FK opcional a `Product` y referencias opcionales `CreatedById`/`UpdatedById` (`Models/QuoteRequest.cs`, `Data/JemNexusDbContext.cs`, migraciones `20260603182917_InitialCommercialSchema.cs` y `20260604020543_AddAuthUsersAndAuditRelations.cs`). La creación pública no asigna `CreatedById`.
5. **Correo.** Tras guardar, `IQuoteNotificationService.SendNewQuoteRequestAsync` intenta avisar por SMTP al destinatario comercial configurado. `SmtpQuoteNotificationService` construye asunto y cuerpo de texto con identificador, fecha, cliente, contacto, empresa, ciudad, preferencia, producto y mensaje; no es un correo de confirmación al cliente. Si está deshabilitado/mal configurado o SMTP falla, devuelve un resultado fallido; el endpoint registra advertencia. Una excepción inesperada se registra como error. En ambos casos la solicitud permanece guardada y el cliente recibe `201`, por lo que el correo es deliberadamente no bloqueante (`Endpoints/CommercialPublicReadEndpoints.cs`, `Services/Notifications/SmtpQuoteNotificationService.cs`).
6. **Panel.** `/admin/cotizaciones` lista todas las solicitudes, busca en nombre/teléfono/email/empresa/ciudad/mensaje, filtra por estado/producto y ordena por fechas/estado (`CommercialReadEndpoints.cs`, `AdminQuotesPage.tsx`). Muestra un seudofolio `COT-` + `Id` rellenado a seis dígitos; **no existe un folio persistido ni una secuencia de cotización**. El detalle muestra datos personales, producto, mensaje, estado y permite editar estado/notas internas (`AdminQuoteDetailPage.tsx`). `SellerResponse` existe y la API lo acepta, pero la pantalla no ofrece un campo visible para editarlo.
7. **Estados.** Son `new`, `contacted`, `quoted`, `closed`, `discarded` (`Models/QuoteRequest.cs`). La primera transición a contacted/quoted/cerrada o descartada fija el timestamp correspondiente; volver de estado no lo limpia. No se observó máquina de transiciones ni historial de cambios.
8. **Autorización.** Lectura exige política `RequireCommercialRead`; escritura, incluida la modificación, `RequireCommercialWrite`. En `Program.cs`, ambas admiten roles `seller` y `support_admin`. Las rutas React están bajo `ProtectedRoute`; soporte administra usuarios en rutas separadas. La API devuelve el conjunto completo: no filtra solicitudes por vendedor. La atribución de actualización usa la identidad autenticada en `UpdatedById`, pero la respuesta no expone ese actor.

### 1.2 Identidad, folio y relaciones

- `AppUser` usa `Id` como identificador relacional real; contiene `SellerCode`, email, hash de contraseña, rol, nombre, activación y timestamps (`Models/AppUser.cs`). `SellerCodeGenerator`/secuencia SQL generan códigos y el índice filtrado garantiza unicidad; el constraint exige código sólo al rol `seller`. El ejemplo esperado es `VEN-0001`.
- Los roles reales son `seller` y `support_admin` (`Models/AppRoles.cs`). La desactivación lógica es `IsActive`; administración de usuarios está restringida a support admin (`Endpoints/AdminUserEndpoints.cs`, `frontend/src/components/admin/ProtectedRoute.tsx`).
- La solicitud sólo relaciona un producto opcional; no contiene múltiples ítems, cantidades, precios ni snapshot de producto. La FK usa `NoAction`, y la eliminación de producto se bloquea si existen solicitudes.
- `CreatedAt`/`UpdatedAt` se mantienen automáticamente. `CreatedById`/`UpdatedById` son atribución parcial, no un log inmutable. No existe vendedor responsable dedicado ni snapshot de su nombre/código.

### 1.3 Eliminación, exportación, retención y pruebas

- **No encontrado:** endpoint backend de eliminación de `QuoteRequest`, anonimización, exportación, política/automatización de retención, PDF o envío al cliente. `frontend/src/services/adminApi.ts` contiene `deleteQuote`, pero no hay ruta DELETE correspondiente ni acción visible: es cliente huérfano, no capacidad efectiva confirmada.
- **Pruebas encontradas:** `CommercialPublicQuoteEndpointTests.cs` cubre creación/validación/producto y notificación; `QuoteNotificationServiceTests.cs`, correo; `CommercialReadEndpointTests.cs` y `CommercialWriteEndpointTests.cs`, lectura, filtros, autorización/actualización; `CommercialValidationTests.cs` y `CommercialModelTests.cs`, reglas/modelo; `AdminUserEndpointTests.cs`, vendedores; `MigrationMetadataTests.cs`, metadatos. Esta auditoría no las ejecutó por instrucción.
- **URL/almacenamiento/analítica:** el producto puede aparecer como `?product=...`; no se ponen datos del cliente allí ni se encontró persistencia local del formulario. `trackQuoteSubmit` transmite sólo identificador/nombre de producto y método preferido (`frontend/src/utils/analytics.ts`), no los campos de contacto. Los tokens administrativos sí quedan en `localStorage`, riesgo transversal que requiere evaluación independiente.
- **Riesgos confirmados:** endpoint público sin rate limiting específico visible; retorno `201` incluye todos los datos enviados; mensajes/notas sin longitudes de base de datos salvo mensaje validado; datos personales accesibles a todos los roles comerciales; sin paginación; sin propietario; sin historial; logging del error SMTP podría incorporar mensajes del proveedor; ausencia de transparencia/retención/operaciones de derechos. **Pendiente:** límites efectivos del servidor/proxy Plesk, política de logs/backups, analítica desplegada y configuración SMTP/hosting reales.

## 2. Separación entre solicitud web y cotización comercial

| Concepto | Solicitud web actual | Cotización comercial futura |
| --- | --- | --- |
| Creador | Visitante | Vendedor autenticado |
| Autenticación | Anónima | Obligatoria; `seller`/control administrativo |
| Propósito | Manifestar interés y pedir contacto | Oferta comercial versionada con importes y condiciones |
| Folio | UI deriva `COT-000123` del `Id`; no persistido | Global, backend, al emitir |
| Vendedor responsable | No existe asignación | FK a `AppUser` + snapshot visible/código |
| Datos del cliente | Contacto y mensaje | Snapshot documental mínimo; perfil opcional separado |
| Productos o ítems | Cero o un `Product` opcional | Uno o más ítems, reglas aún pendientes |
| Estados | new/contacted/quoted/closed/discarded | draft/issued/versioned/void, por definir |
| PDF | No existe | Documento corporativo íntegro |
| Correo | Aviso interno SMTP | V1: descarga/envío externo; integración posterior evaluable |
| Retención | No definida | Política por categoría/finalidad y eventuales obligaciones |
| Auditoría | timestamps y último actualizador | Eventos de emisión, versión, descarga, envío, cambios y privacidad |

**Recomendación:** mantener `QuoteRequest` y cotización comercial como agregados distintos. Un vínculo opcional y explícito permite trazabilidad, precarga y medir conversión sin alterar el registro original. Riesgos: duplicar PII, permisos demasiado amplios, acoplar ciclos de vida, confundir consentimiento/finalidad y borrar en cascada. Debe ser FK nullable, con autorización y auditoría, sin convertir ni fusionar automáticamente entidades.

## 3. Modelo conceptual recomendado

No es una decisión de implementación; la tabla evalúa posibilidades.

| Concepto | Finalidad y mínimos | Relaciones/acceso | Edición/eliminación/historial | PII | Etapa |
| --- | --- | --- | --- | --- | --- |
| Solicitud pública existente | interés, contacto, mensaje, producto opcional | producto; comercial autorizado | corregible/anonimizable según política; preservar eventos | Sí | existente; endurecer |
| Cotización comercial | borrador, responsable, moneda/reglas, estado | vendedor, ítems, vínculo opcional a solicitud/perfil | borrador editable; emitida no se sobrescribe | Sí | V1 |
| Versión/snapshot emitido | representación exacta: folio, partes, totales, condiciones | cotización y versión anterior | inmutable; anular/bloquear, no edición destructiva | Sí | V1, aunque su forma física se decide |
| Ítem | descripción, cantidad, precio/impuesto; referencia opcional | cotización; catálogo opcional | editable en draft; snapshot al emitir | quizá | V1 |
| Perfil reutilizable | autocompletar contacto con finalidad transparente | cotizaciones sin dependencia histórica | corregible/suprimible; nunca reescribe snapshots | Sí | posterior a V1 mínima |
| Vendedor responsable | responsabilidad viva (`AppUser.Id`) | cotización | desactivación no rompe historial; snapshot al emitir | Sí | V1 |
| Secuencia/contador | unicidad del correlativo | emisión | atómico; no borrar/reusar | No | V1 |
| Registro de auditoría | actor, acción, fecha, objeto, motivo, metadatos mínimos | todos; acceso restringido | append-only; retención propia | Puede | V1 mínimo/posterior ampliado |
| Solicitud de derechos | identidad verificada, alcance, hitos, resolución | registros localizados; privacidad/support | estados trazables; evidencia mínima | Sí | etapa privacidad |
| Bloqueo/retención legal | base, alcance, responsable, expiración/revisión | dato/documento afectado | evita tratamiento/borrado indebido; revisable | Puede | posterior, antes de automatizar borrado |

No se justifica implementar cada concepto como tabla independiente: versión puede comenzar como snapshot estructurado inmutable; secuencia puede ser objeto SQL Server; auditoría requiere diseño proporcional.

## 4. Folio y responsabilidad comercial

**Recomendación acordada:** asignar el folio **en backend y dentro de la transición atómica de emisión**, no al crear el borrador. Será global, independiente del vendedor, no manual, no derivado de `SellerCode`, y jamás `MAX + 1`. Una secuencia SQL Server o contador bloqueado transaccional más índice UNIQUE debe tolerar concurrencia; se aceptan saltos para preservar unicidad.

`COT-2026-000001` es legible, pero obliga a definir semántica. Se recomienda contador global que **no reinicie** por año; el año es prefijo de la fecha de emisión en zona `America/Santiago`. Así, el cambio de año no abre dos espacios de secuencia. Alternativa: secuencia anual con unicidad `(year, number)`, más compleja y propensa a errores de borde. Definir una única librería/regla de zona y probar medianoche/año nuevo.

- Borradores abandonados no consumen folio; se purgan según política.
- Cancelación antes de emisión no tiene folio. Fallo después de reservar puede dejar salto, nunca reutilización.
- Una emisión queda inmutable. Corrección crea versión/reemisión enlazada; decidir si conserva folio + versión (`v2`) o recibe uno nuevo. Recomendación inicial: mismo negocio y folio, número de versión explícito, preservando todas; cambio material sujeto a validación comercial/legal.
- Anulación mantiene folio, documento, motivo, actor y fecha, marcado como anulado; no recicla el número.
- SQL Server: secuencia atómica + columna/índice único sobre folio (y, si aplica, componentes); transacción une consumo, snapshot, estado y auditoría.

**Relación viva:** FK no nullable `ResponsibleSellerId -> AppUser.Id`, usada para autorización, asignación y perfil actual. **Snapshot histórico al emitir:** `SellerCode`, nombre visible y, sólo si es necesario, contacto corporativo. Cambiar/desactivar usuario o modificar su nombre/código no altera documentos emitidos. No copiar PasswordHash, tokens ni secretos.

## 5. Datos del cliente y perfil reutilizable

### Datos dentro de la cotización

Una versión emitida conserva únicamente el snapshot de datos usado en ese documento. Corregir un perfil no modifica versiones históricas; una corrección documental crea nueva versión o nota trazable según la regla que Franz apruebe.

### Perfil reutilizable de cliente

Es opcional y sólo autocompleta. Flujo: (1) vendedor escribe datos; (2) completa; (3) se pregunta **«¿Deseas guardar estos datos como cliente para futuras cotizaciones?»** antes o después de emitir según decisión; (4) «no» crea sólo el snapshot; (5) «sí» crea/vincula perfil tras informar finalidad/uso y controlar duplicados.

La deduplicación debe sugerir, no fusionar silenciosamente: email normalizado (trim/case), teléfono en formato internacional cuando sea posible y RUT validado/normalizado sólo si se decide usarlo. RUT/email no son claves infalibles; empresa puede tener varios contactos, y persona natural/empresa requieren modelos distintos. La supresión del perfil no destruye automáticamente snapshots sujetos a finalidad o retención válida.

| Campo candidato | Finalidad | Obligatoriedad inicial | Sensibilidad | PDF | Perfil | Duda pendiente |
| --- | --- | --- | --- | --- | --- | --- |
| Tipo persona/empresa | estructura | condicional | baja | quizá | sí | ¿ambas? |
| Nombre/razón social | destinatario | sí | personal | sí | sí | formato |
| Nombre contacto/cargo | contacto empresa | condicional | personal | quizá | sí | necesidad |
| RUT | identificación | no hasta validar | identificador | por decidir | por decidir | base/finalidad |
| Email | entrega/contacto | al menos un canal | personal | quizá | sí opcional | verificación |
| Teléfono | contacto | al menos un canal | personal | quizá | sí opcional | normalización |
| Dirección/comuna/ciudad | entrega/documento | opcional/condicional | personal | según uso | según uso | granularidad |
| Producto/servicio e ítems | oferta | sí | baja | sí | no | catálogo/libre |
| Condiciones/observaciones | alcance | condicional | puede contener PII | sí | no | límites/sanitización |

Aplicar minimización: no solicitar RUT/dirección/cargo “por si acaso”; separar campos estructurados de texto libre y advertir que no se ingresen datos sensibles innecesarios.

## 6. Privacidad y preparación para la Ley 21.719

**Fuentes oficiales consultadas/referenciadas el 17 de agosto de 2026:** [Ley 21.719, BCN](https://www.bcn.cl/leychile/navegar?idNorma=1209272), [Ley 19.628, BCN](https://www.bcn.cl/leychile/navegar?idNorma=141599) y [FAQ SII sobre conservación de DTE](https://www.sii.cl/preguntas_frecuentes/factura_electronica/001_003_2356.htm). La consulta automatizada fue bloqueada (401/403), por lo que deben releerse los textos oficiales en revisión profesional antes de implementar.

Al 17 de agosto de 2026 rige la Ley 19.628. La Ley 21.719 fue publicada el 13 de diciembre de 2024 y su vigencia diferida comienza el **1 de diciembre de 2026**. Este documento no declara cumplimiento ni interpreta definitivamente bases jurídicas; recomienda preparar desde ahora inventario, privacidad por diseño, evidencia y operaciones de derechos.

### Controles técnicos desde ahora

- Documentar finalidad separada para solicitud, cotización, perfil, entrega, analítica y auditoría; evaluar profesionalmente consentimiento u otra base de licitud. Registrar versión del aviso/manifestación cuando corresponda y permitir revocación sin borrar evidencia u obligaciones válidas.
- Proporcionalidad/minimización; calidad mediante corrección; transparencia antes de capturar/guardar perfil; acceso limitado, cifrado/transporte, backups protegidos y responsabilidad asignada.
- Diseñar acceso, rectificación, supresión, oposición y portabilidad cuando resulte aplicable, con verificación de identidad, trazabilidad, respuesta segura y plazos operativos por confirmar legalmente.
- Plan de incidentes: detectar, contener, preservar evidencia mínima, evaluar alcance/notificación con asesoría y corregir. Inventariar encargados: Plesk/hosting, correo, analítica, backup y almacenamiento PDF; contratos, ubicación/subencargados, eliminación y devolución.
- No registrar PII completa en logs; usar IDs, redacción y accesos/retención. Emails y PDFs son nuevas copias: controlar destinatario, acceso, expiración y eliminación. Restaurar backups debe reaplicar una lista de supresiones/bloqueos para evitar resurrección.

### Retención tributaria no automática

El SII informa seis años para **documentos tributarios electrónicos (DTE)**. Una cotización comercial no se clasifica automáticamente como DTE. Deben inventariarse por separado cotizaciones, órdenes, facturas y otros documentos, y validar profesionalmente la retención tributaria/contractual exacta. Una supresión puede limitarse por obligación legal válida, pero la limitación debe documentarse, justificarse, revisarse y aplicarse sólo a datos necesarios; bloquear usos incompatibles durante la retención.

## 7. Operaciones de privacidad y auditoría

Procedimiento conceptual: recibir y verificar identidad sin recolectar exceso; asignar caso; buscar por identificadores normalizados en solicitudes, perfiles, cotizaciones/snapshots, auditoría, PDFs, correo y sistemas encargados; revisar resultados sin revelar homónimos; exportar resumen legible y, cuando corresponda, JSON/CSV estructurado por canal autenticado; decidir rectificación/supresión/bloqueo/retención con fundamento; ejecutar; registrar actor, fecha, campos/categorías, razón y resultado; notificar; programar revisión y propagación a backups/proveedores.

- **Perfil:** corregir o suprimir sin reescribir emitidas.
- **Solicitud web:** corregir, anonimizar o eliminar según finalidad/retención y vínculos.
- **Snapshot emitido:** conservar íntegro sólo con base válida; corregir mediante versión y bloquear otros usos.
- **Borrador:** borrar tras ventana aprobada si no hay necesidad; nunca recibió folio.
- **Bloqueo legal:** acceso restringido, motivo/alcance/fecha de revisión; no es retención indefinida.
- **Backups:** eliminación diferida documentada por ciclo; acceso sólo recuperación; tras restaurar, reprocesar supresiones.

| Operación | Seller | Support admin | Automatizada | Requiere auditoría |
| --- | ---: | ---: | ---: | ---: |
| Buscar/consultar cliente propio | limitada por asignación | sí, por caso | no | sí |
| Exportación de derechos | no | aprobar/ejecutar | preparación posible | sí |
| Corregir perfil | propuesta/si autorizado | sí | no | sí |
| Rectificar snapshot emitido | no sobrescribir | crea proceso/versión | no | sí |
| Suprimir/anonimizar | solicitar, no ejecutar silenciosamente | decidir/ejecutar | sólo política aprobada | sí |
| Bloquear por retención | no | sí | vencimiento/alerta | sí |
| Purgar borradores vencidos | no ad hoc | supervisa | sí | resumen + excepciones |
| Restaurar backup | no | operación técnica segregada | parcial | sí |

La auditoría debe contener IDs y cambios mínimos, no volcar datos de otros clientes ni secretos.

## 8. Seguridad recomendada

- Mantener creación web pública separada y aplicar rate limiting, antiabuso, DTO estricto, longitudes para todos los textos, límite de cuerpo en app/proxy y respuestas sin PII innecesaria. Nunca confiar sólo en validación React.
- Autenticar cotizador. Definir si seller ve sólo asignadas/propias; support_admin ejerce supervisión. Autorizar cada objeto para prevenir IDOR, incluidos PDFs con IDs/URLs predecibles. Usar descargas autenticadas o enlaces opacos, breves, revocables y de un solo propósito.
- Registrar creación, asignación, cambio de estado/importe, emisión, versión, anulación, descarga, envío y privacidad. Logs sin contraseñas, tokens, secretos ni cuerpos completos/PII; igual prohibición para cotizaciones, perfiles y PDFs.
- Sanitizar/escapar texto al generar HTML/PDF; límites contra contenido hostil, inyección y agotamiento. No aceptar adjuntos en V1; si se agregan, validar tipo/tamaño, malware, nombre y almacenamiento privado.
- Previsualizar y confirmar destinatario antes de correo; evitar autocompletado ambiguo, registrar intentos sin cuerpo, reintentos idempotentes y errores no bloqueantes respecto del documento ya emitido.
- Folio transaccional y UNIQUE. Concurrencia y reintentos no deben emitir dos veces. Desactivar vendedor bloquea sesiones/acciones nuevas, pero conserva FK y snapshot histórico. Evaluar revocación inmediata de tokens existentes.

## 9. PDF y entrega al cliente

El PDF futuro debe fijar logo/identidad, datos legales del emisor confirmados, cliente mínimo, folio, versión, fecha/hora y vigencia en formato chileno/zona `America/Santiago`, vendedor, ítems (descripción, cantidades, precio), subtotal, descuentos, IVA, total, moneda, pago/entrega, observaciones, paginación y marca de anulación. Todos los cálculos ocurren en backend con redondeo definido; el documento se deriva del snapshot, nunca del catálogo/perfil vivo.

| Estrategia | Ventaja | Riesgo |
| --- | --- | --- |
| Generar al descargar | menos almacenamiento | cambios de plantilla pueden alterar el mismo folio; costo/disponibilidad |
| Generar/guardar al emitir | bytes íntegros y entrega reproducible | almacenamiento, acceso, backups y retención de PII |
| Combinada recomendada | snapshot/hash inmutable + PDF emitido privado; regeneración controlada idéntica | mayor diseño, requiere prueba determinista |

Evaluar después bibliotecas compatibles con ASP.NET Core .NET 8, SQL Server y Plesk, licencia, accesibilidad, fuentes/logo embebidos, paginación, rendimiento y operación sin dependencias nativas difíciles. No se selecciona paquete ahora.

**V1 recomendada:** emitir y descargar de forma autorizada; el vendedor envía externamente. Dejar correo integrado fuera hasta resolver remitente, confirmación del destinatario, plantillas, registro de entrega, reintentos idempotentes y fallos no bloqueantes.

## 10. Decisiones pendientes del propietario

Cada pregunta sigue abierta; la recomendación no sustituye decisión de Franz.

### Cliente y documento

1. **¿Persona, empresa o ambas?** Recom.: ambas con campos condicionales. Altern.: sólo empresa/persona. Impacto: esquema, validación, PDF y deduplicación.
2. **¿Se utilizará RUT?** Recom.: no hacerlo obligatorio hasta definir finalidad/base. Altern.: opcional/obligatorio por tipo. Impacto: validación, sensibilidad y derechos.
3. **¿Qué datos del cliente aparecerán en PDF?** Recom.: nombre/razón social y canal/dirección sólo necesarios. Altern.: set amplio. Impacto: exposición y plantilla.
4. **¿Cuándo ofrecer guardar cliente?** Recom.: después de completar y antes de salir, separado de emisión. Altern.: antes/después de emitir. Impacto: UX, transparencia, fallos parciales.
5. **¿Quién exporta/elimina PII?** Recom.: support_admin con doble confirmación/revisión. Altern.: rol privacidad futuro. Impacto: RBAC/auditoría.

### Ítems y cálculos

6. **¿Catálogo, libres o híbridos?** Recom.: híbridos con snapshot. Altern.: sólo catálogo/libres. Impacto: relaciones e integridad histórica.
7. **¿CLP, USD o ambas?** Recom.: una moneda por cotización; iniciar CLP. Altern.: USD/multimoneda. Impacto: precisión, tipo de cambio y PDF.
8. **¿Precios netos o con IVA?** Recom.: entrada neta y desglose explícito, sujeto a validación. Altern.: bruto/ambos. Impacto: cálculo/redondeo.
9. **¿Descuentos por línea/globales?** Recom.: dejarlos fuera de V1 o uno global controlado. Altern.: ambos. Impacto: permisos/cálculo/auditoría.
10. **¿Productos, servicios y repuestos?** Recom.: sí mediante tipo de ítem. Altern.: productos primero. Impacto: campos/unidades.
11. **¿Imágenes?** Recom.: fuera de V1. Altern.: imagen principal congelada. Impacto: peso, licencias, PDF.

### Ciclo comercial y entrega

12. **¿Vigencia configurable?** Recom.: valor por defecto corporativo con override. Altern.: fija/libre. Impacto: reglas/fecha.
13. **¿Pago y entrega?** Recom.: catálogo de textos aprobados + observación. Altern.: libre. Impacto: consistencia/inyección.
14. **¿Editar tras emitir?** Recom.: no sobrescribir. Altern.: corrección menor registrada. Impacto: integridad.
15. **¿Modificación crea versión?** Recom.: sí. Altern.: folio nuevo. Impacto: modelo/visualización.
16. **¿Qué significa anular?** Recom.: documento visible inválido con motivo/actor/fecha, sin borrar. Altern.: estado simple. Impacto: auditoría.
17. **¿Almacenar PDF?** Recom.: sí, privado, junto con hash/snapshot y retención definida. Altern.: regenerar. Impacto: storage/privacidad.
18. **¿Correo integrado o manual?** Recom.: manual en V1. Altern.: SMTP integrado. Impacto: entregabilidad, errores y PII.
19. **¿Cuánto conservar borradores?** Recom.: ventana corta configurable (p. ej., propuesta 30–90 días), validar negocio/legalmente. Altern.: manual/otra ventana. Impacto: job y recuperación.
20. **¿Encabezado/pie corporativo?** Recom.: Franz entregue razón social, RUT, domicilio, contactos, logo, textos y aprobación. Altern.: configuración administrativa posterior. Impacto: snapshot/plantilla.

## 11. Plan de implementación por etapas

Cada etapa debe ser un prompt pequeño; no se fijan correlativos.

| Etapa | Alcance/dependencias | Riesgos | Aceptación y pruebas | Fuera |
| --- | --- | --- | --- | --- |
| Confirmar reglas | responder sección 10, aviso/retención; Franz + asesoría | requisitos ambiguos | matriz aprobada, ejemplos de cálculo/PDF | código |
| Diseñar persistencia/folio | agregado, estados, snapshots, secuencia | concurrencia/borrado | ADR, diagramas, casos de año/reintento | migración |
| Entidades y migración | modelo mínimo SQL/EF | pérdida/rollback | revisión SQL generada, tests modelo/migración aislados | endpoints/UI |
| Servicios/endpoints | CRUD draft, asignación, emisión transaccional | IDOR/doble emisión | autorización, validación, concurrencia/idempotencia | PDF/correo |
| Auditoría/privacidad básica | eventos, búsqueda de caso, bloqueo mínimo | log con PII | tests de acceso/trazabilidad/redacción | automatización plena |
| Listado/editor frontend | drafts/ítems/cálculos preview | cálculos divergentes | accesibilidad, errores, responsive, E2E | botón público/PDF |
| Botón `Crear cotización` | navegación desde cotizaciones | confusión de conceptos | ruta protegida, responsive y etiqueta clara | cambiar solicitud web |
| Emisión/PDF | snapshot, folio, versión, render | integridad/fuentes | golden tests, totales, páginas, zona, concurrencia | correo |
| Descarga segura | storage/autorización/expiración | fuga/IDOR | seller asignado/admin, revocación y logs | enlaces públicos permanentes |
| Evaluar correo | decisión y prototipo operativo | destinatario/duplicados | confirmación, idempotencia, retry, métricas | marketing |
| Perfiles reutilizables | opt-in, dedupe, corrección/supresión | finalidad/duplicados | no altera snapshots, permisos/derechos | importación masiva |
| Auditoría integral | threat model, privacidad, recuperación, rendimiento | brechas residuales | matriz completa, backup/restore, pruebas de abuso | despliegue hasta aprobación |

## 12. Resumen ejecutivo y recomendación

Existe una **Solicitud web** anónima `QuoteRequest`: captura contacto/mensaje y producto opcional, persiste primero, avisa internamente por correo sin bloquear, y permite a seller/support_admin listar, buscar y actualizar estado/notas. Reutilizables: autenticación/roles, `AppUser.Id`, `SellerCode`, catálogo, patrones de timestamps, autorización y SMTP como referencia; no el seudofolio derivado de `Id` ni `QuoteRequest` como documento comercial.

Debe mantenerse separada la futura **cotización comercial**: borrador autenticado, vendedor responsable, ítems/cálculos, folio global al emitir, snapshot versionado y PDF seguro. Un enlace opcional a la solicitud aporta conversión/precarga, con autorización y ciclos independientes.

Antes de programar deben resolverse campos y reglas fiscales/comerciales, estados/versiones/anulación, visibilidad entre vendedores, folio concurrente, política de retención/derechos, transparencia, almacenamiento PDF y correo. Riesgos prioritarios actuales: endpoint anónimo sin rate limit específico, PII ampliamente visible, ausencia de propietario/historial/retención/operaciones de privacidad y seudofolio engañoso.

El mínimo primer cotizador debe incluir: borrador autenticado, cliente escrito manualmente sin perfil reutilizable, ítems mínimos aprobados, un vendedor por FK, emisión atómica con folio global, snapshot inmutable, auditoría esencial y descarga PDF autorizada; correo integrado, imágenes, multimoneda, descuentos complejos y perfiles quedan fuera.

Franz debe responder las 20 decisiones de la sección 10 y obtener validación legal/contable donde corresponda. **Siguiente prompt recomendado:** cerrar y documentar campos, reglas de cálculo, ciclo de estados, permisos y retención con ejemplos de aceptación; todavía sin entidades, migración ni UI.

**Limitaciones:** auditoría estática del commit indicado; no se validó comportamiento desplegado, infraestructura Plesk, configuración/secrets, base de datos, proveedores, backups, logs ni contenido real. Las fuentes oficiales no pudieron abrirse automáticamente por controles 401/403 y requieren reconsulta humana/profesional. No se infiere cumplimiento legal.
