# Clientes potenciales, sus problemas y lo que ya existe

Fecha: 2026-11-27. Investigación de escritorio con Firecrawl, más mediciones propias. No incluye
entrevistas: cada problema es una hipótesis con evidencia escrita y hay que validarlo con una
persona antes de construir. Las citas son textuales y llevan su fuente.

Sirve como insumo de estrategia. Responde a cuatro preguntas: quién tiene el problema, qué ya
resolvemos, qué hicieron otros y qué solo podemos ofrecer nosotros, que es calidad garantizada.

## 0. Punto de partida medido

- **Descargas en PyPI** (pypistats, últimos 30 días): mcp-uruguay 896 y uydatos 1.330. La mayoría
  son de origen no identificado, es decir robots, espejos o el CI. Desde Windows, que es como se
  usa con Claude Desktop, hubo 12 descargas de mcp-uruguay en total.
- **GitHub, últimos 14 días:** 0 estrellas y 0 forks en los dos repos. mcp-uruguay tuvo 11
  visitantes únicos y uydatos 1.
- **Conclusión:** no hay usuarios identificados. Lo que sigue es para elegir a quién buscar.

## 1. Segmentos: problema, qué resolvemos, qué existe y dónde ganamos

### A. Administración y contadores de pymes: cotizaciones, UI, IPC, feriados y RUT

**Problema con evidencia.** La regla del tipo de cambio fiscal circula en al menos tres versiones
contradictorias, todas encontradas en una búsqueda:

| Quién | Qué dice |
|---|---|
| DGI, guía «Operaciones en moneda extranjera» (26/09/2023) | «tipo de cambio **interbancario del día anterior** a la operación. Si el día anterior no hubiese cotización, se deberá ir a la del último día hábil anterior» |
| DGI, comunicado de e-Factura | el campo A-111 «es el factor de conversión utilizado […] **no estableciéndose ninguna especificación**», con los ajustes fiscales en la declaración jurada |
| Guías privadas (cambio-uruguay.com, gro.com.uy, calculame.uy) | «la **compra del BROU** del día hábil anterior». Una agrega que e-Factura «controla» esa referencia, lo que contradice el comunicado de la DGI |
| Un software de facturación (MVD Gestiona, Montevideo COMM) | «dólar interbancario comprador informado por el BCU el día hábil inmediato anterior»; esa pregunta del foro suma 3.492 vistas |

A esto se suman preguntas recurrentes sobre el ajuste del alquiler (coeficiente URA o IPC, «7
errores frecuentes», pisoinmobiliario.com) y sobre cómo actualizar montos por IPC después del
cambio de base a octubre de 2022.

**Qué resolvemos hoy:**
- `cotizacion`: BCU, con feriados y sin inventar el sábado. Ya advierte: «qué cotización
  corresponde para un fin fiscal no lo decide esta herramienta».
- `pesos_constantes` y `variacion_real`.
- `validar_documento` (RUT y cédula).
- `uydatos.feriados`.

**Qué ya existe:**
- **datosuruguay.com:** 31 series (BCU, BROU cada 10 minutos, UI, UR, IPC, IMS, ICCV, coeficiente
  de alquileres, combustibles, UTE, salario mínimo y más). Es gratis, sin clave, CC-BY y vive de
  donaciones. Límite: 300 consultas por hora por IP.
- **Otros sitios:** micontador.com.uy, cambio-uruguay.com, calculame.uy y la calculadora de IPC
  del INE.
- **Librerías:** py_bcu (Python con zeep), cotizabcu (Python), cotizaciones-uruguay (TypeScript:
  BCU, BROU e Itaú), bcu-currency (PHP) y varios gists sobre el SOAP del BCU.
- **Otros servicios:** Frankfurter publica las series del BCU desde 2000; hay un módulo de Odoo y
  UruAPI, que reempaqueta datosuruguay.
- **Por MCP:** Datos UY/AR, pago a partir de 30 llamadas por día.

**Dónde ganamos y dónde no.** El acceso al número es un commodity gratuito. Competir ahí no tiene
sentido. La calidad sí es escasa: hoy nadie devuelve la cotización con la norma citada, el día
efectivamente usado y el motivo por el que se tomó ese día. Nadie advierte tampoco que la regla
depende de la fuente normativa que se consulte. Para este segmento, el producto de calidad es un
«dato fiscal con fundamento», no «el dólar de hoy».

**Validar:** preguntar a 3 contadores qué cotización usan, por qué, y si alguna vez una diferencia
les generó un ajuste o una observación.

### B. Compras públicas: compradores del Estado, sociedad civil y proveedores

**Problema con evidencia.** La consulta pública de ARCE (agosto a octubre de 2023, 14 respuestas: 9
compradores, 3 organizaciones de la sociedad civil y 2 ciudadanos) piden:
- «información sobre precios de referencia y proveedores según giro empresarial»;
- «Ofreciendo referencias de procesos anteriores ej. (referencia de precios)»;
- el 72 % prefiere datos desagregados, y la mitad de los recursos pedidos son «Ejemplos» y
  «Tutoriales».

La queja más precisa, de una organización de la sociedad civil:

> «se quiere analizar un tipo de compra y se encuentra que no está clasificada uniformemente, o
> las unidades de la compra se establecen de forma arbitraria o poco clara haciendo imposible
> comparaciones, o que sabemos que hay compras por fuera del universo de ARCE o que sólo cargan
> parcialmente los datos».

Y de un ciudadano: «Gráficas y cálculos agregados no sirven, porque la historia la está contando
el dueño del dato».

Problemas de calidad documentados por el registro de Open Contracting (revisión de 2021):
- hay JSON con cadenas multilínea que rompen el archivo;
- en las compras directas falta el bloque de licitación, así que hay que detectarlas por
  ausencia;
- no hay contratos, oferentes ni acuerdos marco, ni prórrogas;
- no es obligatorio publicar compras menores al 20 % del umbral de compra directa.

**Qué resolvemos hoy:** `compras_estado`. Lee la fuente primaria y detecta ítems imposibles.
Codex tiene un plan de «ficha de antecedentes para una compra real» (ver
`docs/observatorio-continuidad.md`).

**Qué ya existe:**
- el Observatorio de Compras de ARCE (agregado);
- el registro de Open Contracting, con descargas por año ya armadas (JSON, Excel y CSV; 189 MB
  en total desde 2017);
- un scraper del catálogo en Apify.

**Dónde ganamos.** Es el pedido más explícito y con más evidencia de toda la investigación: el
propio Estado lo pidió por escrito. Lo que falta es exactamente lo que el repo hace bien: unidades
normalizadas, comparabilidad declarada y rechazo con motivo cuando no se puede comparar. El
producto concreto es una ficha de precio de referencia por producto, con los casos excluidos y la
razón de cada exclusión.

**Validar:** una compra real de un comprador real (Intendencia de Salto u otro organismo), con la
ficha usada antes de adjudicar.

### C. Periodistas de datos, sociedad civil y tecnología cívica

**Problema con evidencia:**
- **Nadie responde por la calidad del catálogo.** El propio catálogo nacional lo declara: «La
  calidad de los datos publicados en el catálogo es responsabilidad de cada uno de los
  publicadores» (AGESIC, página «Acerca de»).
- **Enlaces rotos.** El scraper de Apify midió que 8 de 90 URL de descarga no se podían bajar.
  Nuestra verificación semanal encontró esta semana cinco fuentes rotas o alteradas: Parlamento,
  `leyes`, INUMET, sanciones y la ECH.

**Qué resolvemos hoy:**
- `buscar_datasets_catalogo`;
- `uydatos.verificar`, que mide 21 fuentes por semana en el CI;
- trampas documentadas por herramienta.

**Qué ya existe:**
- **Data Uruguay** (data.org.uy): unos 20 proyectos (ATuServicio, QueSabes, DondeReciclo, etc.),
  encuentros mensuales («Datos y Cogollos») y tareas abiertas en GitHub para voluntarios.
  Participó en las consultas de SIPC de 2026.
- **CAinfo:** acceso a la información y libertad de prensa.
- **ILDA, AbreLatam.**

**Dónde ganamos.** Un parte semanal de «qué fuente pública se rompió y cómo», con evidencia. Hoy
no lo publica nadie, y la sociedad civil es quien lo usa para reclamar ante los organismos. Este
segmento paga poco, pero difunde y le da legitimidad al resto.

**Validar:** presentarlo en un «Datos y Cogollos» y ver si alguien lo pide o lo cita.

### D. Investigación académica (ECH y microdatos)

**Problema:**
- Desde 2025 la ECH está en el catálogo ANDA (`www4.ine.gub.uy`), que nos responde 403 a todo.
- El paquete de R más usado, `ech` (calcita), cubre solo de 2011 a 2019. También existe `rECH`.

**Qué resolvemos hoy:** nada; el acceso está bloqueado.

**Lectura:** hay un hueco real (ECH 2020 en adelante en Python, con diseño muestral), pero
depende de un acceso que hoy no tenemos. Queda en espera hasta reprobar desde otra red.

### E. Comercio y distribución: precios de consumo

**Problema con evidencia:**
- **Consulta pública del SIPC** (Defensa del Consumidor, del 21/04 al 15/07/2026, 359
  respuestas, 38 % del interior). Las demandas que recogió: «Monitorear la evolución de los
  precios», «Incorporar información […] de alcance territorial» y «Facilitar el acceso a datos
  abiertos y generar reportes adaptados a los distintos perfiles de usuarios».
- **Prensa de Salto:** caída de ventas y costos en suba (ver el informe anterior).

**Qué resolvemos hoy:** nada publicado. Ya medimos lo siguiente:
- el CSV de 2026 tiene 20,3 millones de filas y llega hasta el 30/09;
- 23 comercios de Salto;
- se compararon 137 productos entre Salto y Montevideo.

**Qué ya existe:**
- **PreciosGub / precios.uy:** la app oficial, pensada para el consumidor, y un reporte mensual
  del MEF.
- **Cabacua:** según su sitio y El Observador, releva más de 380.000 precios por día, superó los
  40.000 usuarios en cuatro meses y se presenta como «un mismo motor para quien compra y para
  quien vende». Es competencia directa para un producto B2B.

**Dónde ganamos.** No en la app de consumo, donde ya hay jugadores con tracción. Sí en el análisis
territorial e histórico para quien vende: las series desde 2014, que pesan 1,5 GB por año y no
entran en una planilla. La validación puede hacerse en casa, con NG.

### F. Quienes construyen agentes de IA (usuarios directos de MCP)

**Problema:**
- Los clientes cortan las llamadas largas (alrededor de 60 s en Claude Desktop y Cursor).
- Hace falta instalar uv y usar una terminal, y eso explica las 12 instalaciones desde Windows.

**Qué ya existe:**
- Datos UY/AR (pago);
- opendata-latam (solo metadatos);
- los MCP de la Open Knowledge Foundation.

Detalle en `docs/2026-11-27-investigacion-externa.md`.

**Lectura:** es el canal, no el cliente. El que paga es alguno de los segmentos A, B o E. El
servidor MCP es la forma de entregarle el dato.

## 2. Quejas recolectadas, textuales

1. «se quiere analizar un tipo de compra y se encuentra que no está clasificada uniformemente, o
   las unidades de la compra se establecen de forma arbitraria» (organización de la sociedad
   civil, consulta de ARCE, 2023).
2. «Gráficas y cálculos agregados no sirven, porque la historia la está contando el dueño del
   dato» (ciudadano, ARCE, 2023).
3. «Contar con información sobre precios de referencia y proveedores según giro empresarial»
   (compradores, ARCE, 2023).
4. «sabemos que hay compras por fuera del universo de ARCE o que sólo cargan parcialmente los
   datos» (organización de la sociedad civil, ARCE, 2023).
5. «Los criterios de la canasta actual fueron establecidos hace varios años, lo que deriva en una
   herramienta con información limitada» (Defensa del Consumidor, consulta SIPC, 2026).
6. «Ante las consultas por parte de los contribuyentes en cuanto a qué tipo de cambio usar en
   Factura Electrónica…» (DGI, comunicado de e-Factura). Que la DGI haya tenido que emitirlo
   muestra que la duda es masiva.
7. «La calidad de los datos publicados en el catálogo es responsabilidad de cada uno de los
   publicadores» (AGESIC).
8. «Es responsabilidad del contribuyente verificar la cotización diaria» (soporte de MVD
   Gestiona). El software traslada el riesgo al usuario.

## 3. Know-how verificado (trampas que un producto de calidad tiene que manejar)

- **Tipo de cambio fiscal.** Hay tres versiones en circulación (sección 1.A). Un producto serio
  cita la norma y el día usado, y no decide por el contador.
- **IPC.** La base cambió a octubre de 2022 = 100. Las series viejas tienen base diciembre de
  2010 y el INE publica un empalme. Mezclar bases da variaciones falsas.
- **UI.** Desde el 6/9/2003 se calcula por fórmula diaria a partir del IPC de los dos meses
  anteriores (INE, PDF mensual de la UI).
- **ARCE / OCDS:**
  - compras directas sin bloque de licitación;
  - JSON multilínea que rompe el archivo;
  - sin contratos ni acuerdos marco;
  - las compras menores al 20 % del umbral no son obligatorias.
- **Catálogo CKAN:** la calidad es del publicador; el catálogo cosecha de seis portales externos y
  no vuelve a verificar lo copiado (Apify); el entorno de prueba aparece en los buscadores.
- **SIPC:**
  - el padrón de comercios y productos viene en cp1252 y los precios en UTF-8;
  - los precios llegan con atraso (el 27/11 había datos hasta el 30/09);
  - cubre supermercados y cadenas, no almacenes de barrio;
  - el dominio precios.uy no resolvió desde los servidores de Firecrawl, pero sí desde Uruguay.
- **ECH:** pasó a ANDA (`www4.ine.gub.uy`) y responde 403. Los paquetes de R existentes llegan a
  2019.
- **CARU:** los informes de playas pasaron a Google Drive (ver
  `docs/2026-11-27-revision-experimental.md`).
- **Parlamento:** responde 403 según el User-Agent. **`leyes`:** CloudFront cachea respuestas
  vacías durante 180 s.

## 4. Implicancias para la estrategia

1. **No competir en indicadores básicos.** datosuruguay ya da 31 series gratis, sin clave y con
   licencia comercial. Nuestro diferencial no es el acceso: es la garantía (procedencia, sello de
   los bytes, rechazo con motivo y norma citada).
2. **Priorizar donde la calidad es el problema que se declara.** Compras públicas (B) tiene el
   pedido escrito del propio Estado y de la sociedad civil, y es donde el repo ya tiene trampas
   medidas. Le siguen los precios para quien vende (E), con un caso propio para validar, y el
   parte de fuentes rotas para la sociedad civil (C).
3. **La garantía de calidad tiene que ser visible.** El catálogo declara que no la ofrece. Un
   producto que publique qué verifica, cada cuánto y qué rechazó ocupa ese lugar.
4. **Postergar** la ECH (sin acceso) y la app de precios para el consumidor (Cabacua y PreciosGub
   ya están ahí).

## 5. Dónde seguir recolectando quejas

Fuentes que se renuevan solas:
- consultas públicas en la Plataforma de Participación Ciudadana (ARCE en 2023, SIPC en 2026);
- el Mirador de Gobierno Abierto, con los compromisos y su avance;
- los informes anuales de la UAIP;
- issues en GitHub de librerías del BCU y de Data Uruguay;
- foros de soporte de los programas de facturación (Montevideo COMM);
- los encuentros «Datos y Cogollos» de Data Uruguay.

Reddit (r/uruguay, r/monte_video) no se puede leer con Firecrawl. Hay que leerlo a mano o con el
navegador.

**Pendiente:**
- el informe completo de la consulta del SIPC de 2026 (está enlazado desde precios.uy);
- el informe anual 2025 de la UAIP;
- tres entrevistas por segmento priorizado.

## 6. Actualización 2026-11-28: X, cobertura de las intendencias y lo que se implementó

**X (con la herramienta `x_search`, que corre sobre Grok).** Pedirle un resumen devuelve prosa genérica
sin citas; pedirle «transcribí N posts literales con autor, fecha y enlace» devuelve posts reales.
- **Compras:** 8 posts reales de agosto a noviembre de 2026. La discusión gira sobre «compra directa
  a dedo» de intendencias y ministerios (publicidad en Canelones y Montevideo, una guardería de
  Cancillería, residuos en Colonia). Las denuncias se arman buscando a mano en
  comprasestatales.gub.uy. Ediles de Maldonado pidieron precisiones porque la Intendencia publica en
  ARCE «solamente una parte» de sus resoluciones.
- **Tipo de cambio fiscal:** sin quejas reales en X. La confusión documentada en la sección 1.A está
  en guías y foros de soporte, no en redes.

**Medido sobre el archivo abierto de la ARCE:**
- **Modalidad:** 92.246 de 140.128 adjudicaciones activas de 2025 (65,8 %) no tienen llamado
  publicado, así que su modalidad no se sabe; en 2024, el 68,7 %. Entre las de «publicidad», 365 de
  399 (91,5 %). Un «X % fue compra directa» calculado con este archivo omite dos tercios.
- **Cobertura de las intendencias en 2025:** Durazno, Lavalleja, Maldonado, Rocha y Soriano no
  figuran como compradoras. Las que figuran:

  | Intendencia | Adjudicaciones | Sin modalidad |
  |---|---|---|
  | Montevideo | 16.752 | 73 % |
  | Canelones | 1.209 | 39 % |
  | Paysandú | 824 | 52 % |
  | Colonia | 536 | 77 % |
  | Florida | 343 | 92 % |
  | Salto | 42 | 64 % |
  | Cerro Largo | 3 | 0 % |

  Que no figuren no prueba que no compren: los gobiernos departamentales publican en otros lugares
  o parcialmente.
- **Unidades:** «guantes de látex descartable no estéril» (catálogo 37021) tiene mediana de $1,13
  por UNIDAD (72 precios) y de $113 por CAJA (63 precios, de los cuales 22 están a más de diez veces
  de la mediana, como una «caja» a $0,14).

**Implementado y publicado:**

| Versión | Qué agrega |
|---|---|
| uydatos 0.20.0 / 0.20.1 | Modalidad de cada adjudicación |
| uydatos 0.21.0 | `precios_de_referencia` y `sin_modalidad` por comprador |
| mcp-uruguay 0.17.0 | `compras_estado` con `modalidad`, `sin_modalidad` y el aviso de que la cifra es un piso |
| mcp-uruguay 0.18.0 | Precios unitarios por unidad con `buscar`; el organismo que no figura se rechaza con motivo |
| mcp-uruguay 0.18.1 | `cotizacion` cita la guía de la DGI, cómo pedirla y qué serie es |

**Para la estrategia:**
- El segmento de compras (B) queda con un producto concreto que nadie ofrece: precio de referencia
  por unidad, con exclusiones y atípicos declarados, más la cobertura de cada organismo.
- Los interesados visibles son quienes hoy buscan compras directas a mano: periodistas, ediles y
  militantes de los dos lados. Los compradores públicos piden lo mismo por escrito.
- **Pendiente:** validar la ficha con un comprador real antes de construir más.
