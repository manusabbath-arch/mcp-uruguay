---
name: clima-de-salto
description: "Lluvia y temperatura de Salto desde dos estaciones. Lluvia y temperatura de Salto en una ventana, desde las dos estaciones públicas disponibles."
---

# Lluvia y temperatura de Salto desde dos estaciones

> Archivo generado por `scripts/generar_skills.py` desde `src/mcp_uruguay/guias.py`. No editar a mano: se regenera y `--check` falla si difiere.

Quiero la lluvia y la temperatura de Salto entre <desde> y <hasta>.

1. `clima` con desde `<desde>` y hasta `<hasta>`: estación de INIA en Salto Grande, serie desde 1970. Su día va de 9 a 9, un vacío es nulo (no cero) y se actualiza cada quincena: si `dias` viene vacío, la ventana pedida está más allá del último dato y hay que decirlo.
2. `observaciones_inumet` con estación `salto` y agregación explícita: `max` o `min` para temperatura, `suma` para lluvia. El día es el local (UTC-3) y un día incompleto devuelve null.

Las dos estaciones no están en el mismo punto ni cortan el día a la misma hora: la lluvia diaria de una no reproduce la de la otra. Compará acumulados de varios días, no días sueltos, y presentá las dos series por separado con su `fuente` y su `bajado` en vez de promediarlas.

## Trampas de las herramientas que nombra

- `clima`: el día va de 9 a 9; un vacío es nulo, no cero; la fuente se actualiza cada quincena
- `observaciones_inumet`: la fuente publica en UTC y el día es el local (UTC-3); un día incompleto devuelve null; la agregación es obligatoria
