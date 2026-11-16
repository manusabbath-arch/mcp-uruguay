"""Combustibles: precios y ventas de ANCAP, y la paridad de importación de URSEA."""

from __future__ import annotations

from typing import Optional

# En Python < 3.12, pydantic no arma el esquema de un `typing.TypedDict`: el SDK se queda sin
# esquema de salida y la respuesta sin `structuredContent`. Medido en el CI de 3.10 y 3.11.
from typing_extensions import NotRequired, TypedDict
from uydatos import ancap, ancap_ventas

from mcp_uruguay import cache
from mcp_uruguay.herramientas.comun import _mes, _sin_tildes

FUENTE_ANCAP = "ANCAP, dataset ancap-precio-combustible-pe de catalogodatos.gub.uy"


FUENTE_ANCAP_VENTAS = "ANCAP, dataset ancap-cantidad-ventas-combustibles de catalogodatos.gub.uy"


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
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


class LineaCombustible(TypedDict):
    """Un producto de las ventas de ANCAP: el nombre para pasar en `linea`, su familia y su unidad."""

    linea: str
    familia: str
    unidad: str
    mercados: list[str]


class MesVentas(TypedDict):
    mes: str
    cantidad: float


class AnioVentas(TypedDict):
    """El total de un año y cuántos meses lo forman: dos años con distinta cantidad de meses no se comparan."""

    anio: int
    cantidad: float
    meses: int
    faltan: list[int]


class VentasCombustible(TypedDict, total=False):
    """La respuesta de `ventas_combustible()`, en sus dos caminos.

    Sin `linea` trae `lineas`, `mercados` y `cobertura`; con `linea`, trae `linea`, `mercado`,
    `unidad`, `ventas` y `por_anio`. `nota`, `fuente` y `bajado` van siempre.
    """

    lineas: list[LineaCombustible]
    mercados: list[str]
    cobertura: dict[str, list[int]]
    linea: str
    mercado: str
    unidad: str
    ventas: list[MesVentas]
    por_anio: list[AnioVentas]
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


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


_NOTA_VENTAS = (
    "Cantidades vendidas por ANCAP (no precios), sumando las banderas B/E y B/N. El archivo es una "
    "ventana móvil de cinco años con meses que no se publicaron: un mes que falta no es cero. Los "
    "negativos son correcciones de la fuente y se suman. QUEROSENO (familia BLANCOS) y QUEROSENOS "
    "(SOLVENTES) son productos distintos."
)


def _clave(texto: str) -> str:
    return " ".join(_sin_tildes(texto).upper().split())


def ventas_combustible(linea: str = "", mercado: str = "", desde: str = "", hasta: str = "") -> VentasCombustible:
    registros, ruta = cache.archivo(
        cache.directorio() / "ancap_ventas.csv", ancap_ventas.descargar, ancap_ventas.leer, cache.DIA
    )
    base = {"nota": _NOTA_VENTAS, "fuente": FUENTE_ANCAP_VENTAS, "bajado": cache.sello(ruta)}
    meses_por_anio: dict[int, set[int]] = {}
    for r in registros:
        meses_por_anio.setdefault(r["anio"], set()).add(r["mes"])
    faltan = {a: [m for m in range(1, 13) if m not in ms] for a, ms in meses_por_anio.items()}
    mercados = sorted({r["mercado"] for r in registros})

    if not linea:
        lineas: dict[tuple[str, str, str], set[str]] = {}
        for r in registros:
            lineas.setdefault((r["linea"], r["familia"], r["unidad"]), set()).add(r["mercado"])
        return {
            "lineas": [
                {"linea": li, "familia": fa, "unidad": un, "mercados": sorted(ms)}
                for (li, fa, un), ms in sorted(lineas.items())
            ],
            "mercados": mercados,
            "cobertura": {str(a): f for a, f in sorted(faltan.items()) if f},
            **base,
        }

    por_clave = {_clave(r["linea"]): r["linea"] for r in registros}
    if _clave(linea) not in por_clave:
        parecidos = sorted(v for k, v in por_clave.items() if _clave(linea).split()[0][:4] in k)
        raise ValueError(f"linea {linea!r} no existe. Parecidas: {parecidos or sorted(por_clave.values())}")
    nombre = por_clave[_clave(linea)]
    elegido = None
    if mercado:
        por_mercado = {_clave(m): m for m in mercados}
        if _clave(mercado) not in por_mercado:
            raise ValueError(f"mercado {mercado!r} no existe. Hay: {mercados}")
        elegido = por_mercado[_clave(mercado)]
    unidades = sorted({r["unidad"] for r in registros if r["linea"] == nombre})
    if len(unidades) != 1:
        raise ValueError(f"la línea {nombre!r} viene en más de una unidad {unidades}: no se suman")
    d = _mes(desde, "desde") if desde else None
    h_ = _mes(hasta, "hasta") if hasta else None
    serie = [
        s
        for s in ancap_ventas.serie_mensual(registros, unidad=unidades[0], mercado=elegido, linea=nombre)
        if (d is None or (s["anio"], s["mes"]) >= (d.year, d.month))
        and (h_ is None or (s["anio"], s["mes"]) <= (h_.year, h_.month))
    ]
    if not serie:
        raise ValueError(f"no hay ventas de {nombre!r}" + (f" en {elegido}" if elegido else "") + " en ese período")
    anios: dict[int, list[dict]] = {}
    for s in serie:
        anios.setdefault(s["anio"], []).append(s)
    return {
        "linea": nombre,
        "mercado": elegido or "todos",
        "unidad": unidades[0],
        "ventas": [{"mes": f"{s['anio']}-{s['mes']:02d}", "cantidad": round(s["cantidad"], 6)} for s in serie],
        "por_anio": [
            {
                "anio": a,
                "cantidad": round(sum(s["cantidad"] for s in ss), 6),
                "meses": len(ss),
                "faltan": [m for m in range(1, 13) if m not in {s["mes"] for s in ss}],
            }
            for a, ss in sorted(anios.items())
        ],
        **base,
    }
