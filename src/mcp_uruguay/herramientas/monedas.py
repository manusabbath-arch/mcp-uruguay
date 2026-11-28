"""Monedas e índices de precios: BCU, IPC de Argentina e IPCA de Brasil, y la variación real."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal, Optional

# En Python < 3.12, pydantic no arma el esquema de un `typing.TypedDict`: el SDK se queda sin
# esquema de salida y la respuesta sin `structuredContent`. Medido en el CI de 3.10 y 3.11.
from typing_extensions import NotRequired, TypedDict
from uydatos import bcu, ibge, indec
from uydatos import feriados as _feriados

from mcp_uruguay import cache
from mcp_uruguay.herramientas.comun import VariacionReal, _fecha, _mes

Moneda = Literal["USD", "UI", "ARS", "BRL"]


MONEDAS: dict[str, int] = {"USD": 2225, "UI": 9800, "ARS": 501, "BRL": 1001}


FUENTE_BCU = "Banco Central del Uruguay, web service de cotizaciones (cotizaciones.bcu.gub.uy)"


FUENTE_INDEC = "INDEC, vía la API de series de tiempo de datos.gob.ar (serie 148.3_INIVELNAL_DICI_M_26)"


FUENTE_IBGE = "IBGE, API SIDRA, tabla 1737, variable 2266 (IPCA número-índice)"


class Cotizacion(cache.Procedencia, TypedDict):
    """La respuesta de `cotizacion()`."""

    moneda: str
    nombre_bcu: str
    fecha_pedida: str
    fecha_cotizacion: Optional[str]
    valor_en_pesos: Optional[float]
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


class MesBCU(TypedDict):
    """Una fila de `cotizacion_mensual()`: el promedio de un mes y cuantos dias entraron."""

    mes: str
    promedio: float
    dias: int
    completo: bool


class CotizacionMensual(cache.Procedencia, TypedDict):
    """La respuesta de `cotizacion_mensual()`."""

    moneda: str
    nombre_bcu: str
    meses: list[MesBCU]
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


class PesosConstantes(cache.Procedencia, TypedDict):
    """La respuesta de `pesos_constantes()`."""

    base: str
    montos_en_pesos_de_la_base: dict[str, float]
    ui_promedio_usada: dict[str, float]
    metodo: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


class PuntoIndice(TypedDict):
    """Un mes de una serie de precios: el indice, no la variacion."""

    periodo: str
    valor: float


class IpcArgentina(cache.Procedencia, TypedDict):
    """La respuesta de `ipc_argentina()`."""

    serie: str
    puntos: list[PuntoIndice]
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


class IpcaBrasil(cache.Procedencia, TypedDict):
    """La respuesta de `ipca_brasil()`."""

    serie: str
    puntos: list[PuntoIndice]
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


MAX_MESES = 240


def _fin_de_mes(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def _codigo(moneda: str) -> int:
    if moneda not in MONEDAS:
        raise ValueError(f"moneda {moneda!r}: las disponibles son {', '.join(MONEDAS)}")
    return MONEDAS[moneda]


def _tipo_de_dia(dia: date) -> str:
    """Qué se sabe del día pedido. No afirma que sea la causa de que falte la publicación."""
    if dia.year >= _feriados.ANIO_MINIMO:
        nombres = [f.nombre for f in _feriados.feriados_de(dia)]
        if nombres:
            return f"es feriado nacional ({' y '.join(nombres)})"
    if dia.weekday() >= 5:
        return "es sábado" if dia.weekday() == 5 else "es domingo"
    if dia.year < _feriados.ANIO_MINIMO:
        return "puede ser feriado o un día sin cotización"
    return "no es fin de semana ni feriado nacional"


#: Lo que se sabe de la regla fiscal, medido el 2026-11-27 (docs/2026-11-27-clientes-problemas-y-lo-que-ya-existe.md).
#: Circulan versiones distintas; la herramienta cita la de la DGI y no decide por el contador.
_USO_FISCAL = (
    " Uso fiscal: la guía de la DGI «Operaciones en moneda extranjera» (26/09/2023) indica el tipo de cambio "
    "interbancario del día anterior a la operación, o el del último día hábil anterior; con esta herramienta "
    "es pedir la fecha del día anterior con hacia_atras=true. Esta serie es la «{serie}» del BCU. Hay guías "
    "privadas que indican la compra del BROU y e-Factura no especifica el campo: confirmar con el contador."
)
_UI_FISCAL = " Qué cotización corresponde para un fin fiscal no lo decide esta herramienta."


def cotizacion(moneda: Moneda, fecha: str, hacia_atras: bool = False, hoy: Optional[date] = None) -> Cotizacion:
    dia = _fecha(fecha, "fecha")
    codigo = _codigo(moneda)
    desde = dia - timedelta(days=bcu.MAX_DIAS_ATRAS) if hacia_atras else dia
    serie, bajado = cache.bcu_serie(codigo, desde, dia, hoy=hoy)
    valor = bcu.cotizacion_del_dia(serie, dia, hacia_atras=hacia_atras)
    usada = next((d for d in sorted(serie, reverse=True) if d <= dia), None) if valor is not None else None
    if valor is None:
        nota = (
            f"Sin publicación ese día: {_tipo_de_dia(dia)}. "
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
        "nota": nota + (_USO_FISCAL.format(serie=bcu.MONEDAS[codigo]) if moneda != "UI" else _UI_FISCAL),
        "fuente": FUENTE_BCU,
        "bajado": bajado,
    }


def cotizacion_mensual(moneda: Moneda, desde: str, hasta: str, hoy: Optional[date] = None) -> CotizacionMensual:
    ini, fin = _mes(desde, "desde"), _fin_de_mes(_mes(hasta, "hasta"))
    if (fin.year - ini.year) * 12 + fin.month - ini.month >= MAX_MESES:
        raise ValueError(f"rango demasiado largo: hasta {MAX_MESES} meses por consulta")
    codigo = _codigo(moneda)
    serie, bajado = cache.bcu_serie(codigo, ini, fin, hoy=hoy)
    hoy = hoy or cache.hoy()
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
