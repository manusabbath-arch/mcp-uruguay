# Estabilización de exactitud y población oficial

Estado: implementación local verificada; versión 0.15.0 preparada, sin Release.

## Alcance

Se integraron selectivamente los cambios de producto de las PR #13 y #14 sobre `13d58d2`:

- MIDES: contar y omitir durante 30 días indicadores cuya lectura fue rechazada.
- Elecciones: explicar escrutinio primario frente a definitivo con observados.
- Normalizar descripciones y limitar el tamaño de las definiciones de herramientas.
- Localidades: agregar la población oficial del Censo 2023 por localidad y departamento sin
  reemplazar la población de la capa cartográfica.
- Conservar `uydatos>=0.18,<0.19` y habilitar el extra `hojas`.

No se integraron las ramas HTTP, evaluación de costos ni skills. No se ejecutó un modelo pago.

## Arreglos encontrados al verificar la integración

Cada uno se reprodujo con un test que fallaba antes del arreglo:

- Si fallaba uno de los dos tabulados, se perdían también los datos del otro. Ahora se manejan
  independientemente y la nota identifica qué tabulado falta.
- Las capas ya cargadas en memoria no figuraban en la procedencia. Ahora se registran en cada
  llamada; los tabulados también declaran su URL.
- Dos escritores de marcas MIDES perdían actualizaciones. Ahora hay un registro por indicador y
  un temporal único por escritura. La prueba sincroniza dos hilos para forzar el solapamiento.
- Las marcas usaban la fecha local del proceso. Ahora usan el reloj común de Uruguay.

Los tests de límites geográficos impiden descargas del censo: los XLSX de unidad son sintéticos.
Los canarios que descargan los originales llevan la marca `red`.

## Verificación realizada

- Base remota antes de integrar: `249 passed, 19 deselected`.
- Suite integrada, Python 3.10: `264 passed, 19 deselected`.
- Suite integrada, Python 3.13: `264 passed, 19 deselected`; cobertura `93.21%`, mínimo `88%`.
- Ruff: lint y formato sin errores.
- Canarios nuevos contra el INE: `3 passed, 18 deselected` con:

      uv run --extra test pytest -q -m red tests/test_red.py -k poblacion_oficial

  Los tres casos se añadieron después de las corridas completas anteriores; por eso el denominador
  de red seleccionado por defecto aumenta en tres, sin aumentar los tests de unidad.

- Se construyeron sdist y wheel con `uv build`. El wheel se instaló en un entorno aislado,
  sin checkout editable. Un cliente MCP por stdio inició un proceso real del servidor y comprobó
  seis consultas: localidad de Salto, departamentos de Paysandú y Montevideo, búsqueda MIDES,
  lectura MIDES y balotaje de Salto. Las seis respondieron sin error.
- En las tres consultas de población, la respuesta conservó tres respaldos y cada sha256 se
  contrastó con los bytes de la caché. El servidor anunció 31 herramientas.

## Contraste independiente de población

La respuesta del wheel dio ciudad de Salto `112527`, población de su capa `114043`, departamento
  de Salto `136195`, departamento de Paysandú `121838` y departamento de Montevideo `1302721`.

Se descargaron y extrajeron las infografías oficiales del INE, fuera del lector de tabulados:

- [Salto](https://www5.ine.gub.uy/documents/CENSO%202023/Infografias/Salto.pdf): contiene `112.527`
  y `136.195`.
- [Paysandú](https://www5.ine.gub.uy/documents/CENSO%202023/Infografias/Paysandu.pdf): contiene `121.838`.

Montevideo se contrastó con el tabulado oficial, no con una segunda publicación independiente.

## Benchmark y límites

El usuario pidió expresamente excluir dos commits de evaluación que aparecieron durante la
integración. Se revirtieron sin reescribir historia. `evals/preguntas.json` y `tests/test_evals.py`
quedan idénticos a la base remota **en esa tanda**; la tanda siguiente (abajo) mueve una cifra del
conjunto de desarrollo, con la fuente medida. Esto preserva el benchmark, pero no resuelve las
ambigüedades de sus preguntas electorales ni actualiza cifras históricas del conjunto de desarrollo.

## Tanda siguiente: la población del país y la cifra vigente de Paysandú

Integrada sobre la versión 0.15.0 preparada, sin Release:

- **`ubicar_punto` trae la población oficial del Censo 2023.** Antes el mismo punto daba dos
  poblaciones en el servidor: 114.043 para Salto (capa, `pob_tot_23`) en `ubicar_punto` y 112.527
  (tabulado del INE) en `localidad`, y quien citaba la primera citaba la que no es oficial. La
  localidad del punto lleva ahora `poblacion_oficial_2023`, la nota dice cuál es cuál y la `fuente`
  suma el Censo; si el tabulado no baja, responde igual con la cifra en `null` y el motivo.
- **`localidad()` sin argumentos responde por el país:** `poblacion_oficial_total` (3.499.451), los
  19 departamentos y las localidades más pobladas. Antes era un `ValueError`, así que «población de
  Uruguay según el Censo 2023» —una pregunta del conjunto de desarrollo de la eval— no tenía
  herramienta que la respondiera. El total es la suma de los departamentos, no la de las localidades
  (3.499.215: 236 personas en filas sin localidad), y va en `null` si el cuadro 12 no trae todos los
  departamentos de la capa.
- **`uru://trampas`:** la trampa de `localidad` pasa a ser que `pob_tot_23` no es la cifra oficial y
  que las localidades no suman el departamento ni el país.
- **`evals/preguntas.json`:** `censo-2023-departamento-paysandu` esperaba 121.843 con tolerancia 0,
  la infografía anterior a mayo de 2026; el PDF vigente, bajado el 2026-11-26, dice
  «PERFIL DEPARTAMENTAL PAYSANDÚ 2011 117.023 2023 121.838», igual que el cuadro 12. El esperado pasa
  a 121.838 y la cita, fecha y URL quedan registradas. De la misma fuente se marcan confirmadas
  Salto ciudad (112.527) y Salto departamento (136.195). **Ninguna pregunta de balotaje se toca:** su
  esperado depende de qué escrutinio se cuenta y esa decisión sigue abierta.

Verificación de esta tanda en `main`: `pytest -q` **268 passed, 22 deselected**; `ruff check` y
`ruff format --check` limpios; llamada real por MCP con `localidad()` (3.499.451, 19 departamentos) y
`ubicar_punto` en el centro de Salto (114.043 de la capa, 112.527 oficial), con `procedencia` que
declara `censo/localidades.xlsx` y `censo/departamentos.xlsx` con sus sha256. Trinquete de
definiciones de herramientas: 19.771 → 19.954 caracteres, en dos pasos (+78 y +105).

No se afirma una mejora de puntuación. No se repitió toda la suite de fuentes reales; se verificaron
las consultas indicadas. La Release, el despliegue remoto y la instalación permanente del usuario
no forman parte de esta tanda.

## Siguiente paso

Publicar solo después de revisar esta tanda. La prueba del wheel no requiere publicar en PyPI.
Antes de retomar la evaluación, resolver explícitamente la versión del conjunto y la interpretación
del escrutinio, sin usar respuestas reservadas para ajustar herramientas.
