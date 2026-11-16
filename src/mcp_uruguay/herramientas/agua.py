"""Calidad del agua potable de OSE."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# En Python < 3.12, pydantic no arma el esquema de un `typing.TypedDict`: el SDK se queda sin
# esquema de salida y la respuesta sin `structuredContent`. Medido en el CI de 3.10 y 3.11.
from typing_extensions import NotRequired, TypedDict
from uydatos import ose, red

from mcp_uruguay import cache
from mcp_uruguay.herramientas.comun import _sin_tildes


class ParametroNumerico(TypedDict):
    """Un parámetro numérico en un trimestre. Los censurados (`<5`) no se promedian ni se mezclan."""

    parametro: str
    unidad: str
    analisis: int
    exactos: int
    menor_que: int
    mayor_que: int
    min_exacto: Optional[float]
    max_exacto: Optional[float]
    limites_de_deteccion: list[float]


class ParametroCategorico(TypedDict):
    parametro: str
    analisis: int
    categorias: dict[str, int]


class TrimestreAgua(TypedDict):
    trimestre: str
    muestras: int
    numericos: list[ParametroNumerico]
    categoricos: list[ParametroCategorico]


class LocalidadOse(TypedDict):
    localidad: str
    departamento: str


class CalidadAgua(TypedDict, total=False):
    """La respuesta de `calidad_agua()`. Sin `localidad`, solo `localidades`."""

    localidades: list[LocalidadOse]
    localidad: str
    departamento: str
    trimestres: list[TrimestreAgua]
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


FUENTE_OSE = "OSE, dataset calidad-de-agua de su propio CKAN (datos.ose.com.uy), bacteriología y fisicoquímico"


TTL_OSE = 30 * cache.DIA  # el dataset declara frecuencia anual; 122 MB no se bajan por consulta


def _archivo_ose(area: str) -> Path:
    """El CSV de un área en la caché, validado entero la vez que se baja.

    Vencida la copia, pregunta a CKAN el tamaño declarado antes de bajar 122 MB: si coincide, la
    copia sigue siendo la publicada y solo se renueva su fecha (`ose.hace_falta_bajar`). Una bajada
    nueva se lee completa con `ose.leer` antes de reemplazar la anterior: lo que no se puede leer no
    entra a la caché."""
    import os

    ruta = cache.directorio() / "ose" / f"{area}.csv"
    if not cache.vencido(ruta, TTL_OSE):
        return ruta
    ruta.parent.mkdir(parents=True, exist_ok=True)
    try:
        vigente = ose.recursos_vigentes()[area]
    except OSError:
        if ruta.exists():  # sin red, la copia vieja sirve y su `bajado` dice de cuándo es
            return ruta
        raise
    falta, _ = ose.hace_falta_bajar(area, ruta, vigente)
    if not falta:
        os.utime(ruta)
        return ruta
    nueva = ruta.with_name(ruta.name + ".nuevo")
    try:
        red.bajar(vigente["url"], nueva)
        ose.leer(nueva)
    except Exception:
        nueva.unlink(missing_ok=True)
        if ruta.exists():
            return ruta
        raise
    nueva.replace(ruta)
    return ruta


def _localidades_ose(rutas: list[Path]) -> dict[str, str]:
    """{localidad: departamento} de los dos CSV, leyendo solo esas dos columnas.

    No es un lector: los CSV ya pasaron `ose.leer` completos al entrar a la caché. Esto solo arma la
    lista para elegir, y se guarda junto a la caché con la fecha de los archivos."""
    import csv
    import json

    indice = cache.directorio() / "ose" / "localidades.json"
    sellos = [r.stat().st_mtime for r in rutas]
    if indice.exists():
        guardado = json.loads(indice.read_text(encoding="utf-8"))
        if guardado.get("sellos") == sellos:
            return guardado["localidades"]
    localidades: dict[str, str] = {}
    for r in rutas:
        with r.open(encoding=ose.CODIFICACION, newline="") as f:
            lector = csv.reader(f, delimiter=ose.DELIMITADOR)
            columnas = [c.replace("﻿", "").strip() for c in next(lector)]
            i_loc, i_dep = columnas.index("LOCALIDAD"), columnas.index("DEPARTAMENTO")
            for campos in lector:
                if len(campos) > max(i_loc, i_dep):
                    localidades.setdefault(campos[i_loc].strip(), campos[i_dep].strip())
    localidades.pop("", None)
    indice.write_text(json.dumps({"sellos": sellos, "localidades": localidades}, ensure_ascii=False), encoding="utf-8")
    return localidades


def _trimestre(texto: str, campo: str) -> tuple[int, int]:
    """'2024' o '2024-T3' -> (2024, 3). Un año solo es su primer trimestre en `desde` y el último en `hasta`."""
    t = texto.strip().upper()
    try:
        if "-T" in t:
            anio, tri = t.split("-T")
            a, q = int(anio), int(tri)
        else:
            a, q = int(t), (1 if campo == "desde" else 4)
    except ValueError:
        raise ValueError(f"{campo}: {texto!r} no es un año AAAA ni un trimestre AAAA-Tn") from None
    if not 1 <= q <= 4:
        raise ValueError(f"{campo}: {texto!r}: el trimestre va de T1 a T4")
    return a, q


def _resumen_trimestre(filas: list[dict]) -> TrimestreAgua:
    numericos: list[ParametroNumerico] = []
    categoricos: list[ParametroCategorico] = []
    for p in sorted({f["parametro"] for f in filas}):
        del_p = [f for f in filas if f["parametro"] == p]
        if p in ose.NUMERICOS:
            exactos = [f["valor"] for f in del_p if f["condicion"] == "exacto"]
            numericos.append(
                {
                    "parametro": p,
                    "unidad": ose.UNIDADES[p],
                    "analisis": len(del_p),
                    "exactos": len(exactos),
                    "menor_que": sum(1 for f in del_p if f["condicion"] == "menor_que"),
                    "mayor_que": sum(1 for f in del_p if f["condicion"] == "mayor_que"),
                    "min_exacto": min(exactos) if exactos else None,
                    "max_exacto": max(exactos) if exactos else None,
                    "limites_de_deteccion": sorted({f["valor"] for f in del_p if f["condicion"] != "exacto"}),
                }
            )
        else:
            conteo: dict[str, int] = {}
            for f in del_p:
                conteo[f["categoria"]] = conteo.get(f["categoria"], 0) + 1
            categoricos.append({"parametro": p, "analisis": len(del_p), "categorias": dict(sorted(conteo.items()))})
    f0 = filas[0]
    return {
        "trimestre": f"{f0['anio']}-T{f0['trimestre']}",
        "muestras": len({f["muestra"] for f in filas}),
        "numericos": numericos,
        "categoricos": categoricos,
    }


def calidad_agua(localidad: str = "", parametro: str = "", desde: str = "", hasta: str = "") -> CalidadAgua:
    rutas = [_archivo_ose(area) for area in ose.ARCHIVOS]
    bajado = min(cache.sello(r) for r in rutas)
    localidades = _localidades_ose(rutas)
    if not localidad:
        return {
            "localidades": [
                {"localidad": n, "departamento": d}
                for n, d in sorted(localidades.items(), key=lambda x: (_sin_tildes(x[1]), _sin_tildes(x[0])))
            ],
            "nota": "Pasar el nombre de `localidad` tal cual (sin importar tildes) para ver sus análisis.",
            "fuente": FUENTE_OSE,
            "bajado": bajado,
        }
    buscado = _sin_tildes(localidad)
    nombre = next((n for n in localidades if _sin_tildes(n) == buscado), None)
    if nombre is None:
        parecidas = sorted(n for n in localidades if any(p in _sin_tildes(n) for p in buscado.split()))
        raise ValueError(
            f"localidad {localidad!r}: OSE no publica análisis con ese nombre. "
            f"Parecidas: {parecidas[:10] or 'ninguna'}. Sin `localidad`, la lista completa."
        )
    if parametro:
        p = _sin_tildes(parametro)
        if p not in ose.PARAMETROS:
            raise ValueError(f"parametro {parametro!r}: los que publica OSE son {sorted(ose.PARAMETROS)}")
        parametro = p
    ini = _trimestre(desde, "desde") if desde else (0, 0)
    fin = _trimestre(hasta, "hasta") if hasta else (9999, 4)
    if ini > fin:
        raise ValueError(f"desde {desde} es posterior a hasta {hasta}")

    filas = []
    for r in rutas:
        try:
            filas += ose.leer(r, localidades=[nombre])
        except ose.OseInvalido as e:
            if "ninguna fila" not in str(e):  # una localidad puede estar en un solo archivo
                raise
    filas = [
        f for f in filas if ini <= (f["anio"], f["trimestre"]) <= fin and (not parametro or f["parametro"] == parametro)
    ]
    if not filas:
        raise ValueError(f"{nombre}: no hay análisis de {parametro or 'ningún parámetro'} en ese período")
    por_trimestre: dict[tuple[int, int], list[dict]] = {}
    for f in filas:
        por_trimestre.setdefault((f["anio"], f["trimestre"]), []).append(f)
    return {
        "localidad": nombre,
        "departamento": localidades[nombre],
        "trimestres": [_resumen_trimestre(por_trimestre[k]) for k in sorted(por_trimestre)],
        "nota": (
            "Un valor `<5` es un límite de detección, no una medición: va en `menor_que` y nunca en "
            "`min_exacto`/`max_exacto`; no promediar censurados como si fueran el número. `mayor_que` son "
            "filas con el signo al revés (casi seguro error de carga): se cuentan, no se corrigen. Una muestra "
            "puede analizarse en más de un laboratorio: `muestras` cuenta muestras, `analisis` cuenta filas. "
            "La resolución es el trimestre, sin fecha de muestra. Esta herramienta no dice si el agua cumple la "
            "norma: informa lo que OSE publicó. El dataset se actualiza una vez por año."
        ),
        "fuente": FUENTE_OSE,
        "bajado": bajado,
    }
