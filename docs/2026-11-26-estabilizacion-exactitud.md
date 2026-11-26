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
quedan idénticos a la base remota. Esto preserva el benchmark, pero no resuelve las ambigüedades de
sus preguntas electorales ni actualiza cifras históricas del conjunto de desarrollo.

No se afirma una mejora de puntuación. No se repitió toda la suite de fuentes reales; se verificaron
las consultas indicadas. La Release, el despliegue remoto y la instalación permanente del usuario
no forman parte de esta tanda.

## Siguiente paso

Publicar solo después de revisar esta tanda. La prueba del wheel no requiere publicar en PyPI.
Antes de retomar la evaluación, resolver explícitamente la versión del conjunto y la interpretación
del escrutinio, sin usar respuestas reservadas para ajustar herramientas.
