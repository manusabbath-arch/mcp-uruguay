# Las herramientas del servidor

**Archivo generado. No se edita a mano**: se regenera con
`python -m mcp_uruguay.documentar`, y `tests/test_docs.py` falla si quedo viejo.


## `clima` — Clima en Salto Grande (INIA)

Clima de la estacion INIA Salto Grande, la misma serie desde 1970.

Sin fechas: la tendencia de la temperatura media anual, en grados Celsius por decada, con su
error estandar. Con `desde` y `hasta` (AAAA-MM-DD, hasta 400 dias): la lluvia y las temperaturas
maxima y minima de cada dia, con la anomalia respecto de la normal 1971-2025. Se pasan las dos
fechas o ninguna.

| parametro | tipo | obligatorio |
|---|---|---|
| `desde` | `string` | no |
| `hasta` | `string` | no |

## `combustible_ancap` — Precios de combustibles de ANCAP

Precio máximo al público, con IVA, de los combustibles de ANCAP fijado por el Poder Ejecutivo.
Sin `producto`, lista los productos disponibles (los nombres hay que pasarlos tal cual).
Con `producto`, la serie mensual; con `anio` y `mes`, ese mes.

| parametro | tipo | obligatorio |
|---|---|---|
| `producto` | `string | null` | no |
| `anio` | `integer | null` | no |
| `mes` | `integer | null` | no |

## `cotizacion` — Cotización del BCU de un día

Cotización oficial del Banco Central del Uruguay, en pesos uruguayos, para una fecha AAAA-MM-DD.

Monedas: USD (dólar billete), UI (Unidad Indexada), ARS (peso argentino billete), BRL (real billete).
Fines de semana y feriados no tienen publicación: con hacia_atras=true se usa el último día hábil
previo (hasta 7 días) y la respuesta dice qué día se usó.

| parametro | tipo | obligatorio |
|---|---|---|
| `moneda` | `string` | si |
| `fecha` | `string` | si |
| `hacia_atras` | `boolean` | no |

## `cotizacion_mensual` — Promedio mensual de una cotización del BCU

Promedio mensual de una cotización del BCU entre dos meses AAAA-MM (hasta 240 meses), con la
cantidad de días publicados de cada mes. El mes en curso viene marcado como incompleto.

| parametro | tipo | obligatorio |
|---|---|---|
| `moneda` | `string` | si |
| `desde` | `string` | si |
| `hasta` | `string` | si |

## `diagnostico` — Que copia de cada fuente se esta usando

Que archivo de cada fuente esta cacheado en esta maquina, de cuando es la copia que se esta
usando, y cuanto pesa. Sirve para saber si un numero viejo viene de una copia vieja.
No sale a la red.

_Sin parametros._

## `estaciones_cercanas` — Estaciones hidrometeorológicas cercanas (Salto Grande)

Estaciones de la red de la Comisión Técnica Mixta de Salto Grande (cuenca del río Uruguay, las dos
orillas) más cercanas a un punto, con las variables que publica cada una y su último dato.

| parametro | tipo | obligatorio |
|---|---|---|
| `lat` | `number` | si |
| `lon` | `number` | si |
| `cantidad` | `integer` | no |

## `geocodificar_direccion` — Geocodificar una dirección de Uruguay (IDE.uy)

Coordenadas (lat, lon) de una dirección o esquina de Uruguay con la API oficial de IDE.uy, con la
calidad del resultado: puerta exacta, puerta aproximada, esquina o centro de calle. Si la API devuelve
otra calle o el centro de la localidad, no se da coordenada. Pasar localidad y departamento mejora
mucho el resultado. Esquinas: '18 de Julio y Ejido' o 'Artigas esq. Solari'.

| parametro | tipo | obligatorio |
|---|---|---|
| `direccion` | `string` | si |
| `localidad` | `string` | no |
| `departamento` | `string` | no |

## `ipc_argentina` — IPC de Argentina (INDEC)

Índice de precios al consumidor nacional de Argentina, base dic-2016 = 100, entre dos meses AAAA-MM.
Devuelve el índice, no la inflación.

| parametro | tipo | obligatorio |
|---|---|---|
| `desde` | `string` | si |
| `hasta` | `string` | si |

## `ipca_brasil` — IPCA de Brasil (IBGE)

IPCA de Brasil como número-índice (base dic-1993 = 100), entre dos meses AAAA-MM.
Devuelve el índice, no la inflación.

| parametro | tipo | obligatorio |
|---|---|---|
| `desde` | `string` | si |
| `hasta` | `string` | si |

## `localidad` — Población y viviendas de una localidad (INE)

Población y viviendas 2023 de una localidad uruguaya, por nombre (sin importar tildes). Si el nombre
existe en más de un departamento, devuelve todas; `departamento` desambigua. Solo con `departamento`,
lista sus localidades de mayor a menor población (hasta `cantidad`).

| parametro | tipo | obligatorio |
|---|---|---|
| `nombre` | `string` | no |
| `departamento` | `string` | no |
| `cantidad` | `integer` | no |

## `nivel_rio` — Nivel del río en una estación de Salto Grande

Altura del río (H) en una estación de la Comisión Técnica Mixta de Salto Grande, resumida por día
(mínimo, media y máximo), con la última lectura y cuánto subió o bajó en el período. Lecturas cada 15
minutos. `estacion` es el nombre o el id (por defecto Salto); `desde`/`hasta` AAAA-MM-DD, hasta 92 días,
por defecto los últimos 14. Para encontrar una estación cerca de un lugar, usar estaciones_cercanas.

| parametro | tipo | obligatorio |
|---|---|---|
| `estacion` | `string` | no |
| `desde` | `string` | no |
| `hasta` | `string` | no |

## `nivel_rio_comparado` — Nivel del río comparado con años anteriores

¿El río está alto o bajo para la época? Media de la altura en los últimos `dias` (1 a 31) hasta
`hasta` (por defecto hoy), comparada con los mismos días de cada año desde 2017, y en qué lugar queda.
Los años con pocas lecturas se excluyen y se listan. La primera consulta puede tardar.

| parametro | tipo | obligatorio |
|---|---|---|
| `estacion` | `string` | no |
| `dias` | `integer` | no |
| `hasta` | `string` | no |

## `pesos_constantes` — Pesos constantes con la Unidad Indexada

Lleva montos en pesos corrientes de distintos meses a pesos de un mes base, deflactando con la
Unidad Indexada promedio del BCU. `montos` es {"AAAA-MM": monto}; `base` es "AAAA-MM".
Sirve para comparar en términos reales pesos de fechas distintas.

| parametro | tipo | obligatorio |
|---|---|---|
| `montos` | `object` | si |
| `base` | `string` | si |

## `recursos_catalogo` — Recursos de un dataset del catálogo de Uruguay

Los archivos vigentes (nombre, URL, formato, fecha) de un dataset de catalogodatos.gub.uy, por su
identificador (por ejemplo `inia-precipitacion-temps-extremas-sg`).

| parametro | tipo | obligatorio |
|---|---|---|
| `dataset` | `string` | si |

## `semana` — Semana ISO de una fecha

Semana ISO 8601 (W1, W2...) de una fecha AAAA-MM-DD, con su lunes y su domingo.

| parametro | tipo | obligatorio |
|---|---|---|
| `fecha` | `string` | si |

## `ubicar_punto` — En qué departamento y localidad cae un punto

Dado un punto (latitud y longitud en grados), en qué departamento y en qué localidad de Uruguay cae,
según los polígonos oficiales del INE, con la población 2023 de la localidad. Si cae en el campo, la
localidad más cercana y a qué distancia. Suma la dirección más cercana de IDE.uy con su distancia.
Combinar con geocodificar_direccion para pasar de una dirección a su departamento.

| parametro | tipo | obligatorio |
|---|---|---|
| `lat` | `number` | si |
| `lon` | `number` | si |

## `validar_documento` — Validar RUT o cédula uruguaya

Valida el dígito verificador de un RUT (12 dígitos) o una cédula de identidad (8 dígitos) de
Uruguay. Acepta puntos, guiones y comas. No consulta a DGI: es validez aritmética.

| parametro | tipo | obligatorio |
|---|---|---|
| `numero` | `string` | si |
| `tipo` | `string` | si |

## `variacion_real` — Variación real descontando la inflación

Cuánto cambió un monto entre dos meses (AAAA-MM) en términos nominales y reales: ventas, precios,
sueldos o alquileres. `indice`: UI para pesos uruguayos (Unidad Indexada del BCU), IPC_AR para pesos
argentinos (INDEC), IPCA_BR para reales (IBGE). Devuelve la variación nominal, la inflación del período,
la variación real y cuánto valdría el monto inicial en moneda del mes final.

| parametro | tipo | obligatorio |
|---|---|---|
| `monto_inicial` | `number` | si |
| `mes_inicial` | `string` | si |
| `monto_final` | `number` | si |
| `mes_final` | `string` | si |
| `indice` | `string` | no |
