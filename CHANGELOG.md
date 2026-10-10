# Cambios

## Sin publicar

### Nuevo

- **`nivel_rio`**: la altura del río en una estación de Salto Grande (por nombre o id), por día,
  con la última lectura, cuánto subió o bajó y la cobertura de lecturas.
- **`nivel_rio_comparado`**: los últimos días contra los mismos días de cada año desde 2017, y en
  qué lugar quedan. El 10/10/2026 la estación Salto estaba en el nivel más alto de los 10 años.
- **`variacion_real`**: variación nominal, inflación y variación real entre dos meses, con la UI,
  el IPC argentino o el IPCA brasileño.

### Corregido

- **Un mes bajado mientras corría quedaba incompleto para siempre.** La caché del BCU lo daba por
  cerrado apenas existía el archivo; ahora un mes se da por cerrado solo si se bajó después de
  terminar, y si no se vuelve a pedir una vez. Aplica también a las lecturas del río.
- Depende de `uydatos>=0.3,<0.4` (lecturas de Salto Grande).

### Cambiado

- Las trece herramientas declaran los campos de su salida, y hay una guarda que impide que vuelva
  a haber una que no lo haga. Sin eso, el modelo que llama tiene que adivinar los nombres.
- `clima_salto` y `clima_tendencia` se fusionaron en **`clima`**: sin fechas devuelve la tendencia
  y con `desde`/`hasta` los dias. Las dos preguntan lo mismo, y tener dos herramientas parecidas
  hace que el modelo elija mal. **Quita dos herramientas**, asi que la proxima version es 0.3.0.

## 0.2.1 — 2026-10-09

- Publicado en PyPI (`uvx mcp-uruguay`) y en el registro oficial de MCP como
  `io.github.manusabbath-arch/mcp-uruguay`, con trusted publishing al crear una Release.
- Depende de `uydatos` desde PyPI (`>=0.2.1,<0.3`) en vez de una etiqueta de GitHub.
- Insignias y un resumen en inglés en el README.

## 0.2.0 — 2026-10-09

- **Nueva herramienta: `geocodificar_direccion`**, sobre `uydatos.ideuy` (IDE.uy). Devuelve la
  calidad del resultado y no da coordenada cuando la API devuelve otra calle o el centro de la
  localidad.
- Pasa a `uydatos` v0.2.0.
- CI: tests en Python 3.10 a 3.13 y Windows, y una corrida semanal contra las fuentes reales.

## 0.1.0 — 2026-10-09

Primera versión: 12 herramientas de solo lectura (BCU, pesos constantes, INDEC, IBGE, ANCAP,
INIA, Salto Grande, RUT y cédula, semanas ISO y catálogo de datos abiertos).
