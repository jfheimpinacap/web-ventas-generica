# Post-deploy API .NET en Plesk

Documento de seguimiento posterior a la publicación controlada de la API ASP.NET Core de JEM Nexus en Plesk Windows/IIS.

- Fecha del hito: `2026-06-06`.
- Dominio API: `https://api.jem-nexus.cl`.
- Base SQL Server productiva: `jemnexusb_prod`.
- Schema real: `jmnexusb_api`.

## A. Estado confirmado

- `/health` OK en `https://api.jem-nexus.cl/health`.
- `/api/health` OK en `https://api.jem-nexus.cl/api/health`.
- `AppUsers` contiene usuarios productivos iniciales:
  - `vendedor` con `Role=seller`, `IsActive=1`, `IsStaff=1`, `IsSuperuser=0`.
  - `soporte` con `Role=support_admin`, `IsActive=1`, `IsStaff=1`, `IsSuperuser=0`.
- Login de `vendedor` OK con `POST https://api.jem-nexus.cl/api/auth/login`.
- `/api/auth/me` OK con Bearer token emitido por login.
- `LastLoginAt` actualizado para `vendedor` después de la prueba de login.

## B. Verificaciones SQL seguras

Consulta permitida para verificación operacional sin exponer `PasswordHash` ni secretos:

```sql
SELECT
    Id,
    Username,
    Role,
    IsActive,
    IsStaff,
    IsSuperuser,
    LastLoginAt,
    CreatedAt,
    UpdatedAt
FROM [jemnexusb_api].[AppUsers]
ORDER BY Id;
```

No consultar, copiar, capturar ni compartir `PasswordHash`. No insertar usuarios manualmente por SQL porque el hash debe generarse con la lógica del backend.

## C. Smoke tests PowerShell

Comandos seguros sin password hardcodeada:

```powershell
$username = "vendedor"
$securePassword = Read-Host "Password vendedor" -AsSecureString

$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
$password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)

try {
  $body = @{
    username = $username
    password = $password
  } | ConvertTo-Json

  $login = Invoke-RestMethod `
    -Uri "https://api.jem-nexus.cl/api/auth/login" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

  "LOGIN OK"
  $login.PSObject.Properties.Name

  $token = $login.access

  Invoke-RestMethod `
    -Uri "https://api.jem-nexus.cl/api/auth/me" `
    -Method Get `
    -Headers @{ Authorization = "Bearer $token" }
}
finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  $password = $null
}
```

## D. Checklist de seguridad inmediata

- [ ] Confirmar `stdoutLogEnabled=false` en `web.config`.
- [ ] Borrar archivos stdout temporales si existen.
- [ ] Confirmar que no quedó un ZIP de publicación dentro de una carpeta pública.
- [ ] Confirmar que no hay secrets en `appsettings*.json` ni `web.config` versionados.
- [ ] No subir capturas con variables, connection strings, JWT secrets o passwords visibles.
- [ ] Rotar contraseñas expuestas durante pruebas manuales.
- [ ] Rotar JWT secret si fue visible en pantallas, chat, tickets o capturas.
- [ ] Mantener el backup previo de Plesk hasta validar estabilidad de la API.

## E. Pendientes

- Rotación controlada de credenciales provisorias.
- Definir flujo de reset password.
- Integración frontend con API .NET.
- Decidir convivencia Django/.NET y estrategia de corte.
- Validación CORS desde el frontend público.
- Pruebas CRUD de catálogo en API .NET.
- Definir monitoreo y logs productivos.


## F. Smoke tests endpoints comerciales read-only

Después de publicar el ZIP read-only, ejecutar los smoke tests PowerShell documentados en `docs/PUBLICACION_API_DOTNET_READONLY_PLESK.md`.

Validaciones mínimas:

- `/health` y `/api/health` siguen respondiendo OK.
- Login vendedor sigue respondiendo OK sin imprimir password ni token.
- `/api/auth/me` responde OK con Bearer.
- Los listados read-only responden OK con Bearer:
  - `/api/products/`
  - `/api/categories/`
  - `/api/brands/`
  - `/api/suppliers/`
  - `/api/promotions/`
  - `/api/quote-requests/`
  - `/api/home-section-items/`
- Al menos un endpoint comercial sin Bearer devuelve `401 Unauthorized`.

No ejecutar SQL ni `dotnet ef database update` durante estas verificaciones. Si falla la publicación, el rollback esperado es restaurar el backup de archivos de Plesk.
