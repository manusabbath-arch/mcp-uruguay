"""Las herramientas del servidor, como funciones comunes: reciben valores simples y devuelven
diccionarios. `servidor.py` solo las registra.

Cada respuesta con un dato trae `fuente` (quién lo publica) y `bajado` (cuándo se obtuvo la copia
que se usó). Un agente que cite el número puede citar también de dónde salió y de qué fecha es.
Los errores son `ValueError` con el motivo en castellano: el agente los recibe como respuesta de
error de la herramienta.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal, Optional

from uydatos import ancap, bcu, catalogo, ibge, ideuy, indec, inia, rut, salto_grande, semanas

from mcp_uruguay import cache

Moneda = Literal["USD", "UI", "ARS", "BRL"]
MONEDAS: dict[str, int] = {"USD": 2225, "UI": 9800, "ARS": 501, "BRL": 1001}

FUENTE_BCU = "Banco Central del Uruguay, web service de cotizaciones (cotizaciones.bcu.gub.uy)"
FUENTE_INDEC = "INDEC, vía la API de series de tiempo de datos.gob.ar (serie 148.3_INIVELNAL_DICI_M_26)"
FUENTE_IBGE = "IBGE, API SIDRA, tabla 1737, variable 2266 (IPCA número-índice)"
FUENTE_ANCAP = "ANCAP, dataset ancap-precio-combustible-pe de catalogodatos.gub.uy"
FUENTE_INIA = "INIA, Unidad GRAS, estación Salto Grande (dataset inia-precipitacion-temps-extremas-sg)"
FUENTE_IDE = "IDE.uy, API pública de direcciones (direcciones.ide.uy)"
FUENTE_CTM = "Comisión Técnica Mixta de Salto Grande, web service www.saltogrande.org/ws.php"

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


def cotizacion(moneda: Moneda, fecha: str, hacia_atras: bool = False, hoy: Optional[date] = None) -> dict:
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


def cotizacion_mensual(moneda: Moneda, desde: str, hasta: str, hoy: Optional[date] = None) -> dict:
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


def pesos_constantes(montos: dict[str, float], base: str, hoy: Optional[date] = None) -> dict:
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


def ipc_argentina(desde: str, hasta: str) -> dict:
    serie, ruta = cache.archivo(cache.directorio() / "indec_ipc.json", indec.descargar, indec.leer, cache.DIA)
    puntos = _recortar(serie, desde, hasta)
    return {
        "serie": "IPC nacional de Argentina, base diciembre 2016 = 100",
        "puntos": puntos,
        "nota": "Es un índice, no una inflación. La variación entre dos meses es índice(b)/índice(a) - 1.",
        "fuente": FUENTE_INDEC,
        "bajado": cache.sello(ruta),
    }


def ipca_brasil(desde: str, hasta: str) -> dict:
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


def combustible_ancap(producto: Optional[str] = None, anio: Optional[int] = None, mes: Optional[int] = None) -> dict:
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


# --- Salto Grande --------------------------------------------------------------------------------


def estaciones_cercanas(lat: float, lon: float, cantidad: int = 5) -> dict:
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


# --- Sin red -------------------------------------------------------------------------------------


def validar_documento(numero: str, tipo: Literal["rut", "ci"]) -> dict:
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


def semana(fecha: str) -> dict:
    s = semanas.semana_de(_fecha(fecha, "fecha"))
    return {
        "etiqueta": s.corta,
        "etiqueta_con_anio": str(s),
        "desde": s.desde.isoformat(),
        "hasta": s.hasta.isoformat(),
        "de_total": s.de_total,
        "nota": "Semana ISO 8601, de lunes a domingo. El año de la semana puede no ser el del día.",
    }


def geocodificar_direccion(direccion: str, localidad: str = "", departamento: str = "") -> dict:
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


def recursos_catalogo(dataset: str) -> dict:
    return {
        "dataset": dataset,
        "recursos": catalogo.recursos(dataset),
        "fuente": f"catalogodatos.gub.uy, package_show?id={dataset}",
    }
