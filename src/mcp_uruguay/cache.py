"""Caché en disco de lo que se baja de cada fuente.

Lo bajado se guarda tal cual vino, así cada respuesta puede decir **cuándo** se obtuvo el dato.
Dos reglas:

- **Lo cerrado no se vuelve a pedir.** Un mes ya terminado del BCU no cambia.
- **Lo vivo vence.** El mes en curso, la serie del IPC o el CSV de ANCAP se refrescan cuando el
  archivo es más viejo que su `ttl`.

Una descarga que no se puede leer **no queda en la caché**: si quedara, envenenaría todas las
consultas siguientes con el mismo error.

Directorio: la variable `MCP_URUGUAY_CACHE`, o `~/.cache/mcp-uruguay`.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, TypeVar

from uydatos import bcu, salto_grande

T = TypeVar("T")

HORA = 3600
DIA = 24 * HORA


def directorio() -> Path:
    base = os.environ.get("MCP_URUGUAY_CACHE")
    d = Path(base) if base else Path.home() / ".cache" / "mcp-uruguay"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sello(ruta: Path) -> str:
    """Cuándo se bajó el archivo, en hora local, para citarlo junto al dato."""
    return datetime.fromtimestamp(ruta.stat().st_mtime).isoformat(timespec="minutes")


def vencido(ruta: Path, ttl: float) -> bool:
    return not ruta.exists() or time.time() - ruta.stat().st_mtime > ttl


def archivo(ruta: Path, bajar: Callable[[Path], object], leer: Callable[[Path], T], ttl: float) -> tuple[T, Path]:
    """Devuelve `(leer(ruta), ruta)`, bajando antes si falta o venció.

    Si la descarga nueva no se puede leer, se descarta y se vuelve a la copia anterior si la
    había. Sin copia anterior, el error sube.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if vencido(ruta, ttl):
        nueva = ruta.with_name(ruta.name + ".nuevo")
        try:
            bajar(nueva)
            dato = leer(nueva)
        except Exception:
            nueva.unlink(missing_ok=True)
            if ruta.exists():
                return leer(ruta), ruta
            raise
        nueva.replace(ruta)
        return dato, ruta
    return leer(ruta), ruta


def _meses(desde: date, hasta: date) -> list[date]:
    out, d = [], desde.replace(day=1)
    while d <= hasta:
        out.append(d)
        d = (d + timedelta(days=32)).replace(day=1)
    return out


def _fin_de_mes(mes: date) -> date:
    return (mes.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def cerrado_en_disco(ruta: Path, mes: date) -> bool:
    """¿La copia de `mes` se bajó **después** de que el mes terminó?

    Un mes bajado mientras corría tiene solo los días hasta ese momento. Cuando el mes termina, el
    archivo ya existe y parece cerrado, pero está incompleto: hay que volver a pedirlo una vez.
    """
    return ruta.exists() and datetime.fromtimestamp(ruta.stat().st_mtime).date() > _fin_de_mes(mes)


def _vigente(ruta: Path, mes: date, hoy: date, ttl_en_curso: float) -> bool:
    """Si la copia de `mes` sirve: cerrada, o del mes en curso y todavía fresca."""
    if not ruta.exists():
        return False
    if (mes.year, mes.month) == (hoy.year, hoy.month):
        return not vencido(ruta, ttl_en_curso)
    return cerrado_en_disco(ruta, mes)


def bcu_serie(moneda: int, desde: date, hasta: date, hoy: date | None = None) -> tuple[dict[date, float], str]:
    """La serie diaria de una moneda entre dos fechas, bajando solo los meses que faltan.

    El mes en curso se vuelve a pedir si el archivo tiene más de 3 horas, y un mes bajado mientras
    corría se vuelve a pedir una vez cerrado. Un mes en curso sin publicaciones todavía (el 1.º de
    enero, por ejemplo) no es un error: aporta cero días.
    """
    hoy = hoy or date.today()
    if desde > hoy:
        raise ValueError(f"{desde} es posterior a hoy ({hoy}): el BCU no publica el futuro")
    hasta = min(hasta, hoy)
    carpeta = directorio() / "bcu"
    carpeta.mkdir(parents=True, exist_ok=True)
    serie: dict[date, float] = {}
    sellos = []
    for mes in _meses(desde, hasta):
        ruta = carpeta / f"{moneda}_{mes:%Y-%m}.xml"
        en_curso = (mes.year, mes.month) == (hoy.year, hoy.month)
        if ruta.exists() and not _vigente(ruta, mes, hoy, 3 * HORA):
            ruta.unlink()
        if not ruta.exists():
            bcu.descargar(moneda, f"{mes:%Y-%m}", f"{mes:%Y-%m}", carpeta)
        try:
            serie.update(bcu.leer_crudo(ruta, moneda))
        except bcu.BcuInvalido as e:
            if en_curso and "sin datos" in str(e):
                sellos.append(sello(ruta))
                continue
            ruta.unlink(missing_ok=True)  # una respuesta mala no se queda en la caché
            raise
        sellos.append(sello(ruta))
    return dict(sorted(serie.items())), min(sellos) if sellos else ""


def sg_lecturas(estacion: str, desde: date, hasta: date, hoy: date | None = None) -> tuple[list[dict], str]:
    """Las lecturas de una estación de Salto Grande, `desde`..`hasta` inclusive, por mes en disco.

    Cada mes es un pedido (a lo sumo 31 días, el límite del servicio). Un mes cerrado no se vuelve a
    pedir; el mes en curso vence a la media hora. Una respuesta con error no queda en la caché.
    """
    hoy = hoy or date.today()
    if desde > hoy:
        raise ValueError(f"{desde} es posterior a hoy ({hoy})")
    hasta = min(hasta, hoy)
    carpeta = directorio() / "salto_grande"
    carpeta.mkdir(parents=True, exist_ok=True)
    lecturas: list[dict] = []
    sellos = []
    for mes in _meses(desde, hasta):
        ruta = carpeta / f"{estacion}_{mes:%Y-%m}.xml"
        if not _vigente(ruta, mes, hoy, 30 * 60):
            nueva = ruta.with_name(ruta.name + ".nuevo")
            try:
                salto_grande.descargar_datos(estacion, mes, _fin_de_mes(mes) + timedelta(days=1), nueva)
                salto_grande.leer_datos(nueva)
            except Exception:
                nueva.unlink(missing_ok=True)
                raise
            nueva.replace(ruta)
        lecturas += salto_grande.leer_datos(ruta)
        sellos.append(sello(ruta))
    ini = datetime.combine(desde, datetime.min.time())
    fin = datetime.combine(hasta + timedelta(days=1), datetime.min.time())
    vistas, unicas = set(), []
    for f in lecturas:  # la medianoche que cierra un mes es también la que abre el siguiente
        if ini <= f["fecha"] < fin and f["fecha"] not in vistas:
            vistas.add(f["fecha"])
            unicas.append(f)
    return unicas, min(sellos) if sellos else ""
