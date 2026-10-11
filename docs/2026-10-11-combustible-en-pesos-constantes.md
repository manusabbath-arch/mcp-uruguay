# El gasoil en pesos constantes, con la paridad de importación y el volumen vendido detrás

**Fecha del informe:** 2026-10-11
**Paquete medido:** `mcp-uruguay` 0.11.0 sobre `uydatos` 0.12.0 (el publicado en PyPI, no un árbol local).

---

## 1. Qué pregunta responde y por qué nadie la responde hoy

La pregunta es: **¿cuánto costó de verdad el gasoil en Uruguay desde 2022 —expresado en pesos de un
mismo mes— y cómo se ubica ese precio contra lo que costaría importarlo, con el volumen vendido
detrás?**

No la responde un solo artefacto público porque hay que juntar cuatro piezas que viven en datasets
distintos, cada una con su propia trampa:

- El **precio máximo al público** de ANCAP (`ancap-precio-combustible-pe`): mensual, en pesos
  corrientes, con meses marcados `S/C` (sin cotización) que hay que dejar como huecos.
- El **precio ex planta** de ANCAP: **otro** dataset, el mismo producto sin fletes, márgenes ni
  impuestos. Si se mezclan, el número cambia de significado.
- El **precio de paridad de importación (PPI)** de URSEA: se publica por ventana, sin impuestos, y
  la ventana que cierra el 25 rige el mes siguiente.
- La **cantidad vendida** de ANCAP (`ancap-cantidad-ventas-combustibles`): una ventana móvil de cinco
  años con huecos, y una columna `Unidad` que mezcla `Miles de m3` con `Toneladas`.

Ninguno de esos archivos trae el precio expresado en pesos constantes, ni cruza el precio con el PPI,
ni con el volumen. El interés por este cruce viene de **una investigación previa de fuentes externas,
privada**; acá se publica solo la medición.

---

## 2. Cómo se midió

Todo se midió llamando a las funciones del paquete publicado, desde un entorno aislado que instala
exactamente lo que recibe un usuario:

```sh
uv run --isolated --no-project --with mcp-uruguay python -c "from mcp_uruguay.herramientas import ..."
```

- **Herramientas usadas:** `combustible_ancap`, `pesos_constantes`, `variacion_real`,
  `ventas_combustible`, `paridad_combustibles`.
- **Versión:** `mcp-uruguay` 0.11.0 (PyPI), que depende de `uydatos>=0.12,<0.13` (resuelto a 0.12.0).
- **Fecha de medición:** 2026-10-11.
- **Copias en caché usadas (campo `bajado` de cada herramienta):**
  - ANCAP precios y ventas, y URSEA/paridad: `2026-10-11T18:48`.
  - BCU (Unidad Indexada, para deflactar): `2026-10-10T00:16`.

Ningún número de este informe está re-tipeado de memoria: cada uno sale de la salida de esas
funciones, citada abajo con su `fuente` y su `bajado`.

---

## 3. La serie mensual nominal

**Precio máximo al público, con IVA, en $/litro, fijado por el Poder Ejecutivo.** `S/C` = sin
cotización: un nulo, no un cero, y **no se interpola**. Los dos gasoiles del mercado interno son
`GASOIL 50-S *` y `GASOIL 10-S *` (los nombres se pasan tal cual los devuelve la herramienta).

- `fuente`: ANCAP, dataset `ancap-precio-combustible-pe` de catalogodatos.gub.uy.
- `bajado`: 2026-10-11T18:48.

| mes | GASOIL 50-S ($/l) | GASOIL 10-S ($/l) |
|---|---|---|
| 2022-01 | S/C | S/C |
| 2022-02 | 52,94 | 65,98 |
| 2022-03 | 53,99 | 67,30 |
| 2022-04 | 58,99 | 72,30 |
| 2022-05 | 61,99 | 73,80 |
| 2022-06 | 64,99 | 75,30 |
| 2022-07 | S/C | S/C |
| 2022-08 | S/C | S/C |
| 2022-09 | S/C | S/C |
| 2022-10 | 64,99 | S/C |
| 2022-11 | S/C | S/C |
| 2022-12 | S/C | S/C |
| 2023-01 | 58,99 | 69,30 |
| 2023-02 | S/C | S/C |
| 2023-03 | 56,99 | 67,30 |
| 2023-04 | S/C | S/C |
| 2023-05 | S/C | S/C |
| 2023-06 | 52,99 | 63,30 |
| 2023-07 | S/C | S/C |
| 2023-08 | 52,82 | 63,10 |
| 2023-09 | 55,99 | 66,30 |
| 2023-10 | 59,39 | 68,10 |
| 2023-11 | S/C | S/C |
| 2023-12 | 57,39 | 65,10 |
| 2024-01 | 55,39 | 61,10 |
| 2024-02 | 53,89 | S/C |
| 2024-03 | 54,89 | 62,10 |
| 2024-04 | S/C | S/C |
| 2024-05 | 53,92 | S/C |
| 2024-06 | 52,42 | 60,60 |
| 2024-07 | S/C | S/C |
| 2024-08 | S/C | S/C |
| 2024-09 | S/C | S/C |
| 2024-10 | 49,92 | 58,10 |
| 2024-11 | S/C | S/C |
| 2024-12 | S/C | S/C |
| 2025-01 | S/C | S/C |
| 2025-02 | 50,92 | S/C |
| 2025-03 | S/C | S/C |
| 2025-04 | 50,17 | S/C |
| 2025-05 | 49,42 | 57,23 |
| 2025-06 | 47,03 | 54,03 |
| 2025-07 | 48,08 | 55,08 |
| 2025-08 | S/C | S/C |
| 2025-09 | 50,14 | 57,14 |
| 2025-10 | S/C | S/C |
| 2025-11 | 49,77 | 56,77 |
| 2025-12 | S/C | S/C |
| 2026-01 | 48,90 | 55,90 |
| 2026-02 | S/C | S/C |
| 2026-03 | 47,32 | 54,32 |
| 2026-04 | 50,63 | 58,13 |
| 2026-05 | 57,72 | 66,27 |
| 2026-06 | 61,76 | 70,91 |
| 2026-07 | 58,68 | 67,33 |
| 2026-08 | S/C | S/C |

De los 56 meses de la ventana, GASOIL 50-S publica precio en **32** y GASOIL 10-S en **27**. Los
restantes son `S/C` y quedan como huecos: no se rellenan.

**No confundir este precio con el precio ex planta.** Este es el **máximo al público con IVA**; el ex
planta (sección 6) es otro dataset y otro número.

### 3.1 El archivo crudo detrás de la tabla: publicaciones apiladas, columnas invertidas y dos meses que se contradicen

Medido el 11/10/26 sobre `~/.cache/mcp-uruguay/ancap.csv` (851.835 bytes), **no** sobre la salida de la
herramienta:

- **25.364 filas, 22 productos.** De ellas, **1.172** son de `GASOIL 50-S *`.
- **El archivo apila publicaciones**: cada par (año, mes) de ese producto aparece **29 veces**. No es
  una serie mensual, es el log de todo lo publicado; el lector (`uydatos.ancap.serie_mensual`)
  deduplica a una fila por (producto, año, mes).
- **Las columnas vienen invertidas**: el encabezado dice `Año;Mes;Producto;Unidad;Valor`, pero la
  columna `Unidad` trae el precio (`52,94`) y la que se llama `Valor` trae la unidad (`$/lt`). El
  lector lo sabe y lo corrige; quien lea el CSV a mano, no.
- **572 de esas 1.172 filas traen `S/C`** (sin cotización) y **600 un precio**. `S/C` es un nulo, no un
  cero.
- **2 de los 56 meses tienen publicaciones que se contradicen**: `2022-10` aparece como `64,99` en una
  publicación y como `S/C` en otra; `2023-08`, como `52,82` y como `S/C`. Son los dos únicos. La regla
  de desempate está declarada en el lector: **el valor manda sobre el `S/C`** (un mes que alguna vez
  tuvo precio no se pierde porque una publicación posterior diga `S/C`) y, entre dos precios distintos,
  gana **el de la publicación más reciente**. Por eso los dos aparecen con precio en la tabla de §3 — y
  por eso hay que saber que el número depende de esa regla y no de una elección de este informe.

Para reproducirlo:

```sh
uv run --quiet python -c "
import csv, collections
filas = [{k.lstrip('\ufeff'): v for k, v in f.items()} for f in
         csv.DictReader(open(r'C:\Users\Usuario\.cache\mcp-uruguay\ancap.csv', encoding='utf-8'), delimiter=';')]
g = [f for f in filas if f['Producto'].strip() == 'GASOIL 50-S *']
meses = collections.defaultdict(set)
for f in g: meses[(f['Año'], f['Mes'])].add(f['Unidad'].strip())   # 'Unidad' trae el precio: invertidas
print(len(filas), 'filas |', len(g), 'de GASOIL 50-S * |', sum(len(v) > 1 for v in meses.values()), 'meses contradictorios')
"
```

Salida esperada: `25364 filas | 1172 de GASOIL 50-S * | 2 meses contradictorios`.

---

## 4. La misma serie en pesos constantes (base julio 2026)

Se deflactó con la **Unidad Indexada promedio del BCU** (código 9800). **Mes base: 2026-07**, el
último mes con precio publicado en los dos gasoiles (2026-08 es `S/C`). Un peso de cada mes se llevó
a pesos de julio de 2026; solo se pueden convertir los meses con precio, así que los `S/C` siguen
siendo huecos.

- `fuente`: Banco Central del Uruguay, web service de cotizaciones (cotizaciones.bcu.gub.uy) (Unidad
  Indexada, código 9800).
- `bajado`: 2026-10-10T00:16.
- `metodo`: monto × UI(base) / UI(mes), con la UI promedio de cada mes.

| mes | GASOIL 50-S ($ de 2026-07) | GASOIL 10-S ($ de 2026-07) | UI promedio del mes |
|---|---|---|---|
| 2022-01 | — | — | — |
| 2022-02 | 67,50 | 84,12 | 5,189957 |
| 2022-03 | 67,71 | 84,40 | 5,276529 |
| 2022-04 | 73,00 | 89,47 | 5,347160 |
| 2022-05 | 76,04 | 90,52 | 5,394790 |
| 2022-06 | 79,33 | 91,92 | 5,420893 |
| 2022-07 | — | — | — |
| 2022-08 | — | — | — |
| 2022-09 | — | — | — |
| 2022-10 | 77,16 | — | 5,573526 |
| 2022-11 | — | — | — |
| 2022-12 | — | — | — |
| 2023-01 | 69,77 | 81,97 | 5,594642 |
| 2023-02 | — | — | — |
| 2023-03 | 66,26 | 78,25 | 5,691461 |
| 2023-04 | — | — | — |
| 2023-05 | — | — | — |
| 2023-06 | 60,22 | 71,94 | 5,822810 |
| 2023-07 | — | — | — |
| 2023-08 | 60,38 | 72,13 | 5,788755 |
| 2023-09 | 64,11 | 75,92 | 5,778977 |
| 2023-10 | 67,78 | 77,72 | 5,797765 |
| 2023-11 | — | — | — |
| 2023-12 | 64,76 | 73,46 | 5,863868 |
| 2024-01 | 62,39 | 68,83 | 5,874332 |
| 2024-02 | 60,42 | — | 5,902414 |
| 2024-03 | 60,81 | 68,80 | 5,973110 |
| 2024-04 | — | — | — |
| 2024-05 | 59,33 | — | 6,013271 |
| 2024-06 | 57,38 | 66,33 | 6,045603 |
| 2024-07 | — | — | — |
| 2024-08 | — | — | — |
| 2024-09 | — | — | — |
| 2024-10 | 54,01 | 62,86 | 6,115655 |
| 2024-11 | — | — | — |
| 2024-12 | — | — | — |
| 2025-01 | — | — | — |
| 2025-02 | 54,20 | — | 6,217179 |
| 2025-03 | — | — | — |
| 2025-04 | 52,55 | — | 6,317290 |
| 2025-05 | 51,52 | 59,66 | 6,347719 |
| 2025-06 | 48,91 | 56,19 | 6,363307 |
| 2025-07 | 49,98 | 57,25 | 6,365832 |
| 2025-08 | — | — | — |
| 2025-09 | 52,13 | 59,41 | 6,364777 |
| 2025-10 | — | — | — |
| 2025-11 | 51,46 | 58,70 | 6,399247 |
| 2025-12 | — | — | — |
| 2026-01 | 50,38 | 57,59 | 6,422687 |
| 2026-02 | — | — | — |
| 2026-03 | 48,28 | 55,42 | 6,485787 |
| 2026-04 | 51,46 | 59,08 | 6,510263 |
| 2026-05 | 58,40 | 67,05 | 6,540168 |
| 2026-06 | 62,12 | 71,32 | 6,578993 |
| 2026-07 | 58,68 | 67,33 | 6,617135 |
| 2026-08 | — | — | — |

**Qué se ve:** el GASOIL 50-S nominal de 2022-02 (52,94) equivale a **67,50 pesos de julio de 2026**;
el de 2026-07 es 58,68, así que en términos reales bajó. El pico de la ventana es 2022-06 con 79,33
(real) y el piso con precio es 2025-06 con 48,91 (real). En los mismos meses el nominal subió y bajó
de forma más ruidosa que el real, que es justamente el punto de deflactar.

---

## 5. El volumen vendido, por año y declarando cuántos meses lo forman

Línea `GAS OIL` (familia BLANCOS), en **miles de m³**. La herramienta devuelve el total de cada año
con **cuántos meses lo forman**: un año de 8 o 9 meses no se compara contra uno de 12. Por eso el
total y el promedio por mes van juntos.

- `fuente`: ANCAP, dataset `ancap-cantidad-ventas-combustibles` de catalogodatos.gub.uy.
- `bajado`: 2026-10-11T18:48.

**Todos los mercados** (INTERNO, UTE, Bunker, Zona Franca):

| año | total (miles de m³) | meses | promedio por mes | meses que faltan |
|---|---|---|---|---|
| 2022 | 1.432,861 | 12 | 119,405 | — |
| 2023 | 1.356,162 | 12 | 113,013 | — |
| 2024 | 1.132,788 | 11 | 102,981 | octubre |
| 2025 | 991,106 | 9 | 110,123 | agosto, setiembre, octubre |
| 2026 | 847,771 | 8 | 105,971 | setiembre a diciembre (borde de la ventana) |

**Solo mercado INTERNO:**

| año | total (miles de m³) | meses | promedio por mes | meses que faltan |
|---|---|---|---|---|
| 2022 | 1.035,996 | 12 | 86,333 | — |
| 2023 | 1.025,299 | 12 | 85,442 | — |
| 2024 | 993,409 | 11 | 90,310 | octubre |
| 2025 | 835,534 | 9 | 92,837 | agosto, setiembre, octubre |
| 2026 | 719,479 | 8 | 89,935 | setiembre a diciembre (borde de la ventana) |

El total anual **no** es comparable entre años sin mirar la columna `meses`: 2024 tiene 11 meses y
2025 tiene 9. El promedio por mes (última columna, derivado de dividir el total del año por sus
meses) sí es comparable y muestra que el volumen mensual del mercado interno se movió en una banda
estrecha (85 a 93 mil m³/mes) pese a que los totales anuales caen mes a mes solo porque hay menos
meses.

**Trampa de la columna `Unidad` (declarada):** el archivo mezcla **`Miles de m3` (1.178 filas)** con
**`Toneladas` (22 filas**: los combustibles sólidos del mercado interno, `PETCOKE`). Para la línea
`GAS OIL` todas las filas son `Miles de m3`, pero sumar la columna entera del archivo sin separar las
dos unidades pone un número junto a otro y los dos parecen plausibles.

---

## 6. La paridad de importación contra el precio ex planta

Compara el **precio ex planta** de ANCAP (el de venta al público menos fletes, márgenes e impuestos)
contra el **precio de paridad de importación (PPI)** que calcula URSEA, los dos **sin impuestos**, en
$/litro, mes a mes desde 2022. `diferencia_pct` positiva = ANCAP por encima de lo que costaría
importar.

- `fuente`: URSEA (PPI y componentes) y ANCAP (precio ex planta), catálogo de datos abiertos.
- `bajado`: 2026-10-11T18:48.
- `metodo` (citado tal cual lo devuelve la herramienta):

> Precio ex planta de ANCAP (el de venta al público menos fletes, márgenes e impuestos) contra el
> precio de paridad de importación de URSEA sin impuestos y con la mezcla de agrocombustibles, en
> $/litro. El PPI de la ventana que cierra el 25 se compara con el mes siguiente, que es cuando rige.
> diferencia_pct positiva = ANCAP por encima de lo que costaría importar. La elección del nivel y del
> mes es de este servidor, no una cifra oficial: a confirmar contra los informes de URSEA.

Último mes comparable (2026-08) y promedio de los últimos 12 meses:

| producto | mes | ex planta ($/l) | PPI ($/l) | diferencia ($/l) | diferencia (%) | promedio 12 meses (%) |
|---|---|---|---|---|---|---|
| Gasoil 50-S | 2026-08 | 34,92 | 39,85 | −4,93 | −12,4 | −3,3 |
| Gasoil 10-S | 2026-08 | 38,95 | 39,89 | −0,94 | −2,4 | +6,8 |

Avisos que devuelve la herramienta (citados, no corregidos):
`ventana del PPI descartada por imposible: 2022-12-26 a 2022-12-25`. Para Gasoil 10-S agrega:
`URSEA publica la vigencia de este cierre como 2026-08; por la regla del resto de las filas rige en
2026-09`.

Desglose del último cierre de URSEA (fecha de cierre 2026-08-25, vigencia 2026-09; Gasoil 50-S):

| componente | valor |
|---|---|
| precio FOB ajustado (USD/m³) | 1.010,24 |
| fletes internacionales (USD/m³) | 56,87 |
| precio CIF (USD/m³) | 1.068,63 |
| ex planta con distribución (USD/m³) | 1.131,35 |
| ex planta con biocombustible (USD/m³) | 1.131,35 |
| IMESI (USD/m³) | 0,00 |
| impuesto CO2 (USD/m³) | 0,00 |
| IVA (USD/m³) | 266,12 |
| total ex planta (USD/m³) | 1.475,74 |
| tipo de cambio promedio ($/USD) | 40,25 |
| total ex planta ($/litro) | 59,39 |

**Los dos precios son distintos y no se mezclan.** El de la sección 3 (58,68 $/l para 50-S en
2026-07) es **máximo al público con IVA**; el ex planta de acá (34,92 $/l para 50-S en 2026-08) es sin
impuestos. La diferencia entre ambos incluye impuestos y márgenes que este par de datasets **no**
desglosa hasta el final.

---

## 7. El canario (resultado y tolerancia)

Se corrieron los tres controles. Los tres **pasan**.

**Control 1 — el precio nominal de la herramienta coincide EXACTAMENTE con el archivo en caché.**
Se comparó la salida de `combustible_ancap` (productos `GASOIL 50-S *` y `GASOIL 10-S *`) contra el
archivo `~/.cache/mcp-uruguay/ancap.csv` leído directo con `uydatos.ancap` (`leer_publicaciones` →
`serie_mensual`), en un entorno que instala `uydatos` 0.12.0.

- Celdas (mes × producto) comparadas: **112** (56 meses × 2 productos).
- **Diferencia máxima absoluta: 0,00.** Celdas que difieren: **0**.
- Tolerancia pedida: 0,00. **Pasa.**
- Contexto medido del archivo: 25.364 publicaciones crudas → 1.232 meses distintos (producto × año ×
  mes); es un log de publicaciones apiladas, no una serie. 2026-08 es el último mes.

**Control 2 — las dos vías de deflactar dan el mismo número.**
`pesos_constantes({mes: monto}, base=mes_final)` contra
`variacion_real(monto_inicial, mes_inicial, monto_final, mes_final)`, comparando el equivalente del
monto inicial en moneda del mes final.

| mes inicial → mes final | pesos_constantes | variacion_real | diferencia | diferencia relativa |
|---|---|---|---|---|
| 2022-06 → 2026-07 (monto 100) | 122,07 | 122,07 | 0,00 | 0,000000 % |
| 2024-06 → 2026-01 (monto 1.234,56) | 1.311,56 | 1.311,56 | 0,00 | 0,000000 % |

Tolerancia pedida: 0,01 %. **Pasa** en los dos pares.

**Control 3 — la serie declara sus huecos y no interpola nada.**

- Precios: GASOIL 50-S tiene **32** meses con precio y **24** con `S/C`, y esos 24 vuelven como
  `null` (ninguno rellenado).
- Ventas: la serie tiene **52** meses; los **8** meses que la fuente no publicó (2024-10, 2025-08,
  2025-09, 2025-10, 2026-09 a 2026-12) están declarados como faltantes y **ninguno aparece en la
  serie**; no hay meses en cero.
- **Pasa.**

---

## 8. Qué no se puede concluir

- **No hay un precio continuo de gasoil.** Los meses `S/C` son huecos: la herramienta los devuelve
  como `null` y no los interpola ni los arrastra desde el mes anterior. Cualquier serie mensual de
  precios de gasoil tiene faltantes y hay que declararlos.
- **El precio ex planta no es el precio al público.** No se puede restar uno del otro para leer
  "impuestos y márgenes": son datasets distintos y el desglose de URSEA no llega hasta esa resta.
- **El PPI es una construcción del servidor, no una cifra oficial.** La elección del nivel y del mes
  es del servidor y hay que confirmarla contra los informes de URSEA. La comparación es **sin
  impuestos contra sin impuestos**: no dice nada del precio final que paga el público.
- **El GLP no se compara en la paridad**: un archivo lo da en $/litro y el otro en $/kg.
- **Los totales anuales de volumen no son comparables entre sí** sin leer `meses`: 2024 tiene 11
  meses, 2025 tiene 9 y 2026 tiene 8. Y el archivo es una **ventana móvil de cinco años con huecos**:
  un mes que falta **no es cero**.
- **No se puede sumar la columna `Unidad` entera del archivo de ventas**: mezcla `Miles de m3` y
  `Toneladas` (los sólidos del mercado interno).
- **Los negativos** de la serie de ventas son correcciones de la fuente y se suman: no son ventas
  negativas reales.
- **`QUEROSENO` (familia BLANCOS) y `QUEROSENOS` (familia SOLVENTES) son productos distintos**, no un
  error de tipeo del otro.
- **Los últimos meses son parciales o de borde de ventana** (2026-08 es el último del archivo de
  precios; 2026 está incompleto en ventas): no sirven para cerrar un año.
