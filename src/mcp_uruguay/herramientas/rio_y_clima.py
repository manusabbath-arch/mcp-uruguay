"""Clima y río: INIA, INUMET, Salto Grande y el sistema de alerta del INA."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Optional

# En Python < 3.12, pydantic no arma el esquema de un `typing.TypedDict`: el SDK se queda sin
# esquema de salida y la respuesta sin `structuredContent`. Medido en el CI de 3.10 y 3.11.
from typing_extensions import NotRequired, TypedDict
from uydatos import ina, inia, inumet, red, salto_grande

from mcp_uruguay import cache
from mcp_uruguay.herramientas.comun import _fecha, _sin_tildes

FUENTE_INIA = "INIA, Unidad GRAS, estación Salto Grande (dataset inia-precipitacion-temps-extremas-sg)"


FUENTE_INUMET = "INUMET, observaciones meteorologicas de siete estaciones, catalogodatos.gub.uy"


FUENTE_CTM = "Comisión Técnica Mixta de Salto Grande, web service www.saltogrande.org/ws.php"


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
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


class EstacionInumet(TypedDict):
    """La cobertura de una estacion de INUMET para una variable. Un dia es completo si trae todas las
    observaciones que esa variable publica por dia."""

    estacion: str
    primera: str
    ultima: str
    filas: int
    dias: int
    dias_completos: int
    nulos: dict[str, int]
    extremos: dict[str, dict[str, Optional[float]]]


class DiaInumet(TypedDict):
    """Un dia local de una estacion. `valor` en None = el dia no esta completo (o tiene un nulo): una
    agregacion sobre horas sueltas es un piso, no el total del dia."""

    fecha: str
    valor: Optional[float]
    observaciones: int
    nulos: int


class SerieInumet(TypedDict):
    """La serie diaria de una columna de la variable pedida."""

    columna: str
    agregacion: str
    dias: list[DiaInumet]


class ObservacionesInumet(TypedDict, total=False):
    """La respuesta de `observaciones_inumet()`, en sus dos caminos.

    Sin `estacion`: `estaciones` trae la cobertura de cada una. Con `estacion`, `desde`, `hasta` y
    `agregacion`: `series` trae un dia por fila. `nota`, `fuente` y `bajado` van siempre.
    """

    variable: str
    estaciones: list[EstacionInumet]
    estacion: str
    series: list[SerieInumet]
    lineas_sin_dato: int
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


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
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


MAX_DIAS = 400


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


_serie_inumet: dict[tuple[str, float], list[dict]] = {}


INUMET_VARIABLES = tuple(n for n, (_, _, horaria) in inumet.DATASETS.items() if horaria)


def _inumet(variable: str) -> tuple[list[dict], Path, int]:
    if variable not in INUMET_VARIABLES:
        raise ValueError(f"variable {variable!r} desconocida; las horarias son {', '.join(INUMET_VARIABLES)}")
    ruta = cache.directorio() / "inumet" / f"inumet_{variable}.csv"
    _, ruta = cache.archivo(
        ruta,
        lambda destino: inumet.descargar(variable, destino),
        lambda r: inumet.valor_por_estacion(r, variable),
        cache.DIA,
    )
    clave = (variable, ruta.stat().st_mtime)
    if clave not in _serie_inumet:
        for vieja in [k for k in _serie_inumet if k[0] == variable]:
            del _serie_inumet[vieja]
        _serie_inumet[clave] = inumet.valor_por_estacion(ruta, variable)
    return _serie_inumet[clave], ruta, inumet.filas_sin_dato(ruta)


def observaciones_inumet(
    variable: str, estacion: str = "", desde: str = "", hasta: str = "", agregacion: str = ""
) -> ObservacionesInumet:
    """Observaciones horarias de INUMET agregadas al dia local. **Sale a la red.**

    Sin `estacion`: la cobertura de las estaciones (filas, dias completos, nulos y extremos). Con
    `estacion` (el nombre, o una parte: "salto" resuelve "Salto G3"), `desde`, `hasta` y `agregacion`:
    una fila por dia local. La agregacion no tiene valor por defecto: para la temperatura el dia es
    el `max` o el `min`, para la lluvia la `suma`, y elegir por quien llama es lo que esto no hace.
    """
    serie, ruta, sin_dato = _inumet(variable)
    base: ObservacionesInumet = {
        "variable": variable,
        "lineas_sin_dato": sin_dato,
        "nota": (
            "La fuente publica la hora en UTC; los dias se cuentan en hora local de Uruguay (UTC-3). "
            "Un dia al que le falta alguna observacion devuelve valor null, no cero. "
            "El viento se publica cada dos horas (12 por dia)."
        ),
        "fuente": FUENTE_INUMET,
        "bajado": cache.sello(ruta),
    }
    if not estacion:
        if desde or hasta or agregacion:
            raise ValueError("observaciones_inumet: `desde`, `hasta` y `agregacion` piden tambien `estacion`.")
        r = inumet.resumen(serie)
        return {
            **base,
            "estaciones": [
                {
                    "estacion": nombre,
                    "primera": d["primera"].isoformat(),
                    "ultima": d["ultima"].isoformat(),
                    "filas": d["filas"],
                    "dias": d["dias"],
                    "dias_completos": d["dias_completos"],
                    "nulos": d["nulos"],
                    "extremos": d["extremos"],
                }
                for nombre, d in r["estaciones"].items()
            ],
        }
    if not (desde and hasta and agregacion):
        raise ValueError(
            "observaciones_inumet: con `estacion` van tambien `desde`, `hasta` (AAAA-MM-DD) y `agregacion` "
            f"({', '.join(inumet.AGREGACIONES)}): no se adivina ninguna."
        )
    if agregacion not in inumet.AGREGACIONES:
        raise ValueError(f"agregacion {agregacion!r} desconocida; las declaradas son {', '.join(inumet.AGREGACIONES)}")
    ini, fin = _fecha(desde, "desde"), _fecha(hasta, "hasta")
    if fin < ini:
        raise ValueError("hasta es anterior a desde")
    if (fin - ini).days >= MAX_DIAS:
        raise ValueError(f"rango demasiado largo: hasta {MAX_DIAS} dias por consulta")
    buscado = _sin_tildes(estacion)
    candidatas = [e for e in inumet.ESTACIONES if buscado in _sin_tildes(e)]
    if len(candidatas) != 1:
        raise ValueError(
            f"estacion {estacion!r}: {len(candidatas)} coincidencias. Las siete son {', '.join(inumet.ESTACIONES)}."
        )
    nombre = candidatas[0]
    series: list[SerieInumet] = []
    for columna in inumet.DATASETS[variable][1]:
        dias = inumet.serie_diaria(serie, nombre, columna, agregacion)
        series.append(
            {
                "columna": columna,
                "agregacion": agregacion,
                "dias": [
                    {
                        "fecha": d["fecha"].isoformat(),
                        "valor": d["valor"],
                        "observaciones": d["horas"],
                        "nulos": d["nulos"],
                    }
                    for d in dias
                    if ini <= d["fecha"] <= fin
                ],
            }
        )
    return {**base, "estacion": nombre, "series": series}


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
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


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
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


ESTACION_SALTO = "A501258E"


MAX_DIAS_RIO = 92


PRIMER_ANIO_RIO = 2017  # desde cuándo hay lecturas en la estación Salto (medido el 10/10/2026)


COBERTURA_MINIMA = 0.5


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
    hoy_ = hoy or cache.hoy()
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
    hoy_ = hoy or cache.hoy()
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


class PuntoRioIna(TypedDict):
    """Un día (o un mes, en rangos largos) de la serie: valor mínimo, medio y máximo."""

    periodo: str
    min: float
    media: float
    max: float
    lecturas: int


class NivelesIna(TypedDict):
    alerta: Optional[float]
    evacuacion: Optional[float]
    aguas_bajas: Optional[float]


class NivelRioIna(TypedDict):
    """La respuesta de `nivel_rio_ina()`."""

    escala: str
    variable: str
    unidad: str
    serie_id: int
    agregacion: str
    puntos: list[PuntoRioIna]
    ultima_lectura: str
    ultima_carga: str
    dias_de_atraso: int
    niveles: NivelesIna
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


FUENTE_INA = "INA (Argentina), sistema de alerta del INFORM, alerta.ina.gob.ar: escalas de Prefectura Naval"


PRIMER_DIA_INA = date(1931, 1, 1)


DIAS_DIARIO_INA = 400  # hasta acá se devuelve un punto por día; más largo, uno por mes


ATRASO_AVISO_INA = 7


def _serie_ina(escala: str, variable: str) -> int:
    buscada = _sin_tildes(escala)
    escalas = sorted({s["nombre"] for s in ina.SERIES.values()})
    for sid, s in ina.SERIES.items():
        if _sin_tildes(s["nombre"]) == buscada and s["var"] == variable:
            return sid
    raise ValueError(f"escala {escala!r}: las del río Uruguay en el INA son {escalas}")


def _niveles_ina(serie: int) -> dict:
    import json

    datos, _ = cache.archivo(
        cache.directorio() / "ina" / f"meta_{serie}.json",
        lambda r: r.write_text(json.dumps(ina.metadata(serie), ensure_ascii=False), encoding="utf-8"),
        lambda r: json.loads(r.read_text(encoding="utf-8")),
        30 * cache.DIA,
    )
    return datos


def nivel_rio_ina(
    escala: str = "Concordia",
    variable: Literal["H", "Q"] = "H",
    desde: str = "",
    hasta: str = "",
    hoy: Optional[date] = None,
) -> NivelRioIna:
    if variable not in ("H", "Q"):
        raise ValueError(f"variable {variable!r}: H (altura, m) o Q (caudal, m³/s)")
    serie = _serie_ina(escala, variable)
    hoy_ = hoy or date.today()
    fin = _fecha(hasta, "hasta") if hasta else hoy_
    ini = _fecha(desde, "desde") if desde else fin - timedelta(days=30)
    if ini >= fin:
        raise ValueError(f"desde {ini} tiene que ser anterior a hasta {fin}")
    if ini < PRIMER_DIA_INA:
        raise ValueError(f"desde {ini}: la serie más larga empieza en {PRIMER_DIA_INA}")
    fin = min(fin, hoy_)
    # Un rango que termina antes de ayer es cerrado; el que llega a hoy vence a la hora: el dato del
    # día se carga por la tarde (medido: 12:43 a 18:01 UY).
    ttl = cache.HORA if fin >= hoy_ - timedelta(days=1) else 30 * cache.DIA
    filas, ruta = cache.archivo(
        cache.directorio() / "ina" / f"serie_{serie}_{ini}_{fin}.csv",
        lambda r: red.bajar(ina.url_observaciones(serie, ini, fin), r),
        lambda r: ina.observaciones(serie, ini, fin, crudo=r),
        ttl,
    )
    mensual = (fin - ini).days > DIAS_DIARIO_INA
    grupos: dict[str, list[float]] = {}
    for f in filas:
        clave = f["dia_local"].strftime("%Y-%m") if mensual else f["dia_local"].isoformat()
        grupos.setdefault(clave, []).append(f["valor"])
    puntos: list[PuntoRioIna] = [
        {
            "periodo": k,
            "min": min(v),
            "media": round(sum(v) / len(v), 3),
            "max": max(v),
            "lecturas": len(v),
        }
        for k, v in sorted(grupos.items())
    ]
    ultima = max(filas, key=lambda f: f["instancia"])
    carga = max(f["carga"] for f in filas)
    atraso = (hoy_ - ultima["dia_local"]).days
    meta = _niveles_ina(serie)
    s = ina.SERIES[serie]
    nota = (
        f"{'Un punto por mes' if mensual else 'Un punto por día local de Uruguay'} con el mínimo, la media y el "
        "máximo de las lecturas: la cadencia no es fija (hay días con dos lecturas) y un día sin fila es un "
        "hueco, no un cero. La unidad la fija el lector (el API no la declara). Las escalas son de Prefectura "
        "Naval Argentina: Concordia está frente a Salto, pero no es la estación Salto de la CTM (`nivel_rio`), "
        "y las dos alturas no son comparables entre sí. `niveles` son los de alerta de la propia escala, "
        "según la metadata del INA, en la misma unidad que la altura."
    )
    if atraso > ATRASO_AVISO_INA:
        nota += (
            f" ATENCIÓN: la última lectura es de hace {atraso} días; la serie viene con atraso en la fuente "
            "(el caudal de Concordia trae meses). No presentarla como el dato de hoy."
        )
    return {
        "escala": s["nombre"],
        "variable": variable,
        "unidad": ina.UNIDADES[variable],
        "serie_id": serie,
        "agregacion": "mensual" if mensual else "diaria",
        "puntos": puntos,
        "ultima_lectura": ultima["instancia"].strftime("%Y-%m-%d %H:%MZ"),
        "ultima_carga": carga.strftime("%Y-%m-%d %H:%MZ"),
        "dias_de_atraso": atraso,
        "niveles": {
            "alerta": meta.get("nivel_alerta"),
            "evacuacion": meta.get("nivel_evacuacion"),
            "aguas_bajas": meta.get("nivel_aguas_bajas"),
        },
        "nota": nota,
        "fuente": FUENTE_INA,
        "bajado": cache.sello(ruta),
    }
