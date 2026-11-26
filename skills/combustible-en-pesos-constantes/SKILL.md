---
name: combustible-en-pesos-constantes
description: "Un combustible en pesos constantes contra la paridad. El precio de un combustible en pesos de un mismo mes, contra la paridad de importación."
---

# Un combustible en pesos constantes contra la paridad

> Archivo generado por `scripts/generar_skills.py` desde `src/mcp_uruguay/guias.py`. No editar a mano: se regenera y `--check` falla si difiere.

Quiero saber cuánto costó de verdad <producto> desde <desde>, en pesos de un mismo mes, y cómo se ubica contra lo que costaría importarlo. Seguí este orden y no saltees pasos:

1. `combustible_ancap` con producto `<producto>` (sin argumentos lista los productos). Es el precio máximo al público con IVA, mensual y en pesos corrientes. Un mes sin cotización es un hueco: no lo interpoles.
2. `pesos_constantes` con los montos {"AAAA-MM": precio} de ese paso y como base el último mes con Unidad Indexada publicada. Elegir la base es una decisión de análisis: decí cuál usaste.
3. `variacion_real` entre el primer y el último mes: da la variación nominal, la inflación y la real.
4. `paridad_combustibles` para el mismo producto: compara el precio ex planta de ANCAP contra la paridad de importación, sin impuestos contra sin impuestos. El ex planta NO es el precio al público.
5. `ventas_combustible` para el volumen. La columna Unidad mezcla miles de m3 con toneladas y la ventana tiene huecos: compará promedios mensuales, no totales anuales, porque los años no tienen los mismos meses.

Citá `fuente` y `bajado` de cada herramienta junto a cada número. Si alguna herramienta rechaza, contá el motivo: no lo reemplaces con una estimación.

## Trampas de las herramientas que nombra

- `combustible_ancap`: es el máximo al público con IVA; el precio ex planta es otro dataset y otro número
- `pesos_constantes`: usa la Unidad Indexada promedio del mes; es una decisión de análisis, no una lectura
- `variacion_real`: con la UI, el mes en curso usa los días publicados
- `paridad_combustibles`: se compara sin impuestos contra sin impuestos; el GLP no se compara ($/L contra $/kg)
- `ventas_combustible`: la columna Unidad mezcla miles de m3 con toneladas; la ventana tiene huecos
