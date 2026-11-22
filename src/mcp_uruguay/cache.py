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
import secrets
import shutil
import tempfile
import time
from contextvars import ContextVar
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator, Optional, TypeVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from typing_extensions import TypedDict
from uydatos import bcu, procedencia, salto_grande

T = TypeVar("T")


class CopiaUsada(TypedDict):
    """Una copia del disco que respaldó la respuesta: qué archivo, de cuándo y con qué sha256.

    Es lo que permite verificar un número contra los bytes exactos que leyó el servidor, sin creerle
    nada a la respuesta. `url` va en `None` cuando la dirección la arma la fuente dentro de `uydatos`
    y no llega hasta acá: preferible un hueco a una URL inventada.
    """

    archivo: str
    url: Optional[str]
    sha256: str
    bajado: str
    bytes: int


class Procedencia(TypedDict, total=False):
    """Lo que el servidor agrega a la respuesta: las copias que se leyeron para armarla.

    Va en la salida y no en las definiciones de las herramientas: el trinquete de
    `tests/test_presupuesto_herramientas.py` no se mueve. Los tipos de respuesta de las herramientas
    heredan de acá, porque el SDK descarta las claves que el esquema declarado no tiene.
    """

    procedencia: list[CopiaUsada]


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


# Las copias del disco que se leyeron durante una llamada: el servidor las pone en la respuesta.
_leidas: ContextVar[Optional[list[CopiaUsada]]] = ContextVar("copias_leidas", default=None)


@contextlib.contextmanager
def vigilar_procedencia() -> Iterator[list[CopiaUsada]]:
    """Anota, durante una llamada, cada copia que se leyó y su sha256.

    El sha256 se calcula solo si alguien está escuchando: fuera de una herramienta (scripts, tests)
    nadie paga el hash de un CSV de 122 MB.
    """
    lista: list[CopiaUsada] = []
    marca = _leidas.set(lista)
    try:
        yield lista
    finally:
        _leidas.reset(marca)


# Los sha256 ya calculados, por (camino, mtime y tamaño): rehacer el de un CSV de 122 MB en cada
# llamada costaba 430 ms (medido); con esto, la segunda llamada no lo paga. Un archivo reemplazado
# cambia de mtime.
_hashes: dict[tuple[str, int, int], str] = {}


def _sha256(ruta: Path) -> str:
    """El sha256 de la copia, recordado mientras el archivo no cambie."""
    estado = ruta.stat()
    clave = (str(ruta), estado.st_mtime_ns, estado.st_size)
    if clave not in _hashes:
        if len(_hashes) > 512:  # un servidor remoto vive meses: el recordado no crece sin techo
            _hashes.clear()
        _hashes[clave] = procedencia.sha256(ruta)
    return _hashes[clave]


def anotar_lectura(ruta: Path, url: Optional[str] = None) -> None:
    """Registra la copia `ruta` como respaldo de la respuesta en curso, una sola vez.

    `url` es la dirección de la que salió el archivo, si la herramienta la conoce: las fuentes que
    arman su URL dentro de `uydatos` la dejan en `None`.
    """
    lista = _leidas.get()
    if lista is None or not ruta.is_file():
        return
    archivo = _nombre(ruta)
    if any(c["archivo"] == archivo for c in lista):
        return
    lista.append(
        {
            "archivo": archivo,
            "url": url,
            "sha256": _sha256(ruta),
            "bajado": sello(ruta),
            "bytes": ruta.stat().st_size,
        }
    )


def _nombre(ruta: Path) -> str:
    """El camino relativo a la caché: en modo remoto, la ruta completa expondría el usuario del
    servidor a cualquiera de internet."""
    try:
        return str(ruta.relative_to(directorio())).replace("\\", "/")
    except ValueError:
        return ruta.name


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


def _temporal(ruta: Path) -> Path:
    """Un temporal propio de esta bajada, junto a `ruta`.

    Dos clientes MCP comparten `~/.cache/mcp-uruguay`: con un nombre fijo (`<archivo>.nuevo`) dos
    bajadas del mismo archivo escribían el mismo temporal y una publicaba la copia a medio escribir
    de la otra. El sufijo `.nuevo` se mantiene porque `diagnostico` ignora esas copias: son
    descargas en curso, no datos. El archivo se crea con `O_EXCL` y los permisos de siempre
    (`0o666` menos el `umask`), que es lo que dejaba `write_bytes`.
    """
    for _ in range(10):
        nombre = ruta.parent / f".{ruta.name}.{secrets.token_hex(4)}.nuevo"
        try:
            os.close(os.open(nombre, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666))
        except FileExistsError:
            continue
        return nombre
    raise FileExistsError(f"no se pudo crear un temporal único para {ruta}")


def es_temporal(relativa: Path) -> bool:
    """¿El camino es una descarga en curso? `_temporal` deja `<archivo>.XXXX.nuevo` y
    `_refrescar_mes_bcu` una carpeta `.nuevo-*`: ninguna de las dos es una copia utilizable."""
    return any(parte.endswith(".nuevo") or parte.startswith(".nuevo-") for parte in relativa.parts)


def vencido(ruta: Path, ttl: float) -> bool:
    return not ruta.exists() or time.time() - ruta.stat().st_mtime > ttl


def archivo(
    ruta: Path,
    bajar: Callable[[Path], object],
    leer: Callable[[Path], T],
    ttl: float,
    *,
    url: Optional[str] = None,
) -> tuple[T, Path]:
    """Devuelve `(leer(ruta), ruta)`, bajando antes si falta o venció.

    Si la descarga nueva no se puede leer, se descarta y se vuelve a la copia anterior si la
    había. Sin copia anterior, el error sube.

    La copia que se sirve queda anotada como respaldo de la respuesta en curso (su sha256), con `url`
    si la herramienta la conoce.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if vencido(ruta, ttl):
        nueva = _temporal(ruta)
        try:
            bajar(nueva)
            dato = leer(nueva)
        except Exception:
            nueva.unlink(missing_ok=True)
            if ruta.exists():
                _servida_vencida(ruta)
                dato = _reintentando(lambda: leer(ruta))
                anotar_lectura(ruta, url)
                return dato, ruta
            raise
        _poner_en_su_lugar(nueva, ruta)
        anotar_lectura(ruta, url)
        return dato, ruta
    dato = _reintentando(lambda: leer(ruta))
    anotar_lectura(ruta, url)
    return dato, ruta


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
        anotar_lectura(ruta)
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
            nueva = _temporal(ruta)
            try:
                salto_grande.descargar_datos(estacion, mes, _fin_de_mes(mes) + timedelta(days=1), nueva)
                salto_grande.leer_datos(nueva)
            except Exception:
                nueva.unlink(missing_ok=True)
                raise
            _poner_en_su_lugar(nueva, ruta)
        lecturas += _reintentando(lambda: salto_grande.leer_datos(ruta))
        sellos.append(sello(ruta))
        anotar_lectura(ruta)
    ini = datetime.combine(desde, datetime.min.time())
    fin = datetime.combine(hasta + timedelta(days=1), datetime.min.time())
    vistas, unicas = set(), []
    for f in lecturas:  # la medianoche que cierra un mes es también la que abre el siguiente
        if ini <= f["fecha"] < fin and f["fecha"] not in vistas:
            vistas.add(f["fecha"])
            unicas.append(f)
    return unicas, min(sellos) if sellos else ""
