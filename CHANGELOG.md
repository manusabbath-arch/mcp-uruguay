# Cambios

## Sin publicar

- **Cinco prompts y cuatro recursos**, aprendidos de mirar cómo otro servidor de Uruguay (`uruguay-mcp`) arma sus guías.
  Los prompts son recetas con el orden de las herramientas y sus trampas (combustible en pesos constantes, clima de
  Salto, el río, compras del Estado, real o nominal); los recursos son `uru://trampas`, `uru://fuentes`,
  `uru://inumet/estaciones` y `uru://bcu/monedas`. A diferencia de los de ese proyecto, los prompts no se limitan a
  decir qué herramienta llamar: dicen qué desconfiar. Un test falla si un prompt nombra una herramienta que no existe o
  si una herramienta queda sin su trampa.
- **La cobertura se mide en el CI** (`pytest-cov`, hoy 91%) y falla si baja del 88%.

## 0.12.0 — 2026-10-14

- **El mínimo de `uydatos` sube a 0.12.1**, que arregla `combustible_ancap` y `ventas_combustible`: ANCAP
  republicó sus datasets el 12/10/26 y la URL fija daba 404.
- **Nueva: `observaciones_inumet`**, sobre `uydatos.inumet` (publicado desde `uydatos`
  0.12.0): las observaciones horarias de INUMET en siete estaciones, agregadas al **día local**
  (la fuente publica en UTC; Uruguay es UTC-3). Sin estación, la cobertura de cada una; con estación,
  fechas y agregación, el valor de cada día. La agregación es obligatoria, un día al que le falta
  alguna observación devuelve `null` en vez de un total parcial, y el viento se mide contra sus 12
  observaciones diarias, no contra 24. La insolación (diaria, con valores imposibles declarados en
  `uydatos`) no se expone.

## 0.11.0 — 2026-10-11

- **Nueva: `pedidos_de_informes`**, sobre `uydatos.parlamento` 0.12: los pedidos de informes de
  Diputados (artículo 118 de la Constitución) de la legislatura actual, cuántos contestó cada
  organismo sobre los que ya cumplieron el plazo de 45 días, por semestre y por partido de los
  autores, con el enlace al oficio y a la respuesta. `presentados_hasta` compara una misma cohorte,
  porque las respuestas llegan tarde: de los pedidos del primer semestre de 2025 está contestado el
  92,5%, de los del segundo de 2026 el 31,9%.
- Depende de `uydatos>=0.12,<0.13`.

## 0.10.1 — 2026-10-11

- **Arreglo: el servidor se anunciaba como 0.7.0** a los clientes MCP desde la 0.7.0 hasta la 0.10.0,
  porque la versión era una constante que nadie actualizó. Ahora sale del paquete instalado, y
  `tests/test_version.py` la ata a `pyproject.toml`.
- **Nuevo: `scripts/humo.py`**, una prueba de humo del paquete **tal como se instala desde PyPI**:
  llama a las 27 herramientas contra las fuentes reales. La corre cada semana el job
  `instalado-desde-pypi` (Python 3.10 y 3.13) y avisa si alguna herramienta no responde. Medido al
  escribirla: 26 de 27 en 3.10 y en 3.13; la que faltó fue `leyes`, porque el Parlamento devolvía
  un archivo vacío para cualquier cliente, no por el paquete.

## 0.10.0 — 2026-10-11

- **Nueva: `paridad_combustibles`**, sobre `uydatos.ursea`: el precio ex planta de ANCAP contra el
  precio de paridad de importación de URSEA, **los dos sin impuestos**, mes a mes desde 2022, para
  la Súper 95, la Premium 97 y los gasoils 50-S y 10-S. Sin producto, el último mes y el promedio de
  12 meses de cada uno; con producto, la serie y el desglose del último PPI desde el FOB hasta los
  impuestos. La respuesta declara el `metodo` (qué nivel de precio y qué mes se comparan) porque es
  una construcción del servidor y no una cifra oficial. El GLP no se compara: un archivo lo da en
  $/litro y el otro en $/kg.
- Depende de `uydatos>=0.11,<0.12`.

## 0.9.0 — 2026-10-11

- **Nuevas: `buscar_indicador_social` e `indicador_social`**, sobre `uydatos.observatorio`: los
  ~1.260 indicadores sociales del MIDES (pobreza, empleo, educación, vivienda, salud...) leídos de su
  página viva en gub.uy, con la unidad, la forma de cálculo y la fuente del dato. **No se usan los
  del catálogo de datos abiertos porque esa copia quedó en 2019**; la página viva llega a 2024. La
  respuesta lleva los avisos del lector: filas «Total» mezcladas, mapas por departamento que muestran
  un solo año (`parcial`, con los períodos que faltan) y fichas que no coinciden con la tabla. `filtro`
  acota por valor de dimensión (`Salto`, `Mujeres,Pobre`); más de 80 filas se recortan con aviso.
- Depende de `uydatos>=0.10,<0.11`.

## 0.8.1 — 2026-10-10

- **Arreglo para Python 3.10 y 3.11**: desde la 0.3.0, en esas versiones las herramientas no
  declaraban su esquema de salida y `diagnostico` fallaba. Los tipos de salida eran `typing.TypedDict`,
  que pydantic sólo acepta desde Python 3.12; ahora salen de `typing_extensions`, que pasa a ser
  dependencia explícita. En 3.12 y posteriores nada cambia.
- **Por qué se publicó así cinco versiones**: el CI de cada push fallaba en 3.10 y 3.11, pero la
  publicación corría los tests sólo en 3.13. Ahora los corre en 3.10 y en 3.13, y no publica si fallan.
- `docs/herramientas.md` se genera igual en cualquier versión de Python (desde la 3.13 el compilador
  quita la sangría de los docstrings; ahora se normaliza siempre).

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
