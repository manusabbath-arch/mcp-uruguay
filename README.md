# mcp-uruguay

<!-- mcp-name: io.github.manusabbath-arch/mcp-uruguay -->

[![tests](https://github.com/manusabbath-arch/mcp-uruguay/actions/workflows/tests.yml/badge.svg)](https://github.com/manusabbath-arch/mcp-uruguay/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/mcp-uruguay)](https://pypi.org/project/mcp-uruguay/)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue)](LICENSE)

> **In English:** an MCP server that gives AI agents Uruguayan and regional public data straight
> from the primary sources: Central Bank of Uruguay exchange rates and inflation-adjusted pesos,
> Argentina's CPI, Brazil's IPCA, ANCAP fuel prices, INIA weather in Salto, Uruguay River stations,
> IDE.uy geocoding and RUT/ID validation. Read-only, and every answer carries its source and
> retrieval time.

Servidor [MCP](https://modelcontextprotocol.io) con **datos públicos de Uruguay y la región**,
leídos de la fuente primaria. Le da a cualquier agente de IA (Claude, o cualquier cliente MCP)
cotizaciones del BCU, pesos constantes, IPC de Argentina y Brasil, combustibles de ANCAP, clima
de Salto, estaciones del río Uruguay y validación de RUT y cédula.

Está construido sobre [uydatos](https://github.com/manusabbath-arch/uy-datos-abiertos), así que
hereda su regla: **rechazar en vez de arreglar**. Un agente que recibe un error con motivo puede
decirlo; uno que recibe un número plausible pero falso lo repite.

## Herramientas

| Herramienta | Qué responde | Fuente |
|---|---|---|
| `cotizacion` | Dólar, UI, peso argentino o real de un día; si es fin de semana, dice qué día hábil usó | BCU |
| `cotizacion_mensual` | Promedio mensual, con los días publicados y el mes en curso marcado como parcial | BCU |
| `pesos_constantes` | Lleva montos de distintos meses a pesos de un mes base, con la Unidad Indexada | BCU |
| `variacion_real` | Cuánto cambió un monto entre dos meses descontando la inflación (UI, IPC argentino o IPCA) | BCU, INDEC, IBGE |
| `ipc_argentina` | IPC nacional, base dic-2016 = 100 | INDEC |
| `ipca_brasil` | IPCA número-índice, base dic-1993 = 100 | IBGE |
| `combustible_ancap` | Precio máximo al público de cada combustible, por mes | ANCAP |
| `paridad_combustibles` | ¿ANCAP vende por encima o por debajo de lo que costaría importar? Ex planta contra el precio de paridad de importación, sin impuestos, mes a mes, con el desglose desde el FOB | URSEA, ANCAP |
| `ventas_combustible` | Cuánto vendió ANCAP de cada combustible por mes y mercado, con los meses que la fuente no publicó | ANCAP |
| `clima` | Lluvia y temperaturas diarias en Salto desde 1970 con su anomalía, o la tendencia por década | INIA |
| `observaciones_inumet` | Temperatura, lluvia, humedad, viento o presión de siete estaciones del país, agregada al día local (UTC-3); un día incompleto devuelve null | INUMET |
| `nivel_rio` | Altura del río en una estación de la cuenca del río Uruguay, por día, y cuánto subió o bajó | CTM Salto Grande |
| `nivel_rio_comparado` | ¿El río está alto o bajo para la época? Contra los mismos días de cada año desde 2017 | CTM Salto Grande |
| `estaciones_cercanas` | Estaciones hidrometeorológicas de la cuenca del río Uruguay cerca de un punto | CTM Salto Grande |
| `geocodificar_direccion` | Coordenadas de una dirección o esquina, con su calidad; descarta otra calle o el centro de la localidad | IDE.uy |
| `ubicar_punto` | En qué departamento y localidad cae un punto, con la población 2023 de la localidad | INE, IDE.uy |
| `localidad` | Población y viviendas 2023 de una localidad, o las de un departamento ordenadas | INE |
| `resultados_electorales` | Nacionales 2024, balotaje 2024 y departamentales 2025: participación y votos por partido o candidato, del país o un departamento | Corte Electoral |
| `compras_estado` | Cuánto adjudicó el Estado en un año, en pesos, por organismo o por texto, con los mayores ítems y un aviso si uno domina el total | ARCE (OCDS) |
| `asistencia_parlamentaria` | Asistencia a sesiones del Senado o Diputados por legislatura, con un mínimo de citaciones y aviso de homónimos | Parlamento |
| `pedidos_de_informes` | Pedidos de informes de Diputados a ministerios: cuántos se contestaron por organismo, semestre y partido, con el enlace al oficio y la respuesta | Parlamento |
| `leyes` | Leyes promulgadas desde 1985 por texto, fecha o número, con el enlace a IMPO | Parlamento |
| `proyectos_parlamento` | Proyectos entrados desde 1985 por texto, legislatura o tipo | Parlamento |
| `validar_documento` | Dígito verificador de RUT o cédula | sin red |
| `semana` | Semana ISO (`W41`) de una fecha, con su lunes y su domingo | sin red |
| `buscar_indicador_social` | Busca entre los ~1.260 indicadores sociales del MIDES por palabras | MIDES (Observatorio Social) |
| `indicador_social` | Un indicador social (pobreza, empleo, educación, vivienda...) con su unidad, cálculo y fuente, por dimensión y año, hasta 2024 | MIDES (Observatorio Social) |
| `recursos_catalogo` | Archivos vigentes de un dataset de catalogodatos.gub.uy | Catálogo de datos abiertos |
| `diagnostico` | De cuándo es cada copia en caché y si está vencida | sin red |

**Todas son de solo lectura**, y así lo declaran al cliente.

Cada respuesta trae dos campos para citar el dato:

- `fuente`: quién lo publica.
- `bajado`: cuándo se obtuvo la copia que se usó.

```json
{
  "moneda": "USD",
  "fecha_pedida": "2026-10-04",
  "fecha_cotizacion": "2026-10-02",
  "valor_en_pesos": 40.342,
  "nota": "Se usó la cotización del 2026-10-02, último día publicado antes del 2026-10-04. ...",
  "fuente": "Banco Central del Uruguay, web service de cotizaciones (cotizaciones.bcu.gub.uy)",
  "bajado": "2026-10-09T20:45"
}
```

## Flujos y referencias

Además de las herramientas, el servidor publica cinco **prompts** (recetas que el usuario elige, con el orden
de las herramientas y lo que hay que desconfiar de cada paso) y cuatro **recursos** (páginas de referencia que
el cliente lee cuando las necesita).

| Prompt | Qué arma |
|---|---|
| `combustible_en_pesos_constantes` | un combustible en pesos de un mismo mes, contra la paridad de importación y el volumen vendido |
| `clima_de_salto` | lluvia y temperatura de Salto desde las dos estaciones públicas, sin promediarlas |
| `el_rio_en_salto` | el río contra la misma época de otros años, con las advertencias de la unidad y de la cota |
| `compras_del_estado` | lo que el Estado adjudicó de un producto, sin dejar que un solo ítem engañe |
| `real_o_nominal` | si un monto subió o bajó descontando la inflación |

| Recurso | Qué trae |
|---|---|
| `uru://trampas` | la trampa que declara cada herramienta |
| `uru://fuentes` | quién publica cada dato, como lo cita el campo `fuente` |
| `uru://inumet/estaciones` | las siete estaciones de `observaciones_inumet` |
| `uru://bcu/monedas` | qué es cada moneda que acepta `cotizacion` |

Un test falla si un prompt nombra una herramienta que ya no existe, o si una herramienta queda sin su trampa.

## Instalación

Requiere [uv](https://docs.astral.sh/uv/). No hace falta clonar nada.

**Claude Code**

```sh
claude mcp add uruguay -- uvx mcp-uruguay
```

**Claude Desktop y otros clientes** (`claude_desktop_config.json` o el equivalente de tu cliente)

```json
{
  "mcpServers": {
    "uruguay": {
      "command": "uvx",
      "args": ["mcp-uruguay"]
    }
  }
}
```

Después, preguntale al agente cosas como:

- *"¿Cuánto valía el dólar el 4 de octubre de 2026?"*
- *"Vendí 1.200.000 pesos en septiembre de 2025 y 1.450.000 en septiembre de 2026. ¿Cuánto crecí en términos reales?"*
- *"¿Hizo más calor de lo normal en Salto en enero de 2026?"*
- *"¿El río Uruguay en Salto está alto para esta época del año?"*
- *"¿En qué departamento cae el punto -31.10, -57.30, y cuál es el pueblo más cercano?"*
- *"¿Cómo votó Salto en el balotaje de 2024?"*
- *"¿Cuánto gastó el Estado en ambulancias en 2025?"*
- *"¿Qué leyes sobre riego se aprobaron desde 2020?"*
- *"¿Cuál es la estación meteorológica más cercana a 18 de Julio y Ejido, en Montevideo?"*

## Caché

Lo que se baja queda en `~/.cache/mcp-uruguay`, o en la carpeta que indique la variable
`MCP_URUGUAY_CACHE`.

- **Lo cerrado no se vuelve a pedir:** un mes ya terminado del BCU no cambia.
- **Lo vivo vence:** el mes en curso a las 3 horas; el IPC, el IPCA, ANCAP y las estaciones al
  día; el clima a la semana.
- **Una descarga ilegible nunca reemplaza a una copia buena.**

La primera consulta de clima baja la serie completa de INIA (unos 57 archivos) y tarda alrededor
de un minuto. Las siguientes son instantáneas.

## Desarrollo

```sh
git clone https://github.com/manusabbath-arch/mcp-uruguay && cd mcp-uruguay
uv run --with pytest --with-editable . pytest            # sin red
uv run --with pytest --with-editable . pytest -m red     # contra las fuentes reales
```

Los tests del servidor conectan un cliente MCP real en el mismo proceso. Verifican que las herramientas
existan, que todas sean de solo lectura, que un error vuelva con su motivo y que los prompts y recursos se
puedan pedir y leer. La cobertura se mide con `pytest-cov` y el CI falla si baja del 88%.

## Licencia

MIT. Usalo, adaptalo y compartilo; solo mantené el aviso de autoría.
