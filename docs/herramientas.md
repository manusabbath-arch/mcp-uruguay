# Las herramientas del servidor

**Archivo generado. No se edita a mano**: se regenera con
`python -m mcp_uruguay.documentar`, y `tests/test_docs.py` falla si quedo viejo.


## `asistencia_parlamentaria` — Asistencia de legisladores (Parlamento)

Asistencia a sesiones del Senado o de Diputados en una legislatura (46 a 50, la actual): menor y mayor
asistencia entre quienes tuvieron al menos `minimo_citaciones` (para no comparar suplentes con dos citaciones),
y las filas que contienen `nombre`. Avisa de nombres repetidos, que pueden ser homónimos.

| parametro | tipo | obligatorio |
|---|---|---|
| `camara` | `string` | si |
| `legislatura` | `integer` | no |
| `nombre` | `string` | no |
| `minimo_citaciones` | `integer` | no |
| `cantidad` | `integer` | no |

## `buscar_indicador_social` — Buscar indicadores sociales del MIDES

Busca entre los ~1.260 indicadores sociales del Observatorio Social del MIDES (pobreza, empleo,
desempleo, educación, vivienda, salud, ingresos, cuidados, juventud, personas mayores, censos...) por
palabras, sin tildes. Devuelve los nombres para pasar a indicador_social. Para un departamento,
incluir la palabra 'departamento' (por ejemplo 'pobreza departamento').

| parametro | tipo | obligatorio |
|---|---|---|
| `texto` | `string` | si |
| `cantidad` | `integer` | no |

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

## `compras_estado` — Compras del Estado (ARCE)

Cuánto adjudicó el Estado uruguayo en un año (2002 en adelante), en pesos, con los organismos que más
compraron y los mayores ítems. `organismo` filtra por comprador (por ejemplo «Intendencia de Montevideo»);
`buscar` filtra los ítems por texto (por ejemplo «ambulancia»). Las monedas se convierten con la
cotización del día. Avisa cuando un solo ítem domina el total: hay registros con cantidad × precio
imposibles. La primera consulta de un año baja unos 30 MB y tarda.

| parametro | tipo | obligatorio |
|---|---|---|
| `anio` | `integer` | si |
| `organismo` | `string` | no |
| `buscar` | `string` | no |
| `cantidad` | `integer` | no |

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

## `indicador_social` — Un indicador social del MIDES, con su ficha

Lee un indicador del Observatorio Social del MIDES (el nombre sale de buscar_indicador_social):
título, unidad, forma de cálculo, fuente del dato (casi siempre la Encuesta Continua de Hogares del
INE) y la tabla por dimensión y período, con datos hasta 2023-2024. `filtro` deja solo las filas con
esos valores de dimensión, separados por coma (por ejemplo 'Salto' o 'Mujeres,Pobre'). Leer los
`avisos`: filas de total mezcladas, mapas que muestran un solo año (`parcial`), y una ficha que no
coincide con la tabla.

| parametro | tipo | obligatorio |
|---|---|---|
| `indicador` | `string` | si |
| `filtro` | `string` | no |

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

## `leyes` — Leyes promulgadas (Parlamento)

Leyes promulgadas desde 1985: por texto del título (sin importar tildes), por rango de fechas AAAA-MM-DD o
por número. Devuelve el enlace al texto actualizado en IMPO.

| parametro | tipo | obligatorio |
|---|---|---|
| `buscar` | `string` | no |
| `desde` | `string` | no |
| `hasta` | `string` | no |
| `numero` | `integer | null` | no |
| `cantidad` | `integer` | no |

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

## `paridad_combustibles` — Combustibles: ANCAP contra el precio de paridad de importación

¿ANCAP vende el combustible por encima o por debajo de lo que costaría importarlo? Compara el precio
ex planta de ANCAP con el precio de paridad de importación (PPI) que calcula URSEA, los dos sin
impuestos, en $/litro, mes a mes desde 2022. Sin `producto`: el último mes y el promedio de 12 meses de
Gasolina Super 95, Gasolina Premium 97, Gasoil 50-S y Gasoil 10-S. Con `producto`: la serie (`desde` y
`hasta` en AAAA-MM) y el desglose del último PPI desde el precio internacional (FOB) hasta los
impuestos. Leer `metodo`: la comparación es una construcción de este servidor, no una cifra oficial.

| parametro | tipo | obligatorio |
|---|---|---|
| `producto` | `string` | no |
| `desde` | `string` | no |
| `hasta` | `string` | no |

## `pesos_constantes` — Pesos constantes con la Unidad Indexada

Lleva montos en pesos corrientes de distintos meses a pesos de un mes base, deflactando con la
Unidad Indexada promedio del BCU. `montos` es {"AAAA-MM": monto}; `base` es "AAAA-MM".
Sirve para comparar en términos reales pesos de fechas distintas.

| parametro | tipo | obligatorio |
|---|---|---|
| `montos` | `object` | si |
| `base` | `string` | si |

## `proyectos_parlamento` — Proyectos entrados al Parlamento

Proyectos entrados al Parlamento desde 1985 (legislaturas 42 a 50), por texto del título, legislatura o
tipo («ley», «resolución», «minuta», «declaración»). Un proyecto que aparece en dos legislaturas cuenta una
vez. La primera búsqueda sin legislatura baja nueve archivos.

| parametro | tipo | obligatorio |
|---|---|---|
| `buscar` | `string` | no |
| `legislatura` | `integer | null` | no |
| `tipo` | `string` | no |
| `cantidad` | `integer` | no |

## `recursos_catalogo` — Recursos de un dataset del catálogo de Uruguay

Los archivos vigentes (nombre, URL, formato, fecha) de un dataset de catalogodatos.gub.uy, por su
identificador (por ejemplo `inia-precipitacion-temps-extremas-sg`).

| parametro | tipo | obligatorio |
|---|---|---|
| `dataset` | `string` | si |

## `resultados_electorales` — Resultados electorales (Corte Electoral)

Resultados de una elección uruguaya, del país o de un departamento: habilitados, emitidos,
participación, votos por partido (nacionales y departamentales) y por opción (candidatos del balotaje,
plebiscitos). Sale de los datos por mesa de la Corte Electoral e incluye los votos observados, que se
escrutan en mesas especiales sin localidad. Los porcentajes son sobre los votos emitidos.

| parametro | tipo | obligatorio |
|---|---|---|
| `eleccion` | `string` | si |
| `departamento` | `string` | no |

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

## `ventas_combustible` — Ventas de combustibles de ANCAP

Cantidad vendida por ANCAP de cada combustible, por mes (volúmenes, no precios; para precios usar
combustible_ancap). Sin `linea`, lista los productos (GAS OIL, GASOLINAS, JET A1, SUPERGAS...) con su
familia, su unidad y los mercados, y los meses que la fuente no publicó. Con `linea`, la serie
mensual y el total de cada año con cuántos meses lo forman: no comparar años con distinta cantidad
de meses. `mercado`: INTERNO, Bunker, UTE, ZONA FRANCA o Exportaciones (vacío = todos). `desde` y
`hasta` en AAAA-MM. Unidades: miles de m3, salvo el petcoke en toneladas.

| parametro | tipo | obligatorio |
|---|---|---|
| `linea` | `string` | no |
| `mercado` | `string` | no |
| `desde` | `string` | no |
| `hasta` | `string` | no |
