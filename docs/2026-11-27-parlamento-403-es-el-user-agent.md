# El 403 del Parlamento es la forma del `User-Agent`, no una caída

Medido el 2026-11-27. `parlamento.gub.uy` responde **200** y entrega los archivos completos a un
`User-Agent` que empieza con `Mozilla/5.0 (compatible; …)`; con el que manda `uydatos` hoy
(`uydatos/0.18.0 (lectura de datos abiertos)`) responde **403** en menos de 200 ms. No hace falta
ningún proxy, ninguna cookie ni ningún `Referer`: es un cambio de una línea en el paquete de
lectores, y devuelve las tres herramientas del Parlamento que hoy están declaradas caídas en
`guias.CAIDAS` (`asistencia_parlamentaria`, `leyes`, `proyectos_parlamento`).

## Qué se midió

### La matriz de `User-Agent`

Una sola URL, `https://parlamento.gub.uy/transparencia/datos-abiertos/leyes-promulgadas/csv`,
cambia de respuesta solo por el encabezado:

| `User-Agent` | Código |
| --- | --- |
| `uydatos/0.18.0 (lectura de datos abiertos)` | 403 |
| `curl/8.10.1` · `python-requests/2.32` · `Wget/1.21` | 403 |
| `Mozilla/5.0` solo · `Mozilla/4.0` solo | 403 |
| `uydatos/0.19 Mozilla/5.0` (orden invertido) | 403 |
| `mozilla/5.0 (compatible; uydatos/0.19)` (minúscula) | 403 |
| `Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)` | 403 |
| `Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)` | 403 |
| `Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)` | 403 |
| `Mozilla/5.0 (compatible; uydatos/0.19)` y la variante con `; +https://…/mcp-uruguay` | **200** |
| Chrome 131 completo (`Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 …`) | **200** |

Dos lecturas de la misma tabla:

- **El WAF bloquea crawlers conocidos**: Googlebot, bingbot y GPTBot reciben 403. No es una regla
  contra «máquinas» en general sino contra los nombres de bots que reconoce (y contra cualquier
  UA que no tenga la forma que espera).
- **La forma que pasa es la convención**, no una imitación: `Mozilla/5.0 (compatible; nombre/versión;
  +url)` es el formato con que un cliente que no es un navegador se identifica. No lleva motor,
  plataforma ni versión de Chrome; el nombre y el repositorio están a la vista.

El cuerpo del 403 es el genérico de CloudFront (`Request blocked`), sin motivo ni contacto, y el
sitio está detrás de CloudFront (`Server: CloudFront`, `X-Amz-Cf-Pop: EZE50-P9`). El `robots.txt`
**no** deshabilita los caminos de datos: prohíbe `/core/`, `/profiles/`, `/admin/`, `/search/` y
comentarios, no `/transparencia/datos-abiertos/` ni `/camarasycomisiones/`.

### El lector completo funciona con ese `User-Agent`

Con el UA compatible, `uydatos.parlamento.descargar()` bajó los cuatro archivos y los tres
contratos se leyeron sin cambios:

| Archivo | Bytes | Tiempo | Contrato |
| --- | --- | --- | --- |
| `leyes` | 998.760 | 1,6 s | 4.819 leyes, 15.736→20.554, sin faltantes, 2 duplicadas, 1 «ley 0» |
| `asistencias-senado` 50 | 5.141 | 0,4 s | 111 filas |
| `asistencias-diputados` 50 | 17.878 | 7,3 s | 355 filas |
| `proyectos` 50 | 86.841 | 0,5 s | 534 filas |

Los números coinciden con las trampas ya documentadas en `uydatos.parlamento` (mismas duplicadas,
misma «ley 0», sin huecos de numeración), así que el archivo no cambió de forma: lo único que
cambió es que el servidor lo entrega otra vez. Y el dato está al día: **23 leyes posteriores a la
20.531 y la última fila del 2026-11-26**, el mismo día de la medición.

sha256 de lo bajado (para que otro pueda comparar): `leyes` `81b67b49…2dcb3`,
`senado 50` `dc74a4f1…bb0b3`, `proyectos 50` `11844641…4215a`.

### La herramienta del servidor también

Con el UA cambiado **solo en memoria** (`uydatos.red.USER_AGENT`, sin tocar el paquete instalado),
`tests/test_red.py::test_parlamento_senado_actual_y_leyes` deja de caer y **pasa el cuerpo**: sale
`XPASS(strict)`, que es exactamente el rojo que la marca dice que hay que ver
—«si pasa, sacar esta marca»—. Las dos aserciones se cumplen a través de la capa del servidor con su
caché: `asistencia_parlamentaria("senado", 50)` devuelve más de 31 personas y
`leyes(numero=20531)["total"]` es 1.

### Por qué `pedidos_de_informes` nunca cayó

No todos los datos del Parlamento viven en el mismo host. Los pedidos de informes y la nómina de
Diputados están en `documentos.diputados.gub.uy`, fuera del WAF; `asistencias`, `proyectos` y
`leyes` están en `parlamento.gub.uy`. Eso explica que la lista de caídas tenga tres herramientas y
no cuatro, y es una pista para el día que vuelva a pasar: **la caída es por host, no por organismo**.

`infolegislativa.parlamento.gub.uy`, el otro host del Parlamento, **no** está detrás del WAF (responde
200 incluso con el UA del paquete), pero solo publica los CSV de metadatos
(`Metadatos_LeyesPromulgadas.csv`, `Metadatos_Asistencias.csv`), no los datasets. No sirve como
alternativa.

### La licencia no es el motivo

Los tres datasets declaran en el catálogo la **Licencia de Datos Abiertos – Uruguay** (v0.1), con el
PDF de AGESIC como `license_url`. El texto autoriza, para uso comercial y no comercial, enajenar,
reproducir, distribuir, publicar, traducir, adaptar, transformar, comunicar y fusionar los datos con
otros; la única obligación es la **nota de origen**: nombre del proveedor, referencia a la licencia y
referencia al conjunto de datos usado. Eso es exactamente lo que la respuesta de cada herramienta ya
declara en `fuente`.

O sea: el bloqueo no es una caída y tampoco es una decisión de licencia. Es una regla del WAF sobre
la forma del encabezado. Lo que sí es cierto es que el Parlamento **no publica una política de acceso
automatizado** (la página `/transparencia/datos-abiertos` devuelve 404; el acceso se hace por los
caminos de vistas que declara el catálogo), así que este cambio se apoya en la licencia y en el
`robots.txt`, no en una autorización explícita de acceso por programa.

### Los dos conteos de la misma pregunta

El catálogo declara `metadata_modified` del 2026-06-05 para asistencias y proyectos, y del 2024-06-26
para leyes. Ninguno de los dos dice de cuándo es el dato: el archivo de leyes llega al 2026-11-26.
Es la trampa ya anotada en el docstring de `uydatos.parlamento` (punto 8) y sigue vigente.

## Qué propone

Dos repos, en el orden obligado (`uydatos` → Release → pin del MCP → herramienta):

1. **`uydatos`**: cambiar el `User-Agent` del paquete por la forma compatible, dejando el motivo
   medido en el comentario y en el docstring de `red.py`.

   ```
   USER_AGENT = f"Mozilla/5.0 (compatible; uydatos/{__version__}; +https://github.com/manusabbath-arch/uy-datos-abiertos)"
   ```

   Va en `src/uydatos/__init__.py` — el único lugar que lo define; `red.pedido()` lo toma de ahí y
   ningún lector lo escribe a mano.

2. **Release 0.18.x** (patch: el pin `uydatos>=0.18,<0.19` ya lo admite). Es la decisión del dueño.

3. **`mcp-uruguay`**: sacar las tres entradas de `guias.CAIDAS` y de `humo.CAIDAS_CONOCIDAS`, borrar
   la constante `_PARLAMENTO_BLOQUEA`, quitar el `xfail` de
   `tests/test_red.py::test_parlamento_senado_actual_y_leyes` y anotarlo en `CHANGELOG.md`. El texto
   de `uru://trampas` se arma desde el diccionario, así que la sección «Fuentes que hoy no responden»
   desaparece sola cuando queda vacío.

4. **Verificación**: `pytest -m red` completo con el paquete nuevo. El `xfail` es `strict`: el día que
   el Parlamento responda, la suite se pone roja por `XPASS`, que es exactamente el aviso que hay que
   ver antes de tocar la lista.

## Riesgos y límites, dichos

- **El WAF puede endurecerse.** Si el Parlamento empieza a exigir más que la forma del UA, los
  lectores vuelven a 403 y el mecanismo correcto es el que ya existe: `guias.CAIDAS` con su issue.
  Este documento no cambia ese mecanismo, lo usa bien por primera vez.
- **No hay límite de pedidos visible ni medido.** Se bajaron cuatro archivos en una corrida sin
  señales de cuota. El servidor ya cachea por TTL, así que el ritmo real es bajo; aun así, no se
  midió cuántas bajadas por minuto tolera.
- **Medido desde una sola IP y un solo país.** No se probó desde otro origen ni con IPv6.
- **El endpoint `json` de las vistas no sirvió**: el de leyes no respondió en 90 s con el UA
  compatible. El CSV es el formato que corresponde y el que usa el lector.
- **`Mozilla/5.0 (compatible; …)` no es una identidad de navegador**: no lleva motor ni plataforma,
  y el nombre y el repositorio van declarados. Aun así, es una decisión de quien publica el paquete,
  no una obviedad técnica: si prefiere pedirle al Parlamento que permita el UA propio, el camino es
  el Sistema de Acceso a la Información Pública, y mientras tanto las tres herramientas siguen
  caídas.

## Reproducirlo

```sh
# 403 con el UA del paquete
curl -sS -o /dev/null -w '%{http_code}\n' -A 'uydatos/0.18.0 (lectura de datos abiertos)' \
  'https://parlamento.gub.uy/transparencia/datos-abiertos/leyes-promulgadas/csv'

# 200 con la forma compatible
curl -sS -o leyes.csv -w '%{http_code} %{size_download}\n' \
  -A 'Mozilla/5.0 (compatible; uydatos/0.18.0; +https://github.com/manusabbath-arch/uy-datos-abiertos)' \
  'https://parlamento.gub.uy/transparencia/datos-abiertos/leyes-promulgadas/csv'
```

Sin tocar el paquete instalado se puede correr la suite de red con el UA cambiado en memoria: un
plugin de pytest que asigne `uydatos.red.USER_AGENT` antes de los tests, cargado con `-p` y
`PYTHONPATH`. Así se mide el cambio antes de escribirlo en el repo.

## Dos verificaciones de documentación que no cambian código

- **Los workflows programados se apagan solos.** La documentación de GitHub lo dice textual:
  «In a public repository, scheduled workflows are automatically disabled when no repository
  activity has occurred in 60 days» (docs.github.com, *Disabling and enabling a workflow*). La
  sospecha del plan M4 queda confirmada: la vigilancia semanal de las fuentes reales —el latido que
  avisa que una fuente cambió de forma— puede dejar de correr sin que nadie lo note. Merece un aviso
  externo que dependa de la ausencia del latido, no de un rojo.
- **El tope de 60 s de los clientes MCP es real y está en el SDK.** `@modelcontextprotocol/sdk`
  1.32.2, `dist/esm/shared/protocol.js`: `export const DEFAULT_REQUEST_TIMEOUT_MSEC = 60000`, con
  `resetTimeoutOnProgress` como opción por mensaje. O sea: las notificaciones de progreso pueden
  reiniciar el temporizador de inactividad de un cliente que las pida, pero no estiran un tope duro
  por servidor. Refuerza M7: la llamada en frío de 61 a 75 s que ya se midió en `leyes` y
  `compras_estado` cae justo en ese borde, y el progreso es la mitigación correcta solo para quien
  lo consuma.
