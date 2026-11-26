# Cambios

## 0.15.0 — sin publicar

- **Las instrucciones del servidor nombran `uru://trampas`.** El recurso existía, pero nada le decía al
  cliente que lo consultara. Un test lo cubre. No se midió si mejora las respuestas: `evals/evaluar.py`
  no entregaba al modelo las instrucciones ni los recursos del servidor.
- **La evaluación tiene un modo `guiado`.** Suma a las herramientas las instrucciones del servidor y la
  lectura de sus recursos; `con` y `sin` no cambian. Un `--modo` mal escrito ahora se rechaza: antes se
  corría sin el servidor. Probado con un cliente falso; no se ejecutaron evaluaciones pagas.
- **La frase sobre `uru://trampas` no mostró efecto medible.** Conjunto de desarrollo en `guiado` con
  `deepseek-v4.1-flash` (Ollama), 3 repeticiones, 114 corridas el 2026-11-26: 53/57 aciertos sin la
  frase y 54/57 con ella; leyeron algún recurso 51/57 y 53/57. Sin la frase el modelo ya leía el
  recurso. No dice nada sobre otros modelos ni clientes. La frase se mantiene.
- **Las 19 preguntas de desarrollo quedan confirmadas o resueltas por cálculo y reglas.** Las 12 que
  faltaban se buscaron en la fuente citada (varias son prensa); la del Frente Amplio se revisó a mano
  (la fuente dice 43,85, dentro de la tolerancia). `balotaje-2024-orsi-pct` falló 6/6: el servidor
  responde 49,77 (definitivo con observados) y la pregunta espera 49,84. Esa decisión sigue abierta.
- **La evaluación guarda el detalle también con modelos como `nombre:cloud`.** En Windows quedaba un
  archivo vacío.
- **`opentelemetry-api` 1.45.2** (dependencia de `mcp`) en `uv.lock`, por CVE-2026-126360.
- **Tres preguntas de desarrollo más:** el peso de la ciudad de Canelones en su departamento, el de los
  tres departamentos más poblados en el país y la comparación inválida entre el precio al público del
  gasoil y su paridad de importación. Con `deepseek-v4.1-flash`, 3 repeticiones: 0/9 sin el servidor,
  8/9 en `con` y 9/9 en `guiado`. Distinguen tener el servidor de no tenerlo; no alcanzan para medir
  diferencias entre `con` y `guiado`. La tabla de la medición anterior es sobre las 19 de antes.
- **Se confirmaron en la fuente 7 respuestas del conjunto reservado**, sin cambiar preguntas, esperados
  ni herramientas. Queda sin confirmar `trampa-pobreza-metodologia`, que no tiene una cifra que buscar.
  Las dos del balotaje usan, como la de desarrollo, cifras de prensa distintas del escrutinio
  definitivo con observados.
- **Correcciones de exactitud verificadas al integrar las PR #13 y #14.** La búsqueda del MIDES
  cuenta y omite por 30 días los indicadores cuya lectura fue rechazada. Las marcas se guardan por
  indicador con temporales únicos, para no perder actualizaciones concurrentes, y usan la fecha de
  Uruguay. Los resultados electorales explican la diferencia entre el escrutinio primario y el
  definitivo con observados. Las descripciones de herramientas se normalizan también en Python
  anterior a 3.13; un test limita su tamaño para que no crezca sin decisión explícita.
- **Degradación y procedencia del censo.** Si falla uno de los dos tabulados, se conserva el otro;
  cada ausencia se avisa por separado. Los tabulados llevan su URL en `procedencia`, y las capas
  cartográficas ya cargadas en memoria también quedan registradas como respaldo.
- **Evaluación reservada intacta.** No se modifican preguntas de balotaje ni el conjunto reservado.
  La tanda posterior de población corrige la cifra de Paysandú del conjunto de desarrollo, con la
  publicación vigente del INE como respaldo. No se declara una mejora de puntuación ni se ejecutan
  evaluaciones pagas.
- **Revisión de seguridad y recuperación.** Los avisos de tabulados ausentes no interpolan errores
  crudos que pueden contener rutas locales: informan un motivo controlado (acceso o formato). Una
  lectura válida del MIDES retira inmediatamente la marca de rechazo, también para el registro
  anterior; la búsqueda no afirma que todo rechazo sea un formato viejo permanente.

- **`clima` (INIA) y `observaciones_inumet` marcan los días dudosos, sin descartar ninguno.** Misma forma que
  `nivel_rio_ina`: por serie, `pruebas`, `marcas`, `marcadas` (hasta 20) y `marcadas_omitidas`. `clima` marca
  `tmax`, `tmin` y `lluvia_mm`; `observaciones_inumet` marca temperatura y presión (rango, plano, sin_dato),
  humedad promedio y mínima (igual), humedad máxima y lluvia (sin `plano`). **`plano` solo donde el historial
  real no tiene rachas de 6 días iguales**: la tmax y la tmin de INIA nunca repitieron más de 3 días en 56
  años, pero la lluvia tiene 1.028 rachas de 6 o más días en 0 mm (53% de los días) y la humedad máxima
  estuvo en 100 durante 27 días seguidos (saturación). Combinaciones sin cotas medidas (la suma de
  temperaturas, el viento) no traen `calidad`. Medido sobre 2025 en Salto: ninguna lectura marcada por rango ni
  por plano, solo `sin_dato` en INUMET (10 días de 365; 22 en lluvia), que ya se veía como `valor: null`; la
  respuesta pesa 1% más en INIA y 2,7% en INUMET. Limitación: en datos reales no apareció ningún defecto de
  estas fuentes, así que lo medido es la ausencia de falsos positivos, no una detección.
- **`nivel_rio_ina` marca las lecturas dudosas, sin descartar ninguna.** La respuesta trae `calidad`:
  `pruebas`, el conteo `marcas` (`ok`, `rango`, `plano`) y las `marcadas` (hasta 20; si hay más,
  `marcadas_omitidas` dice cuántas). Usa `uydatos.calidad` (0.18). `rango` son cotas de sensatez por
  escala, medidas sobre el historial completo; `plano` es el mismo valor seis veces seguidas, un sensor
  trabado. Medido con datos reales: Salto Grande Abajo (altura) tiene 15.029 de 25.301 lecturas planas,
  todas de 2016 (meses de 0, 1 y 2 clavados), y Salto Grande Arriba (el embalse, ~34,5 m) tiene 76 lecturas
  en 0,0 o casi entre 2009 y 2020. **No se prueba el salto entre lecturas**: aguas abajo de la represa un
  río en crecida se mueve 2,5 m entre dos lecturas (p99 del cambio; mediana 0,34 m) y el desvío mediano
  contra los vecinos es unas 5 veces el del embalse, así que cualquier umbral marcaría la operación de la
  represa como error. `sin_dato` tampoco: el lector rechaza filas vacías y un hueco es una fila que no existe.
  Requiere `uydatos>=0.18`.
- **Cada respuesta puede llevar el sha256 de las copias que la respaldan.** Las herramientas que leen
  un archivo de la caché agregan `procedencia`: por copia, el `archivo` (relativo a la caché, nunca la
  ruta del disco del servidor), su `sha256`, `bajado` y `bytes`, y la `url` cuando la herramienta la
  conoce. Es lo que permite verificar un número contra los bytes exactos que leyó el servidor en vez
  de creerle a la respuesta. El campo es opcional y va en la salida, no en las definiciones: el
  presupuesto de herramientas no se mueve. El hash se calcula una vez por copia (430 ms sobre los
  122 MB de OSE, medido; después se recuerda mientras el archivo no cambie).
- **Cada descarga usa su propio temporal.** `cache.archivo`, `cache.sg_lecturas` y `calidad_agua`
  escribían el mismo `<archivo>.nuevo`: dos clientes que comparten la caché —o el servidor en modo
  remoto, donde la caché es compartida por diseño— podían publicar la copia a medio escribir del
  otro. Ahora cada bajada crea un temporal único junto al archivo (`cache._temporal`), y
  `diagnostico` no lista ninguna de las dos formas de temporal (`<archivo>.XXXX.nuevo` y las
  carpetas `.nuevo-*` del BCU, que antes se colaban como copias).
- **`localidad` trae la población oficial del Censo 2023** (`poblacion_oficial_2023` por localidad y
  `departamentos` con la población oficial de cada departamento), de los tabulados del INE que lee
  `uydatos.censo` (cuadros 12 y 13, datos ponderados). `poblacion_2023` sigue siendo la de la capa
  cartográfica: ciudad de Salto 114.043 en la capa y 112.527 oficial. Si el tabulado no se puede bajar,
  la herramienta responde igual y lo dice en la nota. Se conserva `uydatos>=0.18,<0.19` y se agrega
  el extra `hojas` para leer los tabulados publicados.
- **`ubicar_punto` trae la población oficial del Censo 2023 de la localidad.** Antes la respuesta
  llevaba solo `poblacion_2023`, la de la capa cartográfica, así que el servidor daba dos cifras para
  la misma ciudad según la herramienta: 114.043 en `ubicar_punto` y 112.527 en `localidad`. Ahora la
  localidad del punto trae también `poblacion_oficial_2023` (el tabulado del INE, la que se cita) y la
  nota dice cuál es cuál; la `fuente` suma el Censo cuando se pudo leer. Si el tabulado no se puede
  bajar, la herramienta responde igual, con la cifra en `null` y el motivo en la nota. Medido el
  2026-11-26 en el centro de Salto: 114.043 en la capa y 112.527 oficial, igual que `localidad`.
- **`localidad` sin argumentos responde por el país: `poblacion_oficial_total`, los 19 departamentos y
  las localidades más pobladas.** Antes una llamada vacía era un error, así que «¿cuál es la población
  de Uruguay según el Censo 2023?» no tenía herramienta que la respondiera: la pregunta está en el
  conjunto de desarrollo de la eval (`censo-2023-total`) esperando `localidad`. El total es la suma de
  los 19 departamentos del cuadro 12 (3.499.451), **no** la de las localidades (3.499.215): 236
  personas están en filas sin localidad (situación de calle y hogares). Si el cuadro 12 no trae todos
  los departamentos de la capa, el total va en `null` en vez de publicar una suma parcial. Medido el
  2026-11-26 contra los tabulados reales.
- **`herramientas.py` (2.680 líneas) pasa a ser un paquete con un módulo por dominio** (`monedas`,
  `combustibles`, `rio_y_clima`, `territorio`, `estado`, `agua`, `sinred` y `comun`; el más grande tiene 717
  líneas). **Sin cambios para quien usa el servidor ni para quien importa `herramientas`**: el paquete
  reexporta las mismas funciones, tipos y constantes. El código se movió textualmente con un script, y se
  verificó que los esquemas de entrada y salida de las 31 herramientas, `docs/herramientas.md` y
  `manifest.json` quedaron idénticos.

## 0.14.0 — 2026-11-16

- **`calidad_agua`: la calidad del agua potable de OSE**, por localidad y trimestre desde 2017
  (coliformes totales, E. coli, pH, turbidez, color verdadero y olor), sobre `uydatos.ose`. Un `<5`
  es un límite de detección y va contado aparte: nunca entra al mínimo ni al máximo de las
  mediciones, y no se promedia. Los valores con el signo al revés (`>0,2`) se cuentan, no se
  corrigen. `muestras` cuenta muestras y `analisis` cuenta filas, porque una muestra puede pasar por
  más de un laboratorio. Los 122 MB se bajan una vez y se validan enteros; vencida la copia (30
  días), solo se vuelven a bajar si CKAN declara otro tamaño.
- **`nivel_rio_ina`: el río Uruguay en las escalas de Prefectura**, del sistema de alerta del INA
  (`uydatos.ina`): altura o caudal de Concordia (desde 1931) y de Salto Grande Arriba y Abajo, con
  los niveles de alerta, evacuación y aguas bajas de la escala. Hasta 400 días da un punto por día;
  más largo, uno por mes. **`dias_de_atraso` y un aviso en la nota** cuando la última lectura tiene
  más de una semana: el caudal de Concordia viene con meses de atraso en la fuente.
- El prompt `el_rio_en_salto` suma la escala de Concordia y sus niveles de alerta, sin mezclar su
  altura con la de la CTM.
- **TLS con el almacén de certificados del sistema** (`truststore`, solo en el proceso del servidor):
  en Windows, la primera llamada a `datos.ose.com.uy` falló con `CERTIFICATE_VERIFY_FAILED` porque
  Python no ve las raíces que el sistema baja a demanda (probado el 16/11/2026 en una máquina con red).
  Es el mismo arreglo que usa pip, y le importa sobre todo a quien instala la extensión `.mcpb`.
- **El mínimo de `uydatos` sube a 0.17** (`>=0.17,<0.18`), que trae `ose` (0.16) e `ina` (0.17).
- README: «Por qué estas cifras se pueden citar» y «No es oficial».
- **Extensión de Claude Desktop (`.mcpb`), adjunta a cada Release**: se instala con doble clic y
  Claude Desktop resuelve Python y las dependencias (tipo `uv` de MCPB 0.4): quien la usa no necesita
  ni Python ni uv. `manifest.json` se genera desde el servidor (`python -m mcp_uruguay.manifiesto`) y
  un test falla si quedó viejo. Probado: empaquetado con `@anthropic-ai/mcpb` 2.1.2, descomprimido y
  corrido como lo corre Claude Desktop, con un cliente MCP por stdio (31 herramientas, una llamada real).
- **La evaluación de exactitud** (`evals/`): 30 preguntas sobre 13 herramientas, con respuesta oficial
  (elecciones nacionales y departamentales, censo, inflación de Argentina y Brasil, la UI, combustibles,
  leyes) o calculable (semana ISO, dígito de la cédula), y 5 trampas donde lo correcto es avisar y no dar
  un número (un domingo sin cotización, un `<0,2` que no se promedia, un caudal atrasado, dos metodologías
  de pobreza, un ítem que domina las compras del Estado). `evals/confirmar.py` baja cada fuente y marca
  como confirmada solo la cifra que encuentra escrita. Se corren con y sin el servidor, con un conjunto `reservado` que no se mira al ajustar, y se
  mide acierto, llamadas, errores de herramienta y tokens. La respuesta esperada sale siempre de la fuente
  oficial, nunca de este servidor. Necesita una clave de la API de Claude: ver `evals/README.md`.
- **`scripts/publicar.sh`**: crea la Release con las notas del CHANGELOG, después de ruff, los tests y
  de comprobar que `server.json` dice la misma versión. Sin `--de-verdad` solo simula. El trabajo
  `sin-publicar` del CI avisa cuando la versión de `main` no está en PyPI; no publica.
- **`leyes`, `asistencia_parlamentaria` y `proyectos_parlamento` no responden**: `parlamento.gub.uy`
  devuelve `403` a los clientes automáticos desde fines de octubre de 2026
  ([issue #2](https://github.com/manusabbath-arch/mcp-uruguay/issues/2)). El arreglo no está en este
  servidor; lo que cambia es que ahora lo dice:
  - **Cambio visible para clientes: el texto del error.** Un rechazo de la fuente (4xx) ya no termina
    en «Probar de nuevo más tarde», que mandaba al agente a reintentar en vano: dice «La fuente
    rechazó el pedido: … No se arregla reintentando». Los cortes y los 5xx siguen como antes.
  - Las fuentes que se saben caídas están en `guias.CAIDAS`: su estado va en el error de la
    herramienta y en una sección nueva de `uru://trampas`.
- **Arreglo: una descarga cortada volvía como «Error executing tool», sin motivo.** `IncompleteRead`
  no es un `OSError` y se escapaba del manejo de errores de red. Lo encontró el aviso nuevo en su
  primera corrida: `compras_estado` se cortó a los 200 segundos con 25 de 27 MB bajados
  ([issue #5](https://github.com/manusabbath-arch/mcp-uruguay/issues/5)). Ahora dice que no se pudo
  consultar la fuente y que se puede reintentar; la copia cortada no queda en la caché.
- **La corrida semanal abre un issue cuando falla** (trabajo `avisar` de `tests.yml`), o comenta el
  que ya esté abierto. Falló tres lunes seguidos, del 26/10 al 09/11, sin que nadie lo viera.
- **Una caída conocida no pone la corrida en rojo**: `scripts/humo.py` la informa como `CAIDA` y el
  test de red del Parlamento es un `xfail` estricto. El día que la fuente vuelva, la corrida falla
  con `VOLVIO` para que se saque de la lista.

## 0.13.5 — 2026-11-16

- **La primera llamada con la caché fría ya no es un silencio de uno a minuto y medio.** Con la caché
  vacía, `clima` tardó 81 s y `compras_estado` 88 s (medido el 16/11/2026); muchos clientes MCP cortan
  cerca de los 60 s y no había forma de distinguir una llamada lenta de una colgada.
  - Mientras una herramienta trabaja, el servidor manda un **aviso de progreso cada 10 s** (no hace nada
    si el cliente no lo pidió). No cambia lo que devuelve ninguna herramienta.
  - **Comando nuevo, `mcp-uruguay --precalentar`**: baja de una vez las fuentes lentas y dice qué pasó con
    cada una. Una fuente caída no frena a las demás; lo ya declarado caído no hace fallar el comando.
- **La cadena de publicación, endurecida** (sin cambios para quien usa el servidor): las actions están
  fijadas por SHA y no por etiqueta; el hash esperado del binario `mcp-publisher` está escrito en
  `publicar.yml` (antes se comparaba contra un `checksums.txt` bajado del mismo release, que solo
  prueba que la descarga no se cortó); la publicación corre en el entorno `pypi`, con revisor
  requerido y limitado a etiquetas `v*`; y Dependabot propone cada semana las actions y `uv.lock`.
  **Una Release nueva queda esperando la aprobación en Actions antes de subir a PyPI.**
- **La corrida semanal avisa antes de que GitHub la apague.** A los 60 días sin actividad GitHub
  desactiva los workflows programados de un repo público y ningún trabajo puede avisar que dejó de
  correr. El trabajo `inactividad` de `tests.yml` abre un issue (etiqueta `inactividad`) cuando el
  último commit tiene 40 días o más; `simular_inactividad` lo prueba con `workflow_dispatch`.

## 0.13.4 — 2026-11-16

- **Cambio visible para clientes: `bajado` ahora lleva el desplazamiento horario.** Era la hora local
  de la máquina, sin zona (`2026-10-09T20:45`); ahora es la de Uruguay en ISO 8601
  (`2026-10-09T20:45-03:00`). Quien lo compare como texto con el formato viejo tiene que leer la zona.
- **Arreglo: «hoy» ya no depende de la zona de la máquina.** Con el servidor en UTC, entre las 21:00 y
  la medianoche de Montevideo «hoy» era mañana: el último día del mes, el mes en curso se trataba como
  cerrado y se pedía el siguiente. Ahora todo sale de `cache.ahora()` (America/Montevideo; si la
  máquina no tiene la base de zonas, UTC-3 fijo, que es lo mismo desde 2015).
- **Arreglo: `bcu_serie` ya no borra la copia buena antes de bajar la nueva.** Si la descarga fallaba,
  el mes se quedaba sin copia aunque la anterior servía; contradecía la regla del README («una
  descarga ilegible nunca reemplaza a una copia buena»). Ahora baja aparte y solo la pone en su lugar
  si se lee. Cada bajada usa su carpeta temporal: dos clientes MCP en la misma caché ya no se pisan, y
  en Windows el reemplazo y la lectura reintentan si otro proceso tiene el archivo abierto.
- **Una copia vencida que no se pudo refrescar ahora avisa.** La respuesta trae `copia_vencida: true` y
  un `aviso` con la fecha de esa copia. Antes el agente veía un `bajado` viejo y nada que dijera que se
  intentó refrescar. Aplica a las 25 herramientas que traen `bajado`; los campos son opcionales y solo
  aparecen cuando pasa.
## 0.13.3 — 2026-11-16

- **`calidad_agua`: la calidad del agua potable de OSE**, por localidad y trimestre desde 2017
  (coliformes totales, E. coli, pH, turbidez, color verdadero y olor), sobre `uydatos.ose`. Un `<5`
  es un límite de detección y va contado aparte: nunca entra al mínimo ni al máximo de las
  mediciones, y no se promedia. Los valores con el signo al revés (`>0,2`) se cuentan, no se
  corrigen. `muestras` cuenta muestras y `analisis` cuenta filas, porque una muestra puede pasar por
  más de un laboratorio. Los 122 MB se bajan una vez y se validan enteros; vencida la copia (30
  días), solo se vuelven a bajar si CKAN declara otro tamaño.
- **`nivel_rio_ina`: el río Uruguay en las escalas de Prefectura**, del sistema de alerta del INA
  (`uydatos.ina`): altura o caudal de Concordia (desde 1931) y de Salto Grande Arriba y Abajo, con
  los niveles de alerta, evacuación y aguas bajas de la escala. Hasta 400 días da un punto por día;
  más largo, uno por mes. **`dias_de_atraso` y un aviso en la nota** cuando la última lectura tiene
  más de una semana: el caudal de Concordia viene con meses de atraso en la fuente.
- El prompt `el_rio_en_salto` suma la escala de Concordia y sus niveles de alerta, sin mezclar su
  altura con la de la CTM.
- **TLS con el almacén de certificados del sistema** (`truststore`, solo en el proceso del servidor):
  en Windows, la primera llamada a `datos.ose.com.uy` falló con `CERTIFICATE_VERIFY_FAILED` porque
  Python no ve las raíces que el sistema baja a demanda (probado el 16/11/2026 en una máquina con red).
  Es el mismo arreglo que usa pip, y le importa sobre todo a quien instala la extensión `.mcpb`.
- **El mínimo de `uydatos` sube a 0.17** (`>=0.17,<0.18`), que trae `ose` (0.16) e `ina` (0.17).
- README: «Por qué estas cifras se pueden citar» y «No es oficial».
- **Extensión de Claude Desktop (`.mcpb`), adjunta a cada Release**: se instala con doble clic y
  Claude Desktop resuelve Python y las dependencias (tipo `uv` de MCPB 0.4): quien la usa no necesita
  ni Python ni uv. `manifest.json` se genera desde el servidor (`python -m mcp_uruguay.manifiesto`) y
  un test falla si quedó viejo. Probado: empaquetado con `@anthropic-ai/mcpb` 2.1.2, descomprimido y
  corrido como lo corre Claude Desktop, con un cliente MCP por stdio (31 herramientas, una llamada real).
- **La evaluación de exactitud** (`evals/`): 30 preguntas sobre 13 herramientas, con respuesta oficial
  (elecciones nacionales y departamentales, censo, inflación de Argentina y Brasil, la UI, combustibles,
  leyes) o calculable (semana ISO, dígito de la cédula), y 5 trampas donde lo correcto es avisar y no dar
  un número (un domingo sin cotización, un `<0,2` que no se promedia, un caudal atrasado, dos metodologías
  de pobreza, un ítem que domina las compras del Estado). `evals/confirmar.py` baja cada fuente y marca
  como confirmada solo la cifra que encuentra escrita. Se corren con y sin el servidor, con un conjunto `reservado` que no se mira al ajustar, y se
  mide acierto, llamadas, errores de herramienta y tokens. La respuesta esperada sale siempre de la fuente
  oficial, nunca de este servidor. Necesita una clave de la API de Claude: ver `evals/README.md`.
- **`scripts/publicar.sh`**: crea la Release con las notas del CHANGELOG, después de ruff, los tests y
  de comprobar que `server.json` dice la misma versión. Sin `--de-verdad` solo simula. El trabajo
  `sin-publicar` del CI avisa cuando la versión de `main` no está en PyPI; no publica.
- **`leyes`, `asistencia_parlamentaria` y `proyectos_parlamento` no responden**: `parlamento.gub.uy`
  devuelve `403` a los clientes automáticos desde fines de octubre de 2026
  ([issue #2](https://github.com/manusabbath-arch/mcp-uruguay/issues/2)). El arreglo no está en este
  servidor; lo que cambia es que ahora lo dice:
  - **Cambio visible para clientes: el texto del error.** Un rechazo de la fuente (4xx) ya no termina
    en «Probar de nuevo más tarde», que mandaba al agente a reintentar en vano: dice «La fuente
    rechazó el pedido: … No se arregla reintentando». Los cortes y los 5xx siguen como antes.
  - Las fuentes que se saben caídas están en `guias.CAIDAS`: su estado va en el error de la
    herramienta y en una sección nueva de `uru://trampas`.
- **Arreglo: una descarga cortada volvía como «Error executing tool», sin motivo.** `IncompleteRead`
  no es un `OSError` y se escapaba del manejo de errores de red. Lo encontró el aviso nuevo en su
  primera corrida: `compras_estado` se cortó a los 200 segundos con 25 de 27 MB bajados
  ([issue #5](https://github.com/manusabbath-arch/mcp-uruguay/issues/5)). Ahora dice que no se pudo
  consultar la fuente y que se puede reintentar; la copia cortada no queda en la caché.
- **La corrida semanal abre un issue cuando falla** (trabajo `avisar` de `tests.yml`), o comenta el
  que ya esté abierto. Falló tres lunes seguidos, del 26/10 al 09/11, sin que nadie lo viera.
- **Una caída conocida no pone la corrida en rojo**: `scripts/humo.py` la informa como `CAIDA` y el
  test de red del Parlamento es un `xfail` estricto. El día que la fuente vuelva, la corrida falla
  con `VOLVIO` para que se saque de la lista.

## 0.13.2 — 2026-10-22

- **El mínimo de `uydatos` sube a 0.15.1** (`>=0.15.1,<0.16`): 0.15 compara el informe de las fuentes
  contra una línea de base versionada y 0.15.1 deja de contar como sanas a las fuentes que no se
  midieron. **Ninguna herramienta de este servidor cambia**: no usa `revisiones` ni `verificar`, y los
  128 tests y los 16 de red pasan contra 0.15.1.

## 0.13.1 — 2026-10-19

- **El mínimo de `uydatos` sube a 0.14** (`>=0.14,<0.15`): esa versión trae `verificar` (el contrato
  de forma de las fuentes), `revisiones.revisadas` (el pasado reescrito), `errores.DatosInvalidos`
  —base de los diecinueve rechazos— y la guarda de PII que sacó un RUT real del paquete.
  **Ninguna herramienta de este servidor cambia**: los 128 tests pasan contra 0.14.0 resuelto de
  PyPI, no contra un árbol local, y el `except bcu.BcuInvalido` de `cache.py` sigue funcionando
  porque `DatosInvalidos` hereda de `ValueError`.

## 0.13.0 — 2026-10-14

- **Cinco prompts y cuatro recursos**.
  Los prompts son recetas con el orden de las herramientas y sus trampas (combustible en pesos constantes, clima de
  Salto, el río, compras del Estado, real o nominal); los recursos son `uru://trampas`, `uru://fuentes`,
  `uru://inumet/estaciones` y `uru://bcu/monedas`. Los prompts no se limitan a decir qué herramienta llamar: dicen qué desconfiar. Un test falla si un prompt nombra una herramienta que no existe o
  si una herramienta queda sin su trampa.
- **La cobertura se mide en el CI** (`pytest-cov`, hoy 91%) y falla si baja del 88%.

## 0.12.0 — 2026-10-14

- **El mínimo de `uydatos` sube a 0.12.1**, que arregla `combustible_ancap` y `ventas_combustible`: ANCAP
  republicó sus datasets el 12/10/26 y la URL fija daba 404.
- **Nueva: `observaciones_inumet`**, sobre `uydatos.inumet` (publicado desde `uydatos`
  0.12.0): las observaciones horarias de INUMET en siete estaciones, agregadas al **día local**
  (la fuente publica en UTC; Uruguay es UTC-3). Sin estación, la cobertura de cada una; con estación,
  fechas y agregación, el valor de cada día. La agregación es obligatoria, un día al que le falta
  alguna observación devuelve `null` en vez de un total parcial, y el viento se mide contra sus 12
  observaciones diarias, no contra 24. La insolación (diaria, con valores imposibles declarados en
  `uydatos`) no se expone.

## 0.11.0 — 2026-10-11

- **Nueva: `pedidos_de_informes`**, sobre `uydatos.parlamento` 0.12: los pedidos de informes de
  Diputados (artículo 118 de la Constitución) de la legislatura actual, cuántos contestó cada
  organismo sobre los que ya cumplieron el plazo de 45 días, por semestre y por partido de los
  autores, con el enlace al oficio y a la respuesta. `presentados_hasta` compara una misma cohorte,
  porque las respuestas llegan tarde: de los pedidos del primer semestre de 2025 está contestado el
  92,5%, de los del segundo de 2026 el 31,9%.
- Depende de `uydatos>=0.12,<0.13`.

## 0.10.1 — 2026-10-11

- **Arreglo: el servidor se anunciaba como 0.7.0** a los clientes MCP desde la 0.7.0 hasta la 0.10.0,
  porque la versión era una constante que nadie actualizó. Ahora sale del paquete instalado, y
  `tests/test_version.py` la ata a `pyproject.toml`.
- **Nuevo: `scripts/humo.py`**, una prueba de humo del paquete **tal como se instala desde PyPI**:
  llama a las 27 herramientas contra las fuentes reales. La corre cada semana el job
  `instalado-desde-pypi` (Python 3.10 y 3.13) y avisa si alguna herramienta no responde. Medido al
  escribirla: 26 de 27 en 3.10 y en 3.13; la que faltó fue `leyes`, porque el Parlamento devolvía
  un archivo vacío para cualquier cliente, no por el paquete.

## 0.10.0 — 2026-10-11

- **Nueva: `paridad_combustibles`**, sobre `uydatos.ursea`: el precio ex planta de ANCAP contra el
  precio de paridad de importación de URSEA, **los dos sin impuestos**, mes a mes desde 2022, para
  la Súper 95, la Premium 97 y los gasoils 50-S y 10-S. Sin producto, el último mes y el promedio de
  12 meses de cada uno; con producto, la serie y el desglose del último PPI desde el FOB hasta los
  impuestos. La respuesta declara el `metodo` (qué nivel de precio y qué mes se comparan) porque es
  una construcción del servidor y no una cifra oficial. El GLP no se compara: un archivo lo da en
  $/litro y el otro en $/kg.
- Depende de `uydatos>=0.11,<0.12`.

## 0.9.0 — 2026-10-11

- **Nuevas: `buscar_indicador_social` e `indicador_social`**, sobre `uydatos.observatorio`: los
  ~1.260 indicadores sociales del MIDES (pobreza, empleo, educación, vivienda, salud...) leídos de su
  página viva en gub.uy, con la unidad, la forma de cálculo y la fuente del dato. **No se usan los
  del catálogo de datos abiertos porque esa copia quedó en 2019**; la página viva llega a 2024. La
  respuesta lleva los avisos del lector: filas «Total» mezcladas, mapas por departamento que muestran
  un solo año (`parcial`, con los períodos que faltan) y fichas que no coinciden con la tabla. `filtro`
  acota por valor de dimensión (`Salto`, `Mujeres,Pobre`); más de 80 filas se recortan con aviso.
- Depende de `uydatos>=0.10,<0.11`.

## 0.8.1 — 2026-10-10

- **Arreglo para Python 3.10 y 3.11**: desde la 0.3.0, en esas versiones las herramientas no
  declaraban su esquema de salida y `diagnostico` fallaba. Los tipos de salida eran `typing.TypedDict`,
  que pydantic sólo acepta desde Python 3.12; ahora salen de `typing_extensions`, que pasa a ser
  dependencia explícita. En 3.12 y posteriores nada cambia.
- **Por qué se publicó así cinco versiones**: el CI de cada push fallaba en 3.10 y 3.11, pero la
  publicación corría los tests sólo en 3.13. Ahora los corre en 3.10 y en 3.13, y no publica si fallan.
- `docs/herramientas.md` se genera igual en cualquier versión de Python (desde la 3.13 el compilador
  quita la sangría de los docstrings; ahora se normaliza siempre).

## 0.8.0 — 2026-10-10

- **Nueva: `ventas_combustible`**, sobre `uydatos.ancap_ventas`: la cantidad vendida por ANCAP de cada
  combustible, por mes y mercado. Sin `linea` lista los productos con su familia y su unidad (el
  petcoke viene en toneladas y el resto en miles de m³: no se suman) y los meses que la fuente no
  publicó; con `linea`, la serie y el total de cada año **con cuántos meses lo forman**, porque el
  archivo tiene huecos (2024 sin octubre, 2025 sin agosto a octubre) y un año de 9 meses no se compara
  con uno de 12. `QUEROSENO` y `QUEROSENOS` quedan separados: son de familias distintas.
- Depende de `uydatos>=0.9,<0.10`.

## 0.7.0 — 2026-10-10

- **Nuevas: `asistencia_parlamentaria`, `leyes` y `proyectos_parlamento`**, sobre `uydatos.parlamento`.
  La asistencia exige un mínimo de citaciones (hay 3 a 4 veces más personas que bancas, por los
  suplentes) y avisa de nombres repetidos, que pueden ser homónimos. Las leyes salen sin duplicados ni
  la «ley 0», con el enlace a IMPO. Un proyecto que aparece en dos legislaturas cuenta una vez.
- Depende de `uydatos>=0.8,<0.9`.

## 0.6.0 — 2026-10-10

- **Nuevo: `compras_estado`**: cuánto adjudicó el Estado en un año, en pesos (cada moneda con la
  cotización del día), por organismo o por texto de los ítems, con los organismos que más compraron y
  los mayores ítems. **Avisa cuando un solo ítem pasa del 20% del total**: en los datos de la ARCE un
  ítem es el 77% de lo adjudicado en pesos en 2024 y otro el 53% en 2025. No devuelve nombres de
  proveedores, que pueden ser personas físicas.
- Guarda de privacidad (idea de Hermes): falla si un archivo versionado cita internos; los nombres
  específicos van en un archivo local que git ignora.
- Depende de `uydatos>=0.7,<0.8`.

## 0.5.0 — 2026-10-10

- **Nuevo: `resultados_electorales`**: nacionales 2024, balotaje 2024 y departamentales 2025, del país
  o de un departamento, desde los datos por mesa de la Corte Electoral. Incluye los votos observados,
  que la Corte escruta en mesas especiales sin localidad, y lo dice en cada respuesta. Porcentajes
  sobre los votos emitidos, con ese nombre.
- Depende de `uydatos>=0.6,<0.7`.

## 0.4.0 — 2026-10-10

### Nuevo

- **`ubicar_punto`**: en qué departamento y localidad cae un punto, según los polígonos oficiales del
  INE, con la población 2023 de la localidad. Si cae en el campo, la localidad más cercana y la
  distancia; si cae en el mar o en un río limítrofe, lo dice. El límite contestado con Brasil se
  informa como tal, asignado a Artigas. Suma la dirección más cercana de IDE.uy con su distancia.
- **`localidad`**: población y viviendas 2023 por nombre (sin importar tildes). Un nombre que existe
  en varios departamentos —«San Antonio» está en Canelones, Salto y Rocha— devuelve todos; solo con
  el departamento, sus localidades de mayor a menor población.
- Depende de `uydatos>=0.4,<0.5`.

## 0.3.0 — 2026-10-10

### Nuevo

- **`nivel_rio`**: la altura del río en una estación de Salto Grande (por nombre o id), por día,
  con la última lectura, cuánto subió o bajó y la cobertura de lecturas.
- **`nivel_rio_comparado`**: los últimos días contra los mismos días de cada año desde 2017, y en
  qué lugar quedan. El 10/10/2026 la estación Salto estaba en el nivel más alto de los 10 años.
- **`variacion_real`**: variación nominal, inflación y variación real entre dos meses, con la UI,
  el IPC argentino o el IPCA brasileño.

### Corregido

- **Un mes bajado mientras corría quedaba incompleto para siempre.** La caché del BCU lo daba por
  cerrado apenas existía el archivo; ahora un mes se da por cerrado solo si se bajó después de
  terminar, y si no se vuelve a pedir una vez. Aplica también a las lecturas del río.
- Depende de `uydatos>=0.3,<0.4` (lecturas de Salto Grande).

### Cambiado

- Las trece herramientas declaran los campos de su salida, y hay una guarda que impide que vuelva
  a haber una que no lo haga. Sin eso, el modelo que llama tiene que adivinar los nombres.
- `clima_salto` y `clima_tendencia` se fusionaron en **`clima`**: sin fechas devuelve la tendencia
  y con `desde`/`hasta` los dias. Las dos preguntan lo mismo, y tener dos herramientas parecidas
  hace que el modelo elija mal. **Quita dos herramientas**, asi que la proxima version es 0.3.0.

## 0.2.1 — 2026-10-09

- Publicado en PyPI (`uvx mcp-uruguay`) y en el registro oficial de MCP como
  `io.github.manusabbath-arch/mcp-uruguay`, con trusted publishing al crear una Release.
- Depende de `uydatos` desde PyPI (`>=0.2.1,<0.3`) en vez de una etiqueta de GitHub.
- Insignias y un resumen en inglés en el README.

## 0.2.0 — 2026-10-09

- **Nueva herramienta: `geocodificar_direccion`**, sobre `uydatos.ideuy` (IDE.uy). Devuelve la
  calidad del resultado y no da coordenada cuando la API devuelve otra calle o el centro de la
  localidad.
- Pasa a `uydatos` v0.2.0.
- CI: tests en Python 3.10 a 3.13 y Windows, y una corrida semanal contra las fuentes reales.

## 0.1.0 — 2026-10-09

Primera versión: 12 herramientas de solo lectura (BCU, pesos constantes, INDEC, IBGE, ANCAP,
INIA, Salto Grande, RUT y cédula, semanas ISO y catálogo de datos abiertos).
