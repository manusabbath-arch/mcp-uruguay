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

`preguntas.json` tiene tres tipos de pregunta:

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
   acceso a los sitios del Estado. Por eso todas dicen `confirmada_en_fuente: false`, salvo las trampas
   cuya regla está medida en `uydatos`. Hay que abrir cada `url`, comprobar el número y pasar el campo a
   `true`.
2. **Revisar las preguntas que caducan.** `trampa-caudal-concordia-hoy` depende de que la fuente siga
   atrasada.
3. **Correr el conjunto reservado al menos tres veces** (`--repeticiones 3`). Una corrida sola tiene ruido.

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

Imprime una tabla (acierto por modo y tipo, llamadas, errores de herramienta y tokens) y guarda cada
intento en `evals/resultados/<fecha>-<modelo>-<conjunto>.json`, con la respuesta completa. Esa carpeta
no se versiona.

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
- **las 14 preguntas, en los dos modos**: alrededor de **US$ 4**.

La caché debería bajarlo, porque las herramientas se repiten idénticas. Lo que vale es medirlo: correr
una pregunta con `--id` y mirar los tokens del detalle.

## Agregar una pregunta

1. Debe ser una pregunta que alguien haría de verdad, no una instrucción de qué herramienta usar.
2. La cifra debe salir de la fuente oficial, con `url` y `cita`. Si no hay fuente, la pregunta no entra.
3. Al conjunto `reservado` va más o menos una de cada tres.
4. `tests/test_evals.py` comprueba que esté completa y que las herramientas que nombra existan.
