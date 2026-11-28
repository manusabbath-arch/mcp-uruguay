# Segunda pasada: benchmark, protocolo y evaluación (2026-11-26)

## Francia: evidencia de código
- https://github.com/datagouv/datagouv-mcp/blob/main/tools/search_datasets.py (blob a69a42b5dd5fd0495b249866e346ca54a5290bf2): normaliza términos genéricos para búsqueda AND, reintenta consulta original si no hay resultados, pagina y recorta descripción. Copiar el patrón de fallback explícito, no las stopwords francesas. Probar consultas vacías tras limpieza, términos específicos y no resultados; no confundir ausencia de hits con ausencia de datos.
- https://github.com/datagouv/datagouv-skill/blob/main/SKILL.md (blob e7d7c3c42bd5c1e9a0370e78d8feaa8c6482b20a): MCP preferido, HTTP alternativo, resolución de identificadores, límites y separación de exploración interactiva/scripts. Adaptar mediante recursos existentes y lectores uydatos, sin permitir bypass de validaciones ni 403.
- servidor.py propio (blob 4459fe92ea6aea30cf81451493d1fa30081e2500) usa MCPServer v2, decorador central para errores, procedencia y progreso. Mantenerlo. No crear herramientas duplicadas de catálogo sin medir cobertura actual.

## SDK y protocolo
https://py.sdk.modelcontextprotocol.io/advanced/skills/ documenta mcp.server.skills.Skills, Skill y SkillResource, handlers list/get, TextResource y MCPServer(extensions=[...]). El manifiesto incluye URI, tamaño en bytes y digest sha256. No hay descubrimiento automático de filesystem. Usar dos archivos conocidos en allowlist, distribuirlos como package data desde una fuente canónica; no aceptar rutas arbitrarias. Verificar igualdad entre frontmatter anunciado y archivo, bytes UTF-8 y hash, URI desconocida, negociación, cliente legacy, wheel/uvx/MCPB. No cambiar dependencia hasta comprobar versión mínima real mediante wheel instalado. Documentación web no demuestra soporte de mcp 2.3.0.
https://github.com/modelcontextprotocol/ext-tasks/blob/main/specification/2026-07-28/tasks.md y https://py.sdk.modelcontextprotocol.io/v2/es/whats-new/: SEP-2663 sustituye SEP-1686, polling y negociación por petición; docs advierten implementación pendiente. Postergar. Mantener latido existente; investigar timeout y cancelación de hilo por separado.

## Evaluación
https://github.com/benchflow-ai/skillsbench y https://inspect.aisi.org.uk/scoring.html: separar harness, tarea, verificador determinista y log. https://github.com/NVIDIA/SkillEvaluator aporta controles estáticos y seguridad como referencia, no dependencia obligatoria.
Primera etapa sin API: validar nombres y referencias de skills, casos sintéticos y scoring reproducible. Segunda: B vs C pareados en subconjunto de desarrollo; registrar modelo/versión, commits, hash de skill, modalidad de entrega, snapshot de fuente, seed si existe, tokens, latencia, llamadas y error. D con web se mide aparte por variabilidad. No filtrar las 11 reservadas a autores. Congelar rúbrica y fixtures antes de ejecutar. Medir descubrimiento natural además de inyección explícita de skill. Separar fallo de herramienta, método, dato y presentación. Un score no puede compensar una cifra materialmente incorrecta con buena redacción.
Casos sintéticos: mes incompleto, null vs cero, fuente vencida, contradicción territorial, índice vs inflación, falta de bytes, instrucción maliciosa en metadatos. No son resultados de benchmark ni sustituyen preguntas reales.

## Decisión
Skills piloto antes de Tasks; búsqueda progresiva sin duplicar API; evaluación local antes de gasto. Pendiente ejecutar SDK, CI y benchmark; no se afirma conformidad.
