# Plan de integración frontend con API .NET en Plesk

## A. Estado actual

- El frontend React/Vite mantiene el flujo actual y no se hizo un corte total hacia la API .NET.
- La API .NET ya está publicada y validada manualmente en Plesk en `https://api.jem-nexus.cl` según el hito post-deploy documentado.
- El backend Django sigue existiendo y no fue eliminado ni reemplazado.
- El frontend público todavía no queda forzado a usar la API .NET; la selección se controla por variables de entorno Vite.
- No se conectó a Plesk, no se ejecutó SQL real y no se aplicaron migraciones desde este workspace.

## B. Variables frontend

El frontend usa variables Vite seguras, sin secretos, para decidir el backend objetivo:

| Variable | Uso | Valores esperados |
| --- | --- | --- |
| `VITE_API_BASE_URL` | URL base del backend configurado. Puede incluir `/api` por compatibilidad con configuraciones anteriores, pero se recomienda apuntar al origen del backend. | `http://localhost:8000`, `http://127.0.0.1:8001/api`, `https://api.jem-nexus.cl` |
| `VITE_API_PROVIDER` | Selector controlado de proveedor para pequeñas diferencias de rutas, principalmente health y trailing slash. | `django`, `dotnet` |

Ejemplo Django local actual:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_PROVIDER=django
```

Ejemplo API .NET en Plesk, para activar manualmente cuando corresponda:

```env
VITE_API_BASE_URL=https://api.jem-nexus.cl
VITE_API_PROVIDER=dotnet
```

La configuración de ejemplo vive en `frontend/.env.example`. Para cambiar la API no se debe tocar código: se debe crear o actualizar el `.env` correspondiente del entorno de ejecución/build.

## C. Auth

La API .NET validada en Plesk responde al login con esta forma:

```json
{
  "access": "...",
  "refresh": "...",
  "user": { }
}
```

El frontend normaliza respuestas de autenticación hacia una forma interna estable:

```ts
{
  accessToken,
  refreshToken,
  user
}
```

La normalización acepta las variantes de access token `access`, `accessToken`, `access_token` y `token`, además de las variantes de refresh token `refresh`, `refreshToken` y `refresh_token`. Los tokens se siguen guardando en `localStorage` con las claves internas existentes para no romper el flujo actual.

Las llamadas autenticadas usan `Authorization: Bearer <accessToken>`. Esto permite validar `/api/auth/me` contra la API .NET cuando `VITE_API_PROVIDER=dotnet` y `VITE_API_BASE_URL=https://api.jem-nexus.cl`, sin imprimir tokens en consola ni registrar secretos.

## D. Estrategia de migración por fases

### Fase 1: base controlada

- Preparar el cliente API centralizado y variables de entorno.
- Validar health contra la API configurada.
- Validar login contra .NET en un entorno controlado.
- Mantener Django disponible durante la verificación.

### Fase 2: login y panel vendedor

- Migrar login y `/api/auth/me` de forma controlada.
- Validar roles `seller` y `support_admin` con usuarios reales ya rotados o reemplazados.
- Confirmar CORS desde el dominio real del frontend.

### Fase 3: catálogo público y endpoints comerciales

- Migrar gradualmente productos, categorías, marcas, proveedores, promociones, secciones de home y cotizaciones.
- Mantener compatibilidad de payloads o adaptar servicios por endpoint.
- Evitar cambios masivos hasta tener smoke tests post-build.

### Fase 4: imágenes y gestión desde panel vendedor

- Implementar o validar subida de imágenes/productos desde el panel vendedor usando API .NET.
- Verificar almacenamiento, URLs públicas, límites de tamaño y permisos.
- Agregar pruebas específicas antes de activar el flujo en producción.

### Fase 5: convivencia o retiro gradual de Django

- Definir si Django queda como backend paralelo temporal o si se retira por etapas.
- Documentar endpoints retirados y fecha de corte.
- Mantener rollback claro mientras existan operaciones comerciales críticas.

## E. Pendientes

- Rotación controlada de credenciales provisorias usadas en validaciones manuales.
- Módulo `support_admin` para reset de contraseña vendedor.
- Carga de imágenes desde panel con API .NET.
- Validación CORS desde el frontend real.
- Smoke test post-build contra el backend configurado.
- SEO/IA SEO posterior, fuera de esta fase.
- Migración controlada de catálogo y cotizaciones cuando la API .NET tenga contratos confirmados para esos flujos.

## Validación controlada desde frontend

La ruta directa `/diagnostico-api` permite validar la API configurada por variables Vite sin cambiar la navegación pública ni migrar catálogo.

1. Crear `frontend/.env.local` manualmente, no versionado:

   ```env
   VITE_API_BASE_URL=https://api.jem-nexus.cl
   VITE_API_PROVIDER=dotnet
   ```

2. Ejecutar:

   ```bash
   cd frontend
   npm run dev
   ```

3. Abrir:

   ```text
   http://localhost:5174/diagnostico-api
   ```

   Si `start.py` o Vite usan otro puerto en el entorno local, abrir la misma ruta en ese puerto.

4. Presionar **Probar health** y confirmar que el proveedor, la base URL y el endpoint resuelto coincidan con la configuración esperada.
5. Probar login con el usuario vendedor validado manualmente en el entorno correspondiente.
6. Presionar **Probar /auth/me** para confirmar que el access token normalizado funciona como Bearer token.
7. Confirmar CORS desde el origen del frontend usado en la prueba.
8. No dejar passwords, tokens ni respuestas sensibles en capturas públicas o registros compartidos.
9. Volver a configuración Django/local cuando corresponda:

   ```env
   VITE_API_BASE_URL=http://127.0.0.1:8001/api
   VITE_API_PROVIDER=django
   ```

Esta validación no conecta a Plesk desde Codex, no ejecuta SQL, no aplica migraciones, no crea usuarios reales y no publica cambios. Tampoco hace corte total del frontend a .NET ni migra catálogo.
