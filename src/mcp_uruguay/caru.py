"""Informes historicos de Salto Chico para la instalacion local de prueba."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from typing_extensions import TypedDict
from uydatos import red

from mcp_uruguay import cache

_BASE = "https://caru.org.uy/nuevositio/wp-content/uploads/"
_INFORMES = {
    "2023-02-27": _BASE + "2023/10/Informe-Resultados-Semana-del-27-de-Febrero-de-2023.pdf",
    "2025-02-03": _BASE + "2025/02/Informe-Resultados-Semana-del-03-de-Febrero-de-2025.pdf",
}


class InformePlaya(cache.Procedencia, TypedDict):
    playa: str
    fuente: str
    bajado: str
    sha256: str
    muestras: list[dict[str, Any]]
    semana_del_informe: str
    nota: str


def _leer_informe(lector, fecha: str) -> InformePlaya:
    if fecha not in _INFORMES:
        raise ValueError("Elegí la semana 2023-02-27 o 2025-02-03.")
    url = _INFORMES[fecha]
    datos, _ = cache.archivo(
        cache.directorio() / "caru" / f"salto-chico-{fecha}.pdf",
        lambda destino: red.bajar(url, destino),
        lambda pdf: lector(pdf, url, datetime.fromisoformat(cache.sello(pdf))),
        365 * cache.DIA,
        url=url,
    )
    return {
        **datos,
        "semana_del_informe": fecha,
        "nota": "Observaciones historicas de playa. La tabla no publica una decision de habilitacion.",
    }


def registrar(herramienta, anotaciones) -> None:
    try:
        from uydatos.caru import leer_salto_chico
    except ImportError:
        raise SystemExit("--caru requiere un wheel de uydatos que incluya el lector CARU.") from None

    @herramienta("Muestreos historicos de Playa Salto Chico", anotaciones)
    def muestreos_salto_chico(semana: str) -> InformePlaya:
        """Lee el informe semanal de CARU para 2023-02-27 o 2025-02-03.
        Informa muestreos historicos, valores censurados y respaldo del PDF."""
        return _leer_informe(leer_salto_chico, semana)
