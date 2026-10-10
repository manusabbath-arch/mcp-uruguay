"""Las herramientas del servidor, como funciones comunes: reciben valores simples y devuelven
diccionarios. `servidor.py` solo las registra.

Cada respuesta con un dato trae `fuente` (quién lo publica) y `bajado` (cuándo se obtuvo la copia
que se usó). Un agente que cite el número puede citar también de dónde salió y de qué fecha es.
Los errores son `ValueError` con el motivo en castellano: el agente los recibe como respuesta de
error de la herramienta.
"""

from __future__ import annotations

import unicodedata
from datetime import date, timedelta
from typing import Literal, Optional, TypedDict, Union

from uydatos import (
    ancap,
    bcu,
    catalogo,
    compras,
    elecciones,
    ibge,
    ideuy,
    indec,
    inia,
    limites,
    rut,
    salto_grande,
    semanas,
)

from mcp_uruguay import cache

Moneda = Literal["USD", "UI", "ARS", "BRL"]
MONEDAS: dict[str, int] = {"USD": 2225, "UI": 9800, "ARS": 501, "BRL": 1001}

FUENTE_BCU = "Banco Central del Uruguay, web service de cotizaciones (cotizaciones.bcu.gub.uy)"
FUENTE_INDEC = "INDEC, vía la API de series de tiempo de datos.gob.ar (serie 148.3_INIVELNAL_DICI_M_26)"
FUENTE_IBGE = "IBGE, API SIDRA, tabla 1737, variable 2266 (IPCA número-índice)"
FUENTE_ANCAP = "ANCAP, dataset ancap-precio-combustible-pe de catalogodatos.gub.uy"
FUENTE_INIA = "INIA, Unidad GRAS, estación Salto Grande (dataset inia-precipitacion-temps-extremas-sg)"
FUENTE_IDE = "IDE.uy, API pública de direcciones (direcciones.ide.uy)"
FUENTE_COMPRAS = "ARCE, compras del Estado en OCDS (dataset arce-datos-historicos-de-compras)"
FUENTE_ELECCIONES = "Corte Electoral, resultados por mesa publicados en catalogodatos.gub.uy"
FUENTE_LIMITES = "INE: límites departamentales (vía la IDE) y localidades con población 2023 (vía el MIDES)"
FUENTE_CTM = "Comisión Técnica Mixta de Salto Grande, web service www.saltogrande.org/ws.php"


class Cotizacion(TypedDict):
    """La respuesta de `cotizacion()`."""

    moneda: str
    nombre_bcu: str
    fecha_pedida: str
    fecha_cotizacion: Optional[str]
    valor_en_pesos: Optional[float]
    nota: str
    fuente: str
    bajado: str


class Validacion(TypedDict):
    """La respuesta de `validar_documento()`."""

    tipo: str
    normalizado: str
    estado: str
    valido: bool
    nota: str


class SemanaTyped(TypedDict):
    """La respuesta de `semana()`. Se llama asi para no chocar con el modulo `uydatos.semanas`."""

    etiqueta: str
    etiqueta_con_anio: str
    desde: str
    hasta: str
    de_total: str
    nota: str


class MesBCU(TypedDict):
    """Una fila de `cotizacion_mensual()`: el promedio de un mes y cuantos dias entraron."""

    mes: str
    promedio: float
    dias: int
    completo: bool


class CotizacionMensual(TypedDict):
    """La respuesta de `cotizacion_mensual()`."""

    moneda: str
    nombre_bcu: str
    meses: list[MesBCU]
    nota: str
    fuente: str
    bajado: str


class PesosConstantes(TypedDict):
    """La respuesta de `pesos_constantes()`."""

    base: str
    montos_en_pesos_de_la_base: dict[str, float]
    ui_promedio_usada: dict[str, float]
    metodo: str
    fuente: str
    bajado: str


class PuntoIndice(TypedDict):
    """Un mes de una serie de precios: el indice, no la variacion."""

    periodo: str
    valor: float


class IpcArgentina(TypedDict):
    """La respuesta de `ipc_argentina()`."""

    serie: str
    puntos: list[PuntoIndice]
    nota: str
    fuente: str
    bajado: str


class IpcaBrasil(TypedDict):
    """La respuesta de `ipca_brasil()`."""

    serie: str
    puntos: list[PuntoIndice]
    nota: str
    fuente: str
    bajado: str


class PrecioCombustible(TypedDict):
    """Un mes de precio de un producto de ANCAP. `precio` en None = sin cotizacion (S/C)."""

    mes: str
    precio: Optional[float]
    unidad: str


class CombustibleAncap(TypedDict, total=False):
    """La respuesta de `combustible_ancap()`, en sus dos caminos.

    Sin `producto` trae solo `productos`; con `producto`, trae `producto` y `precios`. `nota`,
    `fuente` y `bajado` van siempre.
    """

    productos: list[str]
    producto: str
    precios: list[PrecioCombustible]
    nota: str
    fuente: str
    bajado: str


class DiaClima(TypedDict):
    """Un dia del clima de Salto Grande. Las claves `anomalia_*` en None = sin dato, nunca cero."""

    fecha: str
    tmax: Optional[float]
    tmin: Optional[float]
    lluvia_mm: Optional[float]
    anomalia_tmax: Optional[float]
    anomalia_tmin: Optional[float]


class TendenciaTemperatura(TypedDict):
    """La tendencia de una temperatura (tmax o tmin), en grados Celsius por decada."""

    por_decada: float
    error_estandar: float
    anios: int


class Clima(TypedDict, total=False):
    """La respuesta de `clima()`, en sus dos caminos.

    Con `desde`/`hasta` trae `dias` (una fila por dia) y `ultimo_dato`; sin fechas, `dias` es el
    conteo de dias y trae `periodo` y `tendencia_c_por_decada`. `nota`, `fuente` y `bajado` van
    siempre.
    """

    estacion: str
    dias: list[DiaClima] | int
    ultimo_dato: str
    periodo: str
    tendencia_c_por_decada: dict[str, TendenciaTemperatura]
    nota: str
    fuente: str
    bajado: str


class EstacionCercana(TypedDict):
    """Una estacion de la red de Salto Grande y su distancia en linea recta al punto pedido."""

    id: str
    nombre: str
    distancia_km: float
    variables: list[str]
    ultimo_dato: Optional[str]


class EstacionesCercanas(TypedDict):
    """La respuesta de `estaciones_cercanas()`."""

    estaciones: list[EstacionCercana]
    nota: str
    fuente: str
    bajado: str


class Geocodificacion(TypedDict):
    """La respuesta de `geocodificar_direccion()`. Sin coordenada, `lat`/`lon` van en None."""

    direccion: str
    localidad: str
    departamento: str
    calidad: str
    lat: Optional[float]
    lon: Optional[float]
    dentro_de_uruguay: Optional[bool]
    puerta_pedida: Optional[int]
    puerta_devuelta: Optional[int]
    direccion_devuelta: str
    metodo: str
    aviso_de_la_api: str
    nota: str
    fuente: str


class Recurso(TypedDict):
    """Un archivo vigente de un dataset del catalogo de datos abiertos."""

    nombre: str
    url: str
    formato: str
    modificado: str


class RecursosCatalogo(TypedDict):
    """La respuesta de `recursos_catalogo()`."""

    dataset: str
    recursos: list[Recurso]
    fuente: str


class ArchivoCache(TypedDict):
    """Un archivo cacheado en disco: de cuando es la copia que se usa y cuanto pesa."""

    archivo: str
    bajado: str
    bytes: int


class Diagnostico(TypedDict):
    """La respuesta de `diagnostico()`."""

    directorio: str
    archivos: list[ArchivoCache]
    nota: str


MAX_DIAS = 400
MAX_MESES = 240


def _fecha(texto: str, campo: str) -> date:
    try:
        return date.fromisoformat(texto.strip())
    except ValueError:
        raise ValueError(f"{campo}: {texto!r} no es una fecha AAAA-MM-DD") from None


def _mes(texto: str, campo: str) -> date:
    try:
        anio, mes = texto.strip().split("-")
        return date(int(anio), int(mes), 1)
    except ValueError:
        raise ValueError(f"{campo}: {texto!r} no es un mes AAAA-MM") from None


def _fin_de_mes(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def _codigo(moneda: str) -> int:
    if moneda not in MONEDAS:
        raise ValueError(f"moneda {moneda!r}: las disponibles son {', '.join(MONEDAS)}")
    return MONEDAS[moneda]


# --- BCU ---------------------------------------------------------------------------------------


def cotizacion(moneda: Moneda, fecha: str, hacia_atras: bool = False, hoy: Optional[date] = None) -> Cotizacion:
    dia = _fecha(fecha, "fecha")
    codigo = _codigo(moneda)
    desde = dia - timedelta(days=bcu.MAX_DIAS_ATRAS) if hacia_atras else dia
    serie, bajado = cache.bcu_serie(codigo, desde, dia, hoy=hoy)
    valor = bcu.cotizacion_del_dia(serie, dia, hacia_atras=hacia_atras)
    usada = next((d for d in sorted(serie, reverse=True) if d <= dia), None) if valor is not None else None
    if valor is None:
        nota = (
            "Sin publicación ese día (fin de semana, feriado o día sin cotización). "
            "Pedir hacia_atras=true para usar el último día hábil previo, hasta una semana."
            if not hacia_atras
            else f"Sin publicación en los {bcu.MAX_DIAS_ATRAS} días previos: falta el dato, no es un fin de semana."
        )
    elif usada != dia:
        nota = f"Se usó la cotización del {usada}, último día publicado antes del {dia}."
    else:
        nota = "Cotización publicada ese mismo día."
    return {
        "moneda": moneda,
        "nombre_bcu": bcu.MONEDAS[codigo],
        "fecha_pedida": dia.isoformat(),
        "fecha_cotizacion": usada.isoformat() if usada else None,
        "valor_en_pesos": valor,
        "nota": nota + " Qué cotización corresponde para un fin fiscal no lo decide esta herramienta.",
        "fuente": FUENTE_BCU,
        "bajado": bajado,
    }


def cotizacion_mensual(moneda: Moneda, desde: str, hasta: str, hoy: Optional[date] = None) -> CotizacionMensual:
    ini, fin = _mes(desde, "desde"), _fin_de_mes(_mes(hasta, "hasta"))
    if (fin.year - ini.year) * 12 + fin.month - ini.month >= MAX_MESES:
        raise ValueError(f"rango demasiado largo: hasta {MAX_MESES} meses por consulta")
    codigo = _codigo(moneda)
    serie, bajado = cache.bcu_serie(codigo, ini, fin, hoy=hoy)
    hoy = hoy or date.today()
    meses = bcu.promedio_mensual(serie)
    for m in meses:
        m["completo"] = m["mes"] != f"{hoy:%Y-%m}"
    return {
        "moneda": moneda,
        "nombre_bcu": bcu.MONEDAS[codigo],
        "meses": meses,
        "nota": "Promedio simple de los días publicados; `dias` dice cuántos. El mes en curso es parcial.",
        "fuente": FUENTE_BCU,
        "bajado": bajado,
    }


def pesos_constantes(montos: dict[str, float], base: str, hoy: Optional[date] = None) -> PesosConstantes:
    if not montos:
        raise ValueError("montos vacío: se espera {'AAAA-MM': pesos corrientes}")
    meses = [_mes(m, "montos") for m in montos] + [_mes(base, "base")]
    serie, bajado = cache.bcu_serie(MONEDAS["UI"], min(meses), _fin_de_mes(max(meses)), hoy=hoy)
    ui = {f["mes"]: f["promedio"] for f in bcu.promedio_mensual(serie)}
    convertidos = bcu.a_pesos_de(montos, base, ui)
    return {
        "base": base,
        "montos_en_pesos_de_la_base": {m: round(v, 2) for m, v in convertidos.items()},
        "ui_promedio_usada": {m: ui[m] for m in sorted({*montos, base})},
        "metodo": "monto x UI(base) / UI(mes), con la UI promedio de cada mes.",
        "fuente": FUENTE_BCU + " (Unidad Indexada, código 9800)",
        "bajado": bajado,
    }


# --- Índices de precios de la región ------------------------------------------------------------


def _recortar(serie: list[dict], desde: str, hasta: str) -> list[dict]:
    _mes(desde, "desde"), _mes(hasta, "hasta")
    return [p for p in serie if desde <= p["periodo"] <= hasta]


def ipc_argentina(desde: str, hasta: str) -> IpcArgentina:
    serie, ruta = cache.archivo(cache.directorio() / "indec_ipc.json", indec.descargar, indec.leer, cache.DIA)
    puntos = _recortar(serie, desde, hasta)
    return {
        "serie": "IPC nacional de Argentina, base diciembre 2016 = 100",
        "puntos": puntos,
        "nota": "Es un índice, no una inflación. La variación entre dos meses es índice(b)/índice(a) - 1.",
        "fuente": FUENTE_INDEC,
        "bajado": cache.sello(ruta),
    }


def ipca_brasil(desde: str, hasta: str) -> IpcaBrasil:
    serie, ruta = cache.archivo(cache.directorio() / "ibge_ipca.json", ibge.descargar, ibge.leer, cache.DIA)
    puntos = _recortar(serie, desde, hasta)
    return {
        "serie": "IPCA de Brasil, número-índice, base diciembre 1993 = 100",
        "puntos": puntos,
        "nota": "Es un índice, no una inflación. La variación entre dos meses es índice(b)/índice(a) - 1.",
        "fuente": FUENTE_IBGE,
        "bajado": cache.sello(ruta),
    }


# --- ANCAP ---------------------------------------------------------------------------------------


def combustible_ancap(
    producto: Optional[str] = None, anio: Optional[int] = None, mes: Optional[int] = None
) -> CombustibleAncap:
    publicaciones, ruta = cache.archivo(
        cache.directorio() / "ancap.csv", ancap.descargar, ancap.leer_publicaciones, cache.DIA
    )
    serie = ancap.serie_mensual(publicaciones)
    base = {"fuente": FUENTE_ANCAP, "bajado": cache.sello(ruta)}
    productos = sorted({s["producto"] for s in serie})
    if not producto:
        return {"productos": productos, "nota": "Pasar uno de estos nombres, tal cual, en `producto`.", **base}
    if producto not in productos:
        parecidos = [p for p in productos if producto.lower().split()[0] in p.lower()]
        raise ValueError(f"producto {producto!r} no existe. Parecidos: {parecidos or productos}")
    filas = [s for s in serie if s["producto"] == producto]
    if anio is not None:
        filas = [s for s in filas if s["anio"] == anio and (mes is None or s["mes"] == mes)]
    return {
        "producto": producto,
        "precios": [
            {"mes": f"{s['anio']}-{s['mes']:02d}", "precio": s["precio"], "unidad": s["unidad"]} for s in filas
        ],
        "nota": "Precio máximo al público con IVA, fijado por el Poder Ejecutivo. precio null = sin cotización (S/C).",
        **base,
    }


# --- INIA ----------------------------------------------------------------------------------------

_serie_inia: dict[float, list[dict]] = {}


def _clima() -> tuple[list[dict], str]:
    carpeta = cache.directorio() / "inia"
    carpeta.mkdir(parents=True, exist_ok=True)
    archivos = list(carpeta.glob("ppt_tmax_tmin_sg_*.csv"))
    if not archivos or cache.vencido(max(archivos, key=lambda p: p.stat().st_mtime), 7 * cache.DIA):
        try:
            inia.descargar(carpeta)
        except Exception:
            if not archivos:
                raise
        archivos = list(carpeta.glob("ppt_tmax_tmin_sg_*.csv"))
    clave = max(p.stat().st_mtime for p in archivos)
    if clave not in _serie_inia:
        _serie_inia.clear()
        _serie_inia[clave] = inia.leer_serie(carpeta)
    return _serie_inia[clave], cache.sello(max(archivos, key=lambda p: p.stat().st_mtime))


def clima_salto(desde: str, hasta: str) -> dict:
    ini, fin = _fecha(desde, "desde"), _fecha(hasta, "hasta")
    if (fin - ini).days >= MAX_DIAS:
        raise ValueError(f"rango demasiado largo: hasta {MAX_DIAS} días por consulta")
    serie, bajado = _clima()
    filas = [f for f in inia.clima_diario(serie) if ini <= f["fecha"] <= fin]
    r = lambda v: None if v is None else round(v, 1)  # noqa: E731
    return {
        "estacion": "INIA Salto Grande (-31,27 / -57,89)",
        "dias": [
            {
                "fecha": f["fecha"].isoformat(),
                "tmax": f["temperaturaMaxima"],
                "tmin": f["temperaturaMinima"],
                "lluvia_mm": f["pluviometro"],
                "anomalia_tmax": r(f["anom_tmax"]),
                "anomalia_tmin": r(f["anom_tmin"]),
            }
            for f in filas
        ],
        "ultimo_dato": serie[-1]["fecha"].isoformat(),
        "nota": (
            "El día de INIA va de 9:00 a 9:00. Anomalía = observado menos la normal 1971-2025 de ese día "
            "del año (ventana de ±7 días). null = sin dato, no cero. La fuente se actualiza cada quincena."
        ),
        "fuente": FUENTE_INIA,
        "bajado": bajado,
    }


def clima_tendencia() -> dict:
    serie, bajado = _clima()
    c = inia.cobertura(serie)
    t = inia.tendencia_anual(serie)
    return {
        "periodo": f"{c['primera']} a {c['ultima']}",
        "dias": c["filas"],
        "tendencia_c_por_decada": {k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in t.items()},
        "nota": "Regresión lineal de la media anual, solo años completos 1971-2025.",
        "fuente": FUENTE_INIA,
        "bajado": bajado,
    }


DISPONIBLES = {
    "dias": "lluvia y temperaturas de cada dia de un rango, con la anomalia respecto de la normal",
    "tendencia": "cuanto cambio la temperatura media anual, en grados por decada, desde 1970",
}


def clima(desde: str = "", hasta: str = "") -> Clima:
    """La puerta de entrada al clima de Salto Grande: dias, o tendencia. **Sale a la red.**

    Con `desde` y `hasta` (AAAA-MM-DD) devuelve los dias de ese rango; sin ninguna de las dos, la
    tendencia de la serie completa. No se pueden pasar una sola de las dos: una fecha sola no dice
    que se quiere, y adivinarlo desde aca seria inventar el rango.
    """
    if bool(desde) != bool(hasta):
        raise ValueError(
            "clima: o van las dos fechas (`desde` y `hasta`, AAAA-MM-DD) o no va ninguna. "
            "Una sola no alcanza: no se adivina el otro extremo."
        )
    if desde:
        return clima_salto(desde, hasta)
    return clima_tendencia()


# --- Salto Grande --------------------------------------------------------------------------------


def estaciones_cercanas(lat: float, lon: float, cantidad: int = 5) -> EstacionesCercanas:
    estaciones, ruta = cache.archivo(
        cache.directorio() / "salto_grande.xml",
        salto_grande.descargar_lista,
        salto_grande.leer_estaciones,
        cache.DIA,
    )
    cerca = salto_grande.estaciones_cerca_de(estaciones, lat, lon)[: max(1, min(cantidad, 50))]
    return {
        "estaciones": [
            {
                "id": e["id"],
                "nombre": e["nombre"],
                "distancia_km": round(d, 1),
                "variables": e["variables"],
                "ultimo_dato": e["fecha"],
            }
            for e, d in cerca
        ],
        "nota": "Distancia en línea recta. El servicio no declara las unidades de las variables (P, H, Q).",
        "fuente": FUENTE_CTM,
        "bajado": cache.sello(ruta),
    }


# --- Nivel del río (Salto Grande) ------------------------------------------------------------------


class EstacionRio(TypedDict):
    id: str
    nombre: str


class DiaRio(TypedDict):
    """Un día de lecturas de altura: mínimo, media y máximo, y cuántas lecturas con dato lo forman."""

    dia: str
    min: Optional[float]
    media: Optional[float]
    max: Optional[float]
    lecturas: int


class LecturaRio(TypedDict):
    fecha: str
    H: float


class CoberturaRio(TypedDict):
    esperadas: int
    recibidas: int
    con_H: int


class NivelRio(TypedDict):
    """La respuesta de `nivel_rio()`."""

    estacion: EstacionRio
    dias: list[DiaRio]
    ultima_lectura: Optional[LecturaRio]
    variacion_en_el_periodo: Optional[float]
    caudal_Q_media: Optional[float]
    cobertura: CoberturaRio
    nota: str
    fuente: str
    bajado: str


class VentanaActual(TypedDict):
    desde: str
    hasta: str
    media: float
    cobertura: float


class VentanaAnterior(TypedDict):
    anio: int
    desde: str
    hasta: str
    media: float


class Posicion(TypedDict):
    lugar: int
    de: int
    orden: str


class NivelRioComparado(TypedDict):
    """La respuesta de `nivel_rio_comparado()`."""

    estacion: EstacionRio
    actual: VentanaActual
    anios_anteriores: list[VentanaAnterior]
    anios_excluidos: list[int]
    posicion: Posicion
    nota: str
    fuente: str
    bajado: str


class VariacionReal(TypedDict):
    """La respuesta de `variacion_real()`. `indice` trae el valor de cada mes y su descripción."""

    variacion_nominal_pct: float
    inflacion_del_periodo_pct: float
    variacion_real_pct: float
    monto_inicial_en_moneda_final: float
    moneda: str
    indice: dict[str, Union[float, str]]
    nota: str
    fuente: str
    bajado: str


ESTACION_SALTO = "A501258E"
MAX_DIAS_RIO = 92
PRIMER_ANIO_RIO = 2017  # desde cuándo hay lecturas en la estación Salto (medido el 10/10/2026)
COBERTURA_MINIMA = 0.5


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper().strip()


def _estacion(estacion: str) -> dict:
    """Resuelve una estación por id o por nombre (sin importar tildes ni mayúsculas)."""
    estaciones, _ = cache.archivo(
        cache.directorio() / "salto_grande.xml",
        salto_grande.descargar_lista,
        salto_grande.leer_estaciones,
        cache.DIA,
    )
    buscado = _sin_tildes(estacion)
    for e in estaciones:
        if e["id"].upper() == buscado or _sin_tildes(e["nombre"]) == buscado:
            return e
    parecidas = [e["nombre"] for e in estaciones if any(p in _sin_tildes(e["nombre"]) for p in buscado.split())]
    raise ValueError(
        f"estación {estacion!r} no existe. Parecidas: {parecidas[:10] or 'ninguna'}. "
        "Para ver las cercanas a un punto, usar estaciones_cercanas."
    )


def _lecturas(estacion: dict, desde: date, hasta: date, hoy: Optional[date]) -> tuple[list[dict], str]:
    return cache.sg_lecturas(estacion["id"], desde, hasta, hoy=hoy)


def nivel_rio(estacion: str = "Salto", desde: str = "", hasta: str = "", hoy: Optional[date] = None) -> NivelRio:
    hoy_ = hoy or date.today()
    fin = _fecha(hasta, "hasta") if hasta else hoy_
    ini = _fecha(desde, "desde") if desde else fin - timedelta(days=13)
    if ini > fin:
        raise ValueError(f"desde {ini} es posterior a hasta {fin}")
    if (fin - ini).days >= MAX_DIAS_RIO:
        raise ValueError(f"rango demasiado largo: hasta {MAX_DIAS_RIO} días por consulta")
    e = _estacion(estacion)
    lecturas, bajado = _lecturas(e, ini, fin, hoy)
    dias = salto_grande.resumen_diario(lecturas, "H")
    con_dato = [d for d in dias if d["media"] is not None]
    con_h = [f for f in lecturas if f["H"] is not None]
    caudal = [f["Q"] for f in lecturas if f["Q"] is not None]
    return {
        "estacion": {"id": e["id"], "nombre": e["nombre"]},
        "dias": [{**d, "dia": d["dia"].isoformat()} for d in dias],
        "ultima_lectura": (
            {"fecha": con_h[-1]["fecha"].strftime("%Y-%m-%d %H:%M"), "H": con_h[-1]["H"]} if con_h else None
        ),
        "variacion_en_el_periodo": (
            round(con_dato[-1]["media"] - con_dato[0]["media"], 3) if len(con_dato) > 1 else None
        ),
        "caudal_Q_media": round(sum(caudal) / len(caudal), 1) if caudal else None,
        "cobertura": salto_grande.cobertura(lecturas, ini, min(fin, hoy_)),
        "nota": (
            "H es la altura del río tal como la publica la CTM, una lectura cada 15 minutos; el servicio no "
            "declara la unidad. variacion_en_el_periodo es la media del último día menos la del primero. "
            "Q (caudal) es null cuando la estación no lo mide: la fuente usa -999 para 'sin dato'."
        ),
        "fuente": FUENTE_CTM,
        "bajado": bajado,
    }


def _misma_ventana(anio: int, desde: date, hasta: date) -> tuple[date, date]:
    """La misma ventana de calendario, corrida para que termine en `anio`. Una ventana que cruza el
    año nuevo empieza en el anterior. El 29/02 cae en el 28/02."""
    corrimiento = hasta.year - anio

    def mover(d: date) -> date:
        try:
            return d.replace(year=d.year - corrimiento)
        except ValueError:
            return d.replace(year=d.year - corrimiento, day=28)

    return mover(desde), mover(hasta)


def nivel_rio_comparado(
    estacion: str = "Salto", dias: int = 7, hasta: str = "", hoy: Optional[date] = None
) -> NivelRioComparado:
    hoy_ = hoy or date.today()
    if not 1 <= dias <= 31:
        raise ValueError("dias: de 1 a 31")
    fin = _fecha(hasta, "hasta") if hasta else hoy_
    ini = fin - timedelta(days=dias - 1)
    e = _estacion(estacion)

    def media(desde: date, hasta_: date) -> tuple[Optional[float], float]:
        lecturas, _ = _lecturas(e, desde, hasta_, hoy)
        valores = [f["H"] for f in lecturas if f["H"] is not None]
        esperadas = ((min(hasta_, hoy_) - desde).days + 1) * salto_grande.LECTURAS_POR_DIA
        return (round(sum(valores) / len(valores), 3) if valores else None), len(valores) / esperadas

    actual, cob_actual = media(ini, fin)
    if actual is None:
        raise ValueError(f"la estación {e['nombre']} no tiene lecturas de altura entre {ini} y {fin}")
    anteriores, excluidos = [], []
    for anio in range(PRIMER_ANIO_RIO, fin.year):
        a_ini, a_fin = _misma_ventana(anio, ini, fin)
        m, cob = media(a_ini, a_fin)
        if m is None or cob < COBERTURA_MINIMA:
            excluidos.append(anio)
        else:
            anteriores.append({"anio": anio, "desde": a_ini.isoformat(), "hasta": a_fin.isoformat(), "media": m})
    todas = sorted([actual] + [a["media"] for a in anteriores], reverse=True)
    return {
        "estacion": {"id": e["id"], "nombre": e["nombre"]},
        "actual": {
            "desde": ini.isoformat(),
            "hasta": fin.isoformat(),
            "media": actual,
            "cobertura": round(cob_actual, 3),
        },
        "anios_anteriores": anteriores,
        "anios_excluidos": excluidos,
        "posicion": {"lugar": todas.index(actual) + 1, "de": len(todas), "orden": "de mayor a menor"},
        "nota": (
            f"Media de la altura H en los mismos {dias} días de calendario de cada año desde {PRIMER_ANIO_RIO}. "
            f"Un año con menos del {int(COBERTURA_MINIMA * 100)}% de las lecturas esperadas se excluye y se "
            "lista en anios_excluidos. La primera consulta baja un mes por año y puede tardar; después queda en caché."
        ),
        "fuente": FUENTE_CTM,
        "bajado": cache.sello(cache.directorio() / "salto_grande.xml"),
    }


# --- Variación real ----------------------------------------------------------------------------------

INDICES = {
    "UI": ("pesos uruguayos", "Unidad Indexada promedio del mes, BCU"),
    "IPC_AR": ("pesos argentinos", "IPC nacional de Argentina, INDEC"),
    "IPCA_BR": ("reales", "IPCA de Brasil, IBGE"),
}


def _indice_mensual(indice: str, meses: list[str], hoy: Optional[date]) -> tuple[dict[str, float], str, str]:
    if indice == "UI":
        fechas = [_mes(m, "mes") for m in meses]
        serie, bajado = cache.bcu_serie(MONEDAS["UI"], min(fechas), _fin_de_mes(max(fechas)), hoy=hoy)
        return {f["mes"]: f["promedio"] for f in bcu.promedio_mensual(serie)}, bajado, FUENTE_BCU
    if indice == "IPC_AR":
        serie, ruta = cache.archivo(cache.directorio() / "indec_ipc.json", indec.descargar, indec.leer, cache.DIA)
        return {p_["periodo"]: p_["valor"] for p_ in serie}, cache.sello(ruta), FUENTE_INDEC
    if indice == "IPCA_BR":
        serie, ruta = cache.archivo(cache.directorio() / "ibge_ipca.json", ibge.descargar, ibge.leer, cache.DIA)
        return {p_["periodo"]: p_["valor"] for p_ in serie}, cache.sello(ruta), FUENTE_IBGE
    raise ValueError(f"indice {indice!r}: {', '.join(INDICES)}")


def variacion_real(
    monto_inicial: float,
    mes_inicial: str,
    monto_final: float,
    mes_final: str,
    indice: Literal["UI", "IPC_AR", "IPCA_BR"] = "UI",
    hoy: Optional[date] = None,
) -> VariacionReal:
    if monto_inicial == 0:
        raise ValueError("monto_inicial es cero: la variación no está definida")
    if indice not in INDICES:
        raise ValueError(f"indice {indice!r}: {', '.join(INDICES)}")
    _mes(mes_inicial, "mes_inicial"), _mes(mes_final, "mes_final")
    valores, bajado, fuente = _indice_mensual(indice, [mes_inicial, mes_final], hoy)
    faltan = [m for m in (mes_inicial, mes_final) if m not in valores]
    if faltan:
        ultimo = max(valores) if valores else "ninguno"
        raise ValueError(
            f"sin {indice} para {faltan}: todavía no se publicó o está fuera de la serie (último: {ultimo})"
        )
    factor = valores[mes_final] / valores[mes_inicial]
    nominal = monto_final / monto_inicial
    moneda, descripcion = INDICES[indice]
    pct = lambda x: round((x - 1) * 100, 4)  # noqa: E731
    return {
        "variacion_nominal_pct": pct(nominal),
        "inflacion_del_periodo_pct": pct(factor),
        "variacion_real_pct": pct(nominal / factor),
        "monto_inicial_en_moneda_final": round(monto_inicial * factor, 2),
        "moneda": moneda,
        "indice": {mes_inicial: valores[mes_inicial], mes_final: valores[mes_final], "descripcion": descripcion},
        "nota": (
            "real = (final / inicial) / (índice final / índice inicial) - 1. monto_inicial_en_moneda_final es lo "
            f"que valdría el monto inicial en {moneda} de {mes_final}. Con la UI, el mes en curso usa los días "
            "publicados hasta hoy."
        ),
        "fuente": fuente,
        "bajado": bajado,
    }


# --- Límites: departamento y localidad de un punto ----------------------------------------------------


class DepartamentoDelPunto(TypedDict):
    nombre: Optional[str]
    tipo: Optional[str]
    asignado_a: Optional[str]
    nota: str


class LocalidadDelPunto(TypedDict):
    nombre: str
    departamento: str
    adentro: bool
    distancia_km: float
    poblacion_2023: Optional[int]
    viviendas_2023: Optional[int]


class DireccionCercana(TypedDict):
    direccion: str
    localidad: Optional[str]
    departamento: Optional[str]
    distancia_km: float


class Ubicacion(TypedDict):
    """La respuesta de `ubicar_punto()`."""

    lat: float
    lon: float
    departamento: DepartamentoDelPunto
    localidad: LocalidadDelPunto
    direccion_mas_cercana: Optional[DireccionCercana]
    nota: str
    fuente: str
    bajado: str


class DatosLocalidad(TypedDict):
    nombre: str
    departamento: str
    codigo: int
    poblacion_2023: Optional[int]
    viviendas_2023: Optional[int]
    capital: Optional[bool]
    centro_aproximado: dict[str, float]


class Localidades(TypedDict):
    """La respuesta de `localidad()`."""

    localidades: list[DatosLocalidad]
    total: int
    nota: str
    fuente: str
    bajado: str


_capas: dict[tuple[str, float], list[dict]] = {}


def _capa(capa: str) -> tuple[list[dict], str]:
    """Una capa de límites, de la caché (30 días: los límites casi no cambian) y leída una vez."""
    ruta = cache.directorio() / "limites" / f"{capa}.geojson"
    if cache.vencido(ruta, 30 * cache.DIA):
        cache.archivo(ruta, lambda p: limites.descargar(capa, p), lambda p: limites.leer(capa, p), 30 * cache.DIA)
    clave = (capa, ruta.stat().st_mtime)
    if clave not in _capas:
        _capas.clear() if len(_capas) > 4 else None
        _capas[clave] = limites.leer(capa, ruta)
    return _capas[clave], cache.sello(ruta)


def ubicar_punto(lat: float, lon: float) -> Ubicacion:
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError(f"latitud {lat} / longitud {lon}: coordenadas imposibles (se esperan grados, lat primero)")
    deps, bajado = _capa("departamentos")
    locs, _ = _capa("localidades")
    dep = limites.ubicar(deps, lat, lon)
    if dep is None:
        cercano, km = limites.mas_cercana([d for d in deps if d["tipo"] == "departamento"], lat, lon)
        departamento: DepartamentoDelPunto = {
            "nombre": None,
            "tipo": None,
            "asignado_a": None,
            "nota": f"El punto cae fuera de todo departamento (mar, río o fuera de Uruguay); el más cercano es "
            f"{cercano['nombre']}, a ~{km:.1f} km.",
        }
    elif dep["tipo"] == "limite_contestado":
        departamento = {
            "nombre": dep["nombre"],
            "tipo": dep["tipo"],
            "asignado_a": dep["departamento"],
            "nota": "Zona en disputa con Brasil (Rincón de Artigas). El INE la asigna a Artigas.",
        }
    else:
        departamento = {"nombre": dep["nombre"], "tipo": dep["tipo"], "asignado_a": None, "nota": ""}
    loc = limites.ubicar(locs, lat, lon)
    km_loc = 0.0
    if loc is None:
        loc, km_loc = limites.mas_cercana(locs, lat, lon)
    localidad: LocalidadDelPunto = {
        "nombre": loc["nombre"],
        "departamento": loc["departamento"],
        "adentro": km_loc == 0.0,
        "distancia_km": round(km_loc, 1),
        "poblacion_2023": loc["datos"].get("poblacion_2023"),
        "viviendas_2023": loc["datos"].get("viviendas_2023"),
    }
    notas = [
        "departamento y localidad salen de los polígonos oficiales del INE. Si el punto no está adentro de una "
        "localidad (campo, ruta), se da la más cercana con su distancia hasta el borde, aproximada."
    ]
    direccion = None
    try:
        cercanas = ideuy.inversa(lat, lon, 1)
        if cercanas:
            c = cercanas[0]
            direccion = {k: c[k] for k in ("direccion", "localidad", "departamento", "distancia_km")}
            notas.append(
                "direccion_mas_cercana es la dirección de IDE.uy más próxima, esté a la distancia que esté: su "
                "localidad es una etiqueta de esa dirección, no el polígono del INE."
            )
    except OSError as e:
        notas.append(f"IDE.uy no respondió para la dirección más cercana ({e}); departamento y localidad igual valen.")
    if dep is None:
        notas.append("El punto está fuera de todo departamento: en el mar, en un río limítrofe o fuera de Uruguay.")
    return {
        "lat": lat,
        "lon": lon,
        "departamento": departamento,
        "localidad": localidad,
        "direccion_mas_cercana": direccion,
        "nota": " ".join(notas),
        "fuente": FUENTE_LIMITES + "; " + FUENTE_IDE,
        "bajado": bajado,
    }


def localidad(nombre: str = "", departamento: str = "", cantidad: int = 20) -> Localidades:
    if not nombre.strip() and not departamento.strip():
        raise ValueError("pasar el nombre de una localidad, un departamento, o los dos")
    locs, bajado = _capa("localidades")
    nom, dep = _sin_tildes(nombre), _sin_tildes(departamento)
    elegidas = [
        a
        for a in locs
        if (not nom or _sin_tildes(a["nombre"]) == nom) and (not dep or _sin_tildes(a["departamento"]) == dep)
    ]
    if not elegidas:
        palabras = [p for p in nom.split() if len(p) >= 4] or [nom[:5]]
        parecidas = sorted({a["nombre"] for a in locs if any(p[:5] in _sin_tildes(a["nombre"]) for p in palabras)})
        donde = f" en {departamento}" if departamento else ""
        raise ValueError(f"no hay una localidad {nombre!r}{donde}. Parecidas: {parecidas[:10] or 'ninguna'}")
    elegidas.sort(key=lambda a: -(a["datos"].get("poblacion_2023") or 0))
    salida: list[DatosLocalidad] = [
        {
            "nombre": a["nombre"],
            "departamento": a["departamento"],
            "codigo": a["codigo"],
            "poblacion_2023": a["datos"].get("poblacion_2023"),
            "viviendas_2023": a["datos"].get("viviendas_2023"),
            "capital": a["datos"].get("capital"),
            "centro_aproximado": {
                "lat": round((a["bbox"][1] + a["bbox"][3]) / 2, 5),
                "lon": round((a["bbox"][0] + a["bbox"][2]) / 2, 5),
            },
        }
        for a in elegidas[: max(1, min(cantidad, 100))]
    ]
    return {
        "localidades": salida,
        "total": len(elegidas),
        "nota": (
            "Población y viviendas de los campos pob_tot_23 y viv_tot_23 de la capa del INE (el año sale del nombre "
            "del campo). Ordenadas de mayor a menor población. centro_aproximado es el centro del rectángulo que la "
            "contiene, no un centroide."
        ),
        "fuente": FUENTE_LIMITES,
        "bajado": bajado,
    }


# --- Elecciones ----------------------------------------------------------------------------------------


class MesasElectorales(TypedDict):
    comunes: int
    de_observados: int


class VotosPartido(TypedDict):
    lema: str
    votos: int
    pct_sobre_emitidos: Optional[float]


class VotosOpcion(TypedDict):
    opcion: str
    votos: int
    pct_sobre_emitidos: Optional[float]


class ResultadoElectoral(TypedDict):
    """La respuesta de `resultados_electorales()`."""

    eleccion: str
    departamento: Optional[str]
    mesas: MesasElectorales
    habilitados: int
    emitidos: int
    participacion_pct: Optional[float]
    anulados: int
    en_blanco: int
    observados_escrutados: int
    partidos: list[VotosPartido]
    opciones: list[VotosOpcion]
    nota: str
    fuente: str
    bajado: str


_elecciones: dict[tuple[str, float], list[dict]] = {}


def _archivo_electoral(eleccion: str, archivo: str) -> tuple[list[dict], str]:
    """Totales o desglose de una elección cerrada: se baja una vez (un año en caché) y se lee una vez."""
    ruta = cache.directorio() / "elecciones" / f"{eleccion}_{archivo}.csv"
    leer = elecciones.leer_totales if archivo == "totales" else elecciones.leer_desglose
    if cache.vencido(ruta, 365 * cache.DIA):
        cache.archivo(ruta, lambda p: elecciones.descargar(eleccion, archivo, p), leer, 365 * cache.DIA)
    clave = (str(ruta), ruta.stat().st_mtime)
    if clave not in _elecciones:
        if len(_elecciones) > 6:
            _elecciones.clear()
        _elecciones[clave] = leer(ruta)
    return _elecciones[clave], cache.sello(ruta)


def resultados_electorales(eleccion: str, departamento: str = "") -> ResultadoElectoral:
    if eleccion not in elecciones.ELECCIONES:
        raise ValueError(f"elección {eleccion!r}: las disponibles son {', '.join(elecciones.ELECCIONES)}")
    mesas, bajado = _archivo_electoral(eleccion, "totales")
    try:
        r = elecciones.resumen(mesas, departamento)
    except elecciones.EleccionesInvalido as e:
        raise ValueError(str(e)) from None
    emitidos = r["emitidos"]

    def pct(v: int) -> Optional[float]:
        return round(100 * v / emitidos, 2) if emitidos else None

    partidos: list[VotosPartido] = []
    if "desglose" in elecciones.ELECCIONES[eleccion]["archivos"]:
        desglose, _ = _archivo_electoral(eleccion, "desglose")
        nivel = "departamental" if eleccion.startswith("departamentales") else "nacional"
        partidos = [
            {"lema": p["lema"], "votos": p["votos"], "pct_sobre_emitidos": pct(p["votos"])}
            for p in elecciones.votos_por_lema(desglose, nivel, departamento)
        ]
    opciones: list[VotosOpcion] = [
        {"opcion": k, "votos": v, "pct_sobre_emitidos": pct(v)}
        for k, v in sorted(r["opciones"].items(), key=lambda kv: -kv[1])
    ]
    return {
        "eleccion": eleccion,
        "departamento": elecciones._sin_tildes(departamento) if departamento else None,
        "mesas": {"comunes": r["mesas_comunes"], "de_observados": r["mesas_de_observados"]},
        "habilitados": r["habilitados"],
        "emitidos": emitidos,
        "participacion_pct": r["participacion_pct"],
        "anulados": r["anulados"],
        "en_blanco": r["en_blanco"],
        "observados_escrutados": r["escrutados_en_mesas_de_observados"],
        "partidos": partidos,
        "opciones": opciones,
        "nota": (
            "Suma de todas las mesas publicadas por la Corte, incluidas las mesas de observados (votos de quienes "
            "votaron fuera de su circuito, escrutados aparte): es el escrutinio definitivo de los datos abiertos. "
            "Los observados no tienen localidad, así que no se pueden repartir por barrio o localidad. Partidos: "
            "votos por hoja más votos al lema. Los porcentajes son sobre los votos emitidos; los porcentajes "
            "oficiales de la Corte pueden usar otra base. En las nacionales, opciones son los plebiscitos."
        ),
        "fuente": FUENTE_ELECCIONES,
        "bajado": bajado,
    }


# --- Compras del Estado --------------------------------------------------------------------------------


class OrganismoComprador(TypedDict):
    nombre: str
    adjudicaciones: int
    pesos: float


class ItemMayor(TypedDict):
    ocid: str
    organismo: str
    descripcion: str
    cantidad: float
    precio_unitario: float
    moneda: str
    importe_pesos: float
    pct_del_total: float


class ComprasEstado(TypedDict):
    """La respuesta de `compras_estado()`."""

    anio: int
    organismo: Optional[str]
    buscar: Optional[str]
    adjudicaciones: int
    items: int
    total_pesos: float
    importes_por_moneda: dict[str, float]
    sin_moneda: float
    sin_convertir: dict[str, float]
    excluidas_por_estado: dict[str, int]
    organismos: list[OrganismoComprador]
    mayores_items: list[ItemMayor]
    aviso: str
    nota: str
    fuente: str
    bajado: str


PRIMER_ANIO_COMPRAS = 2002
UMBRAL_AVISO_PCT = 20.0
MINIMO_ITEMS_AVISO = 20  # con pocos ítems, que uno sea mucho del total es lo esperable
_compras_memo: dict[tuple[int, float], list[dict]] = {}


def _es_zip(ruta) -> bool:
    import zipfile

    if not zipfile.is_zipfile(ruta):
        raise ValueError(f"{ruta}: lo bajado no es un ZIP")
    return True


def _compras(anio: int) -> tuple[list[dict], str]:
    """Las adjudicaciones de un año: el ZIP en caché (el año en curso vence a la semana, los cerrados
    al año) y leído una sola vez por proceso. Solo se guarda un año en memoria: pesa."""
    ruta = cache.directorio() / "compras" / f"{anio}.zip"
    ttl = 7 * cache.DIA if anio >= date.today().year else 365 * cache.DIA
    if cache.vencido(ruta, ttl):
        cache.archivo(ruta, lambda p: compras.descargar(anio, p), _es_zip, ttl)
    clave = (anio, ruta.stat().st_mtime)
    if clave not in _compras_memo:
        _compras_memo.clear()
        _compras_memo[clave] = compras.leer_adjudicaciones(ruta)
    return _compras_memo[clave], cache.sello(ruta)


def compras_estado(
    anio: int, organismo: str = "", buscar: str = "", cantidad: int = 10, hoy: Optional[date] = None
) -> ComprasEstado:
    hoy_ = hoy or date.today()
    if not PRIMER_ANIO_COMPRAS <= anio <= hoy_.year:
        raise ValueError(f"año {anio}: la ARCE publica de {PRIMER_ANIO_COMPRAS} a {hoy_.year}")
    adjs, bajado = _compras(anio)
    base = compras.resumen(adjs, organismo, buscar)
    org, txt = _sin_tildes(organismo), _sin_tildes(buscar)

    elegidos = []  # (adjudicacion, item) activos que pasan los filtros
    for a in adjs:
        if a["estado"] != "active":
            continue
        comp = a["comprador"] or {"id": "", "nombre": "(sin comprador en el archivo)"}
        if org and org not in (_sin_tildes(comp["nombre"]), _sin_tildes(comp["id"])):
            continue
        for i in a["items"]:
            if i["moneda"] and (not txt or txt in _sin_tildes(i["descripcion"])):
                elegidos.append((a, comp, i))

    monedas = {i["moneda"] for _, _, i in elegidos if i["moneda"] != "UYU"}
    series: dict[int, dict] = {}
    if monedas and elegidos:
        desde = min(a["fecha"] for a, _, _ in elegidos)
        hasta = min(max(a["fecha"] for a, _, _ in elegidos), hoy_)
        for m in monedas:
            codigo = compras.BCU_POR_MONEDA.get(m)
            if codigo:
                series[codigo], _ = cache.bcu_serie(codigo, desde, hasta, hoy=hoy_)

    def cotizar(codigo: int, fecha: date) -> Optional[float]:
        serie = series.get(codigo)
        return bcu.cotizacion_del_dia(serie, fecha, hacia_atras=True) if serie else None

    total, sin_convertir = 0.0, {}
    por_org: dict[str, dict] = {}
    con_pesos = []
    for a, comp, i in elegidos:
        c = compras.convertir({i["moneda"]: i["importe"]}, a["fecha"], cotizar)
        for m, v in c["sin_convertir"].items():
            sin_convertir[m] = round(sin_convertir.get(m, 0.0) + v, 2)
        if c["sin_convertir"]:
            continue
        total += c["pesos"]
        o = por_org.setdefault(comp["id"], {"nombre": comp["nombre"], "ocids": set(), "pesos": 0.0})
        o["ocids"].add(a["ocid"])
        o["pesos"] += c["pesos"]
        con_pesos.append((c["pesos"], a, comp, i))
    con_pesos.sort(key=lambda x: -x[0])
    mayores: list[ItemMayor] = [
        {
            "ocid": a["ocid"],
            "organismo": comp["nombre"],
            "descripcion": i["descripcion"],
            "cantidad": i["cantidad"],
            "precio_unitario": i["precio_unitario"],
            "moneda": i["moneda"],
            "importe_pesos": round(p, 2),
            "pct_del_total": round(100 * p / total, 2) if total else 0.0,
        }
        for p, a, comp, i in con_pesos[:5]
    ]
    aviso = ""
    if mayores and len(con_pesos) >= MINIMO_ITEMS_AVISO and mayores[0]["pct_del_total"] > UMBRAL_AVISO_PCT:
        aviso = (
            f"Atención: un solo ítem es el {mayores[0]['pct_del_total']}% del total "
            f"({mayores[0]['descripcion'][:60]}, {mayores[0]['cantidad']} × {mayores[0]['precio_unitario']}). "
            "En estos archivos hay registros con cantidad × precio imposibles; revisar los mayores ítems antes "
            "de citar el total."
        )
    organismos: list[OrganismoComprador] = [
        {"nombre": o["nombre"], "adjudicaciones": len(o["ocids"]), "pesos": round(o["pesos"], 2)}
        for o in sorted(por_org.values(), key=lambda o: -o["pesos"])[: max(1, min(cantidad, 50))]
    ]
    return {
        "anio": anio,
        "organismo": organismo or None,
        "buscar": buscar or None,
        "adjudicaciones": base["adjudicaciones"],
        "items": base["items"],
        "total_pesos": round(total, 2),
        "importes_por_moneda": base["importes"],
        "sin_moneda": base["sin_moneda"],
        "sin_convertir": sin_convertir,
        "excluidas_por_estado": base["excluidas_por_estado"],
        "organismos": organismos,
        "mayores_items": mayores,
        "aviso": aviso,
        "nota": (
            "Adjudicaciones activas del año (los llamados, las anulaciones y las adjudicaciones canceladas, "
            "fallidas o pendientes no son gasto). Importe = cantidad × precio unitario; cada moneda se lleva a "
            "pesos con la cotización del BCU del día de la adjudicación (dólar y real billete). sin_moneda son "
            "ítems sin moneda declarada, que no se suman. `aviso` salta cuando, entre al menos 20 ítems, uno solo "
            "pasa del 20% del total. No se devuelven nombres de proveedores: pueden ser personas físicas."
        ),
        "fuente": FUENTE_COMPRAS,
        "bajado": bajado,
    }


# --- Sin red -------------------------------------------------------------------------------------


def validar_documento(numero: str, tipo: Literal["rut", "ci"]) -> Validacion:
    if tipo == "rut":
        estado, digitos = rut.validar_rut(numero)
    elif tipo == "ci":
        estado, digitos = rut.validar_ci(numero)
    else:
        raise ValueError("tipo: 'rut' o 'ci'")
    return {
        "tipo": tipo,
        "normalizado": digitos,
        "estado": estado,
        "valido": estado in ("valido", "dv_ok_estructura_rara"),
        "nota": "Validez aritmética del dígito verificador, no inscripción ante DGI ni existencia de la persona.",
    }


def semana(fecha: str) -> SemanaTyped:
    s = semanas.semana_de(_fecha(fecha, "fecha"))
    return {
        "etiqueta": s.corta,
        "etiqueta_con_anio": str(s),
        "desde": s.desde.isoformat(),
        "hasta": s.hasta.isoformat(),
        "de_total": s.de_total,
        "nota": "Semana ISO 8601, de lunes a domingo. El año de la semana puede no ser el del día.",
    }


def geocodificar_direccion(direccion: str, localidad: str = "", departamento: str = "") -> Geocodificacion:
    if not direccion.strip():
        raise ValueError("direccion vacía")
    r = ideuy.geocodificar(direccion, localidad, departamento)
    return {
        **r,
        "nota": (
            "calidad, de mejor a peor: puerta_exacta, puerta_aproximada (la API ajustó a una puerta vecina), "
            "esquina, calle_sin_numero (centro de la calle). calle_distinta, localidad_descartada y "
            "no_encontrado no traen coordenada: la API devolvió otra calle o el centro de la localidad."
        ),
        "fuente": FUENTE_IDE,
    }


def recursos_catalogo(dataset: str) -> RecursosCatalogo:
    return {
        "dataset": dataset,
        "recursos": catalogo.recursos(dataset),
        "fuente": f"catalogodatos.gub.uy, package_show?id={dataset}",
    }


# --- Diagnostico ----------------------------------------------------------------------------------


def diagnostico() -> Diagnostico:
    """Que copia de cada fuente esta en disco, de cuando es, y si esta vencida.

    Es la primera pregunta cuando un numero no cierra: no todos los archivos se refrescan igual (un
    mes cerrado del BCU no cambia nunca, el IPC se vuelve a pedir cada dia). **No sale a la red.**
    """
    d = cache.directorio()
    archivos = []
    for ruta in sorted(d.rglob("*")):
        if not ruta.is_file() or ruta.name.endswith(".nuevo"):
            continue
        archivos.append(
            {
                "archivo": str(ruta.relative_to(d)).replace("\\", "/"),
                "bajado": cache.sello(ruta),
                "bytes": ruta.stat().st_size,
            }
        )
    return {
        "directorio": str(d),
        "archivos": archivos,
        "nota": (
            "`bajado` es cuando se obtuvo la copia que se esta usando, en hora local. "
            "Si una fuente no aparece, todavia no se pidio en esta maquina: no es un error. "
            "Los archivos `.nuevo` son descargas en curso y se omiten."
        ),
    }
