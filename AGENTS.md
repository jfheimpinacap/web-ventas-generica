# Instrucciones para agentes

- Trabaja preferentemente con Codex local en VS Code y sigue el flujo detallado en
  [`docs/DEVELOPMENT_WORKFLOW.md`](docs/DEVELOPMENT_WORKFLOW.md).
- Comprueba el sistema operativo y la raíz real antes de editar o validar. Si la
  tarea exige Windows y el ejecutor está en otro entorno, detente; consulta la guía.
- No edites fuentes directamente en `main`; usa una rama por tarea desde un `main`
  actualizado de forma segura.
- Ejecuta las validaciones pertinentes antes de solicitar aprobación para publicar,
  pero distingue siempre las pruebas automatizadas de la revisión visual.
- Entrega el Summary y el diff para revisión antes de publicar. Commit, push y PR
  requieren el prompt de publicación aprobado; el merge y los despliegues quedan
  bajo control de Franz.
- No reveles secretos ni uses producción para validar. No cambies dependencias,
  configuración personal o herramientas globales sin justificación y autorización.
- Todo bloque PowerShell debe comenzar con `Set-Location -LiteralPath` y la ruta
  Windows absoluta que corresponda.
