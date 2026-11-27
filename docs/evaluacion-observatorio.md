# Evaluación del observatorio

El banco `evals/observatorio.json` tiene 30 escenarios, cada uno en español e inglés. Hay 10 de dominio, 10 de descubrimiento y 10 donde la evidencia no alcanza. Para inferir mejoras, usar el escenario como unidad pareada. Las traducciones no son observaciones independientes. Los casos de dominio se basan en preguntas de desarrollo. El banco reservado existente se mantiene separado.

```powershell
uv run --with anthropic python evals/evaluar.py --archivo evals/observatorio.json --modo sin_catalogo,con --esfuerzo low
```

Ambos modos reciben el mismo sistema y servidor. En `sin_catalogo` solo se retira la búsqueda por tema. Los resultados incluyen llamadas, argumentos, texto de respuesta, errores y duración. La tabla distingue acierto de respuesta y aparición de la herramienta esperada. Revisar las citas y los argumentos contra la ficha de cada pregunta antes de concluir que una respuesta es utilizable. El patrón de descubrimiento mide si encontró el recurso esperado. Otras fuentes válidas requieren revisión.

Antes de una corrida con pago, asignar una credencial de un proyecto de evaluación con un tope de gasto en el proveedor. Registrar tope, precios, modelo, SHA y fecha en el acta. Mantener una repetición por modo. El evaluador no fija un límite monetario por sí mismo.
