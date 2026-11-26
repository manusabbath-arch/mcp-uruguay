---
name: real-o-nominal
description: "Si un monto subió en términos reales. Si un monto subió o bajó descontando la inflación."
---

# Si un monto subió en términos reales

> Archivo generado por `scripts/generar_skills.py` desde `src/mcp_uruguay/guias.py`. No editar a mano: se regenera y `--check` falla si difiere.

Un monto pasó de <monto_inicial> en <mes_inicial> a <monto_final> en <mes_final>. ¿Subió o bajó en términos reales?

Usá `variacion_real` con esos cuatro valores y el índice `UI`. Devuelve la variación nominal, la inflación del período y la variación real: informá las tres. El mes en curso usa solo los días publicados, y la Unidad Indexada es una elección de deflactor, no la única posible: decilo.

## Trampas de las herramientas que nombra

- `variacion_real`: con la UI, el mes en curso usa los días publicados
