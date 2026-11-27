# Investigación externa: SDK, clientes, vecinos y fuentes

Hecha el 2026-11-27 con búsquedas web (Firecrawl) y mediciones locales sobre `main` en `eab2f82`.
Cada afirmación lleva su fuente o la medición que la respalda. El 403 del Parlamento no entra:
lo trata otra rama (`docs/2026-11-27-parlamento-403-es-el-user-agent.md`).

## 1. SDK y protocolo: al día, sin deuda escondida

- **El pin `mcp>=2.3,<3` está en la última versión.** v2.3.0 es la última release del SDK de
  Python (2026-10-02, [releases](https://github.com/modelcontextprotocol/python-sdk)). v2 habla la
  revisión 2026-07-28 del protocolo (sin handshake ni sesión) y sigue sirviendo a clientes 2025.
- **El cambio de v2 que más podía doler ya está cubierto.** En v2 «solo el mensaje de un
  `ToolError` llega al modelo; cualquier otra excepción se lee `Error executing tool <name>`»
  ([What's new in v2](https://py.sdk.modelcontextprotocol.io/whats-new/)). Las herramientas lanzan
  `ValueError`, pero `servidor.py` las convierte en `ToolError` junto con `OSError` y
  `HTTPException`, y `tests/test_servidor.py` lo prueba.
- **Lo que la revisión 2026-07-28 depreca no se usa:** roots, sampling y logging del protocolo
  (`grep` sin coincidencias en `src/`). Las tareas (*tasks*) salieron del núcleo a una extensión
  que el SDK de Python todavía no implementa: no son camino para las llamadas largas hoy.

## 2. Llamadas largas: el progreso no salva a todos los clientes

Lo que dicen los clientes:

| Cliente | Comportamiento | Fuente |
|---|---|---|
| SDK TypeScript (base de muchos clientes) | corta a los 60 s; el progreso solo reinicia el reloj si **el cliente** pide `resetTimeoutOnProgress` | [agentcat](https://agentcat.com/guides/fixing-mcp-error-32001-request-timeout/) |
| Claude Code | reloj = máx(60 s, timeout del servidor, `MCP_TIMEOUT`); a los 2 min pasa la llamada a segundo plano; corte por inactividad `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT` | [docs de Claude Code](https://code.claude.com/docs/en/mcp) |
| Claude Desktop / Cowork | corta a ~60 s y no respeta el progreso (bug abierto) | [claude-code#58687](https://github.com/anthropics/claude-code/issues/58687) |
| Cursor (cliente ACP) | no pasa `resetTimeoutOnProgress`: corta a 60 s | [foro de Cursor](https://forum.cursor.com/t/acp-mcp-client-should-reset-json-rpc-tool-call-timeout-on-notifications-progress-or-honour-resettimeoutonprogress/160548) |

El servidor ya emite progreso (`ctx.report_progress` en `servidor.py`). Eso ayuda en Claude Code y
no alcanza en Claude Desktop ni en Cursor: ahí lo único que sirve es **responder en menos de 60 s**.

Medido hoy con `scripts/sonda.py` (31 herramientas, caché existente de semanas anteriores):

| Herramienta | Segundos |
|---|---|
| `compras_estado` (2025) | 339,9 (ver abajo) |
| `calidad_agua` | 78,1 |
| `observaciones_inumet` | 53,4 |
| `resultados_electorales` | 53,3 |
| `ubicar_punto` | 10,1 |
| las otras 26 | menos de 9 cada una |

Los 339,9 s de `compras_estado` **no se reproducen**: aislada, la misma llamada tardó 16,3 s
directa y 19,6 s por un cliente MCP en proceso, y 67 s con el perfilador. No bajó ningún archivo:
el ZIP de 2025 tiene TTL de 365 días y su copia es del 2026-10-11. El perfil reparte el tiempo
entre `uydatos.compras._items` (22 s) y `json.loads` de los 12 JSON del ZIP (13 s). La causa del
valor atípico queda abierta, pero una segunda medición la acota. Con cinco herramientas pesadas en
un mismo proceso, la misma `observaciones_inumet` tardó 19,0 s con el recolector de basura activo y
93,4 s con el recolector apagado. El proceso tenía 1,8 millones de objetos vivos: los memos de
compras y electorales quedan en memoria. Con el recolector apagado se usa más memoria, y la
variación grande apunta a presión de memoria de la máquina, no a la lógica de una herramienta. Un
servidor que vive horas acumula esos memos. Medir su memoria residente es el paso siguiente.

Corrección posterior: `--precalentar` **ya existía**; este documento lo daba por faltante. Le
faltaban `resultados_electorales` y las capas de `ubicar_punto`, que se agregaron con su test.
`observaciones_inumet` no entra a propósito: su TTL es de un día, así que precalentarla no sirve.
En caliente, `calidad_agua` tarda de 8 a 19 s.

## 3. Tamaño de las respuestas: holgado

Claude Code guarda en un archivo cualquier resultado de texto de más de 50.000 caracteres. Se
puede subir por herramienta con `_meta["anthropic/maxResultSizeChars"]`. Los errores de más de
~11.000 caracteres se recortan al medio ([docs](https://code.claude.com/docs/en/mcp)). Medido en
la sonda, la respuesta más larga es la de `diagnostico` (35.990 caracteres de texto), seguida por
`compras_estado` (20.227) y `recursos_catalogo` (19.900). No hace falta declarar
`maxResultSizeChars`. `diagnostico` crece con cada archivo de la caché: es la única que conviene
vigilar.

## 4. Un hallazgo en el código: el aviso de copia vencida pisa el aviso propio

`_con_aviso_de_copia` (`servidor.py`) arma `{**resultado, "copia_vencida": True, "aviso": ...}`.
`compras_estado` es la única herramienta que trae su propio `aviso` (un ítem que domina el total,
`estado.py:294`). Si se sirve una copia vencida del año en curso (TTL de 7 días) porque la ARCE no
respondió, **el aviso de dominancia desaparece** y queda solo el de la copia. Es justo el aviso
que dice «revisar los mayores ítems antes de citar el total». Se encontró leyendo el código, no
reproducido con un test todavía. El arreglo es conservar los dos (concatenarlos o usar una clave
aparte), con un test en rojo antes.

## 5. Vecinos: quién más sirve datos de Uruguay por MCP

| Proyecto | Qué hace | Relación con este repo |
|---|---|---|
| [okfn/mcp-datos-uruguay](https://github.com/okfn/mcp-datos-uruguay) | Datasets declarativos (YAML) sobre catalogodatos.gub.uy para el servidor de OKFN; alfa; compras OCDS en un SQLite de ~1 GB | misma fuente de compras, otro diseño; último commit 2026-06-25 |
| [okfn/mcp-datos-uruguay-ben](https://github.com/okfn/mcp-datos-uruguay-ben) + [chat público](https://mcp.okfn.org/ben-uruguay/) | Balance Energético Nacional (MIEM), 27 herramientas | tema que este repo no cubre |
| [Datos UY/AR](https://ai-powered.com/mcp/datos-uy-ar) | remoto en `datosuyar.dev/mcp`, freemium (30 llamadas/día, después API paga en USDC por x402): UI, BCU, **feriados UY/AR, días hábiles**, RUT/CUIT, UVA/CER | se superpone en BCU y RUT; tiene feriados y días hábiles, que acá faltan |
| [opendata-latam-mcp](https://lobehub.com/mcp/alcastaro-opendata-latam-mcp) | metadatos CKAN de 6 portales (Uruguay: 2.679 datasets), búsqueda entre países | solo metadatos; equivale a `recursos_catalogo` |

Tres conclusiones:

- **Lo que distingue a este repo** es leer el dato (no el metadato) con trampas declaradas,
  `procedencia` con sha256 y rechazo con motivo. Ninguno de los vecinos lo hace. Conviene decirlo
  en el README, que hoy no se compara con nada.
- **Hueco concreto: feriados y días hábiles de Uruguay.** Es una herramienta `sinred` (los
  feriados fijos están en la ley; Carnaval y Turismo salen de la fecha de Pascua). Ya aparece en
  el propio servidor: `cotizacion` explica que «un fin de semana o feriado no tiene cotización»
  y hoy no puede decir cuál de los dos es. Antes de implementarla hay que medir las reglas de
  traslado de feriados (Ley 16.805 y modificativas) en la fuente oficial; no salen de este
  documento.
- **El transporte remoto (M8) ya tiene precedente en el mismo nicho:** Datos UY/AR se instala con
  una URL en Claude, ChatGPT, Cursor y VS Code, sin `uv`. El instalador de `ai-powered.com` saca
  los pasos del MCP Registry, así que una entrada `remotes` en `server.json` se publicaría sola
  ahí.

## 6. La ECH del INE: se mudó, pero no es alcanzable

La nota «cerrada en negativo» decía que los 25 recursos del catálogo devolvían la portada del
sitio nuevo. Novedad: el INE publica ahora los microdatos en su catálogo **ANDA** (software NADA
del IHSN). La ECH 2025 está en
[catalog/779](https://www4.ine.gub.uy/Anda5/index.php/catalog/779), anunciada el 2026-04-23
([INE](https://www.gub.uy/instituto-nacional-estadistica/comunicacion/publicaciones/microdatos-encuesta-continua-hogares-ech-2025)),
y la de 2026 en `anda/index.php/catalog/784`.

Pero `www4.ine.gub.uy` devuelve **403 `Forbidden.`** (10 bytes) a todo lo que se probó desde aquí:
curl con UA propio, con UA de Chrome y con el de `uydatos`, Firecrawl con proxy *stealth* y un
navegador real. También la portada del catálogo y la API de NADA. Al no pasar ni el navegador, no
es la forma del UA, como en el Parlamento: parece un bloqueo por IP o del host entero. Queda
cerrado hasta que alguien lo abra desde otra red. Si abre, NADA tiene API de catálogo y conviene
medir la licencia de cada edición antes de escribir un lector.

## Qué hacer, en orden de valor

1. ~~Test en rojo y arreglo del aviso pisado (§4).~~ Hecho (CHANGELOG, «Sin publicar»).
2. ~~Completar `--precalentar` (§2).~~ Hecho: elecciones y capas de `ubicar_punto`.
3. Herramienta `feriados`/`dias_habiles` sin red (§5). El módulo va primero a `uydatos`, después la
   Release y el pin, y recién ahí la herramienta.
4. Una línea en el README sobre qué distingue a este servidor de los vecinos (§5).
5. Medir la memoria residente de un servidor que respondió varias herramientas pesadas (§2).
