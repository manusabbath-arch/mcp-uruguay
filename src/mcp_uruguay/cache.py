"""Caché en disco de lo que se baja de cada fuente.

Lo bajado se guarda tal cual vino, así cada respuesta puede decir **cuándo** se obtuvo el dato.
Dos reglas:

- **Lo cerrado no se vuelve a pedir.** Un mes ya terminado del BCU no cambia.
- **Lo vivo vence.** El mes en curso, la serie del IPC o el CSV de ANCAP se refrescan cuando el
  archivo es más viejo que su `ttl`.

Una descarga que no se puede leer **no queda en la caché**: si quedara, envenenaría todas las
consultas siguientes con el mismo error. Y tampoco **reemplaza a una copia buena**: se baja aparte y
solo se pone en su lugar si se lee. Si no se pudo refrescar y se sirvió la copia anterior, la
respuesta lo dice (`copia_vencida`).

La hora es siempre la de Uruguay (`ahora()`), no la de la máquina: en un servidor en UTC, entre las
21:00 y la medianoche de Montevideo, «hoy» ya sería mañana.

Directorio: la variable `MCP_URUGUAY_CACHE`, o `~/.cache/mcp-uruguay`.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
import time
from contextvars import ContextVar
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator, TypeVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from uydatos import bcu, salto_grande

T = TypeVar("T")

HORA = 3600
DIA = 24 * HORA


def directorio() -> Path:
    base = os.environ.get("MCP_URUGUAY_CACHE")
    d = Path(base) if base else Path.home() / ".cache" / "mcp-uruguay"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _zona() -> timezone | ZoneInfo:
    """Montevideo. Uruguay no tiene horario de verano desde 2015: si la máquina no trae la base de
    zonas horarias (Windows sin `tzdata`), UTC-3 fijo es la misma hora."""
    try:
        return ZoneInfo("America/Montevideo")
    except (ZoneInfoNotFoundError, ValueError):
        return timezone(timedelta(hours=-3), "America/Montevideo")


def ahora() -> datetime:
    """El instante actual en Uruguay, con su desplazamiento. Lo único que dice qué hora es."""
    return datetime.fromtimestamp(time.time(), tz=_zona())


def hoy() -> date:
    """La fecha de hoy en Uruguay, no la de la máquina."""
    return ahora().date()


def sello(ruta: Path) -> str:
    """Cuándo se bajó el archivo, en ISO 8601 con el desplazamiento de Uruguay (`-03:00`)."""
    return datetime.fromtimestamp(ruta.stat().st_mtime, tz=_zona()).isoformat(timespec="minutes")


# Las copias vencidas que se sirvieron durante una llamada: el servidor las pone en la respuesta.
_vencidas: ContextVar[list[str] | None] = ContextVar("copias_vencidas", default=None)


@contextlib.contextmanager
def vigilar_copias() -> Iterator[list[str]]:
    """Anota, durante una llamada, los sellos de las copias vencidas que se sirvieron."""
    lista: list[str] = []
    marca = _vencidas.set(lista)
    try:
        yield lista
    finally:
        _vencidas.reset(marca)


def _servida_vencida(ruta: Path) -> None:
    lista = _vencidas.get()
    if lista is not None and ruta.exists():
        lista.append(sello(ruta))


def _reintentando(accion: Callable[[], T]) -> T:
    """Corre `accion` y, si Windows dice `PermissionError` (otro hilo o proceso está reemplazando el
    archivo justo ahora), reintenta unas veces antes de dejar subir el error."""
    for intento in range(6):
        try:
            return accion()
        except PermissionError:
            if intento == 5:
                raise
            time.sleep(0.05 * (intento + 1))
    raise AssertionError("inalcanzable")


def _poner_en_su_lugar(nueva: Path, ruta: Path) -> None:
    """`os.replace` con reintentos: en Windows falla con `PermissionError` si otro hilo o proceso
    tiene abierta la copia justo ahora (dos clientes MCP comparten la caché). Si no se logra y ya hay
    una copia, esa es de otro que bajó lo mismo: se deja."""
    for intento in range(6):
        try:
            os.replace(nueva, ruta)
            return
        except PermissionError:
            if intento == 5:
                if ruta.exists():
                    return
                raise
            time.sleep(0.05 * (intento + 1))


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
                _servida_vencida(ruta)
                return _reintentando(lambda: leer(ruta)), ruta
            raise
        _poner_en_su_lugar(nueva, ruta)
        return dato, ruta
    return _reintentando(lambda: leer(ruta)), ruta


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
    return ruta.exists() and datetime.fromtimestamp(ruta.stat().st_mtime, tz=_zona()).date() > _fin_de_mes(mes)


def _vigente(ruta: Path, mes: date, hoy: date, ttl_en_curso: float) -> bool:
    """Si la copia de `mes` sirve: cerrada, o del mes en curso y todavía fresca."""
    if not ruta.exists():
        return False
    if (mes.year, mes.month) == (hoy.year, hoy.month):
        return not vencido(ruta, ttl_en_curso)
    return cerrado_en_disco(ruta, mes)


def _refrescar_mes_bcu(moneda: int, mes: date, ruta: Path, *, tolera_sin_datos: bool) -> None:
    """Baja el mes **aparte** y lo pone en `ruta` solo si se lee: nunca se borra la copia buena antes.

    Si la descarga falla o viene ilegible, queda la copia anterior (y la respuesta avisa que está
    vencida); sin copia anterior, el error sube. Cada bajada usa su propia carpeta temporal, así que
    dos procesos que comparten la caché no se pisan el archivo.
    """
    aparte = Path(tempfile.mkdtemp(prefix=".nuevo-", dir=ruta.parent))
    try:
        try:
            bcu.descargar(moneda, f"{mes:%Y-%m}", f"{mes:%Y-%m}", aparte)
            nueva = aparte / ruta.name
            try:
                bcu.leer_crudo(nueva, moneda)
            except bcu.BcuInvalido as e:
                if not (tolera_sin_datos and "sin datos" in str(e)):
                    raise
        except Exception:
            if ruta.exists():
                _servida_vencida(ruta)
                return
            raise
        _poner_en_su_lugar(nueva, ruta)
    finally:
        shutil.rmtree(aparte, ignore_errors=True)


def bcu_serie(moneda: int, desde: date, hasta: date, hoy: date | None = None) -> tuple[dict[date, float], str]:
    """La serie diaria de una moneda entre dos fechas, bajando solo los meses que faltan.

    El mes en curso se vuelve a pedir si el archivo tiene más de 3 horas, y un mes bajado mientras
    corría se vuelve a pedir una vez cerrado. Un mes en curso sin publicaciones todavía (el 1.º de
    enero, por ejemplo) no es un error: aporta cero días.
    """
    hoy = hoy or ahora().date()
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
        if not _vigente(ruta, mes, hoy, 3 * HORA):
            _refrescar_mes_bcu(moneda, mes, ruta, tolera_sin_datos=en_curso)
        try:
            serie.update(_reintentando(lambda: bcu.leer_crudo(ruta, moneda)))
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
    hoy = hoy or ahora().date()
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
            _poner_en_su_lugar(nueva, ruta)
        lecturas += _reintentando(lambda: salto_grande.leer_datos(ruta))
        sellos.append(sello(ruta))
    ini = datetime.combine(desde, datetime.min.time())
    fin = datetime.combine(hasta + timedelta(days=1), datetime.min.time())
    vistas, unicas = set(), []
    for f in lecturas:  # la medianoche que cierra un mes es también la que abre el siguiente
        if ini <= f["fecha"] < fin and f["fecha"] not in vistas:
            vistas.add(f["fecha"])
            unicas.append(f)
    return unicas, min(sellos) if sellos else ""
