---
name: compras-del-estado
description: "Lo que el Estado adjudicó de un producto en un año. Cuánto adjudicó el Estado de un producto en un año, sin dejar que un solo ítem engañe."
---

# Lo que el Estado adjudicó de un producto en un año

> Archivo generado por `scripts/generar_skills.py` desde `src/mcp_uruguay/guias.py`. No editar a mano: se regenera y `--check` falla si difiere.

¿Cuánto adjudicó el Estado de «<producto>» en <anio>?

1. `compras_estado` con anio `<anio>` y buscar `<producto>`. Cuenta solo adjudicaciones activas; el importe es cantidad por precio unitario; llamados y anulaciones no son compras.
2. Antes de citar un total, mirá `aviso` y `mayores_items`: un solo ítem puede ser la mitad del total y a veces es un registro imposible (el monto en la cantidad y precio 1). Si domina, decilo y mostrá el total con y sin ese ítem.
3. Las monedas se suman aparte; lo que no se pudo convertir a pesos viene en `sin_convertir` y los ítems sin moneda en `sin_moneda`: no los descartes en silencio.
4. La búsqueda es por texto de la descripción: probá singular y plural y la palabra sin tilde, y revisá que lo que coincidió sea el producto y no otra cosa con el mismo nombre.

## Trampas de las herramientas que nombra

- `compras_estado`: el importe es cantidad por precio unitario; llamados y anulaciones no son compras; un solo ítem puede dominar el total
