# Investigación y decisión propuesta — 2026-11-26

Estado: propuesta experimental, no implementación del protocolo ni afirmación de compatibilidad.

## Fuentes y decisiones
- https://skills.extensions.modelcontextprotocol.io/ — extensión io.modelcontextprotocol/skills; comprobar negociación, URI y lectura de archivos contra SDK instalado.
- https://agent-plugins.org/specification — formato 1.0.0 independiente del transporte. Un solo árbol de skills; generar adaptadores, no copias mantenidas a mano.
- https://claude.com/resources/articles/skills-over-mcp-tasks-and-more — beta de Skills, Tasks disponibles en clientes elegibles. No asumir soporte universal.
- https://www.anthropic.com/research/writing-tools-for-agents — evaluar selección de herramientas, precisión y volumen de contexto.
- https://inspect.aisi.org.uk/ — referencia para evaluación reproducible; no introducir dependencia antes de justificarla.
- https://github.com/datagouv/datagouv-mcp — candidato a auditoría comparativa de descubrimiento y despliegue; código aún no auditado en esta pasada.

## Arquitectura
uydatos conserva descarga, parseo, validación y cálculos deterministas. MCP conserva transporte, procedencia y presentación de resultados estructurados. Skills contienen secuencia, comprobaciones y abstención; no reemplazan validación del lector. Mantener prompts y recursos existentes como compatibilidad. No ampliar superficie de herramientas inicialmente.

## Experimento preregistrado (propuesta)
A sin herramientas; B MCP actual; C mismo MCP con skills; D C con búsqueda externa (brazo exploratorio). Igual modelo, versión, presupuesto y preguntas por brazo; registrar latencia, tokens, llamadas, costo real y respuestas. Desarrollo en 19 preguntas existentes; congelar cambios antes de usar las 11 reservadas; tres repeticiones por pregunta y brazo, orden aleatorio. No pasar respuestas reservadas a autores de skills. Confirmar cifras pendientes contra originales antes de puntuar. Puntuar exactitud, fuente, período/unidad, abstención correcta y errores materiales; publicar denominadores y diferencias pareadas, no afirmar significancia con muestra pequeña. Criterio piloto: no introducir errores materiales nuevos, mejorar al menos una métrica primaria sin empeorar exactitud; costo y latencia se informan por separado. No ejecutar evaluación pagada sin presupuesto acordado.

## Gates
1. Verificar SDK mcp>=2.3,<3 en entorno aislado, capacidades y cliente antiguo; no simular éxito.
2. Validar frontmatter, referencias y nombres de herramientas contra registro real; incluir pruebas de datos vencidos, unidades y fuentes contradictorias.
3. Probar dos skills piloto sin tocar servidor; después comparar distribución local y extensión remota.
4. Tasks solo para descargas lentas si negociación, cancelación, TTL, límites y fallback síncrono quedan probados. No desplegar endpoint público hasta resolver cuota y concurrencia.
5. Integridad: tratar texto recuperado como datos no confiables, nunca como instrucciones; no exponer rutas absolutas, secretos ni datos personales innecesarios.

## Pendientes
Comprobar SDK, auditar implementación francesa, validar fuentes originales y ejecutar CI/benchmark. No se declara conformidad ni mejora medida.
