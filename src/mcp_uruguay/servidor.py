"""El servidor MCP: registra las herramientas de `herramientas/` y corre por stdio."""

from __future__ import annotations

import functools
import http.client
import inspect
import time
from typing import Any, Callable, Literal, Optional

import anyio
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from mcp_uruguay import __version__, cache, guias
from mcp_uruguay import herramientas as h

INSTRUCCIONES = """\
Datos públicos de Uruguay y la región, leídos de la fuente primaria.

Cada respuesta trae `fuente` y `bajado` (cuándo se obtuvo la copia usada): citalos junto con el
número. Los lectores rechazan en vez de arreglar: un error con motivo es preferible a un número
plausible pero falso. Los índices de precios se devuelven como índices, no como inflación.
Un null es "sin dato", nunca cero."""

servidor = MCPServer(name="mcp-uruguay", version=__version__, instructions=INSTRUCCIONES)

EN_RED = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True)
LOCAL = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


def _codigo_http(error: BaseException) -> Optional[int]:
    """El código HTTP detrás de un `OSError` de la red, si lo hay: `uydatos` lo encadena como causa."""
    visto: Optional[BaseException] = error
    while visto is not None:
        codigo = getattr(visto, "code", None)
        if isinstance(codigo, int):
            return codigo
        visto = visto.__cause__
    return None


def motivo_de_red(nombre: str, error: Exception) -> str:
    """Qué decirle a quien llamó cuando la fuente no respondió.

    Un 4xx es un rechazo: esperar no lo arregla, y decir «probar más tarde» manda al agente a
    reintentar en vano. Si la herramienta está en `guias.CAIDAS`, el motivo conocido va en el mensaje.
    """
    codigo = _codigo_http(error)
    if codigo is not None and 400 <= codigo < 500:
        texto = f"La fuente rechazó el pedido: {error}. No se arregla reintentando."
    else:
        texto = f"No se pudo consultar la fuente: {error}. Probar de nuevo más tarde."
    conocido = guias.CAIDAS.get(nombre)
    return f"{texto} Estado conocido de esta fuente: {conocido}" if conocido else texto


def _con_aviso_de_copia(resultado: Any, vencidas: list[str]) -> Any:
    """Si para responder se usó una copia que ya debía refrescarse y no se pudo, la respuesta lo dice.

    El agente ve un `bajado` viejo, pero nada le dice que se **intentó** refrescar y la fuente no
    respondió: sin esto lo cita como si fuera la copia de siempre.
    """
    if not vencidas or not isinstance(resultado, dict):
        return resultado
    mas_vieja = min(vencidas)
    return {
        **resultado,
        "copia_vencida": True,
        "aviso": (
            "No se pudo refrescar el dato: la fuente no respondió o devolvió algo ilegible, y se usó la "
            f"copia que ya estaba guardada (bajada {mas_vieja}). Puede estar desactualizada: citá su "
            "`bajado` y reintentá más tarde."
        ),
    }


def _con_procedencia(resultado: Any, leidas: list[cache.CopiaUsada]) -> Any:
    """Agrega `procedencia`: qué copias del disco respaldan los números de esta respuesta.

    Va acá y no en cada herramienta: una sola forma para todas, y el campo viaja en la salida (el
    trinquete de las definiciones no se mueve). Sin copias leídas no se agrega nada: una lista vacía
    en cada respuesta es ruido.
    """
    if not leidas or not isinstance(resultado, dict):
        return resultado
    return {**resultado, "procedencia": leidas}


#: Cada cuántos segundos una herramienta lenta avisa que sigue trabajando. Con la caché fría una
#: primera llamada tarda de 40 a 75 s (`leyes`, `compras_estado`, `clima`) y muchos clientes cortan
#: cerca de los 60 s: sin ningún aviso en ese rato, no hay forma de distinguirla de una colgada.
LATIDO_S = 10.0


async def _latido(ctx: Context, nombre: str) -> None:
    """Un aviso de progreso cada `LATIDO_S` mientras la herramienta trabaja.

    Es un no-op si el cliente no pidió progreso. Un fallo al avisar nunca rompe la herramienta.
    """
    inicio = time.monotonic()
    while True:
        await anyio.sleep(LATIDO_S)
        segundos = int(time.monotonic() - inicio)
        try:
            await ctx.report_progress(
                segundos,
                None,
                f"{nombre}: consultando la fuente, {segundos} s. "
                "La primera vez tarda; las siguientes salen de la caché.",
            )
        except Exception:  # un cliente que cerró o no entiende el aviso no es un error de la herramienta
            return


def herramienta(titulo: str, anotaciones: ToolAnnotations) -> Callable:
    """Registra la función y convierte en `ToolError` (con el motivo visible) los errores esperables.

    Los `ValueError` de los lectores ya son mensajes escritos para quien llama: "respuesta mala del
    BCU", "producto inexistente". Un `OSError` es la fuente que no respondió. Cualquier otra
    excepción es un error de este servidor y el SDK la oculta detrás de un mensaje genérico.
    """

    def decorar(funcion: Callable) -> Callable:
        def llamar(args: tuple, kwargs: dict) -> Any:
            """El cuerpo, síncrono: corre en un hilo para que el aviso de progreso salga a tiempo."""
            try:
                with cache.vigilar_copias() as vencidas, cache.vigilar_procedencia() as leidas:
                    resultado = funcion(*args, **kwargs)
                return _con_procedencia(_con_aviso_de_copia(resultado, vencidas), leidas)
            except ValueError as e:
                raise ToolError(str(e)) from e
            except (OSError, http.client.HTTPException) as e:
                # `IncompleteRead` (una descarga cortada) no es un `OSError`: sin esto salía como un
                # error genérico sin motivo. Pasó con `compras_estado` el 16/11/2026, a los 200 s.
                raise ToolError(motivo_de_red(funcion.__name__, e)) from e

        @functools.wraps(funcion)
        async def envuelta(*args: Any, ctx: Context, **kwargs: Any) -> Any:
            resultado: Any = None
            error: Optional[Exception] = None
            async with anyio.create_task_group() as grupo:
                grupo.start_soon(_latido, ctx, funcion.__name__)
                try:
                    resultado = await anyio.to_thread.run_sync(lambda: llamar(args, kwargs))
                except Exception as e:  # se re-lanza abajo, fuera del grupo (que lo envolvería)
                    error = e
                finally:
                    grupo.cancel_scope.cancel()
            if error is not None:
                raise error
            return resultado

        # El SDK inyecta el `Context` según la firma: la función registrada lo declara, y el esquema
        # de entrada de la herramienta no lo incluye.
        firma = inspect.signature(funcion, eval_str=True)  # con las anotaciones ya evaluadas
        envuelta.__signature__ = firma.replace(  # type: ignore[attr-defined]
            parameters=[
                *firma.parameters.values(),
                inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, annotation=Context),
            ]
        )
        envuelta.__annotations__ = {
            **{nombre: parametro.annotation for nombre, parametro in firma.parameters.items()},
            "return": firma.return_annotation,
            "ctx": Context,
        }

        return servidor.tool(
            title=titulo, annotations=anotaciones, description=inspect.cleandoc(funcion.__doc__ or "")
        )(envuelta)

    return decorar


@herramienta("Cotización del BCU de un día", EN_RED)
def cotizacion(moneda: Literal["USD", "UI", "ARS", "BRL"], fecha: str, hacia_atras: bool = False) -> h.Cotizacion:
    """Cotización oficial del Banco Central del Uruguay, en pesos uruguayos, para una fecha AAAA-MM-DD.

    Monedas: USD (dólar billete), UI (Unidad Indexada), ARS (peso argentino billete), BRL (real billete).
    Fines de semana y feriados no tienen publicación: con hacia_atras=true se usa el último día hábil
    previo (hasta 7 días) y la respuesta dice qué día se usó."""
    return h.cotizacion(moneda, fecha, hacia_atras)


@herramienta("Promedio mensual de una cotización del BCU", EN_RED)
def cotizacion_mensual(moneda: Literal["USD", "UI", "ARS", "BRL"], desde: str, hasta: str) -> h.CotizacionMensual:
    """Promedio mensual de una cotización del BCU entre dos meses AAAA-MM (hasta 240 meses), con la
    cantidad de días publicados de cada mes. El mes en curso viene marcado como incompleto."""
    return h.cotizacion_mensual(moneda, desde, hasta)


@herramienta("Pesos constantes con la Unidad Indexada", EN_RED)
def pesos_constantes(montos: dict[str, float], base: str) -> h.PesosConstantes:
    """Lleva montos en pesos corrientes de distintos meses a pesos de un mes base, deflactando con la
    Unidad Indexada promedio del BCU. `montos` es {"AAAA-MM": monto}; `base` es "AAAA-MM".
    Sirve para comparar en términos reales pesos de fechas distintas."""
    return h.pesos_constantes(montos, base)


@herramienta("IPC de Argentina (INDEC)", EN_RED)
def ipc_argentina(desde: str, hasta: str) -> h.IpcArgentina:
    """Índice de precios al consumidor nacional de Argentina, base dic-2016 = 100, entre dos meses AAAA-MM.
    Devuelve el índice, no la inflación."""
    return h.ipc_argentina(desde, hasta)


@herramienta("IPCA de Brasil (IBGE)", EN_RED)
def ipca_brasil(desde: str, hasta: str) -> h.IpcaBrasil:
    """IPCA de Brasil como número-índice (base dic-1993 = 100), entre dos meses AAAA-MM.
    Devuelve el índice, no la inflación."""
    return h.ipca_brasil(desde, hasta)


@herramienta("Precios de combustibles de ANCAP", EN_RED)
def combustible_ancap(
    producto: Optional[str] = None, anio: Optional[int] = None, mes: Optional[int] = None
) -> h.CombustibleAncap:
    """Precio máximo al público, con IVA, de los combustibles de ANCAP fijado por el Poder Ejecutivo.
    Sin `producto`, lista los productos disponibles (los nombres hay que pasarlos tal cual).
    Con `producto`, la serie mensual; con `anio` y `mes`, ese mes."""
    return h.combustible_ancap(producto, anio, mes)


@herramienta("Ventas de combustibles de ANCAP", EN_RED)
def ventas_combustible(linea: str = "", mercado: str = "", desde: str = "", hasta: str = "") -> h.VentasCombustible:
    """Cantidad vendida por ANCAP de cada combustible, por mes (volúmenes, no precios; para precios usar
    combustible_ancap). Sin `linea`, lista los productos (GAS OIL, GASOLINAS, JET A1, SUPERGAS...) con su
    familia, su unidad y los mercados, y los meses que la fuente no publicó. Con `linea`, la serie
    mensual y el total de cada año con cuántos meses lo forman: no comparar años con distinta cantidad
    de meses. `mercado`: INTERNO, Bunker, UTE, ZONA FRANCA o Exportaciones (vacío = todos). `desde` y
    `hasta` en AAAA-MM. Unidades: miles de m3, salvo el petcoke en toneladas."""
    return h.ventas_combustible(linea, mercado, desde, hasta)


@herramienta("Combustibles: ANCAP contra el precio de paridad de importación", EN_RED)
def paridad_combustibles(producto: str = "", desde: str = "", hasta: str = "") -> h.ParidadCombustibles:
    """¿ANCAP vende el combustible por encima o por debajo de lo que costaría importarlo? Compara el precio
    ex planta de ANCAP con el precio de paridad de importación (PPI) que calcula URSEA, los dos sin
    impuestos, en $/litro, mes a mes desde 2022. Sin `producto`: el último mes y el promedio de 12 meses de
    Gasolina Super 95, Gasolina Premium 97, Gasoil 50-S y Gasoil 10-S. Con `producto`: la serie (`desde` y
    `hasta` en AAAA-MM) y el desglose del último PPI desde el precio internacional (FOB) hasta los
    impuestos. Leer `metodo`: la comparación es una construcción de este servidor, no una cifra oficial."""
    return h.paridad_combustibles(producto, desde, hasta)


@herramienta("Clima en Salto Grande (INIA)", EN_RED)
def clima(desde: str = "", hasta: str = "") -> h.Clima:
    """Clima de la estacion INIA Salto Grande, la misma serie desde 1970.

    Sin fechas: la tendencia de la temperatura media anual, en grados Celsius por decada, con su
    error estandar. Con `desde` y `hasta` (AAAA-MM-DD, hasta 400 dias): la lluvia y las temperaturas
    maxima y minima de cada dia, con la anomalia respecto de la normal 1971-2025. Se pasan las dos
    fechas o ninguna."""
    return h.clima(desde, hasta)


@herramienta("Observaciones horarias de INUMET, por día local", EN_RED)
def observaciones_inumet(
    variable: Literal["temperatura", "precipitacion", "humedad", "viento", "presion"],
    estacion: str = "",
    desde: str = "",
    hasta: str = "",
    agregacion: Literal["", "promedio", "max", "min", "suma"] = "",
) -> h.ObservacionesInumet:
    """Observaciones meteorológicas de INUMET en siete estaciones del país (Salto, Artigas, Colonia,
    Mercedes, Paso de los Toros, Rocha y Aeropuerto Melilla).

    Solo con `variable`: la cobertura de cada estación (filas, días completos, nulos, extremos). Con
    `estacion`, `desde`, `hasta` (AAAA-MM-DD, hasta 400 días) y `agregacion`: el valor de cada día local.
    La fuente publica en UTC y acá el día es el de Uruguay (UTC-3). Un día incompleto devuelve null,
    nunca un total parcial. La agregación es obligatoria: temperatura se pide con max o min, lluvia con suma."""
    return h.observaciones_inumet(variable, estacion, desde, hasta, agregacion)


@herramienta("Estaciones hidrometeorológicas cercanas (Salto Grande)", EN_RED)
def estaciones_cercanas(lat: float, lon: float, cantidad: int = 5) -> h.EstacionesCercanas:
    """Estaciones de la red de la Comisión Técnica Mixta de Salto Grande (cuenca del río Uruguay, las dos
    orillas) más cercanas a un punto, con las variables que publica cada una y su último dato."""
    return h.estaciones_cercanas(lat, lon, cantidad)


@herramienta("Nivel del río en una estación de Salto Grande", EN_RED)
def nivel_rio(estacion: str = "Salto", desde: str = "", hasta: str = "") -> h.NivelRio:
    """Altura del río (H) en una estación de la Comisión Técnica Mixta de Salto Grande, resumida por día
    (mínimo, media y máximo), con la última lectura y cuánto subió o bajó en el período. Lecturas cada 15
    minutos. `estacion` es el nombre o el id (por defecto Salto); `desde`/`hasta` AAAA-MM-DD, hasta 92 días,
    por defecto los últimos 14. Para encontrar una estación cerca de un lugar, usar estaciones_cercanas."""
    return h.nivel_rio(estacion, desde, hasta)


@herramienta("Nivel del río comparado con años anteriores", EN_RED)
def nivel_rio_comparado(estacion: str = "Salto", dias: int = 7, hasta: str = "") -> h.NivelRioComparado:
    """¿El río está alto o bajo para la época? Media de la altura en los últimos `dias` (1 a 31) hasta
    `hasta` (por defecto hoy), comparada con los mismos días de cada año desde 2017, y en qué lugar queda.
    Los años con pocas lecturas se excluyen y se listan. La primera consulta puede tardar."""
    return h.nivel_rio_comparado(estacion, dias, hasta)


@herramienta("Nivel y caudal del río Uruguay en las escalas de Prefectura (INA)", EN_RED)
def nivel_rio_ina(
    escala: Literal["Concordia", "Salto Grande Arriba", "Salto Grande Abajo"] = "Concordia",
    variable: Literal["H", "Q"] = "H",
    desde: str = "",
    hasta: str = "",
) -> h.NivelRioIna:
    """Altura (H, en metros) o caudal (Q, en m³/s) del río Uruguay en las escalas de Prefectura Naval
    Argentina que publica el sistema de alerta del INA: Concordia (frente a Salto, desde 1931) y Salto
    Grande Arriba y Abajo (la represa). Con los niveles de alerta, evacuación y aguas bajas de la escala.

    `desde`/`hasta` AAAA-MM-DD, por defecto los últimos 30 días. Hasta 400 días devuelve un punto por
    día; más largo, uno por mes (la serie entera cabe en un pedido). Leer `dias_de_atraso` antes de
    decir "hoy": el caudal de Concordia viene con meses de atraso en la fuente, y el dato del día se
    carga por la tarde. Para la estación Salto de la CTM y el río comparado con otros años, usar
    nivel_rio y nivel_rio_comparado."""
    return h.nivel_rio_ina(escala, variable, desde, hasta)


@herramienta("Calidad del agua potable de OSE por localidad", EN_RED)
def calidad_agua(localidad: str = "", parametro: str = "", desde: str = "", hasta: str = "") -> h.CalidadAgua:
    """Los análisis de laboratorio con que OSE controla el agua potable, por localidad y trimestre,
    desde 2017: coliformes totales y Escherichia coli (presencia o ausencia), pH, turbidez (NTU), color
    verdadero (UC) y olor.

    Sin `localidad`, la lista de localidades con su departamento. Con `localidad`, cada trimestre con la
    cantidad de muestras y, por parámetro, cuántos análisis fueron mediciones y cuántos límites de
    detección (`<5`), con el mínimo y el máximo de las mediciones. `parametro` filtra uno (por ejemplo
    `turbidez`); `desde`/`hasta` son AAAA o AAAA-Tn (por ejemplo 2024-T3). No dice si el agua cumple la
    norma: informa lo que OSE publicó. La primera consulta baja unos 122 MB y tarda."""
    return h.calidad_agua(localidad, parametro, desde, hasta)


@herramienta("Variación real descontando la inflación", EN_RED)
def variacion_real(
    monto_inicial: float,
    mes_inicial: str,
    monto_final: float,
    mes_final: str,
    indice: Literal["UI", "IPC_AR", "IPCA_BR"] = "UI",
) -> h.VariacionReal:
    """Cuánto cambió un monto entre dos meses (AAAA-MM) en términos nominales y reales: ventas, precios,
    sueldos o alquileres. `indice`: UI para pesos uruguayos (Unidad Indexada del BCU), IPC_AR para pesos
    argentinos (INDEC), IPCA_BR para reales (IBGE). Devuelve la variación nominal, la inflación del período,
    la variación real y cuánto valdría el monto inicial en moneda del mes final."""
    return h.variacion_real(monto_inicial, mes_inicial, monto_final, mes_final, indice)


@herramienta("En qué departamento y localidad cae un punto", EN_RED)
def ubicar_punto(lat: float, lon: float) -> h.Ubicacion:
    """Dado un punto (latitud y longitud en grados), en qué departamento y en qué localidad de Uruguay cae,
    según los polígonos oficiales del INE, con la población 2023 de la localidad. Si cae en el campo, la
    localidad más cercana y a qué distancia. Suma la dirección más cercana de IDE.uy con su distancia.
    Combinar con geocodificar_direccion para pasar de una dirección a su departamento."""
    return h.ubicar_punto(lat, lon)


@herramienta("Población y viviendas de una localidad (INE)", EN_RED)
def localidad(nombre: str = "", departamento: str = "", cantidad: int = 20) -> h.Localidades:
    """Población y viviendas 2023 de una localidad uruguaya, por nombre (sin importar tildes). Si el nombre
    existe en más de un departamento, devuelve todas; `departamento` desambigua. Solo con `departamento`,
    lista sus localidades de mayor a menor población (hasta `cantidad`)."""
    return h.localidad(nombre, departamento, cantidad)


@herramienta("Resultados electorales (Corte Electoral)", EN_RED)
def resultados_electorales(
    eleccion: Literal["nacionales-2024", "balotaje-2024", "departamentales-2025"], departamento: str = ""
) -> h.ResultadoElectoral:
    """Resultados de una elección uruguaya, del país o de un departamento: habilitados, emitidos,
    participación, votos por partido (nacionales y departamentales) y por opción (candidatos del balotaje,
    plebiscitos). Sale de los datos por mesa de la Corte Electoral e incluye los votos observados, que se
    escrutan en mesas especiales sin localidad. Los porcentajes son sobre los votos emitidos."""
    return h.resultados_electorales(eleccion, departamento)


@herramienta("Compras del Estado (ARCE)", EN_RED)
def compras_estado(anio: int, organismo: str = "", buscar: str = "", cantidad: int = 10) -> h.ComprasEstado:
    """Cuánto adjudicó el Estado uruguayo en un año (2002 en adelante), en pesos, con los organismos que más
    compraron y los mayores ítems. `organismo` filtra por comprador (por ejemplo «Intendencia de Montevideo»);
    `buscar` filtra los ítems por texto (por ejemplo «ambulancia»). Las monedas se convierten con la
    cotización del día. Avisa cuando un solo ítem domina el total: hay registros con cantidad × precio
    imposibles. La primera consulta de un año baja unos 30 MB y tarda."""
    return h.compras_estado(anio, organismo, buscar, cantidad)


@herramienta("Asistencia de legisladores (Parlamento)", EN_RED)
def asistencia_parlamentaria(
    camara: Literal["senado", "diputados"],
    legislatura: int = 50,
    nombre: str = "",
    minimo_citaciones: int = 10,
    cantidad: int = 10,
) -> h.AsistenciaParlamentaria:
    """Asistencia a sesiones del Senado o de Diputados en una legislatura (46 a 50, la actual): menor y mayor
    asistencia entre quienes tuvieron al menos `minimo_citaciones` (para no comparar suplentes con dos citaciones),
    y las filas que contienen `nombre`. Avisa de nombres repetidos, que pueden ser homónimos."""
    return h.asistencia_parlamentaria(camara, legislatura, nombre, minimo_citaciones, cantidad)


@herramienta("Pedidos de informes de Diputados y si se contestaron", EN_RED)
def pedidos_de_informes(
    organismo: str = "", presentados_hasta: str = "", tema: str = "", cantidad: int = 20
) -> h.PedidosDeInformes:
    """Pedidos de informes de la Cámara de Diputados a ministerios y organismos (artículo 118 de la
    Constitución), legislatura actual: cuántos se contestaron por organismo y por semestre, sobre los que ya
    cumplieron el plazo legal de 45 días, y cuántos pidió cada partido. `organismo` y `tema` filtran por texto
    (sin tildes) y devuelven los pedidos con el enlace al oficio y a la respuesta. `presentados_hasta`
    (AAAA-MM-DD) compara una misma cohorte: las respuestas llegan tarde, así que los pedidos nuevos siempre
    parecen menos contestados. Leer `nota` antes de comparar."""
    return h.pedidos_de_informes(organismo, presentados_hasta, tema, cantidad)


@herramienta("Leyes promulgadas (Parlamento)", EN_RED)
def leyes(
    buscar: str = "", desde: str = "", hasta: str = "", numero: Optional[int] = None, cantidad: int = 20
) -> h.Leyes:
    """Leyes promulgadas desde 1985: por texto del título (sin importar tildes), por rango de fechas AAAA-MM-DD o
    por número. Devuelve el enlace al texto actualizado en IMPO."""
    return h.leyes(buscar, desde, hasta, numero, cantidad)


@herramienta("Proyectos entrados al Parlamento", EN_RED)
def proyectos_parlamento(
    buscar: str = "", legislatura: Optional[int] = None, tipo: str = "", cantidad: int = 20
) -> h.ProyectosParlamento:
    """Proyectos entrados al Parlamento desde 1985 (legislaturas 42 a 50), por texto del título, legislatura o
    tipo («ley», «resolución», «minuta», «declaración»). Un proyecto que aparece en dos legislaturas cuenta una
    vez. La primera búsqueda sin legislatura baja nueve archivos."""
    return h.proyectos_parlamento(buscar, legislatura, tipo, cantidad)


@herramienta("Validar RUT o cédula uruguaya", LOCAL)
def validar_documento(numero: str, tipo: Literal["rut", "ci"]) -> h.Validacion:
    """Valida el dígito verificador de un RUT (12 dígitos) o una cédula de identidad (8 dígitos) de
    Uruguay. Acepta puntos, guiones y comas. No consulta a DGI: es validez aritmética."""
    return h.validar_documento(numero, tipo)


@herramienta("Semana ISO de una fecha", LOCAL)
def semana(fecha: str) -> h.SemanaTyped:
    """Semana ISO 8601 (W1, W2...) de una fecha AAAA-MM-DD, con su lunes y su domingo."""
    return h.semana(fecha)


@herramienta("Geocodificar una dirección de Uruguay (IDE.uy)", EN_RED)
def geocodificar_direccion(direccion: str, localidad: str = "", departamento: str = "") -> h.Geocodificacion:
    """Coordenadas (lat, lon) de una dirección o esquina de Uruguay con la API oficial de IDE.uy, con la
    calidad del resultado: puerta exacta, puerta aproximada, esquina o centro de calle. Si la API devuelve
    otra calle o el centro de la localidad, no se da coordenada. Pasar localidad y departamento mejora
    mucho el resultado. Esquinas: '18 de Julio y Ejido' o 'Artigas esq. Solari'."""
    return h.geocodificar_direccion(direccion, localidad, departamento)


@herramienta("Buscar indicadores sociales del MIDES", EN_RED)
def buscar_indicador_social(texto: str, cantidad: int = 20) -> h.IndicadoresEncontrados:
    """Busca entre los ~1.260 indicadores sociales del Observatorio Social del MIDES (pobreza, empleo,
    desempleo, educación, vivienda, salud, ingresos, cuidados, juventud, personas mayores, censos...) por
    palabras, sin tildes. Devuelve los nombres para pasar a indicador_social. Para un departamento,
    incluir la palabra 'departamento' (por ejemplo 'pobreza departamento')."""
    return h.buscar_indicador_social(texto, cantidad)


@herramienta("Un indicador social del MIDES, con su ficha", EN_RED)
def indicador_social(indicador: str, filtro: str = "") -> h.IndicadorSocial:
    """Lee un indicador del Observatorio Social del MIDES (el nombre sale de buscar_indicador_social):
    título, unidad, forma de cálculo, fuente del dato (casi siempre la Encuesta Continua de Hogares del
    INE) y la tabla por dimensión y período, con datos hasta 2023-2024. `filtro` deja solo las filas con
    esos valores de dimensión, separados por coma (por ejemplo 'Salto' o 'Mujeres,Pobre'). Leer los
    `avisos`: filas de total mezcladas, mapas que muestran un solo año (`parcial`), y una ficha que no
    coincide con la tabla."""
    return h.indicador_social(indicador, filtro)


@herramienta("Recursos de un dataset del catálogo de Uruguay", EN_RED)
def recursos_catalogo(dataset: str) -> h.RecursosCatalogo:
    """Los archivos vigentes (nombre, URL, formato, fecha) de un dataset de catalogodatos.gub.uy, por su
    identificador (por ejemplo `inia-precipitacion-temps-extremas-sg`)."""
    return h.recursos_catalogo(dataset)


@herramienta("Que copia de cada fuente se esta usando", LOCAL)
def diagnostico() -> h.Diagnostico:
    """Que archivo de cada fuente esta cacheado en esta maquina, de cuando es la copia que se esta
    usando, y cuanto pesa. Sirve para saber si un numero viejo viene de una copia vieja.
    No sale a la red."""
    return h.diagnostico()


for _nombre, (_funcion, _titulo) in guias.PROMPTS.items():
    servidor.prompt(name=_nombre, title=_titulo, description=(_funcion.__doc__ or "").strip())(_funcion)

for _uri, (_funcion, _titulo, _descripcion) in guias.RECURSOS.items():
    servidor.resource(
        _uri,
        name=_uri.removeprefix("uru://").replace("/", "-"),
        title=_titulo,
        description=_descripcion,
        mime_type="text/markdown",
    )(_funcion)


def main() -> None:
    """Sin argumentos corre el servidor por stdio. `--precalentar` baja la caché y termina."""
    import sys

    # Validar TLS con el almacén de certificados del sistema, no con el que trae Python. En Windows
    # el almacén baja las raíces a demanda y Python solo ve las que ya están: la primera llamada a
    # datos.ose.com.uy (raíz Certum) falló con CERTIFICATE_VERIFY_FAILED en una máquina con red, y
    # pasó después de abrir el sitio una vez con curl (16/11/2026, comentario en el PR #1). Es lo
    # que hace pip. Solo en el proceso del servidor: importar el paquete no cambia nada global.
    # También `--precalentar`, que sale a la red igual.
    import truststore

    truststore.inject_into_ssl()
    if "--precalentar" in sys.argv[1:]:
        from mcp_uruguay.precalentar import precalentar

        raise SystemExit(precalentar())
    servidor.run()


if __name__ == "__main__":
    main()
