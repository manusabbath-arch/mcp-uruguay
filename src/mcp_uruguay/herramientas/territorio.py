"""Territorio: límites departamentales, localidades y geocodificación de direcciones."""

from __future__ import annotations

from typing import Optional

# En Python < 3.12, pydantic no arma el esquema de un `typing.TypedDict`: el SDK se queda sin
# esquema de salida y la respuesta sin `structuredContent`. Medido en el CI de 3.10 y 3.11.
from typing_extensions import NotRequired, TypedDict
from uydatos import censo, ideuy, limites
from uydatos.errores import DatosInvalidos

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
    poblacion_oficial_2023: Optional[int]


class DireccionCercana(TypedDict):
    direccion: str
    localidad: Optional[str]
    departamento: Optional[str]
    distancia_km: float


class Ubicacion(cache.Procedencia, TypedDict):
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
    poblacion_oficial_2023: Optional[int]
    centro_aproximado: dict[str, float]


class PoblacionDepartamento(TypedDict):
    departamento: str
    poblacion_oficial_2023: Optional[int]


class Localidades(cache.Procedencia, TypedDict):
    """La respuesta de `localidad()`."""

    localidades: list[DatosLocalidad]
    departamentos: list[PoblacionDepartamento]
    poblacion_oficial_total: Optional[int]
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
    cache.anotar_lectura(ruta)
    return _capas[clave], cache.sello(ruta)


FUENTE_CENSO = censo.FUENTE


def _tabulado_censo(cuadro: str) -> dict[str, int]:
    """Población oficial del Censo 2023, de la caché (30 días): por código INE de 5 dígitos (cuadro 13)
    o por nombre de departamento sin tildes (cuadro 12; el nombre, porque la capa y el tabulado lo
    escriben igual y el código de la capa no siempre trae el del departamento).

    Levanta `OSError` o `DatosInvalidos` si no se pudo bajar o leer: quien llama decide."""
    leer = censo.leer_departamentos if cuadro == "departamentos" else censo.leer_localidades
    filas, _ = cache.archivo(
        cache.directorio() / "censo" / f"{cuadro}.xlsx",
        lambda p: censo.descargar(cuadro, p),
        leer,
        30 * cache.DIA,
        url=censo.URLS[cuadro],
    )
    if cuadro == "departamentos":
        return {_sin_tildes(f["departamento"]): f["poblacion"] for f in filas}
    return {f["codigo"]: f["poblacion"] for f in filas}


def _aviso_censo(cuadro: str, error: Exception) -> str:
    """Motivo público de la ausencia: el error crudo puede contener rutas del servidor."""
    motivo = (
        "el tabulado no cumple el formato esperado"
        if isinstance(error, DatosInvalidos)
        else "no se pudo acceder a la fuente o a la copia local"
    )
    return (
        f" No se pudo leer el tabulado oficial de {cuadro} del INE ({motivo}): "
        "su poblacion_oficial_2023 queda sin dato."
    )


def _poblacion_oficial(area: dict) -> tuple[Optional[int], str]:
    """Población oficial del Censo 2023 de una localidad de la capa, y el aviso si no se pudo leer.

    El código INE de la localidad es la llave del cuadro 13: la capa lo trae como número y el tabulado
    como texto de 5 dígitos. Un tabulado que no se puede bajar no invalida el polígono, así que la
    respuesta sale igual, con la cifra en `None` y el motivo en la nota."""
    codigo = area.get("codigo")
    if not isinstance(codigo, int):
        return None, ""
    try:
        return _tabulado_censo("localidades").get(f"{codigo:05d}"), ""
    except (OSError, DatosInvalidos) as e:
        return None, _aviso_censo("localidades", e)


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
    oficial, aviso_censo = _poblacion_oficial(loc)
    localidad: LocalidadDelPunto = {
        "nombre": loc["nombre"],
        "departamento": loc["departamento"],
        "adentro": km_loc == 0.0,
        "distancia_km": round(km_loc, 1),
        "poblacion_2023": loc["datos"].get("poblacion_2023"),
        "viviendas_2023": loc["datos"].get("viviendas_2023"),
        "poblacion_oficial_2023": oficial,
    }
    notas = [
        "departamento y localidad salen de los polígonos oficiales del INE. Si el punto no está adentro de una "
        "localidad (campo, ruta), se da la más cercana con su distancia hasta el borde, aproximada.",
        "poblacion_oficial_2023 es la cifra que publica el INE y la que se cita; poblacion_2023 y viviendas_2023 "
        "son los campos pob_tot_23 y viv_tot_23 de la capa cartográfica, que difieren (ciudad de Salto: 114.043 "
        "en la capa, 112.527 oficial)." + aviso_censo,
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
    fuente = FUENTE_LIMITES + "; " + FUENTE_IDE
    if not aviso_censo:
        fuente = FUENTE_LIMITES + "; " + FUENTE_CENSO + "; " + FUENTE_IDE
    return {
        "lat": lat,
        "lon": lon,
        "departamento": departamento,
        "localidad": localidad,
        "direccion_mas_cercana": direccion,
        "nota": " ".join(notas),
        "fuente": fuente,
        "bajado": bajado,
    }


def localidad(nombre: str = "", departamento: str = "", cantidad: int = 20) -> Localidades:
    """Sin nombre ni departamento, el país: el total, los 19 departamentos y las localidades más pobladas."""
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
    tabulados: dict[str, dict[str, int]] = {}
    avisos_censo = []
    for cuadro in ("localidades", "departamentos"):
        try:
            tabulados[cuadro] = _tabulado_censo(cuadro)
        except (OSError, DatosInvalidos) as e:
            tabulados[cuadro] = {}
            avisos_censo.append(_aviso_censo(cuadro, e))
    oficial_loc, oficial_dep = tabulados["localidades"], tabulados["departamentos"]
    aviso_censo = "".join(avisos_censo)
    salida: list[DatosLocalidad] = [
        {
            "nombre": a["nombre"],
            "departamento": a["departamento"],
            "codigo": a["codigo"],
            "poblacion_2023": a["datos"].get("poblacion_2023"),
            "viviendas_2023": a["datos"].get("viviendas_2023"),
            "capital": a["datos"].get("capital"),
            "poblacion_oficial_2023": oficial_loc.get(f"{a['codigo']:05d}") if isinstance(a["codigo"], int) else None,
            "centro_aproximado": {
                "lat": round((a["bbox"][1] + a["bbox"][3]) / 2, 5),
                "lon": round((a["bbox"][0] + a["bbox"][2]) / 2, 5),
            },
        }
        for a in elegidas[: max(1, min(cantidad, 100))]
    ]
    departamentos: list[PoblacionDepartamento] = [
        {"departamento": nombre_dep, "poblacion_oficial_2023": oficial_dep.get(_sin_tildes(nombre_dep))}
        for nombre_dep in sorted({a["departamento"] for a in elegidas})
    ]
    # La suma de los departamentos es el total del país; la de las localidades no (hay gente sin localidad).
    # El total solo si el cuadro 12 trae todos los departamentos de la capa: con filas faltantes, la suma
    # sería un número plausible y falso, que es justo lo que este servidor no emite.
    del_capa = {_sin_tildes(a["departamento"]) for a in locs}
    total_pais = sum(oficial_dep.values()) if oficial_dep and del_capa <= oficial_dep.keys() else None
    return {
        "localidades": salida,
        "departamentos": departamentos,
        "poblacion_oficial_total": total_pais,
        "total": len(elegidas),
        "nota": (
            "poblacion_oficial_2023 es la cifra que publica el INE (tabulados del Censo 2023, datos "
            "ponderados, cuadro 13 por localidad y cuadro 12 por departamento): es la que se cita. "
            "poblacion_2023 y viviendas_2023 son los campos pob_tot_23 y viv_tot_23 de la capa "
            "cartográfica, que no están ponderados y difieren (ciudad de Salto: 114.043 en la capa, "
            "112.527 oficial). La población de un departamento está en departamentos, no en la suma de "
            "sus localidades, y el total del país en poblacion_oficial_total (la suma de los 19 "
            "departamentos del cuadro 12), que tampoco es la de las localidades: 236 personas están en "
            "filas sin localidad (situación de calle y hogares). 11 de las 652 localidades de la capa no "
            "están en el tabulado (medido el "
            "2026-11-21): ahí poblacion_oficial_2023 es null. Ordenadas de mayor a menor población. "
            "centro_aproximado es el centro del rectángulo que la contiene, no un centroide." + aviso_censo
        ),
        "fuente": f"{FUENTE_LIMITES}; {FUENTE_CENSO}",
        "bajado": bajado,
    }
