# Cambios

## 0.8.0 — 2026-10-10

- **Nueva: `ventas_combustible`**, sobre `uydatos.ancap_ventas`: la cantidad vendida por ANCAP de cada
  combustible, por mes y mercado. Sin `linea` lista los productos con su familia y su unidad (el
  petcoke viene en toneladas y el resto en miles de m³: no se suman) y los meses que la fuente no
  publicó; con `linea`, la serie y el total de cada año **con cuántos meses lo forman**, porque el
  archivo tiene huecos (2024 sin octubre, 2025 sin agosto a octubre) y un año de 9 meses no se compara
  con uno de 12. `QUEROSENO` y `QUEROSENOS` quedan separados: son de familias distintas.
- Depende de `uydatos>=0.9,<0.10`.

## 0.7.0 — 2026-10-10

- **Nuevas: `asistencia_parlamentaria`, `leyes` y `proyectos_parlamento`**, sobre `uydatos.parlamento`.
  La asistencia exige un mínimo de citaciones (hay 3 a 4 veces más personas que bancas, por los
  suplentes) y avisa de nombres repetidos, que pueden ser homónimos. Las leyes salen sin duplicados ni
  la «ley 0», con el enlace a IMPO. Un proyecto que aparece en dos legislaturas cuenta una vez.
- Depende de `uydatos>=0.8,<0.9`.

## 0.6.0 — 2026-10-10

- **Nuevo: `compras_estado`**: cuánto adjudicó el Estado en un año, en pesos (cada moneda con la
  cotización del día), por organismo o por texto de los ítems, con los organismos que más compraron y
  los mayores ítems. **Avisa cuando un solo ítem pasa del 20% del total**: en los datos de la ARCE un
  ítem es el 77% de lo adjudicado en pesos en 2024 y otro el 53% en 2025. No devuelve nombres de
  proveedores, que pueden ser personas físicas.
- Guarda de privacidad (idea de Hermes): falla si un archivo versionado cita internos; los nombres
  específicos van en un archivo local que git ignora.
- Depende de `uydatos>=0.7,<0.8`.

## 0.5.0 — 2026-10-10

- **Nuevo: `resultados_electorales`**: nacionales 2024, balotaje 2024 y departamentales 2025, del país
  o de un departamento, desde los datos por mesa de la Corte Electoral. Incluye los votos observados,
  que la Corte escruta en mesas especiales sin localidad, y lo dice en cada respuesta. Porcentajes
  sobre los votos emitidos, con ese nombre.
- Depende de `uydatos>=0.6,<0.7`.

## 0.4.0 — 2026-10-10

### Nuevo

- **`ubicar_punto`**: en qué departamento y localidad cae un punto, según los polígonos oficiales del
  INE, con la población 2023 de la localidad. Si cae en el campo, la localidad más cercana y la
  distancia; si cae en el mar o en un río limítrofe, lo dice. El límite contestado con Brasil se
  informa como tal, asignado a Artigas. Suma la dirección más cercana de IDE.uy con su distancia.
- **`localidad`**: población y viviendas 2023 por nombre (sin importar tildes). Un nombre que existe
  en varios departamentos —«San Antonio» está en Canelones, Salto y Rocha— devuelve todos; solo con
  el departamento, sus localidades de mayor a menor población.
- Depende de `uydatos>=0.4,<0.5`.

## 0.3.0 — 2026-10-10

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
