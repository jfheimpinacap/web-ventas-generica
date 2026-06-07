# Publicación API .NET read-only en Plesk

Guía operativa para publicar manualmente en Plesk la API ASP.NET Core con endpoints comerciales **solo lectura** agregados en el Prompt 021.

> Alcance: publicar archivos de la API .NET mediante ZIP. No conecta a Plesk desde el repo, no sube archivos automáticamente, no ejecuta SQL, no ejecuta `dotnet ef database update`, no modifica variables productivas y no toca secretos reales.

## 1. Alcance funcional

La publicación incorpora endpoints comerciales read-only para:

- `products`
- `categories`
- `brands`
- `suppliers`
- `promotions`
- `quote-requests`
- `home-section-items`
- `product-images`
- `product-specs`

Todos los endpoints comerciales requieren `Authorization: Bearer <access>` mediante la política `RequireCommercialRead`. La política autoriza identidades con rol `seller`, rol `support_admin`, claim `is_staff=true` o claim `is_superuser=true`.

No se agrega escritura: no hay `POST`, `PUT`, `PATCH` ni `DELETE` comerciales en esta publicación. No se agrega carga real de imágenes.

## 2. Confirmación de schema

Revisión del Prompt 021:

- Archivos agregados/modificados: endpoints, DTOs, tests, registro de política/rutas y documentación.
- No se modificaron modelos persistidos en `backend-dotnet/JemNexus.Api/Models/`.
- No se modificó `JemNexusDbContext`.
- No se agregaron migraciones EF Core.
- No se agregaron tablas ni columnas nuevas.

Conclusión: esta publicación **no requiere migraciones SQL ni cambios de schema productivo**. No crear scripts SQL para esta fase, no ejecutar SQL real y no ejecutar `dotnet ef database update` contra producción.

## 3. Generar publish ZIP local desde Windows

Desde Windows PowerShell, en la raíz del repositorio:

```powershell
cd C:\Users\Franz\desktop\web-ventas-generica

.\backend-dotnet\scripts\publish-plesk.ps1
.\backend-dotnet\scripts\package-plesk.ps1
```

El script `backend-dotnet/scripts/publish-plesk.ps1` debe dejar la salida en `backend-dotnet/publish/JemNexus.Api`. Luego `backend-dotnet/scripts/package-plesk.ps1` debe crear el ZIP seguro `backend-dotnet/publish/JemNexus.Api-plesk.zip`. La carpeta `backend-dotnet/publish/` es un artefacto local ignorado por git.

El script local:

- publica `JemNexus.Api` en `Release`;
- limpia la salida anterior de `backend-dotnet/publish/JemNexus.Api`;
- ejecuta restore/build/test antes de publicar;
- no incluye secretos;
- no incluye `frontend/.env.local`;
- no modifica `appsettings` productivos con secretos;
- no ejecuta migraciones;
- no ejecuta SQL;
- no conecta a Plesk;
- no sube archivos.

El empaquetado seguro:

- excluye `web.config` por defecto para no sobrescribir variables productivas mantenidas en Plesk;
- excluye `logs/`;
- excluye archivos stdout (`stdout*.log` y `stdout*.txt`);
- excluye `.env`, `.env.*`, `*.env.local` y archivos locales sensibles `*.local`;
- no conecta a Plesk, no ejecuta SQL, no ejecuta migraciones y no toca secretos.

No usar más `Compress-Archive -Path backend-dotnet\publish\JemNexus.Api\*` para este flujo: ese wildcard incluye `web.config` y puede sobrescribir el `web.config` productivo.

`package-plesk.ps1` acepta `-IncludeWebConfig` solo para un caso excepcional y peligroso en el que se haya decidido reemplazar explícitamente el `web.config` productivo. No usar ese parámetro en publicaciones normales.

## 4. `web.config` productivo conservado en Plesk

El ZIP seguro normal **no debe incluir `web.config`**. El `web.config` real productivo se mantiene en Plesk porque contiene variables de entorno productivas y secretos que no se commitean ni se copian a documentación. Existe una plantilla sin secretos en `backend-dotnet/JemNexus.Api/web.config.template` solo como referencia de estructura.

Antes de subir el ZIP, confirmar que la carpeta de publish local contiene `web.config` generado por el SDK Web, pero que el ZIP creado con `package-plesk.ps1` lo excluye. En Plesk, confirmar que el `web.config` productivo existente conserva:

```xml
processPath="dotnet"
arguments=".\JemNexus.Api.dll"
stdoutLogEnabled="false"
```

También confirmar que el `web.config` productivo mantiene el bloque `<environmentVariables>` con variables productivas configuradas en Plesk, sin copiar sus valores a git ni a documentación. No cambiar `stdoutLogEnabled` a `true` para operación normal de producción. Si en una incidencia futura aparece error 500.30, puede habilitarse stdout temporalmente solo para diagnóstico manual y debe volver a `false` después.

## 5. Checklist previo

- [ ] `main` actualizado localmente.
- [ ] `git status --short` limpio antes de generar/publicar artefactos.
- [ ] `dotnet build backend-dotnet/JemNexus.sln` OK.
- [ ] `dotnet test backend-dotnet/JemNexus.sln` OK.
- [ ] `python backend/manage.py check` OK.
- [ ] `python backend/manage.py test core catalog -v 2` OK.
- [ ] `cd frontend && npm run build` OK.
- [ ] ZIP local `backend-dotnet/publish/JemNexus.Api-plesk.zip` generado con `backend-dotnet/scripts/package-plesk.ps1`.
- [ ] Confirmado que el ZIP seguro no contiene `web.config`.
- [ ] Confirmado que no se usó `Compress-Archive` manual con wildcard sobre toda la carpeta de publish.
- [ ] Confirmado que esta publicación no tiene migraciones pendientes.
- [ ] Confirmado que no se requiere SQL.
- [ ] Confirmado que el ZIP no contiene secretos reales ni `frontend/.env.local`.

## 6. Backup manual en Plesk

1. Entrar a Plesk.
2. Abrir **Administrador de archivos**.
3. Ir a la carpeta actual de `api.jem-nexus.cl`.
4. Crear un ZIP de backup previo en el directorio padre, por ejemplo:

   ```text
   backup_api_jem_nexus_cl_YYYYMMDD_antes_readonly_endpoints.zip
   ```

5. Verificar que el backup exista y tenga tamaño consistente antes de borrar o reemplazar archivos.
6. No tocar la base de datos durante este backup de archivos.

## 7. Reemplazo manual de archivos

1. Entrar a la carpeta raíz de `api.jem-nexus.cl`.
2. Subir `JemNexus.Api-plesk.zip`.
3. Extraer el ZIP en la carpeta raíz de la API.
4. Confirmar que el ZIP seguro reemplazó DLLs y dependencias, pero **no reemplazó `web.config`**.
5. Confirmar que existan al menos:
   - `JemNexus.Api.dll`
   - `JemNexus.Api.runtimeconfig.json`
   - `JemNexus.Api.deps.json`
   - `web.config` productivo ya existente en Plesk
   - DLLs de dependencias
   - `runtimes/`
6. Verificar que el `web.config` productivo siga existiendo después de extraer.
7. Verificar que contiene `<environmentVariables>`.
8. Verificar `stdoutLogEnabled="false"`.
9. Verificar `arguments=".\JemNexus.Api.dll"`.
10. Eliminar el ZIP subido después de extraerlo.
11. No tocar variables de entorno.
12. No tocar connection strings.
13. No tocar la base de datos.
14. No ejecutar SQL.
15. No ejecutar `dotnet ef database update`.

## 8. Reinicio

- Reiniciar la aplicación desde Plesk si existe botón o acción segura de reinicio.
- Si Plesk no reinicia automáticamente, tocar `web.config` solo si esa práctica ya es segura en el hosting, o usar el botón de reinicio si existe.
- Mantener `stdoutLogEnabled="false"` salvo diagnóstico temporal.

## 9. Rollback

Si falla la publicación:

1. Si aparece error 500.30 y el stdout indica variables faltantes, revisar primero si `web.config` fue sobrescrito o perdió `<environmentVariables>`.
2. Si `web.config` fue sobrescrito, restaurar **solo `web.config`** desde el backup de Plesk y conservar los DLL nuevos si el resto de la publicación es correcta.
3. Si el fallo no es de variables o no se puede aislar, restaurar el backup ZIP anterior de archivos.
4. No ejecutar SQL.
5. No ejecutar `dotnet ef database update`.
6. No cambiar variables productivas al azar.
7. Revisar `/health`, `/api/health` y logs disponibles.
8. Si se habilita stdout temporalmente para diagnóstico, volver a `false` después.
9. Repetir smoke tests con la versión restaurada.

Rollback de esta publicación es restaurar archivos. No hay rollback de base de datos porque esta fase no cambia schema ni datos productivos.

## Incidente corregido: no sobrescribir web.config productivo

En la publicación manual read-only se detectó un incidente operacional: el ZIP anterior incluía el `web.config` generado por `dotnet publish`. Al extraerlo en Plesk, ese archivo sobrescribió el `web.config` productivo que contenía el bloque `<environmentVariables>`, dejando a la API sin variables de entorno productivas.

Síntoma observado:

- HTTP Error 500.30 - ASP.NET Core app failed to start.
- stdout mostró: `Jwt:Secret or JWT_SECRET must be configured in Production.`

Solución manual aplicada:

- restaurar solo `web.config` desde el backup de Plesk;
- conservar los DLL nuevos ya publicados;
- no ejecutar SQL;
- no ejecutar `dotnet ef database update`;
- no cambiar secretos ni variables al azar.

Procedimiento corregido desde este hotfix:

- generar publish con `backend-dotnet/scripts/publish-plesk.ps1`;
- generar ZIP con `backend-dotnet/scripts/package-plesk.ps1`;
- subir y extraer el ZIP seguro;
- no reemplazar `web.config` en publicaciones normales.

## 10. Smoke tests PowerShell post-publicación

Ejecutar después de reemplazar archivos y reiniciar. No hardcodear password real, no imprimir tokens, no guardar passwords en archivos.

```powershell
$baseUrl = "https://api.jem-nexus.cl"

Invoke-RestMethod "$baseUrl/health"
Invoke-RestMethod "$baseUrl/api/health"

$body = @{
  username = "vendedor"
  password = Read-Host "Password vendedor"
} | ConvertTo-Json

$login = Invoke-RestMethod `
  -Uri "$baseUrl/api/auth/login" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body

$token = $login.access

Invoke-RestMethod `
  -Uri "$baseUrl/api/auth/me" `
  -Method Get `
  -Headers @{ Authorization = "Bearer $token" }

Invoke-RestMethod `
  -Uri "$baseUrl/api/products/" `
  -Method Get `
  -Headers @{ Authorization = "Bearer $token" }

Invoke-RestMethod `
  -Uri "$baseUrl/api/categories/" `
  -Method Get `
  -Headers @{ Authorization = "Bearer $token" }

Invoke-RestMethod `
  -Uri "$baseUrl/api/brands/" `
  -Method Get `
  -Headers @{ Authorization = "Bearer $token" }

Invoke-RestMethod `
  -Uri "$baseUrl/api/suppliers/" `
  -Method Get `
  -Headers @{ Authorization = "Bearer $token" }

Invoke-RestMethod `
  -Uri "$baseUrl/api/promotions/" `
  -Method Get `
  -Headers @{ Authorization = "Bearer $token" }

Invoke-RestMethod `
  -Uri "$baseUrl/api/quote-requests/" `
  -Method Get `
  -Headers @{ Authorization = "Bearer $token" }

Invoke-RestMethod `
  -Uri "$baseUrl/api/home-section-items/" `
  -Method Get `
  -Headers @{ Authorization = "Bearer $token" }
```

Prueba negativa esperada: sin Bearer, un endpoint comercial debe devolver `401 Unauthorized`.

```powershell
try {
  Invoke-RestMethod `
    -Uri "$baseUrl/api/products/" `
    -Method Get `
    -ErrorAction Stop

  throw "ERROR: /api/products/ respondió sin Bearer; se esperaba 401."
}
catch {
  $statusCode = $_.Exception.Response.StatusCode.value__
  if ($statusCode -ne 401) {
    throw "ERROR: status inesperado sin Bearer: $statusCode"
  }

  "OK: /api/products/ sin Bearer devolvió 401."
}
```

## 11. Validación frontend post-publicación

En ambiente local de validación, configurar `frontend/.env.local` sin commitearlo:

```dotenv
VITE_API_BASE_URL=https://api.jem-nexus.cl
VITE_API_PROVIDER=dotnet
```

Luego ejecutar:

```powershell
cd frontend
npm run dev
```

Abrir:

```text
http://localhost:5174/login
```

Validar:

- login vendedor;
- entrada a `/admin/productos`;
- listados de productos;
- categorías;
- marcas;
- proveedores;
- promociones;
- cotizaciones;
- ofertas Hero section si aplica.

Resultado esperado:

- ya no debería aparecer “endpoint pendiente” para los endpoints read-only;
- si no hay datos, se debe mostrar lista vacía o mensaje normal;
- no probar escritura todavía;
- no probar carga real de imágenes todavía.

## Validación producción read-only completada

Estado documentado después de restaurar el `web.config` productivo desde backup, sin copiar secretos ni tokens:

- `/health` OK.
- `/api/health` OK.
- Login vendedor OK.
- `/api/auth/me` OK.
- Endpoints comerciales read-only OK: `/api/products/`, `/api/categories/`, `/api/brands/`, `/api/suppliers/`, `/api/promotions/`, `/api/quote-requests/`, `/api/home-section-items/`, `/api/product-images/` y `/api/product-specs/`.
- Prueba sin Bearer devuelve `401 Unauthorized` OK.
- Panel vendedor OK con `VITE_API_PROVIDER=dotnet`.
- Los datos devueltos actualmente pueden ser listas vacías o sin registros; ese estado es esperado mientras no haya carga productiva en esas tablas.
- Escritura comercial y uploads reales siguen pendientes y no forman parte de esta publicación.

## 12. Prohibiciones de esta publicación

- No conectar a Plesk desde este repo.
- No subir archivos automáticamente.
- No ejecutar SQL real.
- No ejecutar `dotnet ef database update`.
- No aplicar migraciones reales.
- No crear usuarios reales.
- No poner ni tocar secretos reales.
- No modificar variables productivas.
- No commitear `frontend/.env.local`.
- No borrar Django.
- No tocar Render.
- No implementar escritura.
- No implementar carga real de imágenes.
- No rotar contraseñas en esta fase.
