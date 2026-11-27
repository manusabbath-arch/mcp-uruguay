# Continuidad del Observatorio de Salto

La próxima entrega propuesta es una **ficha de antecedentes para una compra municipal real** y, en paralelo, **una revisión manual de diez fuentes públicas**. El comprador podrá aceptar o descartar antecedentes con motivo. La revisión identificará incidencias que un responsable pueda reproducir y corregir. La segunda solicitud de cada equipo ayudará a decidir qué automatizar.

## Punto de partida comprobado

- El piloto ya responde consultas de río, lluvia y agua potable. La búsqueda CKAN devuelve fichas de datasets y `recursos_catalogo` entrega sus archivos. Un recorrido instalado por stdio encontró los 58 recursos de INIA Salto Grande y conservó las URL de los CSV de OSE tras precalentar. [Ficha del piloto](observatorio-salto.md)
- El transporte remoto de cinco herramientas se probó en loopback desde Codex y Claude Code. La beta por invitación requiere un destino autorizado y observación diaria. El precalentamiento de las tres fuentes se puede ejecutar con `--precalentar-piloto`. [Guía HTTP](observatorio-http.md)
- El lector histórico de Salto Chico se probó por stdio con un wheel local de `uydatos`. El lector de esa dependencia está commiteado en la rama `codex/observatorio-caru` de `uy-datos-abiertos`, en `4c74be6`. La opción aún depende del wheel local y de Poppler. [Guía CARU](observatorio-caru.md)
- El banco comparativo tiene 60 preguntas, con 30 escenarios en español e inglés. Hermes pudo contestar una pregunta real usando su sesión ya configurada. Esa prueba usó el catálogo MCP anterior y no mide el efecto de CKAN. La comparación completa sigue pendiente y requiere dos configuraciones con el mismo modelo y la búsqueda como única diferencia. [Protocolo de evaluación](evaluacion-observatorio.md)

## Pruebas de demanda

Proponer al Área de Innovación y Desarrollo de Salto una reunión con quien prepara antecedentes de compras y quien mantiene publicaciones de datos. Pedir el último antecedente preparado, una compra próxima y las fuentes que usan habitualmente. Medir cuánto tarda el proceso actual y qué revisiones exige. La primera entrega puede hacerse con el equipo antes de desplegar la beta. [Agenda digital de Salto](https://www.salto.gub.uy/noticias/salto-se-suma-la-agenda-digital-de-uruguay-rumbo-2040)

| Prioridad | Experimento | Evidencia para avanzar |
|---|---|---|
| Compras | Entregar una ficha y un CSV para un ítem de una compra próxima. | Una persona usa la ficha, explica qué candidatos sirven y pide otra. Medir tiempo hasta una respuesta citable, incluidos los minutos de revisión. |
| Calidad de fuentes | Revisar diez recursos que el equipo usa o publica. Separar disponibilidad, legibilidad, estructura, cobertura y frecuencia. | El responsable confirma una incidencia accionable y acuerda cómo volver a comprobarla. |
| Seguridad vial | Preparar con QGIS una ficha de tres cruces cerca de un centro educativo, para una recorrida ya prevista. | Tránsito indica qué decisión modificó la ficha. La exposición al tránsito y la verificación en campo son insumos para evaluar el riesgo. [UNASEV](https://www.gub.uy/unidad-nacional-seguridad-vial/comunicacion/noticias/unasev-presenta-nuevo-tablero-interactivo-para-consultar-datos-sobre) · [Proyecto de liceos de Salto](https://visualizador.ide.uy/descargas/datos/Documentos_IDE/proy_gvsigbatovi/html/2025-propuesta/2025-salto.html) |

Otras líneas investigadas son ejecución presupuestal, acceso a servicios, llamados para proveedores pequeños, reclamos y residuos, drenaje, transparencia y precios. La ejecución histórica de OPP tiene crédito ajustado, gasto ejecutado y pagado. La lectura del CSV encontró 1.784 filas de Salto, con observaciones de 1989 y 2022. Para seguimiento actual hace falta una fuente con cobertura más reciente. El SIPC ofrece precios por producto y comercio, pero el CSV de enero a setiembre de 2026 pesa 1,53 GB y CKAN no lo indexa en DataStore. Para los reclamos y el mantenimiento, validar primero si el municipio puede compartir un extracto autorizado. [Egresos de OPP](https://catalogodatos.gub.uy/dataset/opp-ingresos-y-egresos-de-los-gobiernos-departamentales-y-egresos-de-los-gobiernos-municipales) · [Metadatos del SIPC](https://catalogodatos.gub.uy/api/3/action/resource_show?id=8226cb72-6ff0-4ed5-84a4-6eb7ee3be208) · [Plan de Aguas Urbanas de Salto](https://www.gub.uy/ministerio-ambiente/comunicacion/publicaciones/planes-aguas-urbanas-uruguay-ciudad-salto)

## Implementación tras la prueba manual

1. **Ficha de compras.** Crear una CLI que genere CSV y Markdown a partir de los ZIP de ARCE. Reutilizar `uydatos.compras.iterar_adjudicaciones`. Extraer código y descripción antes de la compactación del servidor cuando el dato esté disponible. Guardar identificador, fecha, organismo, cantidad, unidad, moneda, precio original, respaldo y fecha de descarga. Permitir marcar comparable, descartado o pendiente con motivo. La normalización, cuando corresponda, queda junto al valor original.
2. **Comprobación.** Reproducir el ejemplo público de 2025 por búsqueda textual «residuos» y comprador «Intendencia de Salto». Devolvió la adjudicación `ocds-yfs5dr-1229985`, con 100 contenedores a UYU 12.153,27 y 50 papeleras a UYU 1.750. Los ítems coincidentes suman UYU 1.302.827 adjudicados. Probar con datos sintéticos estados excluidos, unidad y moneda faltantes, duplicados y resultado vacío. El ejemplo publicado es un antecedente, con alcance limitado por el filtro y por la diferencia entre adjudicación y pago. [Histórico ARCE](https://catalogodatos.gub.uy/dataset/arce-datos-historicos-de-compras)
3. **Revisión de fuentes.** Reutilizar `uydatos.verificar` y `uydatos.revisiones`. Versionar URL, organismo y frecuencia esperada por recurso. Probar que una descarga fallida, un cambio de columnas y una actualización normal produzcan evidencias distinguibles. Agregar seguimiento periódico cuando haya un responsable.
4. **Beta.** Agregar al MCP la salida que ya se usó en trabajo real. Conservar un artefacto archivable, probar el paquete instalado por stdio y HTTP, y ampliar la sonda con una consulta estable. Para medir retorno, usar frecuencia observada por tiempo neto ahorrado, descontando revisión y mantenimiento. La primera beta exige un destino de despliegue y acceso acordados.

## Reutilización externa

| Recurso | Decisión |
|---|---|
| [Lib CoVE OCDS](https://github.com/open-contracting/lib-cove-ocds) | Validación puntual de una muestra de ARCE. Describe problemas estructurales por campo. La equivalencia comercial se revisa con el comprador. |
| [Flatten Tool](https://github.com/opendataservices/flatten-tool) | Evaluar si hace falta entregar hojas relacionadas. La primera ficha usa un CSV sencillo. |
| [DuckDB](https://github.com/duckdb/duckdb) | Comparar tiempo y memoria con el iterador si la demanda requiere consultas repetidas sobre varios años o archivos masivos. |
| [CSV Detective](https://github.com/datagouv/csv-detective) y [Lychee](https://github.com/lycheeverse/lychee) | Explorar formatos nuevos y revisar enlaces. El contrato de datos se define con evidencia y pruebas locales. |
| [Hydra](https://github.com/datagouv/hydra), [MCP francés](https://github.com/datagouv/datagouv-mcp) y [MQA europeo](https://data.europa.eu/mqa/methodology?locale=en) | Adaptar el control de recursos, la comprobación de consultas de extremo a extremo y la separación entre accesibilidad y calidad. |
| [Kingfisher](https://github.com/open-contracting/kingfisher-process) y [Cardinal](https://github.com/open-contracting/cardinal-rs) | Evaluar ante una colección grande de OCDS o cuando exista una necesidad de control con reglas, datos y responsables definidos. |

Francia aporta el acceso por URL, el recorrido desde el dataset hasta su archivo y la sonda que prueba el servicio con una consulta real. ChileCompra y Prozorro muestran cómo vincular hallazgos a revisión humana y por qué conviene medir la cobertura antes de convertir registros en indicadores. En la beta medir tiempo y utilidad de los antecedentes. Una reducción de precios necesita evidencia propia. [ChileCompra](https://www.chilecompra.cl/alertas-automatizadas-del-observatorio/) · [Caso Prozorro](https://www.open-contracting.org/2024/12/04/how-to-make-better-public-procurement-decisions-with-business-intelligence-insights-from-ukraine/) · [Estudio sobre contratación electrónica](https://www.aeaweb.org/articles?id=10.1257/pol.20140258)

## Vías institucionales

Para contactar a Salto, preparar una página de propuesta, dos fichas de ejemplo y una demo breve. Para una futura edición de Desafíos Públicos, la institución puede presentar el problema que haya validado, sujeto a las bases aplicables. Las ediciones 2026 de Desafíos Públicos y Escala GovTech tenían plazos de setiembre ya vencidos. Si el equipo desarrollador explora Escala GovTech en otra edición, comprobar formalización y requisitos vigentes. [Desafíos Públicos](https://innovacionpublica.anii.org.uy/desafios-publicos-con-alto-impacto-ciudadano/) · [Escala GovTech](https://innovacionpublica.anii.org.uy/escala-govtech/)
