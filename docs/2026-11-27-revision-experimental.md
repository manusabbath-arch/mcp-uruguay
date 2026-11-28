# Revisión de lo experimental de 0.16.0 y candidatas de producto

Fecha: 2026-11-27. Se revisaron `main` en `845dc4c` y la rama `codex/observatorio-caru` de
`uy-datos-abiertos` en `4c74be6`. Lo que dice «medido» se probó contra la fuente real ese día.

## 1. Lector de CARU (`uydatos.caru`, sin publicar)

**Lo bueno:** conserva la censura (`<LD`, `<5` → `valor=None` con `limite_deteccion`), valida
unidades y orden de columnas, exige fechas crecientes, no interpreta umbrales y ante la duda
rechaza. El adaptador del MCP (`--caru`) anota la procedencia y falla con un mensaje claro si falta
el lector.

**Lo que impide publicarlo así:**

1. **Apunta a un sitio que CARU dejó de usar.** Los dos URLs fijos están en el WordPress viejo.
   Desde fines de 2025 los informes están en carpetas públicas de Google Drive enlazadas desde
   `caru.org.uy/nuevositio/vigilancia-de-playas/`, con otro nombre de archivo
   (`2026 01 05 - Inf VP.pdf`), duplicados (`(1)`, `(2)`) y frecuencia todo el año: 19 informes en
   2026, hasta el 19/10, y 27 en 2025. Medido: la carpeta se lista sin credenciales con
   `drive.google.com/embeddedfolderview?id=<carpeta>` y cada PDF baja con
   `drive.google.com/uc?export=download&id=<archivo>`. Antes de 2025 hay tres esquemas de URL
   distintos (`web/informesalgas/`, `web/wp-content/`, `nuevositio/wp-content/`), con informes desde
   2011.
2. **`pdftotext -layout` no sirve para los informes nuevos.** En los PDF de 2026 separa la columna de
   fechas de la de valores. El lector rechaza, así que no da datos falsos, pero no lee ningún informe
   de la temporada actual (medido con los de enero, marzo y octubre de 2026). **pdfplumber**
   (`extract_tables`, Python puro) devuelve las filas bien emparejadas. Se verificó contra la página
   renderizada: Monte Caseros, 21/07/2026, E. coli 2300 y enterococos 494. Además elimina la
   dependencia de Poppler, que un usuario de Claude Desktop no tiene.
3. **Solo Salto Chico.** Cada informe de temporada trae 25 playas de las dos orillas, desde Bella
   Unión y Monte Caseros hasta Banco Pelay y El Sauzal; fuera de temporada, 10. Medido: pdfplumber
   detecta las 25 tablas de los informes de enero y marzo de 2026 y las 10 del de octubre. Limitarlo a una es una decisión del piloto,
   no del lector.
4. **Una playa ausente se trata como error.** En la temporada no estival Salto Chico no figura
   (informe del 19/10/2026) y el lector levanta «se esperaba una sola tabla». Ausente es «sin
   muestreo esa semana», no un archivo roto.
5. **Cada informe repite la temporada acumulada.** El del 19/10 trae las cinco fechas desde junio.
   Una serie se arma deduplicando por (playa, fecha) y tiene que detectar si dos informes discrepan
   en la misma fila.
6. **Falta lo que el repo exige a un lector**: trampas medidas en el docstring, una fila en
   `fuentes.FUENTES` y en la tabla del README, un adaptador en `verificar` y un test `red` contra un
   PDF real. Hoy solo hay un test con texto sintético.

**Recomendación:** reescribirlo sobre pdfplumber para todas las playas, con descubrimiento por las
carpetas de Drive, y publicarlo recién con un test contra tres PDF reales: uno de 2023, uno de enero
de 2026 y uno de octubre de 2026. La serie resultante es la parte valiosa: de 2011 a hoy, hasta 25
playas y muestreos semanales en temporada. No existe como dato abierto: hoy está encerrada en
cientos de PDF.

## 2. Modo `--remoto` (piloto HTTP)

Correcto para una beta. Escucha solo en `127.0.0.1`, limita por IP con cubeta de tokens, toma la IP
del último salto del proxy, ofrece `/health` y una sonda remota, y serializa las llamadas a una
misma herramienta.

- **No tiene autenticación.** La guía dice «acceso restringido» en el proxy, pero no cómo. Para una
  beta por invitación conviene un token por invitado, verificado en la app o en el proxy, y medir
  el uso por token. Sin eso no hay manera de saber quién usa qué, que es la evidencia que busca el
  piloto.
- El límite por IP vive en memoria del proceso: con dos réplicas se duplica. Está bien para una sola
  instancia; conviene dejarlo escrito.
- Las cinco herramientas del piloto son las livianas en memoria salvo `calidad_agua` (CSV de OSE de
  122 MB; p95 de 7,3 s medido por Codex). Es la que conviene vigilar en el servidor.

## 3. `buscar_datasets_catalogo`

Simple y útil: `package_search` de CKAN con paginado y la licencia de cada ficha. No devuelve
`procedencia`, lo que está bien: es una consulta en vivo y no lee un archivo. Falta una trampa
medida: el catálogo indexa título y notas, no el contenido de los archivos. Tampoco ve los datos que
un organismo publica fuera de CKAN, y CARU es el ejemplo de hoy: su serie de playas no está en el
catálogo.

## 4. Banco de evaluación del observatorio

Está bien diseñado: 30 escenarios pareados en dos idiomas, comparación con y sin búsqueda y el
escenario como unidad. **Nunca se corrió**: requiere una credencial de API con tope de gasto. Hasta
que corra no hay evidencia de que la búsqueda CKAN mejore las respuestas. Es la medición más barata
que queda pendiente.

## 5. Candidatas de producto encontradas en los datos

Problemas con evidencia de esta semana. Ninguna está validada con quien la sufre.

| Problema | Quién lo sufre | Dato que existe | Por qué nadie lo resolvió |
|---|---|---|---|
| ¿Se puede nadar hoy en esta playa del río Uruguay, y cómo viene la temporada? | bañistas, turismo, intendencias del litoral | Informes semanales de CARU desde 2011, hasta 25 playas, E. coli y enterococos (con valores de 2.300 UFC/100 mL medidos en invierno) | La serie está en cientos de PDF, en cuatro lugares distintos y con formatos que cambian |
| ¿Mis productos están más caros en góndola en Salto que en el resto del país? ¿Quién está en oferta? | distribuidoras y comercios del interior (incluida NG) | SIPC 2026: precios diarios de 379 productos en 930 establecimientos, 23 en Salto, con marca de oferta. 1,5 GB por año, desde 2014 | El archivo es demasiado grande para una planilla y no está en DataStore |
| Antecedentes de precio para una compra pública | compradores municipales | ARCE (OCDS), ya leído por `compras_estado` | Plan de Codex en `docs/observatorio-continuidad.md`; requiere validar con la Intendencia |
| Las fuentes abiertas se rompen en silencio | quien reutiliza datos públicos, y los propios organismos | Solo esta semana: el Parlamento con 403, `leyes` vacía, INUMET con un recurso duplicado, sanciones con RUT destruidos por Excel, la ECH del INE inaccesible | Nadie mide las fuentes semana a semana; `uydatos.verificar` ya lo hace |

Lo que falta para elegir es el criterio. Se pidió aplicar la filosofía de trabajo de un video,
pero el transcript que se pasó estaba vacío al leerlo.
