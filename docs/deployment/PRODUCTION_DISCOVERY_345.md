# Descubrimiento productivo de solo lectura — Prompt 345

## Propósito y autorización

`tools/deployment/Inspect-JemNexusProduction.ps1` prepara un reporte sanitizado para reconciliar, antes de desplegar, el backend, la identidad, las migraciones, el esquema crítico, los usuarios y el catálogo EP de producción. **Crear esta herramienta no autoriza ejecutarla**: su ejecución real desde Windows requiere una aprobación posterior, una ventana acordada y credenciales de mínimo privilegio.

No es una herramienta de despliegue, reparación ni migración. Su resultado más favorable es `READY_FOR_REVIEW`, nunca un `GO` definitivo: backups, artefactos, restauración ensayada y aprobación humana siguen pendientes.

## Garantías read-only

- HTTP pasa por una única función que solo admite `GET`/`HEAD` (la versión actual emite únicamente `GET`), desactiva redirects automáticos, cookies y cualquier persistencia de cuerpos completos. Los redirects no se siguen y un destino ajeno se rechaza.
- SQL pasa por `Invoke-ReadOnlyQuery`: el texto debe comenzar por `SELECT` o `WITH`, después de quitar comentarios y literales; además se rechazan `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `ALTER`, `CREATE`, `DROP`, `TRUNCATE`, `EXEC`, `GRANT`, `REVOKE`, `DENY` y `DBCC`. Hay timeout de 15 segundos y parámetros para nombres variables.
- No se ejecutan procedimientos, migraciones, SQL diferencial, transacciones de escritura, descargas multimedia, imports, correcciones ni fallbacks mutantes.
- La herramienta no busca producción ni tokens en configuraciones, navegador, portapapeles, historial, logs o checkpoints.

Estas garantías se revisaron estáticamente; deben validarse también en una estación Windows controlada antes de la ventana real.

## Requisitos

- PowerShell 7.2 o posterior en Windows, acceso HTTPS aprobado al backend y acceso read-only a SQL Server.
- URL HTTPS y host productivo esperado, indicados por separado.
- Nombre exacto esperado de servidor SQL y base.
- JWT temporal en un archivo `.txt` local regular y no enlazado, con una única línea.
- Proveedor `System.Data.SqlClient`, coherente con SQL Server usado por el repositorio.
- Permisos API para `/api/auth/me`, lecturas comerciales y listado administrativo de usuarios; permisos SQL exclusivamente de lectura y metadata.

## Variable de entorno

La única fuente de la cadena es:

```text
JEM_PRODUCTION_READONLY_CONNECTION_STRING
```

No existe parámetro de cadena. El constructor valida `DataSource`, `InitialCatalog`, `ApplicationIntent=ReadOnly` y exige `Encrypt=True`. `TrustServerCertificate` debe ser `False`: un valor `True` omite la validación normal de la cadena de confianza del certificado SQL, por lo que se rechaza como configuración insegura con código 3 antes de abrir la conexión. La herramienta no altera la cadena ni ofrece un flag para ignorar certificados. Luego `DB_NAME()` y `SERVERPROPERTY('ServerName')` deben confirmar nuevamente el destino. La cadena, usuario y contraseña nunca se imprimen.

## Parámetros

| Parámetro | Uso |
|---|---|
| `-BaseUrl` | URL raíz HTTPS, sin credenciales, query ni fragmento. |
| `-ExpectedHost` | Host DNS exacto; se rechazan localhost, loopback, IP privada/link-local y resolución a una dirección no pública. |
| `-ExpectedDatabase` / `-ExpectedSqlServer` | Identidades exactas esperadas, comprobadas antes y después de abrir SQL. |
| `-TokenFile` | Ruta explícita al JWT temporal `.txt`. |
| `-MinimumTokenLifetimeMinutes` | Margen mínimo de expiración; default 10. |
| `-ExpectedIssuer` / `-ExpectedAudience` | Validaciones JWT opcionales pero recomendadas cuando el operador conoce los valores aprobados. |
| `-OutputPath` | Archivo JSON opcional; debe estar fuera del repositorio y en un directorio existente. |
| `-Force` | Permite reemplazar atómicamente un output existente. |

## Seguridad de destino

Se rechazan HTTP, credenciales embebidas, fragmentos, query, una ruta base distinta de `/`, host diferente, `localhost`, `127.0.0.1`, `::1`, IP privadas/link-local y nombres SQL distintos. También se resuelve el DNS para impedir que el host esperado apunte a una dirección no pública. Los redirects automáticos están deshabilitados; incluso uno válido al mismo host queda como evidencia incompleta y `NO-GO`.

No hay dominio, token, password, connection string ni nombre productivo real incorporado al repositorio.

## Token temporal

El JWT debe tener tres segmentos Base64URL, payload JSON, `exp` vigente con margen y, cuando se pasan, `iss`/`aud` exactos. La herramienta nunca valida criptográficamente la firma por sí sola: la autenticación real del endpoint aporta esa comprobación y esta limitación se refleja en la evidencia.

El archivo se elimina en `finally` tanto en éxito como en error. La salida solo informa `TOKEN_VALID=True/False` y `TOKEN_FILE_REMOVED=True/False`; nunca incluye el JWT ni Authorization. Si la eliminación falla, la ejecución no puede quedar lista para revisión.

## Endpoints GET derivados del código

Se consultan exclusivamente rutas existentes:

1. `/health`, anónimo y sin Bearer, para estado, aplicación, ambiente y timestamp. Es la ruta canónica que conserva el frontend en el origen incluso cuando la base configurada termina en `/api`.
2. `/api/auth/me`, autenticado, para identidad resumida.
3. `/api/admin/users`, autenticado como `support_admin`, como contraste del acceso administrativo.
4. `/api/products?include_unpublished=true` y `/api/product-images`, autenticados, para confirmar contratos de catálogo/multimedia sin omitir productos no publicados.
5. `/api/technical-sheets`, autenticado, para confirmar el contrato de fichas.

No se descargan archivos. Un 401/403 termina con código 4; 404, redirect, JSON incompatible u otro fallo aportan un bloqueante y nunca activan un método alternativo. En particular, la herramienta no prueba una ruta health alternativa bajo el prefijo API.

Los cuatro listados actuales no son paginados: sus handlers materializan una única consulta completa con `ToListAsync` y responden un array JSON, sin parámetros `page`, `limit`, `offset`, `Skip` ni `Take`. La herramienta exige ese contrato, limita cada respuesta a 20 MiB y compara los conteos de usuarios administrables, todos los productos, imágenes y fichas contra conteos SQL independientes. Una envoltura paginada, truncamiento, diferencia de conteos o respuesta no-array produce `NO-GO`; no se intenta adivinar páginas o rutas.

## Consultas SQL realizadas

Todas son `SELECT` parametrizados cuando incorporan valores variables:

- identidad: `DB_NAME()` y `SERVERPROPERTY('ServerName')`;
- existencia de tablas/columnas mediante `sys.tables` y `sys.columns`;
- historial exacto ordenado de `__EFMigrationsHistory`;
- metadata de PK/FK, índices, nulabilidad y acción de borrado de `AppUserPermissions` y `CommercialQuotes.IssuedById`;
- conteos de cotizaciones con emisor nulo/huérfano, responsable huérfano y actor distinto del responsable;
- inventario sanitizado de `AppUsers`, conteo de permisos, códigos duplicados y permisos asignados;
- productos cuya marca es EP, modelo/SKU, conteos de `ProductImages`, asociación a `TechnicalSheets`, referencias vacías, modelos duplicados y presencia separada de LGMG/JLG.

Si `IssuedById` o `AppUserPermissions` no existen porque su migración está pendiente, se informa el pendiente y se omiten consultas que referencien esos objetos.

## Campos deliberadamente omitidos

No aparecen passwords/hashes, refresh tokens, JWT, cookies, cabeceras, connection string, usuario SQL, correo, teléfono, nombre personal, detalles de clientes/cotizaciones ni contenido de archivos. Las respuestas API completas no se guardan: solo se proyectan campos previstos y códigos de estado.

## Inventarios y evaluación

- **Migraciones:** las 22 migraciones conocidas se comparan en orden con producción, incluidas `20260917000000_AddGranularSellerPermissions` y `20260922000000_AddCommercialQuoteIssuedBy`; se informan faltantes y desconocidas.
- **Usuarios:** ID, username, rol, activo, existencia de código, cantidad de permisos y coincidencia con la sesión. Se buscan `support`, `soporte`, `supadmin`, `jmateluna` y `fheim`; se evalúan administradores activos, sellers sin código, duplicados, roles/permisos desconocidos y `users.manage` en sellers.
- **EP:** productos/modelos, cantidades de imágenes/fichas, referencias vacías, posibles duplicados y conteo separado de LGMG/JLG. No se asume equivalencia de IDs locales ni se reutilizan checkpoints.

## Reporte y decisión

El JSON contiene `target`, `token`, `health`, `identity`, `migrations`, `schema`, `users`, `ep_catalog`, `multimedia`, `observable_configuration`, `blockers`, `warnings` y `decision`.

- `NO-GO`: hay faltantes, diferencias o evidencia incompleta. No significa que la herramienta deba reparar nada.
- `READY_FOR_REVIEW`: toda la evidencia observable fue coherente; aún requiere backups, artefactos y aprobación humana.

`-OutputPath` escribe UTF-8 sin BOM, fuera del repositorio, mediante archivo temporal y movimiento/reemplazo atómico. No sobrescribe salvo `-Force`.

## Códigos de salida

| Código | Significado |
|---:|---|
| 0 | Inspección completa y `READY_FOR_REVIEW`. |
| 2 | Inspección completa con `NO-GO`. |
| 3 | Entrada insegura/inválida o fallo no clasificable antes de completar. |
| 4 | Fallo de autenticación/autorización HTTP. |
| 5 | Configuración, validación o conexión SQL fallida. |

## Ejemplo ficticio

```powershell
$env:JEM_PRODUCTION_READONLY_CONNECTION_STRING = 'Server=sql.example.invalid;Database=example_prod;User Id=readonly_example;Password=<FROM-VAULT>;Encrypt=True;TrustServerCertificate=False;ApplicationIntent=ReadOnly'
./tools/deployment/Inspect-JemNexusProduction.ps1 `
  -BaseUrl 'https://api.example.invalid/' `
  -ExpectedHost 'api.example.invalid' `
  -ExpectedDatabase 'example_prod' `
  -ExpectedSqlServer 'sql.example.invalid' `
  -TokenFile 'C:\secure-temp\jem-token.txt' `
  -ExpectedIssuer 'https://issuer.example.invalid' `
  -ExpectedAudience 'example-api' `
  -OutputPath 'C:\secure-reports\jem-discovery.json'
```

Salida abreviada esperada:

```json
{
  "target": { "validated": true, "scheme": "https" },
  "token": { "TOKEN_VALID": true, "TOKEN_FILE_REMOVED": true },
  "migrations": { "missing": [], "unknown": [] },
  "blockers": [],
  "decision": "READY_FOR_REVIEW"
}
```

## Limitaciones y pasos prohibidos

- La revisión de este cambio es exclusivamente estática: no se ejecutó PowerShell, red, API, SQL Server, localhost, .NET, Node, builds, servidores ni migraciones. No hay infraestructura PowerShell offline existente y no se agregó una dependencia o suite nueva.
- La disponibilidad de `System.Data.SqlClient`, la forma exacta de `SERVERPROPERTY('ServerName')`, resolución DNS, cadena de confianza TLS instalada, permisos metadata, límite de 20 MiB y escritura atómica sobre el filesystem destino deben comprobarse primero en una estación Windows aislada y aprobada.
- La herramienta cuenta asociaciones/referencias, no verifica que los binarios existan en disco ni sus hashes, y no descarga multimedia.
- Continúan prohibidos: aplicar/generar migraciones, `dotnet ef database update`, SQL de escritura, procedimientos, modificar usuarios/productos, importar EP, descargar archivos, reutilizar checkpoints locales, descubrir secretos y ejecutar contra cualquier destino sin aprobación posterior.
