# Informes de Salto Chico por MCP local

La opción `--caru` agrega `muestreos_salto_chico` al catálogo stdio. Acepta la semana del informe `2023-02-27` o `2025-02-03`. Devuelve observaciones históricas, fecha y unidad de muestreo, censura y procedencia del PDF. Ambos informes corresponden a Salto Chico. Los campos de la tabla cubren el monitoreo recreativo. Una decisión de habilitación requiere su propia fuente.

Para la prueba se necesitan el wheel de MCP Uruguay, un wheel de `uydatos` que incluya `uydatos.caru` y `pdftotext` de Poppler en PATH. El wheel de prueba de `uydatos` debe satisfacer la restricción de dependencia del wheel MCP. La versión publicada de la dependencia todavía carece de ese lector. La prueba actual usa el wheel local de la rama de CARU construido sobre 0.18 y conserva la línea 0.19 preparada aparte.

El piloto HTTP conserva su catálogo inicial de cinco herramientas. La opción de informes permite verificar el lector y el contrato MCP antes de distribuirlo.
