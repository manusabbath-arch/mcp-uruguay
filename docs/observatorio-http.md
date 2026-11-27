# Beta HTTP del Observatorio de Salto

El piloto ofrece nivel del río, clima, agua potable y el recorrido de descubrimiento del catálogo. El servidor HTTP escucha en loopback. Una instalación local normal sigue usando stdio.

## Arranque y verificación

```powershell
uv run --extra remoto mcp-uruguay --precalentar-piloto
uv run --extra remoto mcp-uruguay --remoto
```

Con el proceso activo, conectar el cliente a `http://127.0.0.1:8420/mcp` o ejecutar `uv run python scripts/sonda_remota.py http://127.0.0.1:8420/mcp`. La sonda verifica el catálogo y la cobertura de un rango histórico de Salto. `GET /health` comprueba que el proceso contesta. Mantener ambas comprobaciones porque una fuente puede estar caída con el proceso disponible.

Para la beta por invitación, poner el proceso detrás de un proxy TLS con acceso restringido. Conservar un directorio de caché persistente y ejecutar el precalentamiento con esa misma ruta. El proxy debe reemplazar `Host` por la dirección de loopback con puerto y reemplazar `X-Forwarded-For` por la IP del cliente observada por el proxy de confianza. Configurar el monitor con acceso al mismo endpoint y ejecutar la sonda diariamente. La aplicación registra estado HTTP y duración. Medir memoria del proceso y crecimiento de la caché desde el entorno de despliegue.

Los valores iniciales son 30 solicitudes por IP por minuto, ráfaga de cinco y dos consultas simultáneas. Las consultas a una misma herramienta se serializan para reutilizar la caché tras un refresco. El límite HTTP devuelve 429 y `Retry-After`. El puerto y el límite admiten ajustes mediante `MCP_URUGUAY_HTTP_PORT`, `MCP_URUGUAY_RATE_LIMIT_POR_MIN` y `MCP_URUGUAY_RATE_LIMIT_RAFAGA`.

## Medición por stdio

Con el wheel del commit de búsqueda CKAN, el precalentamiento de INIA y OSE tardó 96 s en una caché vacía. Después se hicieron 20 llamadas por herramienta para las consultas del piloto. El p95 por rango más cercano fue 0,68 s para clima, 0,33 s para río y 7,33 s para OSE. El río llenó su caché en la primera llamada, que tardó 0,97 s.
