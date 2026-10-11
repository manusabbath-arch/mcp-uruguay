# Qué puede responder el servidor, medido — 2026-10-11

Este documento contesta una sola pregunta: **de las 28 herramientas de `mcp-uruguay` 0.11.0, qué
dato sale de cada una hoy, qué no sale, y qué informes se pueden escribir con eso**. No es un
catálogo de deseos: cada fila de §1 y §2 trae la respuesta real de una corrida, no una promesa.

## 0. Cómo se midió

```sh
uv run --quiet --with-editable . python scripts/sonda.py \
  --salida "C:/Users/Usuario/AppData/Local/hermes/cache/scratch/sonda-2026-10-11.json"
```

`scripts/sonda.py` reusa la lista de llamadas de `scripts/humo.py` (una sola lista para las dos
cosas: probar que respondan y guardar **qué** responden) y corre cada herramienta contra la fuente
real a través de un cliente MCP de verdad.

- **Paquete:** `mcp-uruguay` **0.11.0** sobre `uydatos` **0.12.0**.
- **Herramientas publicadas:** 28 (`scripts/humo.py` las llama a todas; `docs/herramientas.md` las
  documenta).
- **Resultado: 28 de 28 OK, ninguna con error y ninguna devolviendo vacío.** 282 segundos de punta a
  punta; las cuatro caras fueron `leyes` (75,5 s), `compras_estado` (61,3 s), `proyectos_parlamento`
  (59,8 s) y `clima` (41,8 s: baja 57 archivos de INIA la primera vez).
- **Caché:** 218 archivos y 67,8 MB en `~/.cache/mcp-uruguay` al terminar (`diagnostico`).

Todo lo que sigue sale de ese JSON, salvo lo que dice de dónde sale.

## 1. Las 28 herramientas: la pregunta que cierra cada una

La columna «respuesta de hoy» es el valor que devolvió la herramienta el 11/10/26 — con el argumento
que usa `humo.py`, que no siempre es el más informativo (por eso, cuando el número es flojo, la fila
dice qué pedir). La columna «la trampa que declara» es la que el módulo tiene escrita en su docstring.

| # | Herramienta | La pregunta que cierra | Respuesta de hoy (11/10/26) | La trampa que declara | s |
|---|---|---|---|---|---|
| 1 | `cotizacion` | ¿cuánto valía el dólar un día? | USD 09/10/2026 = **40,184** | un fin de semana no tiene cotización: devuelve `null` salvo `hacia_atras`, y no salta más de una semana | 0,6 |
| 2 | `cotizacion_mensual` | el promedio de un mes | USD ago-2026 **40,25455** (20 días), sep-2026 **40,207455** (22) | el mes en curso es parcial y lo dice | 0,3 |
| 3 | `pesos_constantes` | llevar montos a pesos de un mes base | $1.000 de ene-2025 = **$1.073,57** de ago-2026 | usa la UI promedio del mes; es una decisión de análisis, no una lectura | 2,5 |
| 4 | `variacion_real` | cuánto cambió un monto descontando la inflación | 1.000→1.100 entre ene-25 y ago-26: nominal **+10,0%**, inflación **7,3574%**, real **+2,4615%** | con la UI, el mes en curso usa los días publicados | 0,1 |
| 5 | `ipc_argentina` | el IPC nacional de Argentina | ene-2026 **10.413,0309** → mar-2026 **11.077,0608** | **es un índice, no una inflación**; la API sigue sirviendo bases discontinuadas | 0,4 |
| 6 | `ipca_brasil` | el IPCA de Brasil | ene-2026 **7.427,72** → mar-2026 **7.545,53** | la tabla SIDRA trae varias variables: una variación leída como índice no da error | 1,0 |
| 7 | `combustible_ancap` | el precio de cada combustible | **22 productos** (sin argumento los lista) | es el **máximo al público con IVA**; el ex planta es **otro** dataset y otro número | 1,5 |
| 8 | `ventas_combustible` | cuánto se vendió y de qué | GAS OIL mercado INTERNO 2026: **719,4791** miles de m³ en **8 meses** (faltan sep-dic) | la columna `Unidad` **mezcla miles de m³ con toneladas**; la ventana tiene huecos (2024 sin octubre, 2025 sin ago-oct) | 0,7 |
| 9 | `paridad_combustibles` | ¿ANCAP vende arriba o abajo de importar? | ago-2026: Súper 95 **+2,5%**; Premium 97 **+1,9%**; **Gasoil 50-S −12,4%**; Gasoil 10-S −2,4% | se compara **sin impuestos contra sin impuestos**; el PPI de una ventana rige el mes siguiente; el GLP no se compara ($/L contra $/kg) | 3,2 |
| 10 | `clima` | lluvia y temperatura de Salto desde 1970 | **20.526 días** (1970-07-01 a 2026-09-10); tendencia **+0,267 °C/década** (máx, EE 0,042) | el día va de 9 a 9; un vacío es **nulo, no cero**; la fuente se actualiza cada quincena | 41,8 |
| 11 | `nivel_rio` | la altura del río por día | Salto: 30/09/2026 media **9,129 m** (96 lecturas) | declara la cobertura; una estación sin lecturas no es un cero | 2,2 |
| 12 | `nivel_rio_comparado` | ¿está alto o bajo para la época? | 05-11/10/2026: media **11,374 m** — **el más alto de los últimos 10 años** para esos días (lugar **1 de 10**) | los años sin la ventana completa se excluyen y se declaran | 2,6 |
| 13 | `estaciones_cercanas` | qué estaciones hay cerca | 5 estaciones en 15 km de Salto; la más cercana **a 1,7 km**, último dato 11/10 18:15 | buscar por el nombre del campo SOAP da lista vacía sin error | 0,0 |
| 14 | `geocodificar_direccion` | coordenadas de una dirección | «Uruguay 1000» (Salto) → **calidad `puerta_aproximada`**, devolvió 1001 | ante lo que no encuentra devuelve el centro de la localidad, una puerta vecina u otra calle, **sin error** | 1,0 |
| 15 | `ubicar_punto` | en qué departamento y localidad cae un punto | −31,39/−57,96 → **SALTO**, adentro de la localidad, población 2023 **114.043** | sin `srsName=EPSG:4326` la capa llega en metros y ningún punto cae adentro | 13,7 |
| 16 | `localidad` | población y viviendas 2023 | SALTO: **114.043 / 41.536** | el año sale del nombre del campo; el «centro aproximado» es el del rectángulo, no un centroide | 0,0 |
| 17 | `resultados_electorales` | votos y participación | nacionales-2024: **7.234** mesas comunes + **118** de observados; **2.727.120** habilitados; **89,61%**; FA **1.071.826** (43,86%) | los observados se escrutan en **mesas especiales sin habilitados ni localidad**: sumar solo las comunes deja afuera **34.422** votos | 5,7 |
| 18 | `compras_estado` | cuánto adjudicó el Estado | 2025: **140.128** adjudicaciones, **333.575** ítems, **$247.035.812.724,6** | el importe es **precio unitario** (222.616 ítems con cantidad ≠ 1); llamados y anulaciones mezclados; **un solo ítem puede dominar el total** (acá, el 28,7%) | 61,3 |
| 19 | `asistencia_parlamentaria` | asistencia por legislatura | Senado 50: **111 personas**, solo **56** con el mínimo de 10 citaciones | hay **3 a 4 veces más personas que bancas** (suplentes) y **no hay identificador de persona** (homónimos) | 2,3 |
| 20 | `pedidos_de_informes` | cuántos pedidos contesta cada ministerio | 17/02/2025–08/10/2026: **2.532** pedidos, **1.726** contestados, **74,2%** de los que ya cumplieron plazo | las respuestas llegan tarde: hay que comparar la **misma cohorte** | 0,3 |
| 21 | `leyes` | las leyes promulgadas desde 1985 | «presupuesto» → **11**, entre ellas la **20.446** (16/12/2025) | 4.799 filas son 4.796 leyes: 2 duplicadas y una «ley 0» | 75,5 |
| 22 | `proyectos_parlamento` | los proyectos entrados | «agua» → **103** | 311 proyectos aparecen en dos legislaturas: 8.880 filas son 8.569 proyectos | 59,8 |
| 23 | `validar_documento` | el dígito verificador de un RUT o una cédula | `1.234.567-2` → válido | Excel convierte el RUT en float y se come el cero inicial | 2,1 |
| 24 | `semana` | la semana ISO de una fecha | 2026-10-11 → **2026-W41** (W41/53) | el 01/01/2027 es la 2026-W53 | 0,0 |
| 25 | `buscar_indicador_social` | buscar entre los indicadores del MIDES | «pobreza departamento» → **2 de 1.264** | los nombres salen del título sin tildes; la copia del catálogo abierto quedó en 2019 | 0,0 |
| 26 | `indicador_social` | una ficha con unidad, cálculo y fuente | desempleo por quintil: unidad «Por cien», fuente INE-ECH, ficha 2006-2023 | trae filas «Total» mezcladas, `parcial: true` y mapas con un solo año | 1,1 |
| 27 | `recursos_catalogo` | los archivos vigentes de un dataset | `inia-precipitacion-temps-extremas-sg`: metadatos + series | las URLs cambian cuando el organismo resube el archivo | 0,7 |
| 28 | `diagnostico` | de cuándo es cada copia en caché | **218 archivos, 67,8 MB** (ancap.csv 851.835 B) | es la caché de la máquina: una fuente que no aparece nunca se pidió | 0,5 |

## 2. Lo que ninguna herramienta hace sola: los cruces

Acá está el valor: ninguna herramienta cruza sus datos con los de otra, así que cada fila de esta
tabla es un informe que **hoy no existe** y que se arma con dos o tres llamadas.

| Cruce | Herramientas | La pregunta | Medido el 11/10/26 |
|---|---|---|---|
| Precio real del combustible | `combustible_ancap` + `pesos_constantes` | ¿el gasoil subió de verdad desde 2022? | Gasoil 50-S 2022-02 = 52,94 $/l = **67,50** en pesos de jul-2026; jul-2026 = 58,68 → **+10,8% nominal y −13,1% real**. Serie de 56 meses con **32 con precio y 24 `S/C`** |
| Precio contra paridad y contra volumen | `paridad_combustibles` + `ventas_combustible` | ¿ANCAP vende abajo de importar mientras el volumen cae? | Gasoil 50-S: ex planta **34,92** contra PPI **39,85** = **−12,4%** (promedio 12 meses −3,3%). Volumen INTERNO: 2025 **835,534** miles de m³ en **9 meses** contra 2024 **993,409** en **11** |
| Precio ex planta contra precio al público | `paridad_combustibles` (desglose) + `combustible_ancap` | ¿cuánto ponen los impuestos y los márgenes? | Jul-2026 al público **58,68** $/l contra ago-2026 ex planta **34,92** $/l: **no se desglosa hasta el final** en estos dos datasets |
| Votantes contra habitantes | `resultados_electorales` + `localidad` | ¿cuánta gente hay por habilitado a votar? | Salto: **104.873** habilitados (2024) sobre **114.043** habitantes (2023) = **0,92**; participación **90,67%** contra **89,61%** del país |
| Un punto en el territorio | `ubicar_punto` + `localidad` | ¿en qué localidad cae esto y cuánta gente vive ahí? | −31,39/−57,96 → **SALTO**, adentro, **114.043** habitantes; la dirección más cercana, «25 DE AGOSTO 139», a **0,014 km** |
| El río contra la lluvia | `nivel_rio_comparado` + `clima` | ¿está alto y con qué lluvia detrás? | 05-11/10/2026: **11,374 m**, el más alto de los últimos 10 años. `clima` con esas fechas devuelve `dias: []` porque **INIA llega al 10/09/2026**: la ventana pedida está más allá del último dato |
| El Estado que compra | `compras_estado` + `cotizacion_mensual` | ¿cuánto adjudicó cada organismo, con las monedas convertidas? | 2025: **140.128** adjudicaciones y **$247.035.812.724,6**; UTE **$88.114.265.894,61** (743), ANCAP **$82.312.342.144,85** (1.324); **177.623.636,64 sin moneda** |
| Qué responde el Estado | `pedidos_de_informes` + `leyes`/`proyectos_parlamento` | ¿los ministerios contestan lo que el Parlamento les pide? | **74,2%** contestado sobre los que cumplieron plazo; **MSP 78,8%** (431 pedidos), **MEC 64,8%** (253), **MTOP 29,0%** (137) |
| La inflación de los vecinos | `ipc_argentina` + `ipca_brasil` + `variacion_real` | ¿cuánto se encareció cada lado de la frontera? | ene→mar 2026: IPC argentino **+6,38%**, IPCA **+1,59%** en los mismos meses (es un índice: la variación sale de dividir, no de restar) |

## 3. Lo que el servidor **no** puede responder todavía

### 3.1 Dos módulos de la librería no tienen herramienta

```sh
cd /c/Users/Usuario/mcp-uruguay
for m in $(ls ../uy-datos-abiertos/src/uydatos/*.py | xargs -n1 basename | sed 's/\.py$//' \
          | grep -v -E "^(red|procedencia|__init__|__main__|hojas|py)$"); do
  grep -q "\b$m\b" src/mcp_uruguay/herramientas.py || echo "SIN HERRAMIENTA: $m"
done
```

Salida esperada (medida): `SIN HERRAMIENTA: inumet` y `SIN HERRAMIENTA: mides`.

- **`inumet`**: observaciones horarias de **7 estaciones nacionales** (temperatura, precipitación,
  humedad, viento, presión, insolación) desde 2020. Hoy el servidor tiene clima de **una** estación
  (INIA Salto Grande): con INUMET, «¿qué pasó en Artigas o en Mercedes?» tendría respuesta. El módulo
  **ya está publicado** en `uydatos` 0.12.0, así que falta la herramienta, no una Release.
- **`mides`**: los 1.869 indicadores del catálogo abierto, en **cp1252**. **No conviene** agregarlo, y
  el motivo está medido: `indicador_social` ya expone los indicadores del Observatorio Social **de la
  página viva**, que llega a 2024, mientras la copia del catálogo abierto quedó en 2019. Agregarlo
  sería sumar una copia vieja de lo que ya se responde.

### 3.2 Fuentes medidas y descartadas (no reabrir sin motivo)

| Fuente | Estado medido | Disparador |
|---|---|---|
| ECH del INE | los **25** recursos de sus 7 datasets devuelven la portada del sitio nuevo: **link rot**, no un certificado roto (10/10/26) | que alguno vuelva a entregar un archivo |
| SIPC precios | **1.004 MB (2026)** y **2.025 MB (2025)** por año | una pregunta que necesite **más de un año** |
| Sanciones de Defensa del Consumidor | el archivo trae `razon_social` y `rut` de terceros | decisión del dueño, con asesor (Ley 18.331) |
| OPP (presupuesto) | 19 datasets, todos CSV puro, **un lector por dataset** porque las columnas no coinciden | la próxima tanda de fuentes |
| RUPE (proveedores), credencial cívica de candidatos, edad de diputados | **datos personales** | decisión del dueño, con asesor |

### 3.3 Una diferencia que apareció y no está explicada

El documento del 10/10/26 midió **110.063 adjudicaciones y 333.595 ítems** en el archivo de 2025; la
herramienta devuelve hoy **140.128 adjudicaciones y 333.575 ítems** —los ítems coinciden casi
exactos, las adjudicaciones no—, y el mayor ítem de 2025 pasó de ser **el 53%** del total en ese
documento a **el 28,7%** acá. No se midió por qué. **Hasta que se explique, cualquier total de
compras de 2025 se cita con esa diferencia a la vista**, y el aviso de «un ítem domina el total» se
lee con el número que devuelve la herramienta, no con el del documento.

## 4. Informes que salen de esto, ordenados

El orden es por **datos completos, trampas pocas y medibles, y riesgo de datos personales bajo** —
no por lo llamativo.

| # | Informe | Con qué | Trampas | PII |
|---|---|---|---|---|
| 1 | **El gasoil en pesos constantes, con la paridad y el volumen detrás** — ya escrito: `docs/2026-10-11-combustible-en-pesos-constantes.md` | 4 herramientas | la columna `Unidad` mezcla unidades; 24 de 56 meses son `S/C`; el PPI de una ventana rige el mes siguiente | ninguna |
| 2 | **El río más alto en diez años** — qué dice la serie de Salto Grande de octubre de 2026, y con qué lluvia | `nivel_rio_comparado`, `nivel_rio`, `clima`, `estaciones_cercanas` | INIA llega al 10/09; los años sin ventana completa se excluyen | ninguna |
| 3 | **Qué compra el Estado, y por qué el total no es la suma de los importes** | `compras_estado` (+ `cotizacion_mensual`) | precio unitario, monedas mezcladas, llamados y anulaciones, el ítem dominante, y la diferencia de §3.3 | nombres de proveedores: agregar por organismo y rubro; **no** exponer personas físicas |
| 4 | **El gasoil de ANCAP contra lo que costaría importarlo** — con el desglose desde el FOB | `paridad_combustibles` | sin impuestos contra sin impuestos; una ventana del PPI imposible (2022-12-26 a 2022-12-25) | ninguna |
| 5 | **Votar en Salto: 104.873 habilitados sobre 114.043 habitantes** — participación y votos contra población | `resultados_electorales`, `localidad` | los observados están en mesas sin habilitados ni localidad; los nombres cambian entre elecciones | **no** leer la integración de hojas (credencial cívica) |
| 6 | **Qué le contestan los ministerios al Parlamento** | `pedidos_de_informes`, `leyes`, `proyectos_parlamento` | comparar la misma cohorte; los recursos de un dataset comparten URL final | ninguna |
| 7 | **El clima de Salto en 56 años: +0,27 °C por década** | `clima` | el día va de 9 a 9; los años incompletos se excluyen de la tendencia | ninguna |

## 5. Límites y lo que no se publica

- **Ninguna herramienta escribe.** Todo el servidor es de solo lectura, y así lo declara al cliente.
- **Los datos personales no se exponen acá.** La integración de hojas de la Corte Electoral trae la
  **credencial cívica** de 217.932 candidatos, el RUPE trae el nombre, el RUT y el domicilio de
  personas físicas que le venden al Estado, y la nómina de diputados trae su **edad**. Nada de eso
  entra en un informe de este repositorio, ni de ejemplo.
- **Neutralidad.** El servidor devuelve datos; no opina sobre un resultado electoral, un ministerio ni
  una empresa. Las notas explican qué se sumó y qué no.
- **Un resultado vacío no es un resultado.** `clima` con una ventana posterior al 10/09/2026 devuelve
  `dias: []` con su motivo: una lista vacía se declara, no se muestra como si fuera el dato.
- **Este documento no publica datos**, publica código y mediciones: los archivos de cada fuente tienen
  su propia licencia y no se versionan.

## Para reproducir todo

```sh
uv run --quiet --with-editable . python scripts/sonda.py --salida sonda.json   # 28 herramientas, ~5 min la primera vez
uv run --quiet --with pytest --with-editable . pytest -q                       # sin red
uvx ruff check src tests scripts && uvx ruff format --check src tests scripts
```
