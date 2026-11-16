"""Territorio: límites departamentales, localidades y geocodificación de direcciones."""

from __future__ import annotations

from typing import Optional

# En Python < 3.12, pydantic no arma el esquema de un `typing.TypedDict`: el SDK se queda sin
# esquema de salida y la respuesta sin `structuredContent`. Medido en el CI de 3.10 y 3.11.
from typing_extensions import NotRequired, TypedDict
from uydatos import ideuy, limites

from mcp_uruguay import cache
from mcp_uruguay.herramientas.comun import _sin_tildes

FUENTE_IDE = "IDE.uy, API pública de direcciones (direcciones.ide.uy)"


FUENTE_LIMITES = "INE: límites departamentales (vía la IDE) y localidades con población 2023 (vía el MIDES)"


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
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


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
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


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
