# Rotación controlada de credenciales de producción

Esta guía prepara una rotación manual y controlada de credenciales expuestas durante diagnósticos operativos. No contiene secretos reales, no debe usarse para pegar valores sensibles en tickets/chats y no reemplaza el `web.config` productivo completo.

## A. Alcance

Credenciales y variables a rotar o limpiar:

- `Jwt__Secret` / `JWT_SECRET`: secreto de firma JWT.
- Contraseña del usuario vendedor configurado por `SeedUsers__SellerUsername` / `SeedUsers:SellerUsername`.
- Contraseña del usuario soporte configurado por `SeedUsers__SupportUsername` / `SeedUsers:SupportUsername`.
- Contraseña del usuario SQL/API usada por `ConnectionStrings__DefaultConnection`.
- Seed passwords temporales: remover `SeedUsers__SellerPassword` y `SeedUsers__SupportPassword` después de usarlos, o dejarlos ausentes/vacíos si ya no se requieren.
- Bandera temporal `SeedUsers__UpdateExistingPasswords`: dejarla en `false` o removerla después del reset.
- Revisar que el `web.config` productivo conserve sus `environmentVariables` necesarias y que no se sobrescriba durante publicaciones normales.

No rotar desde Codex, no ejecutar SQL real desde esta guía, no correr `dotnet ef database update` y no copiar valores reales a documentación.

## B. Orden recomendado

1. Generar backup de archivos Plesk, incluyendo el `web.config` productivo actual, fuera del repositorio.
2. Confirmar estado actual OK con `/health` y `/api/health`.
3. Generar nuevos valores fuera del repo y en una consola/local seguro.
4. Rotar `Jwt__Secret` / `JWT_SECRET` en el `web.config` productivo administrado manualmente en Plesk.
5. Rotar passwords vendedor/soporte configurando temporalmente:
   - `SeedUsers__UpdateExistingPasswords=true`
   - `SeedUsers__SellerUsername=<USUARIO_VENDEDOR>`
   - `SeedUsers__SellerPassword=<NUEVA_PASSWORD_VENDEDOR>`
   - `SeedUsers__SupportUsername=<USUARIO_SOPORTE>`
   - `SeedUsers__SupportPassword=<NUEVA_PASSWORD_SOPORTE>`
6. Reiniciar la app desde Plesk.
7. Validar login con passwords nuevos.
8. Cambiar `SeedUsers__UpdateExistingPasswords=false` o remover la variable.
9. Remover `SeedUsers__SellerPassword` y `SeedUsers__SupportPassword` del `web.config` si ya no son necesarias.
10. Rotar password SQL en el panel/base de datos usando el procedimiento operacional aprobado.
11. Actualizar `ConnectionStrings__DefaultConnection` en el `web.config` productivo con el nuevo password SQL, sin pegarlo en chats o docs.
12. Reiniciar la app desde Plesk.
13. Validar `/health`, `/api/health`, login y endpoints read-only.
14. Eliminar stdout logs temporales si existieran y revisar que no contengan secretos.
15. Mantener `stdoutLogEnabled="false"`.

## C. Generación segura de secretos en PowerShell

Ejecutar estos comandos en una terminal segura y fuera del repositorio. No pegar la salida en documentación, chats ni commits.

```powershell
# Secreto JWT fuerte en Base64.
[Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(48))

# Password temporal larga para usuario vendedor/soporte o SQL.
[Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

Si se usa un gestor de contraseñas corporativo, guardar los valores allí y no en archivos del proyecto.

## D. Smoke tests post-rotación

Ejecutar desde una consola segura. Los passwords se piden con `Read-Host`; no hardcodearlos.

```powershell
$BaseUrl = "https://api.example.com"
$SellerUsername = Read-Host "Usuario vendedor"
$SellerPassword = Read-Host "Password vendedor nuevo" -AsSecureString
$SellerPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
  [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SellerPassword)
)

Invoke-RestMethod -Method Get -Uri "$BaseUrl/health"
Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/health"

$LoginBody = @{
  username = $SellerUsername
  password = $SellerPasswordPlain
} | ConvertTo-Json

$Login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/auth/login" -ContentType "application/json" -Body $LoginBody
$AccessToken = $Login.access

Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/auth/me" -Headers @{ Authorization = "Bearer $AccessToken" }
Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/products/" -Headers @{ Authorization = "Bearer $AccessToken" }

try {
  Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/products/" -ErrorAction Stop
  throw "ERROR: /api/products/ sin Bearer no devolvió 401."
} catch {
  if ($_.Exception.Response.StatusCode.value__ -ne 401) { throw }
  "OK: /api/products/ sin Bearer devuelve 401."
}
```

Prueba controlada opcional para password antigua: intentar login con la password anterior solo si todavía está disponible de forma segura en el gestor de contraseñas. El resultado esperado es `401 Unauthorized`. No escribir la password antigua en scripts, tickets ni capturas.

## E. Rollback

- Si falla JWT/login después de editar `web.config`, restaurar el backup completo del `web.config` productivo y reiniciar la app.
- Si falla conexión SQL, revisar `ConnectionStrings__DefaultConnection` o restaurar el password SQL anterior solo si está disponible de forma segura.
- No ejecutar `dotnet ef database update`.
- No ejecutar SQL al azar.
- No pegar secretos en chats, capturas, issues o documentación.
- No publicar un ZIP que contenga `web.config` productivo real.

## F. Limpieza

- Revisar logs de la app y eliminar stdout logs temporales si existieran.
- Confirmar `stdoutLogEnabled="false"` en `web.config`.
- Eliminar archivos ZIP locales que pudieran contener secretos.
- No subir capturas con `web.config` completo ni con environment variables visibles.
- Actualizar documentación de estado solo con placeholders y resultados generales, nunca con valores reales.
- Confirmar que `SeedUsers__UpdateExistingPasswords` quedó en `false` o ausente y que `SeedUsers__SellerPassword` / `SeedUsers__SupportPassword` fueron removidos si ya cumplieron su función.
