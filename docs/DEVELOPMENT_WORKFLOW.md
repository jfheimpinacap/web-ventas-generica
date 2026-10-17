# Flujo de desarrollo local

## Entorno y coordinación

JEM Nexus se trabaja preferentemente con Codex local en la extensión de VS Code.
No se debe trabajar simultáneamente desde Codex Cloud y VS Code sobre cambios
pendientes de la misma tarea.

Abrir VS Code no demuestra que el ejecutor sea local. Antes de editar o validar,
se comprueban el sistema operativo del ejecutor y la raíz real del repositorio
mediante herramientas. Si la tarea exige Windows y se ejecuta en otro entorno,
se detiene sin editar ni validar.

La opción “Work locally” corresponde al flujo local acordado en esta guía.
“Apply changes and continue locally?” permite trasladar trabajo Cloud revisado a
una rama local preparada; después de aplicarlo se verifican el entorno y el
estado Git. Aplicar cambios no autoriza commit, push, PR ni merge: la publicación
mantiene las aprobaciones indicadas más abajo.

No se repite Apply para cambios ya transferidos o recibidos mediante merge y
sincronización.

El coordinador prepara prompts numerados. Franz los copia en Codex y devuelve el
Summary para revisión. Una tarea nueva usa el siguiente entero y una rama propia
creada desde `main` actualizado. Los correctivos anteriores al merge se identifican
con `A`, `B`, etc., y continúan en la misma conversación y rama. Después del merge,
cualquier trabajo nuevo usa el siguiente entero.

No se modifican fuentes directamente sobre `main`. Antes de empezar una tarea hay
que comprobar la raíz Git, rama, `HEAD`, árbol e índice, remoto esperado e
instrucciones `AGENTS.md` o `AGENTS.override.md` aplicables. Los remotos se muestran
sin credenciales. Si existen cambios previos, divergencia o una base incompatible,
se conservan y se informa el impedimento antes de editar; no se usan `reset --hard`,
`clean`, stash automático ni reescrituras de historial.

## Comandos en Windows

Cada bloque PowerShell debe comenzar con `Set-Location -LiteralPath` y la ruta
Windows absoluta correspondiente. Las ubicaciones habituales son:

- Raíz: `C:\Users\Franz\Desktop\web-ventas-generica`.
- Frontend: `C:\Users\Franz\Desktop\web-ventas-generica\frontend`.
- API: `C:\Users\Franz\Desktop\web-ventas-generica\backend-dotnet\JemNexus.Api\JemNexus.Api.csproj`.

Ejemplo:

```powershell
Set-Location -LiteralPath "C:\Users\Franz\Desktop\web-ventas-generica\frontend"
npm.cmd run test:sidebar-menu
if ($LASTEXITCODE -ne 0) { throw "Fallo en test:sidebar-menu" }
```

No se muestran secretos, tokens, cabeceras de autorización ni contenidos de
archivos de credenciales en comandos, registros, capturas, diffs o resúmenes.

## Validación local

En local se autoriza ejecutar las pruebas y compilaciones pertinentes al alcance
antes de entregar el Summary. La antigua prohibición de hacerlo en Codex Cloud no
se aplica automáticamente al entorno local. Las pruebas deben completarse antes de
solicitar aprobación para publicar.

Las instalaciones o restauraciones necesarias deben respetar los manifiestos
existentes. No se cambian dependencias o versiones para resolver un bloqueo sin
justificarlo. Tampoco se realizan instalaciones globales ni se modifica como parte
rutinaria de una tarea la configuración personal del equipo.

No se modifican bases de producción, no se ejecutan migraciones y no se usan
servicios de producción para validar. Se pueden utilizar servidores locales cuando
el alcance lo requiera, identificando los procesos propios y respetando los que
Franz ya tenga abiertos.

La validación visual y las pruebas automatizadas se informan por separado. Nunca se
declara una revisión visual que no se realizó. Un build o una suite verde no
sustituyen la comprobación del comportamiento en el navegador.

## Revisión, publicación e integración

Antes de publicar se entregan el Summary y el diff para revisión. Commit, push y
creación de PR requieren el prompt de publicación aprobado; Franz no necesita
hacer commits manualmente. El merge queda bajo control de Franz: no se ejecutan
merge, automerge ni despliegues por iniciativa propia.

Tras el merge se sincroniza `main` de forma segura, mediante avance rápido cuando
corresponda, y se comprueba la integración. Las suites completas solo se repiten si
existe una razón concreta, como cambios posteriores, diferencias de entorno o una
validación pendiente que el merge deba confirmar.
