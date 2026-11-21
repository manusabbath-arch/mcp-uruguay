"""El Estado: resultados electorales, compras públicas y el Parlamento."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

# En Python < 3.12, pydantic no arma el esquema de un `typing.TypedDict`: el SDK se queda sin
# esquema de salida y la respuesta sin `structuredContent`. Medido en el CI de 3.10 y 3.11.
from typing_extensions import NotRequired, TypedDict
from uydatos import bcu, compras, elecciones, parlamento

from mcp_uruguay import cache
from mcp_uruguay.herramientas.comun import _fecha, _sin_tildes

FUENTE_COMPRAS = "ARCE, compras del Estado en OCDS (dataset arce-datos-historicos-de-compras)"


FUENTE_PARLAMENTO = "Parlamento del Uruguay, datos abiertos en catalogodatos.gub.uy"


FUENTE_ELECCIONES = "Corte Electoral, resultados por mesa publicados en catalogodatos.gub.uy"


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
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


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
            "votos por hoja más votos al lema. Los porcentajes son sobre los votos emitidos, observados incluidos. "
            "La cifra difundida la noche de la elección es el escrutinio primario, sin observados, y por eso "
            "difiere en unas décimas: al citar un porcentaje, decir que es del escrutinio definitivo con "
            "observados. En las nacionales, opciones son los plebiscitos."
        ),
        "fuente": FUENTE_ELECCIONES,
        "bajado": bajado,
    }


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
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


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
    ttl = 7 * cache.DIA if anio >= cache.hoy().year else 365 * cache.DIA
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
    hoy_ = hoy or cache.hoy()
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


LEGISLATURA_ACTUAL = 50


LEGISLATURAS_ASISTENCIA = range(46, LEGISLATURA_ACTUAL + 1)


LEGISLATURAS_PROYECTOS = range(42, LEGISLATURA_ACTUAL + 1)


class FilaAsistencia(TypedDict):
    nombre: Optional[str]
    citaciones: int
    asistencias: int
    faltas_con_aviso: int
    faltas_sin_aviso: int
    licencias: int
    pasajes_a_presidente: int
    pct_asistencia: Optional[float]


class TasaPedidos(TypedDict):
    """Cuántos pedidos hay en cada estado y qué porcentaje de los que ya cumplieron el plazo se contestó."""

    pedidos: int
    contestado: int
    vencido: int
    sin_contestar: int
    no_entregado: int
    con_plazo_cumplido: int
    pct_contestado_con_plazo_cumplido: Optional[float]


class OrganismoPedidos(TasaPedidos):
    organismo: str


class SemestrePedidos(TasaPedidos):
    semestre: str


class PedidoInforme(TypedDict):
    fecha: str
    organismo: str
    autores: list[str]
    tema: str
    estado: str
    url_oficio: str
    url_contestacion: Optional[str]


class PedidosDeInformes(TypedDict):
    """La respuesta de `pedidos_de_informes()`."""

    desde: str
    hasta: str
    plazo_dias: int
    total: TasaPedidos
    por_organismo: list[OrganismoPedidos]
    por_semestre: list[SemestrePedidos]
    pedidos_por_partido: dict[str, int]
    autores_sin_identificar: dict[str, int]
    contestados_sin_enlace: int
    con_varios_autores: int
    repetidos: int
    pedidos: list[PedidoInforme]
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


class AsistenciaParlamentaria(TypedDict):
    """La respuesta de `asistencia_parlamentaria()`."""

    camara: str
    legislatura: int
    personas: int
    filas_sin_nombre: int
    nombres_repetidos: list[str]
    minimo_citaciones: int
    con_el_minimo: int
    fuera_por_pocas_citaciones: int
    menor_asistencia: list[FilaAsistencia]
    mayor_asistencia: list[FilaAsistencia]
    encontrados: list[FilaAsistencia]
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


class Ley(TypedDict):
    numero: int
    fecha: str
    titulo: str
    texto_impo: str
    texto_parlamento: str
    cantidad_que_cita: Optional[int]
    cantidad_que_la_citan: Optional[int]


class Leyes(TypedDict):
    """La respuesta de `leyes()`."""

    total: int
    leyes: list[Ley]
    duplicadas_descartadas: int
    sin_numero_descartadas: int
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


class Proyecto(TypedDict):
    asunto: int
    fecha: str
    titulo: str
    tipo: Optional[str]
    legislaturas: list[int]


class ProyectosParlamento(TypedDict):
    """La respuesta de `proyectos_parlamento()`."""

    total: int
    proyectos: list[Proyecto]
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


def _archivo_parlamento(clave: str, legislatura: Optional[int] = None) -> Path:
    """Un archivo del Parlamento en caché: la legislatura en curso y las leyes vencen al día, las
    legislaturas cerradas al año."""
    unico = legislatura is None
    nombre = f"{clave}.csv" if unico else f"{clave}-{legislatura}.csv"
    ruta = cache.directorio() / "parlamento" / nombre
    ttl = cache.DIA if unico or legislatura == LEGISLATURA_ACTUAL else 365 * cache.DIA
    if cache.vencido(ruta, ttl):
        cache.archivo(ruta, lambda p: parlamento.descargar(clave, p, legislatura), lambda p: p, ttl)
    return ruta


def asistencia_parlamentaria(
    camara: str,
    legislatura: int = LEGISLATURA_ACTUAL,
    nombre: str = "",
    minimo_citaciones: int = 10,
    cantidad: int = 10,
) -> AsistenciaParlamentaria:
    if camara not in ("senado", "diputados"):
        raise ValueError("camara: senado o diputados")
    if legislatura not in LEGISLATURAS_ASISTENCIA:
        primera = LEGISLATURAS_ASISTENCIA.start
        raise ValueError(f"legislatura {legislatura}: hay asistencias de la {primera} a la {LEGISLATURA_ACTUAL}")
    ruta = _archivo_parlamento(f"asistencias-{camara}", legislatura)
    try:
        r = parlamento.resumen_asistencias(
            parlamento.leer_asistencias(ruta), max(0, minimo_citaciones), nombre, max(1, min(cantidad, 50))
        )
    except parlamento.ParlamentoInvalido as e:
        raise ValueError(str(e)) from None
    campos = ("menor_asistencia", "mayor_asistencia", "encontrados")
    return {
        "camara": camara,
        "legislatura": legislatura,
        **{k: v for k, v in r.items() if k not in ("citaciones_totales",)},
        **{k: r[k] for k in campos},
        "nota": (
            "Hay muchas más personas que bancas: los suplentes, a veces con una o dos citaciones. El ranking solo "
            f"incluye a quienes tuvieron al menos {minimo_citaciones} citaciones. Citaciones = asistencias + faltas "
            "con y sin aviso; las licencias no son citaciones. El archivo no trae un identificador de persona: dos "
            "filas con el mismo nombre (nombres_repetidos) pueden ser dos períodos de una persona o dos homónimos, "
            "y no se unen. El porcentaje es un dato de asistencia a sesiones, no una evaluación del trabajo."
        ),
        "fuente": FUENTE_PARLAMENTO,
        "bajado": cache.sello(ruta),
    }


_NOTA_PEDIDOS = (
    "Pedidos de informes de Diputados (artículo 118 de la Constitución) de la legislatura actual. La Ley 17.673 "
    "da 45 días para contestar: el porcentaje se calcula sólo sobre los pedidos con ese plazo cumplido. Las "
    "respuestas siguen llegando después del plazo, así que los pedidos más nuevos tienen menos contestados "
    "(ver por_semestre): para comparar organismos, usar presentados_hasta y comparar una misma cohorte. Los "
    "estados son los que publica la Cámara: SIN CONTESTAR incluye pedidos con más de 45 días que no figuran "
    "como VENCIDO. No hay fecha de respuesta: se sabe si contestó, no cuánto tardó. El organismo es por donde "
    "se canaliza el pedido (un pedido sobre UTE va al Ministerio de Industria). Un pedido con autores de dos "
    "partidos cuenta en los dos. Medir cuánto contesta un organismo no evalúa su gestión."
)


def pedidos_de_informes(
    organismo: str = "", presentados_hasta: str = "", tema: str = "", cantidad: int = 20
) -> PedidosDeInformes:
    ruta = _archivo_parlamento("pedidos-informes")
    ruta_nomina = _archivo_parlamento("nomina")
    try:
        pedidos = parlamento.leer_pedidos(ruta)
        nomina = parlamento.leer_nomina(ruta_nomina)
        if tema:
            clave = _sin_tildes(tema)
            pedidos = [p for p in pedidos if clave in _sin_tildes(p["tema"])]
            if not pedidos:
                raise ValueError(f"ningún pedido con {tema!r} en el tema")
        hasta = _fecha(presentados_hasta, "presentados_hasta") if presentados_hasta else None
        r = parlamento.resumen_pedidos(pedidos, cache.hoy(), nomina, organismo, hasta)
    except parlamento.ParlamentoInvalido as e:
        raise ValueError(str(e)) from None
    elegidos = pedidos
    if organismo:
        clave = _sin_tildes(organismo)
        elegidos = [p for p in elegidos if clave in _sin_tildes(p["organismo"])]
    if hasta:
        elegidos = [p for p in elegidos if p["fecha"] <= hasta]
    muestra = sorted(elegidos, key=lambda p: p["fecha"], reverse=True)[: max(0, min(cantidad, 100))]
    return {
        **r,
        "pedidos": [{**p, "fecha": p["fecha"].isoformat()} for p in muestra] if (organismo or tema) else [],
        "nota": _NOTA_PEDIDOS,
        "fuente": "Cámara de Representantes, dataset crr-pedidos-de-informes y nómina, catalogodatos.gub.uy",
        "bajado": cache.sello(ruta),
    }


def leyes(
    buscar: str = "", desde: str = "", hasta: str = "", numero: Optional[int] = None, cantidad: int = 20
) -> Leyes:
    ruta = _archivo_parlamento("leyes")
    try:
        datos = parlamento.leer_leyes(ruta)
    except parlamento.ParlamentoInvalido as e:
        raise ValueError(str(e)) from None
    txt = _sin_tildes(buscar)
    ini = _fecha(desde, "desde") if desde else None
    fin = _fecha(hasta, "hasta") if hasta else None
    elegidas = [
        x
        for x in datos["leyes"]
        if (numero is None or x["numero"] == numero)
        and (not txt or txt in _sin_tildes(x["titulo"]))
        and (ini is None or x["fecha"] >= ini)
        and (fin is None or x["fecha"] <= fin)
    ]
    elegidas.sort(key=lambda x: -x["numero"])
    return {
        "total": len(elegidas),
        "leyes": [
            {
                "numero": x["numero"],
                "fecha": x["fecha"].isoformat(),
                "titulo": x["titulo"],
                "texto_impo": x["texto_impo"],
                "texto_parlamento": x["texto_parlamento"],
                "cantidad_que_cita": x["cantidad_que_cita"],
                "cantidad_que_la_citan": x["cantidad_que_la_citan"],
            }
            for x in elegidas[: max(1, min(cantidad, 100))]
        ],
        "duplicadas_descartadas": datos["duplicadas"],
        "sin_numero_descartadas": len(datos["sin_numero"]),
        "nota": (
            "Leyes promulgadas desde 1985, de la más nueva a la más vieja. texto_impo es el texto actualizado en "
            "IMPO. cantidad_que_cita y cantidad_que_la_citan son cantidades de leyes relacionadas, no listas."
        ),
        "fuente": FUENTE_PARLAMENTO,
        "bajado": cache.sello(ruta),
    }


def proyectos_parlamento(
    buscar: str = "", legislatura: Optional[int] = None, tipo: str = "", cantidad: int = 20
) -> ProyectosParlamento:
    if legislatura is not None and legislatura not in LEGISLATURAS_PROYECTOS:
        raise ValueError(
            f"legislatura {legislatura}: hay proyectos de la {LEGISLATURAS_PROYECTOS.start} a la {LEGISLATURA_ACTUAL}"
        )
    legs = [legislatura] if legislatura is not None else list(LEGISLATURAS_PROYECTOS)
    txt, tip = _sin_tildes(buscar), _sin_tildes(tipo)
    por_asunto: dict[int, Proyecto] = {}
    sellos = []
    for leg in legs:
        ruta = _archivo_parlamento("proyectos", leg)
        sellos.append(cache.sello(ruta))
        try:
            filas = parlamento.leer_proyectos(ruta)
        except parlamento.ParlamentoInvalido as e:
            raise ValueError(str(e)) from None
        for x in filas:
            if txt and txt not in _sin_tildes(x["titulo"]):
                continue
            if tip and tip not in _sin_tildes(x["tipo"] or ""):
                continue
            if x["asunto"] in por_asunto:
                por_asunto[x["asunto"]]["legislaturas"].append(leg)
                continue
            por_asunto[x["asunto"]] = {
                "asunto": x["asunto"],
                "fecha": x["fecha"].isoformat(),
                "titulo": x["titulo"],
                "tipo": x["tipo"],
                "legislaturas": [leg],
            }
    proyectos = sorted(por_asunto.values(), key=lambda p: p["fecha"], reverse=True)
    return {
        "total": len(proyectos),
        "proyectos": proyectos[: max(1, min(cantidad, 100))],
        "nota": (
            "Proyectos entrados al Parlamento desde 1985 (legislatura 42). Un mismo asunto puede aparecer en dos "
            "legislaturas (311 casos medidos): se cuenta una vez y legislaturas dice en cuáles está. Que un proyecto "
            "haya entrado no dice si se aprobó: para eso, leyes."
        ),
        "fuente": FUENTE_PARLAMENTO,
        "bajado": min(sellos) if sellos else "",
    }
