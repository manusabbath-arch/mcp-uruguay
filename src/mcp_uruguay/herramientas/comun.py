"""Lo que comparten las herramientas: tipos de respuesta, fuentes citadas y ayudantes de fechas."""

from __future__ import annotations

import unicodedata
from datetime import date
from typing import Union

# En Python < 3.12, pydantic no arma el esquema de un `typing.TypedDict`: el SDK se queda sin
# esquema de salida y la respuesta sin `structuredContent`. Medido en el CI de 3.10 y 3.11.
from typing_extensions import NotRequired, TypedDict

from mcp_uruguay import cache


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


class VariacionReal(cache.Procedencia, TypedDict):
    """La respuesta de `variacion_real()`. `indice` trae el valor de cada mes y su descripción."""

    variacion_nominal_pct: float
    inflacion_del_periodo_pct: float
    variacion_real_pct: float
    monto_inicial_en_moneda_final: float
    moneda: str
    indice: dict[str, Union[float, str]]
    nota: str
    fuente: str
    bajado: str
    copia_vencida: NotRequired[bool]
    aviso: NotRequired[str]


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper().strip()
