from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def cache_temporal(tmp_path, monkeypatch):
    """Cada test con su propia caché: nunca toca la del usuario."""
    monkeypatch.setenv("MCP_URUGUAY_CACHE", str(tmp_path / "cache"))
    return tmp_path / "cache"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def xml_bcu(datos: list[tuple[str, int, float]], status: int = 1, codigo: int = 0) -> str:
    """Una respuesta del web service del BCU, con la forma real."""
    filas = "".join(
        f'<datoscotizaciones.dato xmlns="Cotiza"><Fecha>{f}</Fecha><Moneda>{m}</Moneda>'
        f"<Nombre>X</Nombre><CodigoISO>X</CodigoISO><Emisor>X</Emisor>"
        f"<TCC>{v:.6f}</TCC><TCV>{v:.6f}</TCV><ArbAct>1</ArbAct><FormaArbitrar>0</FormaArbitrar>"
        f"</datoscotizaciones.dato>"
        for f, m, v in datos
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Body>'
        '<wsbcucotizaciones.ExecuteResponse xmlns="Cotiza"><Salida xmlns="Cotiza">'
        f"<respuestastatus><status>{status}</status><codigoerror>{codigo}</codigoerror><mensaje/></respuestastatus>"
        f"<datoscotizaciones>{filas}</datoscotizaciones>"
        "</Salida></wsbcucotizaciones.ExecuteResponse></SOAP-ENV:Body></SOAP-ENV:Envelope>"
    )


class BcuFalso:
    """Reemplaza `bcu.descargar`: publica de lunes a viernes `valor(dia)` y cuenta las bajadas."""

    def __init__(self, valor=lambda d: 40.0, hasta: date | None = None, respuesta_mala: bool = False):
        self.valor, self.hasta, self.respuesta_mala = valor, hasta, respuesta_mala
        self.bajadas: list[str] = []

    def __call__(self, moneda: int, desde: str, hasta: str, destino: Path) -> list[Path]:
        self.bajadas.append(desde)
        anio, mes = map(int, desde.split("-"))
        d, datos = date(anio, mes, 1), []
        while d.month == mes:
            if d.weekday() < 5 and (self.hasta is None or d <= self.hasta):
                datos.append((d.isoformat(), moneda, self.valor(d)))
            d += timedelta(days=1)
        p = Path(destino) / f"{moneda}_{desde}.xml"
        contenido = xml_bcu([], status=0, codigo=104) if self.respuesta_mala else xml_bcu(datos)
        p.write_text(contenido, encoding="utf-8")
        return [p]
