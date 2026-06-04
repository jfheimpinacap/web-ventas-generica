# Plan controlado de aplicación de schema en Plesk / SQL Server

## 0. Alcance y regla principal

Este documento prepara la aplicación manual y controlada del schema ASP.NET Core / EF Core en Plesk, pero **no aplica SQL**, **no conecta a `jemnexusb_prod`**, **no ejecuta `dotnet ef database update`** y **no crea usuarios reales**.

Antes de ejecutar cualquier script en Plesk/SQL Server se debe diagnosticar el estado real de la base. No asumir que la base está vacía.

## A. Datos conocidos del entorno

- Hosting: Plesk Windows/IIS.
- Dominio API: `https://api.jem-nexus.cl`.
- Motor: SQL Server 2022.
- Base de datos: `jemnexusb_prod`.
- Usuario de base de datos: `jemnexusb_api`.
- Host visible en Plesk: `.\MSSQLSERVER2022`.
- La base fue creada previamente, pero desde este flujo todavía no se ha aplicado schema real.

> No incluir contraseñas, cadenas de conexión completas, claves JWT ni credenciales reales en este documento ni en el repositorio.

## B. Checklist antes de aplicar

Marcar cada punto antes de pegar o ejecutar SQL:

- [ ] Confirmar backup reciente y restaurable de `jemnexusb_prod`.
- [ ] Confirmar ventana de trabajo y responsable de ejecución.
- [ ] Confirmar que se está conectado a la base correcta (`jemnexusb_prod`), no a otra base del servidor.
- [ ] Confirmar si la base tiene tablas existentes.
- [ ] Confirmar si existe la tabla `__EFMigrationsHistory`.
- [ ] Confirmar si `__EFMigrationsHistory` tiene registros.
- [ ] Confirmar si existen tablas comerciales: `Brands`, `Categories`, `Suppliers`, `Products`, `ProductImages`, `ProductSpecs`, `Promotions`, `HomeSectionItems`, `QuoteRequests`.
- [ ] Confirmar si existen tablas auth: `AppUsers`, `AppRefreshTokens`.
- [ ] Confirmar acceso al panel SQL de Plesk o herramienta SQL Server disponible.
- [ ] Confirmar que la herramienta permite pegar y ejecutar un script SQL completo con separadores `GO`.
- [ ] Confirmar que no se ejecutará `dotnet ef database update` contra producción.
- [ ] Confirmar que no se crearán usuarios reales ni contraseñas reales por SQL sin procedimiento definido.

## C. Queries de diagnóstico de solo lectura

Ejecutar manualmente en Plesk/SQL Server antes de decidir el script. Estas consultas no modifican datos.

### Confirmar base actual

```sql
SELECT DB_NAME() AS CurrentDatabase;
```

### Listar tablas existentes

```sql
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;
```

### Revisar historial EF Core, si existe

```sql
IF OBJECT_ID(N'__EFMigrationsHistory', N'U') IS NOT NULL
    SELECT * FROM [__EFMigrationsHistory]
    ORDER BY [MigrationId];
```

### Verificar tablas comerciales esperadas

```sql
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
  AND TABLE_NAME IN (
      'Brands',
      'Categories',
      'Suppliers',
      'Products',
      'ProductImages',
      'ProductSpecs',
      'Promotions',
      'HomeSectionItems',
      'QuoteRequests'
  )
ORDER BY TABLE_NAME;
```

### Verificar tablas auth esperadas

```sql
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
  AND TABLE_NAME IN ('AppUsers', 'AppRefreshTokens')
ORDER BY TABLE_NAME;
```

### Verificar FKs hacia `AppUsers`, si ya existe

```sql
SELECT
    fk.name AS ForeignKeyName,
    OBJECT_NAME(fk.parent_object_id) AS SourceTable,
    OBJECT_NAME(fk.referenced_object_id) AS ReferencedTable
FROM sys.foreign_keys AS fk
WHERE OBJECT_NAME(fk.referenced_object_id) = 'AppUsers'
ORDER BY SourceTable, ForeignKeyName;
```

## D. Decisión de script

### Estado de scripts existentes

- `backend-dotnet/sql/InitialCommercialSchema.sql` es un script inicial que crea `__EFMigrationsHistory`, tablas comerciales e inserta la migración `20260603182917_InitialCommercialSchema`.
- `backend-dotnet/sql/AddAuthUsersAndAuditRelations.sql` es **acumulado desde cero**, no solo diferencial. Se identifica como acumulado porque crea `__EFMigrationsHistory`, crea tablas comerciales como `Brands` desde el inicio, inserta `20260603182917_InitialCommercialSchema`, luego crea `AppUsers`/`AppRefreshTokens`, agrega FKs de auditoría e inserta `20260604020543_AddAuthUsersAndAuditRelations`.
- La migración inicial real en código es `20260603182917_InitialCommercialSchema`.
- La migración auth real en código es `20260604020543_AddAuthUsersAndAuditRelations`.

### Caso 1: base completamente vacía

Condición:

- No hay tablas de usuario.
- No existe `__EFMigrationsHistory`.
- No existen tablas comerciales ni auth.

Decisión:

- Aplicar un script acumulado que cree todo desde cero.
- El candidato es `backend-dotnet/sql/AddAuthUsersAndAuditRelations.sql`, porque está generado como script acumulado completo hasta la migración auth.
- Revisar el script completo antes de aplicarlo y mantener backup disponible.

Resultado esperado:

- `__EFMigrationsHistory` contiene:
  - `20260603182917_InitialCommercialSchema`
  - `20260604020543_AddAuthUsersAndAuditRelations`
- Existen tablas comerciales y auth.
- Existen FKs de auditoría opcionales desde `CreatedById`/`UpdatedById` hacia `AppUsers`.

### Caso 2: base con `InitialCommercialSchema` ya aplicado

Condición:

- Existen tablas comerciales.
- Existe `__EFMigrationsHistory`.
- `__EFMigrationsHistory` contiene `20260603182917_InitialCommercialSchema`.
- No contiene `20260604020543_AddAuthUsersAndAuditRelations`.
- No existen `AppUsers` ni `AppRefreshTokens`.

Decisión:

- **No aplicar** `backend-dotnet/sql/AddAuthUsersAndAuditRelations.sql`, porque es acumulado y volvería a intentar crear tablas comerciales existentes.
- Usar un script diferencial desde `InitialCommercialSchema` hasta `AddAuthUsersAndAuditRelations`.
- Si no existe todavía el archivo diferencial revisable, generarlo localmente con .NET SDK y `dotnet-ef`:

```bash
dotnet ef migrations script InitialCommercialSchema AddAuthUsersAndAuditRelations \
  --project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj \
  --startup-project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj \
  -o backend-dotnet/sql/FromInitialCommercialSchemaToAddAuthUsersAndAuditRelations.sql
```

Resultado esperado del diferencial:

- Crea `AppUsers`.
- Crea `AppRefreshTokens`.
- Agrega índices auth.
- Agrega FKs de auditoría hacia `AppUsers`.
- Inserta solo `20260604020543_AddAuthUsersAndAuditRelations` en `__EFMigrationsHistory`.

### Caso 3: base con tablas parciales pero sin historial EF

Condición:

- Existen algunas tablas comerciales o auth.
- No existe `__EFMigrationsHistory`, o existe vacía/inconsistente.

Decisión:

- Detenerse.
- No aplicar script acumulado ni diferencial.
- Revisar manualmente estructura, datos, constraints e índices para evitar duplicados o inconsistencias.
- Definir plan de reconciliación o restaurar/limpiar base solo si el responsable confirma que no hay datos útiles.

### Caso 4: base con `AppUsers` o `AppRefreshTokens` ya existentes

Condición:

- Existe `AppUsers` o `AppRefreshTokens`, con o sin historial EF.

Decisión:

- Detenerse.
- No aplicar nada sin revisar estructura exacta, datos existentes, FKs e historial EF.
- Confirmar si esas tablas provienen de esta migración, de un intento anterior o de creación manual.

## E. Checklist después de aplicar

- [ ] Verificar que `SELECT DB_NAME()` sigue mostrando `jemnexusb_prod`.
- [ ] Verificar listado de tablas creado/actualizado.
- [ ] Verificar que `__EFMigrationsHistory` tiene las migraciones esperadas para el caso aplicado.
- [ ] Verificar que existen `AppUsers` y `AppRefreshTokens` si se aplicó la migración auth.
- [ ] Verificar que existen tablas comerciales esperadas.
- [ ] Verificar FKs de auditoría hacia `AppUsers`.
- [ ] Verificar que no se crearon usuarios reales manualmente por SQL.
- [ ] Preparar variables JWT y `SeedUsers` en Plesk antes de publicar/iniciar la API real.
- [ ] Confirmar que la cadena de conexión productiva queda solo en Plesk/IIS, no en git.

## F. Rollback / contingencia

- Si la base estaba completamente vacía antes de aplicar, el rollback más simple puede ser eliminar las tablas recién creadas o restaurar el backup. Preferir restaurar backup si está disponible y validado.
- Si la base tenía datos antes de aplicar, el rollback debe ser restaurar backup. No hacer cambios manuales destructivos tabla por tabla.
- Nunca hacer modificaciones manuales sin respaldo confirmado.
- Si falla un script a mitad de ejecución, detenerse, guardar error exacto, revisar si la transacción hizo rollback y comparar tablas/historial EF antes de intentar nuevamente.

## G. Variables necesarias para Plesk

Configurar en Plesk/IIS sin escribir secretos reales en archivos del repo:

- `ConnectionStrings__DefaultConnection`: cadena SQL Server completa para `jemnexusb_prod` con usuario `jemnexusb_api` y contraseña configurada fuera de git.
- `Jwt__Secret` o `JWT_SECRET`: secreto fuerte para firma JWT.
- `Jwt__Issuer` o `JWT_ISSUER`: issuer esperado por la API.
- `Jwt__Audience` o `JWT_AUDIENCE`: audience esperado por la API/frontend.
- `SeedUsers__SellerUsername`: usuario demo/vendedor si se decide sembrar.
- `SeedUsers__SellerPassword`: contraseña configurada fuera de git.
- `SeedUsers__SupportUsername`: usuario soporte si se decide sembrar.
- `SeedUsers__SupportPassword`: contraseña configurada fuera de git.
- `FRONTEND_ORIGINS`: orígenes frontend permitidos si aplica, por ejemplo dominio principal y `www`.

Opcionales según configuración:

- `ASPNETCORE_ENVIRONMENT`.
- `PUBLIC_SITE_URL`.
- `Jwt__AccessTokenMinutes`.
- `Jwt__RefreshTokenDays`.
- `SeedUsers__SellerEmail`.
- `SeedUsers__SellerFullName`.
- `SeedUsers__SupportEmail`.
- `SeedUsers__SupportFullName`.

## H. Comandos locales útiles

No ejecutar estos comandos contra producción salvo que el plan lo indique explícitamente. En particular, **no ejecutar `dotnet ef database update` contra Plesk/producción**.

```bash
dotnet build backend-dotnet/JemNexus.sln
```

```bash
dotnet test backend-dotnet/JemNexus.sln
```

```bash
dotnet ef migrations list \
  --project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj \
  --startup-project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj
```

Script acumulado hasta la última migración:

```bash
dotnet ef migrations script \
  --project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj \
  --startup-project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj \
  -o backend-dotnet/sql/AddAuthUsersAndAuditRelations.sql
```

Script diferencial desde schema comercial inicial hasta auth/auditoría:

```bash
dotnet ef migrations script InitialCommercialSchema AddAuthUsersAndAuditRelations \
  --project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj \
  --startup-project backend-dotnet/JemNexus.Api/JemNexus.Api.csproj \
  -o backend-dotnet/sql/FromInitialCommercialSchemaToAddAuthUsersAndAuditRelations.sql
```

Publicación local revisable para IIS/Plesk:

```bash
dotnet publish backend-dotnet/JemNexus.Api/JemNexus.Api.csproj -c Release -f net8.0 -o backend-dotnet/publish-test
```

## Próximo paso recomendado

Ejecutar solo las queries de diagnóstico en Plesk/SQL Server, registrar resultados exactos de tablas e `__EFMigrationsHistory`, y recién después elegir entre script acumulado, script diferencial o detención para revisión manual.

## Incidente de aplicación fallida por cascadas SQL Server

Durante el intento de aplicar en SQL Server real/Plesk el script acumulado `backend-dotnet/sql/AddAuthUsersAndAuditRelations.sql`, la base `jemnexusb_prod` había sido diagnosticada como vacía: `TABLES: 0`, sin `__EFMigrationsHistory`, sin `AppUsers` y sin `AppRefreshTokens`.

El intento falló al crear la FK self-reference de categorías con el error SQL Server:

```text
Msg 1785: Introducing FOREIGN KEY constraint 'FK_Categories_Categories_ParentId' on table 'Categories' may cause cycles or multiple cascade paths. Specify ON DELETE NO ACTION or ON UPDATE NO ACTION, or modify other FOREIGN KEY constraints.
```

Después del error, el script continuó parcialmente y dejó la base en estado inconsistente. El diagnóstico post-error informado para `jemnexusb_prod` fue:

- Base actual: `jemnexusb_prod`.
- Tablas existentes: `__EFMigrationsHistory`, `Suppliers`.
- Tablas faltantes: `Brands`, `Categories`, `Products`, `AppUsers`, `AppRefreshTokens`.
- `__EFMigrationsHistory` contiene `20260603182917_InitialCommercialSchema` y `20260604020543_AddAuthUsersAndAuditRelations`.
- `OBJECT_ID` de `Brands`, `Categories`, `Products`, `AppUsers` y `AppRefreshTokens` es `NULL`.

Por este incidente, `__EFMigrationsHistory` **no es confiable** como única fuente de verdad: contiene migraciones registradas aunque los objetos principales no existen. No se debe considerar el schema aplicado en Plesk si el historial EF dice que sí pero las tablas reales faltan.

Acciones obligatorias antes de reintentar:

1. No reejecutar el script viejo que contiene cascadas problemáticas.
2. Ejecutar diagnóstico de tablas e historial EF y guardar la salida.
3. Limpiar la base parcialmente ensuciada antes de aplicar de nuevo, usando `backend-dotnet/sql/CleanupFailedPleskApply.sql` en modo diagnóstico primero.
4. Confirmar que no existen tablas inesperadas; si existen, detenerse y hacer revisión manual.
5. Aplicar únicamente el script acumulado corregido con `ON DELETE NO ACTION` en relaciones comerciales y self-reference de categorías.

El hotfix ajusta el modelo EF Core, la migración inicial, el snapshot y el script acumulado para evitar cascadas comerciales peligrosas en SQL Server. La única cascada conservada es `AppRefreshTokens.UserId -> AppUsers.Id`, limitada a tokens de autenticación dependientes del usuario.
