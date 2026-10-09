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

from uydatos import bcu

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


def bcu_serie(moneda: int, desde: date, hasta: date, hoy: date | None = None) -> tuple[dict[date, float], str]:
    """La serie diaria de una moneda entre dos fechas, bajando solo los meses que faltan.

    El mes en curso se vuelve a pedir si el archivo tiene más de 3 horas. Un mes en curso sin
    publicaciones todavía (el 1.º de enero, por ejemplo) no es un error: aporta cero días.
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
        if ruta.exists() and en_curso and vencido(ruta, 3 * HORA):
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
