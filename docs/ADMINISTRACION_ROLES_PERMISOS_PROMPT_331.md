# Administración de usuarios, roles y permisos

La sección **Usuarios** administra exclusivamente los roles técnicos `seller` (**Vendedor**) y
`support_admin` (**Superadministrador**). Ambos son cuentas de panel (`IsStaff=true`); solamente el
segundo mantiene `IsSuperuser=true` y recibe automáticamente todos los permisos efectivos.

## Catálogo y matriz

`GET /api/admin/users/permission-catalog` publica, con autorización de superadministrador, los dos
roles, los 29 permisos operativos concedibles a vendedores y `users.manage` como permiso reservado.
El frontend obtiene este catálogo para construir una matriz accesible, agrupada y responsive; no
mantiene una segunda lista de claves autorizadas. Un vendedor conserva únicamente filas válidas de
`AppUserPermissions`; un superadministrador no utiliza filas persistentes.

## Escritura y transiciones

En creación, omitir `role` conserva compatibilidad y crea un vendedor. Para vendedores, omitir
`permissions` asigna los 29 permisos predeterminados, mientras `permissions: []` asigna ninguno y una
lista válida define exactamente el conjunto inicial. Un superadministrador solo admite permisos
omitidos o un arreglo vacío. Los campos internos `seller_code`, `is_staff` e `is_superuser` nunca son
autoridad del cliente.

En actualización, omitir o enviar `null` en `permissions` conserva el conjunto de un vendedor y un
arreglo lo reemplaza atómicamente. La transición vendedor a superadministrador elimina el código y
las filas de permisos; la transición inversa genera un `SellerCode` nuevo y usa permisos explícitos o
los 29 predeterminados. El código permanece estable mientras la cuenta continúa como vendedor.

## Protecciones y sesiones

La sesión actual puede editar datos y contraseña, pero no desactivarse ni degradar su propio rol. Si
cambia su contraseña, el frontend limpia la sesión y solicita un nuevo ingreso. El backend protege al
último superadministrador activo con una transacción serializable en proveedores relacionales y una
comprobación equivalente en pruebas no relacionales.

`DELETE` realiza una desactivación reversible: no borra registros, invalida la contraseña y revoca los
refresh tokens. Reactivar requiere una contraseña nueva. Los cambios de contraseña, rol, permisos o
estado revocan también todas las sesiones renovables del usuario.

## Alcance pendiente

Las cuentas reales `supadmin`, `jmateluna`, `fheim`, `support` y `soporte` aún no fueron normalizadas.
El Prompt 332 adaptará los controles visuales del resto del panel a permisos granulares. Los avisos
continúan usando `ui-note` y `aria-live`; el sistema global de toasts queda pendiente.
