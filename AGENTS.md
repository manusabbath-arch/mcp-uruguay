# Guía para agentes

## Antes de escribir

- Leer `docs/sesiones-paralelas.md`, ejecutar `git status --short --branch` y `git worktree list`.
- Trabajar en una rama y un worktree propios por sesión. El checkout principal es de integración;
  otro worktree del mismo agente puede pertenecer a otra sesión.
- Ejecutar `uv run --no-project python scripts/sesiones.py comprobar` en el worktree propio.
- Si aparecen cambios u operaciones Git que esta sesión no inició, no revertir, abortar, resetear
  ni guardar en stash. Informar y dejar el trabajo ajeno intacto.

## Desarrollo

- Leer definiciones y usos antes de editar. Reproducir un defecto con un test en rojo antes del arreglo.
- Agregar archivos propios mediante rutas explícitas, sin `git add .`, `git add -A` ni `commit -a`.
- No modificar preguntas reservadas de evaluación para mejorar la puntuación.
- No versionar credenciales, cachés, rutas privadas ni datos internos de quien usa el proyecto.
- Los lectores de fuentes viven en el paquete `uydatos`; el registro MCP está en
  `src/mcp_uruguay/servidor.py` y las herramientas en `src/mcp_uruguay/herramientas/`.
- Ante datos inválidos, rechazar con motivo: no inventar cifras, convertir nulos en cero ni exponer
  rutas locales en respuestas públicas. Conservar fuente, fecha de descarga y procedencia.
- Si cambian descripciones de herramientas, regenerar con
  `uv run python -m mcp_uruguay.documentar` y revisar el presupuesto de definiciones.

## Verificación e integración

- Commitear los cambios propios en su rama. Ejecutar
  `uv run --no-project python scripts/sesiones.py verificar` sobre el árbol limpio.
- Integrar únicamente con `uv run --no-project python scripts/sesiones.py integrar`.
  El recibo vale para el SHA exacto y el main verificado. Si main avanzó, actualizar la rama propia
  y repetir las pruebas. Resolver conflictos solo en ese worktree, nunca en el checkout compartido.
- No robar bloqueos ni borrar worktrees de otras sesiones. El protocolo y la recuperación están
  documentados en `docs/sesiones-paralelas.md`.
- Una revisión cita el SHA que inspeccionó; un informe viejo no aprueba cambios posteriores.
- Verificar el paquete instalado por stdio cuando cambien herramientas, dependencias o arranque;
  tests en proceso no demuestran la instalación real. Para llamadas de humo, usar `scripts/humo.py`;
  para conservar respuestas y procedencia, `scripts/sonda.py`.
- No hacer push, tag, Release ni cambiar instalaciones sin autorización correspondiente.

## Límites de la coordinación

El coordinador protege a las sesiones que lo usan: no intercepta Git directo ni escrituras por
otros programas. Un hook de commit tampoco bloquea todos los merges. Informar por separado código
integrado, controles efectivamente instalados, revisión recibida, publicación e instalación.
No declarar un hook instalado sin comprobar su configuración y probar un rechazo real.
