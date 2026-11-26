---
name: el-rio-en-salto
description: "El río en Salto contra la misma época de otros años. El nivel del río en Salto, comparado con la misma época de años anteriores."
---

# El río en Salto contra la misma época de otros años

> Archivo generado por `scripts/generar_skills.py` desde `src/mcp_uruguay/guias.py`. No editar a mano: se regenera y `--check` falla si difiere.

¿Cómo está el río en Salto en los últimos <dias> días respecto a la misma época de otros años?

1. `nivel_rio_comparado` con estación `Salto` y dias `<dias>`: compara la media de la ventana contra las mismas fechas de cada año. Los años sin la ventana completa se excluyen y se declaran.
2. `nivel_rio` para el detalle por día si hace falta, con su cobertura.
3. `nivel_rio_ina` con escala `Concordia` (la escala de Prefectura frente a Salto): trae los niveles de alerta y evacuación de esa escala. Es otra estación y otra altura: no la mezcles con la de la CTM, y mirá `dias_de_atraso` antes de decir que es el dato de hoy.

Dos advertencias: la unidad de la altura de la CTM la publica el servicio sin declararla, y la cifra es viva (la media del día en curso cambia entre dos corridas). Para decir si es mucho o poco, comparala contra las cotas oficiales del puerto que publica el organismo de emergencias, y no afirmes que el agua llega a un lugar sin conocer la cota del terreno de ese lugar.

## Trampas de las herramientas que nombra

- `nivel_rio_comparado`: la unidad de la altura la publica el servicio sin declararla y la cifra es viva: cambia entre dos corridas
- `nivel_rio`: declara la cobertura; una estación sin lecturas no es un cero
- `nivel_rio_ina`: el id es de serie y no de estación (hay una 'Concordia' de Brasil); el caudal de Concordia trae meses de atraso y el dato del día se carga por la tarde: mirar `dias_de_atraso`
