# Piloto del observatorio de Salto

La primera medición recuperó datos del puerto de Salto, de INIA Salto Grande y del sistema de agua potable de OSE. Para comparar eventos, fijar primero una ventana común y revisar la cobertura de cada fuente.

## Observaciones comprobadas

Medición del 27 de noviembre de 2026. Wheel 0.15.0 construido desde el código de `97b64c2`, con caché existente.

| Tema | Resultado | Respaldo y límite |
|---|---|---|
| Río Uruguay | La última lectura disponible de la estación Salto (`A501258E`) fue `H = 7,81` el 27/11 a las 00:00. La ventana devolvió 1.249 de 1.344 lecturas esperadas e incluyó el día en curso. | Copia mensual descargada a las 00:32 del 27/11 (UTC−03). El servicio deja implícita la unidad de `H`. [CTM de Salto Grande](https://www.saltogrande.org/ws.php) |
| Clima | La serie disponible de INIA Salto Grande cubrió del 01/07/1970 al 20/11/2026. Para lluvia diaria se pide un rango cerrado y se lee `lluvia_mm`. | Descarga del 26/11 a las 16:34 (UTC−03). El día de INIA va de 09:00 a 09:00. Un nulo indica falta de dato. El wheel de la primera medición no incluía los hashes. La versión del piloto actual los adjunta incluso con la serie cargada en memoria. [Catálogo de INIA](https://catalogodatos.gub.uy/dataset/inia-precipitacion-temps-extremas-sg) |
| Agua potable | OSE reportó 112 muestras con análisis de turbidez en Salto en 2025-T1. De 112 análisis, 87 fueron exactos (0,2 a 0,7 NTU) y 25 quedaron por debajo del límite de detección de 0,2 NTU. | Copias descargadas el 26/11 a las 11:38 (UTC−03). La resolución es trimestral. El rango describe los valores exactos y la respuesta carece de un dictamen de cumplimiento. [Catálogo de OSE](https://datos.ose.com.uy/dataset/calidad-de-agua) |

El XML mensual de CTM tiene SHA-256 `6f9264af03d30221ff23f1d8fa2e2dd3d61842a66be6c9f60674ccd082d75f28`. El archivo fisicoquímico de OSE tiene SHA-256 `ae052ae069d70bfec21348b6f36005436d1ba4448c4fad8885f36943a55b8781`. La sonda guarda los respaldos completos en `datos.procedencia` cuando el servidor los incluye.

## Aguas superficiales y recreativas

- **Ministerio de Ambiente.** El reporte publicado en julio de 2026 describe las campañas de 2024 en tributarios del río Uruguay, incluidos Arapey y Daymán. El PDF contiene estaciones, variables, cronograma y estadísticas. El PDF remite al portal iSIA para la descarga completa. Al consultarlo el 27/11/2026 mostraba una página de servicio fuera de línea, sin exportación disponible. [Portal de descarga](https://www.ambiente.gub.uy/iSIA_OAN/) [Informe](https://www.gub.uy/ministerio-ambiente/comunicacion/publicaciones/plan-monitoreo-tributarios-del-rio-uruguay-reporte-datos-calidad-agua)
- **Observatorio Ambiental Nacional.** El catálogo ofrece XLSX de oxígeno disuelto, fósforo total, nitrógeno total y clorofila a. Se descargaron y abrieron las planillas de oxígeno disuelto y fósforo total. La hoja de la cuenca del río Uruguay contiene agregados anuales por curso, sin filas para Arapey o Daymán ni observaciones por estación. La exportación por estación queda pendiente de verificación en iSIA. [Datos abiertos](https://www.ambiente.gub.uy/oan/datos/listado-de-datos-abiertos/)
- **CARU y Salto Grande.** El programa documenta muestreos recreativos y un mapa que incluye Playa Salto Chico. El informe de la semana del 3 de febrero de 2025 contiene cinco muestreos de Salto Chico entre el 2 de diciembre de 2024 y el 3 de febrero de 2025. [Vigilancia de playas](https://caru.org.uy/nuevositio/vigilancia-de-playas/)

## Repetir la medición

```powershell
uv build --wheel
uv run --isolated --no-project --with ./dist/mcp_uruguay-0.15.0-py3-none-any.whl python scripts/sonda.py --stdio --herramienta clima --herramienta observaciones_inumet --herramienta nivel_rio --herramienta calidad_agua --salida dist/observatorio-salto.json
```

Las cuatro llamadas por stdio devolvieron datos. Los tiempos con caché existente fueron 1,35 s para clima, 13,53 s para INUMET, 0,26 s para río y 9,73 s para OSE. El JSON guarda los argumentos. La ventana por defecto del río se mueve con la fecha de ejecución.

## Casos para comparar clientes

| Pregunta | Evidencia esperada |
|---|---|
| ¿Cuál fue la altura diaria en el puerto de Salto del 1 al 3 de septiembre de 2026? | `nivel_rio` con estación y fechas. Citar cobertura y respetar la unidad que declara la fuente. |
| ¿Cuánta lluvia registró INIA Salto Grande del 1 al 3 de septiembre de 2026? | `clima` con ambas fechas. Informar milímetros por día y distinguir faltantes de ceros. |
| ¿Qué muestran los análisis de turbidez de OSE para Salto en 2025? | `calidad_agua` con localidad, parámetro y año. Distinguir valores exactos y censurados. |
| ¿Puedo usar esas muestras de OSE para saber si Playa Salto Chico estaba habilitada? | Explicar la diferencia de lugar y población muestreada y pedir un informe recreativo con fecha. |
| ¿Cuánta lluvia midió INIA Salto Grande en enero de 2099? | Informar la falta de observaciones y el último día disponible. |

Usar el mismo wheel y registrar por pregunta la herramienta, los argumentos, la evidencia citada y el tiempo. Para medir caché fría, usar un directorio separado y guardar el resultado junto al de la corrida caliente.

## Comprobaciones desde los clientes

- **Codex.** La traza registró la llamada a `uruguay-observatorio/nivel_rio`. Para el 1 al 3 de septiembre de 2026 devolvió 288 de 288 lecturas y medias diarias de 6,470, 6,095 y 5,922 en la escala H de origen, cuya unidad el servicio deja implícita. En una segunda consulta informó 0 observaciones para enero de 2099 y dejó indeterminado el acumulado. La serie llegaba al 20/11/2026.
- **Claude Code.** Coincidió en las cifras y la cobertura del río. Informó 0 mm de lluvia cada día en INIA Salto Grande y 492 análisis trimestrales de turbidez en 2025, incluidos 72 censurados. Identificó que la habilitación de la playa requiere otra fuente. La consulta terminó con código cero. Su hook de cierre informó un problema con el alias de Python.
- **Hermes.** El registro del piloto descubrió 31 herramientas. El registro Uruguay previo anunció 29 y carecía de la herramienta de OSE. La traza del registro nuevo muestra las tres llamadas correctas. Su respuesta coincidió con Claude Code en río, lluvia y turbidez y explicó que la habilitación de la playa queda fuera del alcance de esas observaciones.

Las tres comprobaciones usaron el entorno local del piloto. Codex recibió el nombre de la herramienta de río. Claude Code y Hermes recibieron las preguntas temáticas y el nombre del servidor, por lo que el resultado mide una comprobación guiada de integración y exactitud. Una evaluación M6 requeriría preguntas sin pistas, un conjunto reservado y resultados comparables entre modelos.

## Muestra recreativa con respaldo

| Playa y fecha | Escherichia coli | Enterococcus | Floraciones algales |
|---|---:|---:|---|
| Salto Chico, 20/01/2025 | <5 UFC/100 mL | <5 UFC/100 mL | Vigilancia |
| Salto Chico, 03/02/2025 | 80 UFC/100 mL | 50 UFC/100 mL | Vigilancia |

Son dos de las cinco fechas de la tabla de CARU y Salto Grande. El signo menor que se conserva como límite de detección. Vigilancia es el estado informado para floraciones algales. Determinar la habilitación requeriría una fuente que publique esa decisión para la fecha. PDF descargado el 27/11/2026, SHA-256 `ab4f4f5aa97731d9471ded6d60979ef698d16648bbd37c1525045915e20fe8d7`. [Informe semanal CARU y Salto Grande](https://caru.org.uy/nuevositio/wp-content/uploads/2025/02/Informe-Resultados-Semana-del-03-de-Febrero-de-2025.pdf)

## Prioridad operativa

Se repitieron las tres consultas con el wheel del código de `3c9a388`, primero con un directorio de caché vacío y luego reutilizando ese mismo directorio. Se comprobaron contra los archivos 57 hashes de clima, dos del río y dos de OSE.

| Llamada | Caché vacía | Caché reutilizada |
|---|---:|---:|
| Clima | 35,52 s | 1,77 s |
| Nivel del río | 1,10 s | 0,18 s |
| Calidad de agua | 61,22 s | 9,45 s |

El contenido de las observaciones coincidió en ambas corridas. En OSE las dos URL directas de los CSV se informaron al descargarlos y quedaron en nulo al reutilizarlos, aun con hashes y sellos idénticos. Para replicar la medición, asignar una ruta vacía a `MCP_URUGUAY_CACHE` antes de ejecutar la sonda por stdio y repetir con esa misma ruta.

Para el piloto, la prioridad es **M7 y la cobertura de fuentes**. El comando existente `mcp-uruguay --precalentar` ya incluye calidad de agua de Salto, que fue la única de estas tres consultas que superó el minuto en frío. Conservar la URL directa de OSE al reutilizar la caché mejoraría la trazabilidad. Para aguas superficiales, el siguiente paso es conseguir una exportación con estación, fecha, parámetro, unidad y calificador. Para playas ya existe una fuente histórica con ese detalle en PDF. La viabilidad de un lector depende de comprobar la consistencia entre informes. La ficha permite operar por stdio y deja el transporte remoto sujeto a la necesidad de acceso desde otros clientes.
