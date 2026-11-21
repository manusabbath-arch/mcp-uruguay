# La evaluación de exactitud

¿El agente acierta más con `mcp-uruguay` que sin él? ¿Y cuándo le toca avisar en vez de dar un número,
avisa? Esto lo mide con preguntas que tienen **respuesta oficial**, y la misma pregunta se corre con el
servidor y sin él.

## Por qué

- Anthropic, en [*Writing effective tools for agents*](https://www.anthropic.com/engineering/writing-tools-for-agents),
  pone la evaluación como la forma más efectiva de mejorar herramientas para agentes. Pide tareas
  realistas con un resultado verificable, un conjunto reservado para no sobreajustar, y medir acierto,
  llamadas, errores y tokens.
- La DINUM, en el balance del MCP de data.gouv.fr, reconoció que «es muy difícil auditar los resultados de
  un servidor MCP» (según Next y Alliancy). Este servidor dice que sus cifras se pueden citar, y esta
  evaluación es la forma de probarlo con un número.

## Qué mide

`preguntas.json` tiene 30 preguntas de tres tipos, que cubren 13 herramientas (19 de desarrollo y 11 reservadas):

| tipo | qué se espera | cómo se verifica |
|---|---|---|
| `numero` | una cifra oficial (votos, población, inflación, la UI) | la última línea `RESPUESTA:` dentro de `esperado ± tolerancia` |
| `texto` | una fecha o un nombre | la línea `RESPUESTA:` contiene `patron` |
| `comportamiento` | **las trampas**: un domingo sin cotización, un `<0,2` que no se promedia, un caudal con meses de atraso, una pobreza con dos metodologías | la respuesta completa menciona lo que tiene que mencionar |

Las preguntas de comportamiento son el diferencial: miden si el agente **rechaza en vez de inventar**,
que es la regla de `uydatos`.

**La respuesta esperada nunca sale de este servidor.** Sale de la publicación oficial, o de prensa que
la cita, y cada pregunta lleva su `url`, la `cita` y el campo `via`. Medir contra lo que devuelve el
propio servidor sería circular.

Hay dos conjuntos. `desarrollo` es el que se mira para mejorar las herramientas. `reservado` **no se
mira** al ajustar: es el número que se publica.

## Antes de publicar un resultado

1. **Confirmar cada respuesta en la fuente.** Las cifras se buscaron el 2026-11-04 desde una máquina sin
   acceso a los sitios del Estado. Por eso las que vienen de una página dicen `confirmada_en_fuente:
   false`. Las que salen de un cálculo (semana ISO, dígito verificador) o de una regla medida en `uydatos`
   ya están confirmadas. `confirmar.py` baja cada fuente (HTML o PDF) y busca la cifra escrita en
   cualquiera de sus formas (`49,84`, `1.101.296`, `09/07/2020`):

   ```sh
   uv run --with pypdf python evals/confirmar.py            # informa, no toca nada
   uv run --with pypdf python evals/confirmar.py --marcar   # marca las que encontró, con fecha y URL
   ```

   Lo que no encuentra queda para revisar a mano: el script no adivina.
2. **Revisar las preguntas que caducan.** `trampa-caudal-concordia-hoy` depende de que la fuente siga
   atrasada.
3. **Correr el conjunto reservado al menos tres veces** (`--repeticiones 3`). Una corrida sola tiene ruido.
   Con más de una repetición, debajo de la tabla sale `inestables`: las preguntas que aciertan en unas
   repeticiones y fallan en otras.

La tabla separa dos cosas que el porcentaje mezcla: `usó la esperada` (si el agente llamó a alguna de
las `herramientas_esperadas` de la pregunta: un fallo con `0/1` es de elección, no de dato) y
`no corrió` (intentos en que el motor falló o no devolvió resultado; no entran en el porcentaje).

## Cómo correrla

Necesita una clave de la API de Claude (`ANTHROPIC_API_KEY` o `ant auth login`) y red hacia las
fuentes. **Cada corrida cuesta dinero.**

```sh
# Una pregunta, para ver el costo real antes de correr todo
uv run --with anthropic python evals/evaluar.py --id ipca-brasil-2024 --conjunto todos

# El conjunto de desarrollo, con y sin el servidor
uv run --with anthropic python evals/evaluar.py --modo con,sin --conjunto desarrollo

# El número para publicar
uv run --with anthropic python evals/evaluar.py --modo con,sin --conjunto reservado --repeticiones 3
```

Imprime una tabla (acierto por modo y tipo, llamadas, errores de herramienta, tokens, costo en US$ y
costo por acierto) y guarda cada intento en `evals/resultados/<fecha>-<modelo>-<conjunto>.json`, con la
respuesta completa. Esa carpeta no se versiona.

### Trazas, presupuesto y costo

Cada intento guardado trae su traza:

- `pasos`: una entrada por llamada a herramienta, con el turno, los argumentos, los segundos, si dio
  error y el tamaño del resultado en bytes.
- `turnos_detalle`: los tokens de entrada, salida y caché (leídos y escritos) y los segundos de cada
  turno del modelo.
- `costo_usd`: calculado con la tabla `PRECIOS` de `evaluar.py`. Un modelo sin precio da `null` y la
  tabla dice `s/d`: sin dato no es gratis. Para otro modelo, `--precio ENTRADA,SALIDA` (US$ por millón).

`--presupuesto-tokens N` pone un tope duro por intento: cuando los tokens procesados (entrada, salida y
caché leída y escrita: con caché la entrada nueva es casi cero) llegan a `N`, el
intento corta antes del turno siguiente, queda con `motivo_fin: "presupuesto_agotado"` y cuenta como
fallo. La tabla muestra cuántos intentos se cortaron. El **costo por acierto** divide el gasto total
del grupo, fallidos incluidos, por los aciertos: es lo que cuesta de verdad una respuesta correcta.

```sh
# Una pregunta con tope de 60.000 tokens, para medir el costo real antes de correr todo
uv run --with anthropic python evals/evaluar.py --id ipca-brasil-2024 --conjunto todos --presupuesto-tokens 60000
```

### Con Claude Code en vez de la API (`--motor claude-cli`)

Si no hay clave de la API pero sí Claude Code instalado y con sesión iniciada (`claude`, y adentro
`/login`), `--motor claude-cli` corre cada pregunta con `claude -p` (`evals/motor_claude_cli.py`):

- un proceso nuevo por pregunta, sin sesión guardada, en una carpeta vacía;
- sin las herramientas propias de Claude Code (`--tools ""`) ni la configuración del usuario
  (`--setting-sources ""`), y con el mismo prompt de sistema que el motor de la API;
- con servidor, la única herramienta es `mcp-uruguay` por stdio (`--strict-mcp-config`).

La traza sale del stream de eventos (los segundos de cada paso son los que pasan entre la llamada y su
resultado) y el costo es el que informa Claude Code: con suscripción es lo que costaría por la API, no
lo que se paga. Si la sesión venció, el intento termina con `motivo_fin: "error"` y cuenta como fallo.

```sh
uv run --with-editable . python evals/evaluar.py --motor claude-cli --id ipca-brasil-2024 --conjunto todos
```

El modelo por defecto es `claude-opus-5-5` con esfuerzo `medium` (`--modelo` y `--esfuerzo` lo
cambian). Un `refusal` cuenta como fallo y queda registrado. **No se usa el respaldo automático a otro
modelo** (`fallbacks`), para que el número sea de un solo modelo.

### Cuánto cuesta (estimado, sin medir)

Las 31 herramientas ocupan unos 7.400 tokens y viajan en cada turno. Con `claude-opus-5-5` (US$ 4 por
millón de tokens de entrada y US$ 20 por millón de salida), y antes de descontar la caché de prompts que
el script activa:

- **con el servidor**: unos 4 turnos de unos 11.000 tokens de entrada y unos 3.000 de salida, alrededor
  de **US$ 0,25 por pregunta**;
- **sin el servidor**: alrededor de **US$ 0,05 por pregunta**;
- **las 30 preguntas, en los dos modos**: alrededor de **US$ 9**.

La caché debería bajarlo, porque las herramientas se repiten idénticas. Lo que vale es medirlo: correr
una pregunta con `--id` y mirar los tokens del detalle.

## Agregar una pregunta

1. Debe ser una pregunta que alguien haría de verdad, no una instrucción de qué herramienta usar.
2. La cifra debe salir de la fuente oficial, con `url` y `cita`. Si no hay fuente, la pregunta no entra.
3. Al conjunto `reservado` va más o menos una de cada tres.
4. `tests/test_evals.py` comprueba que esté completa y que las herramientas que nombra existan.
