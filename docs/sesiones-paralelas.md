# Coordinación de sesiones paralelas

## Estado de esta entrega

Hay un coordinador local en `scripts/sesiones.py`, probado contra repos Git temporales.
Las instrucciones comunes viven en `AGENTS.md`, creado con autorización del dueño. El hook
`pre-commit` también está versionado, pero no se activa por clonar el repo: se instala explícitamente
en cada clon como se explica abajo. La configuración no se publica ni afecta a otros repositorios.
No se presupone que todos los clientes lean `AGENTS.md` o ejecuten el coordinador automáticamente.

## Motivo y diseño

El incidente fue una colisión de dos escritores sobre el mismo checkout e índice: aparecieron
commits y un merge que la sesión activa no había iniciado. Aumentar los avisos no separa los
índices. La solución acotada reutiliza patrones medidos en otros proyectos:

- Un checkout por tarea: Git mantiene un índice independiente por worktree.
- Integración serializada mediante un directorio de bloqueo en el directorio Git común.
- Verificación ligada al SHA exacto y al `main` que existía al correr las pruebas.
- Rechazo del trabajo sin commit y de operaciones Git pendientes, sin intentar limpiarlas.
- Fast-forward a un SHA, nunca un merge con resolución dentro del árbol compartido.
- Entorno Git aislado: un `GIT_INDEX_FILE` heredado de un hook no se usa contra otro worktree.

No se copiaron servicios, dependencias, registros ni reglas privadas de otros proyectos.

## Comandos

Desde el repositorio, para ver los worktrees y la configuración vigente de hooks:

    uv run --no-project python scripts/sesiones.py estado

Para crear una tarea nueva (sustituir el nombre y elegir una carpeta libre):

    git worktree add ../mcp-mi-tarea -b agente/mi-tarea main
    cd ../mcp-mi-tarea
    uv run --no-project python scripts/sesiones.py comprobar

El comando `comprobar` rechaza el checkout principal, `main` y HEAD detached. Es una comprobación
explícita: sin un hook o integración con el cliente, no bloquea por sí sola un `git commit` directo.

Después de commitear la tarea en su propio worktree:

    uv run --no-project python scripts/sesiones.py verificar
    uv run --no-project python scripts/sesiones.py integrar

`verificar` exige un árbol limpio, ejecuta los mismos comandos de lint, formato y tests sin red
usados por el proyecto y guarda un recibo local en el directorio Git del worktree. Una corrida
fallida borra el recibo anterior. Si `HEAD` o `main` cambian durante las pruebas, no genera recibo.
Un commit posterior, incluso de documentación, obliga a verificar de nuevo.

`integrar` adquiere el bloqueo común, exige ese recibo vigente y ambos árboles limpios y hace
`git merge --ff-only --no-overwrite-ignore` al SHA verificado. Así una ruta nueva versionada no
sobrescribe archivos locales ignorados que `git status` no muestra; los ignorados sin colisión no
impiden integrar. No rebasea, no hace stash, no aborta operaciones ajenas,
no borra ramas ni worktrees y no hace push. Los tests de este coordinador entran en el `pytest`
habitual y, por lo tanto, en el CI existente.

## Hook de commit: instalación y prueba

Una vez integrada la tanda en un main limpio:

    uv run --no-project python scripts/sesiones.py instalar-hook
    uv run --no-project python scripts/sesiones.py estado

El instalador escribe `core.hooksPath` solo en la configuración local del clon y lee de vuelta el
valor efectivo. Si hay otro directorio de hooks configurado o archivos distintos de las muestras
predeterminadas en el directorio Git de hooks, rechaza la instalación sin reemplazarlos ni ocultarlos.
También exige que el hook y el coordinador estén versionados en el árbol de main, limpio.

La ruta configurada es absoluta y apunta al hook canónico del árbol de main, no al de cada rama.
Así también funciona al commitear en worktrees anteriores que no traen todavía `scripts/sesiones.py`.
Un worktree con una configuración propia de hooks puede tener otro comportamiento; `estado` permite
consultar su valor efectivo. Después de mover el clon de carpeta hay que revisar esa configuración.

El hook llama a `comprobar`: rechaza commits desde el checkout principal (aunque esté en otra rama),
desde `main` y desde HEAD detached; permite una rama en un worktree propio. Se prueba con Git real,
con rutas que contienen espacios y commits por ruta que usan un índice temporal. En Windows, la
ruta del script se convierte a formato nativo para no depender de la traducción automática de MSYS.

No ejecuta la suite en cada commit: las pruebas completas siguen en `verificar` antes de integrar.
Requiere `uv` en PATH. No añade una excepción por variable de entorno: la habilitación temporal
usada para editar la guarda no desactiva la comprobación del hook instalado.

## Rechazos y recuperación

- **Main cambió:** actualizar la rama propia contra el main nuevo, resolver allí y volver a verificar.
- **Cambios sin commit:** identificar a su dueño. El comando no los guarda ni los borra.
- **Merge/rebase/cherry-pick pendiente:** identificar quién lo inició antes de actuar.
- **Integración ocupada:** esperar a quien posee el bloqueo. Su PID está en `propietario.txt`, dentro
  de `mcp-integracion.lock` del directorio Git común. Si el proceso murió, una persona revisa el
  estado y decide retirarlo; no hay robo automático ni caducidad por tiempo.
- **Rama no fast-forward:** resolver la divergencia en el worktree propio y repetir la verificación.

## Límites

Es coordinación cooperativa, no una frontera de seguridad: un programa que edite el árbol de
integración o ejecute Git directamente puede ignorarla. Un hook de commit tampoco intercepta
un merge fast-forward ni todas las escrituras. Los recibos locales son comprobantes operativos,
no firmas contra un actor malicioso. El bloqueo no se recupera automáticamente si el proceso muere.

El hook es una protección local contra errores, no una frontera de seguridad: Git permite omitir
hooks y tampoco intercepta todas las escrituras o los merges fast-forward. No se usa como prueba de
que toda sesión haya seguido el protocolo. La cobertura de cada cliente requiere comprobar que
efectivamente lee `AGENTS.md`; no se atribuye esa lectura a todos los clientes.
No se tocó la configuración global de Git ni de ningún cliente de agentes.
