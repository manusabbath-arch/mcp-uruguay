"""Herramientas que no salen a la red (validar documentos, semanas, catálogos) y el diagnóstico."""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Optional, Union

# En Python < 3.12, pydantic no arma el esquema de un `typing.TypedDict`: el SDK se queda sin
# esquema de salida y la respuesta sin `structuredContent`. Medido en el CI de 3.10 y 3.11.
from typing_extensions import NotRequired, TypedDict
from uydatos import catalogo, ideuy, observatorio, rut, semanas, ursea

from mcp_uruguay import cache
from mcp_uruguay.herramientas.comun import _fecha, _mes, _sin_tildes
from mcp_uruguay.herramientas.territorio import FUENTE_IDE

FUENTE_OBSERVATORIO = "MIDES, Observatorio Social: página de cada indicador en www.gub.uy/ministerio-desarrollo-social"


FUENTE_URSEA = "URSEA (PPI y componentes) y ANCAP (precio ex planta), catálogo de datos abiertos"


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


class IndicadoresEncontrados(TypedDict):
    """La respuesta de `buscar_indicador_social()`: nombres para pasar a `indicador_social`."""

    indicadores: list[str]
    encontrados: int
    total: int
    descartados_ilegibles: int
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


class FilaIndicador(TypedDict):
    """Una combinación de dimensiones (por ejemplo Sexo=Mujeres) con su valor en cada período."""

    dimensiones: dict[str, str]
    valores: dict[str, Optional[float]]


class IndicadorSocial(TypedDict):
    """La respuesta de `indicador_social()`: la ficha del MIDES y la tabla, con sus avisos."""

    titulo: str
    descripcion: str
    unidad: str
    calculo: str
    fuente_del_dato: str
    frecuencia: str
    periodo_ficha: dict[str, Optional[int]]
    dimensiones: list[str]
    periodos: list[str]
    filas: list[FilaIndicador]
    filas_totales: int
    parcial: bool
    periodos_disponibles: list[str]
    avisos: list[str]
    url: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


class MesParidad(TypedDict):
    """Un mes: precio ex planta de ANCAP contra el PPI, los dos sin impuestos, en $/litro."""

    mes: str
    ancap_ex_planta: float
    ppi: float
    diferencia: float
    diferencia_pct: float


class ResumenParidad(TypedDict):
    producto: str
    ultimo: MesParidad
    promedio_pct_12_meses: float
    meses: int


class ParidadCombustibles(TypedDict, total=False):
    """La respuesta de `paridad_combustibles()`, en sus dos caminos.

    Sin `producto` trae `resumen` (los cuatro comparables); con `producto`, `producto`, `serie`,
    `promedio_pct` y `desglose_ultimo`. `metodo`, `avisos`, `fuente` y `bajado` van siempre.
    """

    resumen: list[ResumenParidad]
    producto: str
    serie: list[MesParidad]
    promedio_pct: float
    desglose_ultimo: dict[str, Union[str, float]]
    metodo: str
    avisos: list[str]
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


class ArchivoCache(TypedDict):
    """Un archivo cacheado en disco: de cuando es la copia que se usa y cuanto pesa."""

    archivo: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]
    bytes: int


class Diagnostico(TypedDict):
    """La respuesta de `diagnostico()`."""

    directorio: str
    archivos: list[ArchivoCache]
    nota: str


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


_NOTA_OBSERVATORIO = (
    "Indicadores del Observatorio Social del MIDES, leídos de su página viva (la copia del catálogo de "
    "datos abiertos quedó en 2019). Los valores van en la `unidad` de la ficha; `None` es «sin dato», "
    "nunca cero. Las filas «Total» van mezcladas con las demás: no sumar la columna."
)


_MAX_FILAS_INDICADOR = 80


def _indice_observatorio() -> tuple[list[str], Path]:
    import json

    def bajar(ruta: Path) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(observatorio.indice()), encoding="utf-8")

    return cache.archivo(
        cache.directorio() / "observatorio" / "indice.json",
        bajar,
        lambda ruta: json.loads(ruta.read_text(encoding="utf-8")),
        7 * cache.DIA,
    )


_DIAS_ILEGIBLE = 30


def _ruta_ilegibles() -> Path:
    return cache.directorio() / "observatorio" / "ilegibles.json"


def _leer_marcas() -> dict[str, str]:
    try:
        marcas = json.loads(_ruta_ilegibles().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return marcas if isinstance(marcas, dict) else {}


def _ilegibles() -> set[str]:
    """Indicadores cuya página se intentó leer en los últimos 30 días y tenía un formato que no se lee.

    La búsqueda no los ofrece: sugerir un nombre que la lectura va a rechazar lleva al agente a un
    callejón (medido en la eval del 2026-11-21: cuatro llamadas perdidas)."""
    limite = (date.today() - timedelta(days=_DIAS_ILEGIBLE)).isoformat()
    return {slug for slug, dia in _leer_marcas().items() if str(dia) >= limite}


def _marcar_ilegible(slug: str) -> None:
    ruta = _ruta_ilegibles()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    marcas = _leer_marcas()
    marcas[slug] = date.today().isoformat()
    # Escritura atómica: en modo remoto varios clientes comparten la caché.
    nueva = ruta.with_name(f"{ruta.name}.{os.getpid()}.nuevo")
    nueva.write_text(json.dumps(marcas, sort_keys=True), encoding="utf-8")
    os.replace(nueva, ruta)


def buscar_indicador_social(texto: str, cantidad: int = 20) -> IndicadoresEncontrados:
    slugs, ruta = _indice_observatorio()
    ilegibles = _ilegibles()
    todos = observatorio.buscar(slugs, texto, cantidad=len(slugs))
    encontrados = [s for s in todos if s not in ilegibles]
    descartados = len(todos) - len(encontrados)
    return {
        "indicadores": encontrados[: max(1, min(cantidad, 100))],
        "encontrados": len(encontrados),
        "total": len(slugs),
        "descartados_ilegibles": descartados,
        "nota": (
            "Pasar uno de estos nombres, tal cual, a indicador_social. Los nombres salen del título, sin "
            "tildes: 'segun-departamento' abre por departamento, 'segun-sexo' por sexo, y 'total-pais' "
            "es del país entero. Los más cortos primero."
            + ("" if encontrados else " Sin resultados: probar con menos palabras o con su raíz.")
            + (
                f" Se omitieron {descartados} con la página en formato viejo, que indicador_social no puede leer."
                if descartados
                else ""
            )
        ),
        "fuente": FUENTE_OBSERVATORIO + " (sitemap)",
        "bajado": cache.sello(ruta),
    }


def indicador_social(indicador: str, filtro: str = "") -> IndicadorSocial:
    url = observatorio.url_de(indicador)
    nombre = url.rsplit("/", 1)[-1]
    slugs, _ = _indice_observatorio()
    if nombre not in slugs:
        palabras = " ".join(p for p in nombre.split("-") if len(p) > 4)[:60]
        try:
            parecidos = observatorio.buscar(slugs, palabras, cantidad=8) if palabras else []
        except observatorio.ObservatorioInvalido:
            parecidos = []
        sugerencia = parecidos or "buscarlo con buscar_indicador_social"
        raise ValueError(f"{indicador!r} no es un indicador del MIDES. Parecidos: {sugerencia}")
    try:
        r, ruta = cache.archivo(
            cache.directorio() / "observatorio" / f"{nombre}.html",
            lambda ruta: observatorio.red.bajar(url, ruta),
            lambda ruta: observatorio.leer_pagina(ruta.read_text(encoding="utf-8"), url),
            cache.DIA,
        )
    except observatorio.ObservatorioInvalido:
        _marcar_ilegible(nombre)
        raise
    filas = r["filas"]
    if filtro:
        palabras = [_sin_tildes(p) for p in filtro.split(",") if p.strip()]
        filas = [
            f
            for f in filas
            if all(any(p.strip() == _sin_tildes(v) for v in f["dimensiones"].values()) for p in palabras)
        ]
        if not filas:
            valores = sorted({v for f in r["filas"] for v in f["dimensiones"].values()})
            raise ValueError(f"ninguna fila tiene {filtro!r}. Valores posibles: {valores[:60]}")
    avisos = list(r["avisos"])
    if len(filas) > _MAX_FILAS_INDICADOR:
        avisos.append(f"se muestran {_MAX_FILAS_INDICADOR} de {len(filas)} filas: usar `filtro` para acotar")
    return {
        "titulo": r["titulo"],
        "descripcion": r["descripcion"],
        "unidad": r["unidad"],
        "calculo": r["calculo"],
        "fuente_del_dato": r["fuente"],
        "frecuencia": r["frecuencia"],
        "periodo_ficha": r["periodo_ficha"],
        "dimensiones": r["dimensiones"],
        "periodos": r["periodos"],
        "filas": filas[:_MAX_FILAS_INDICADOR],
        "filas_totales": len(filas),
        "parcial": r["parcial"],
        "periodos_disponibles": r["periodos_disponibles"],
        "avisos": avisos + [_NOTA_OBSERVATORIO],
        "url": url,
        "fuente": FUENTE_OBSERVATORIO,
        "bajado": cache.sello(ruta),
    }


_METODO_PARIDAD = (
    "Precio ex planta de ANCAP (el de venta al público menos fletes, márgenes e impuestos) contra el "
    "precio de paridad de importación de URSEA sin impuestos y con la mezcla de agrocombustibles, en "
    "$/litro. El PPI de la ventana que cierra el 25 se compara con el mes siguiente, que es cuando rige. "
    "diferencia_pct positiva = ANCAP por encima de lo que costaría importar. La elección del nivel y del "
    "mes es de este servidor, no una cifra oficial: a confirmar contra los informes de URSEA."
)


# Los nombres de los componentes de URSEA para los productos que se comparan con ANCAP.
_COMPONENTES_DE = {
    "Gasolina Super 95": "Gasolina Súper 95",
    "Gasolina Premium 97": "Gasolina Premium 97",
    "Gasoil 50-S": "Gas Oil 50S",
    "Gasoil 10-S": "Gas Oil 10S",
}


_DESGLOSE = (
    "precio_fob_ajustado",
    "fletes_internacionales",
    "subtotal_1_precio_cif",
    "subtotal_2_precio_ex_planta_distribucion",
    "subtotal_3_precio_ex_planta_con_biocombustible",
    "imesi",
    "impuesto_co2",
    "iva",
    "total_precio_ex_planta_1",
    "tipo_cambio_promedio",
    "total_precio_ex_planta_2",
)


def _archivo_ursea(clave: str, leer):
    dataset, nombre = ursea.ARCHIVOS[clave]

    def bajar(ruta: Path) -> Path:
        return ursea.red.bajar(ursea.url_de(catalogo.recursos(dataset), nombre), ruta)

    return cache.archivo(cache.directorio() / "ursea" / nombre, bajar, leer, cache.DIA)


def paridad_combustibles(producto: str = "", desde: str = "", hasta: str = "") -> ParidadCombustibles:
    ppi, ruta = _archivo_ursea("ppi", ursea.leer_ppi)
    ex, _ = _archivo_ursea("ex_planta", ursea.leer_ex_planta)
    avisos = [f"ventana del PPI descartada por imposible: {d['inicio']} a {d['fin']}" for d in ppi["descartadas"]]
    base = {"metodo": _METODO_PARIDAD, "fuente": FUENTE_URSEA, "bajado": cache.sello(ruta)}
    if not producto:
        resumen = []
        for p in ursea.COMPARABLES:
            serie = ursea.comparar(ppi, ex, p)
            ultimos = serie[-12:]
            resumen.append(
                {
                    "producto": p,
                    "ultimo": serie[-1],
                    "promedio_pct_12_meses": round(sum(s["diferencia_pct"] for s in ultimos) / len(ultimos), 1),
                    "meses": len(serie),
                }
            )
        return {"resumen": resumen, "avisos": avisos, **base}

    elegido = next((p for p in ursea.COMPARABLES if _sin_tildes(p) == _sin_tildes(producto)), None)
    if elegido is None:
        raise ValueError(f"producto {producto!r}: se comparan {list(ursea.COMPARABLES)} (el GLP no: $/l contra $/kg)")
    d = _mes(desde, "desde") if desde else None
    h_ = _mes(hasta, "hasta") if hasta else None
    serie = [
        s
        for s in ursea.comparar(ppi, ex, elegido)
        if (d is None or s["mes"] >= f"{d.year}-{d.month:02d}")
        and (h_ is None or s["mes"] <= f"{h_.year}-{h_.month:02d}")
    ]
    if not serie:
        raise ValueError(f"no hay meses comparables de {elegido} en ese período")
    componentes, _ = _archivo_ursea("componentes", ursea.leer_componentes)
    propias = [c for c in componentes if c["producto"] == _COMPONENTES_DE[elegido]]
    desglose: dict = {}
    if propias:
        ultimo = max(propias, key=lambda c: c["fecha_cierre"])
        desglose = {"fecha_cierre": ultimo["fecha_cierre"], "vigencia": ultimo["vigencia"]}
        desglose |= {k: ultimo[k] for k in _DESGLOSE if k in ultimo}
        desglose["unidad"] = "USD/m3, salvo tipo_cambio_promedio ($/USD) y total_precio_ex_planta_2 ($/litro)"
        if ultimo["vigencia"] != ultimo["vigencia_publicada"]:
            avisos.append(
                f"URSEA publica la vigencia de este cierre como {ultimo['vigencia_publicada']}; "
                f"por la regla del resto de las filas rige en {ultimo['vigencia']}"
            )
    return {
        "producto": elegido,
        "serie": serie,
        "promedio_pct": round(sum(s["diferencia_pct"] for s in serie) / len(serie), 1),
        "desglose_ultimo": desglose,
        "avisos": avisos,
        **base,
    }


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
