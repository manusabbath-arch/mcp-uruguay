"""`feriados`: la herramienta sobre `uydatos.feriados`, sin red.

Los esperados de 2027 salen de un calendario publicado (Brañas, «Feriados de Uruguay 2026 y 2027»,
leído el 2026-11-27), no del módulo.
"""

from __future__ import annotations

import pytest
from conftest import BcuFalso, xml_bcu
from mcp import Client

from mcp_uruguay import herramientas as h
from mcp_uruguay.servidor import servidor


def test_lista_del_anio_con_los_traslados():
    r = h.feriados(anio=2027)
    piedras = next(f for f in r["feriados"] if f["nombre"] == "Batalla de Las Piedras")
    assert piedras == {
        "fecha": "2027-05-17",
        "nombre": "Batalla de Las Piedras",
        "tipo": "laborable",
        "fecha_original": "2027-05-18",
        "trasladado": True,
    }
    assert {f["fecha"] for f in r["feriados"] if f["tipo"] == "pago"} == {
        "2027-01-01",
        "2027-05-01",
        "2027-07-18",
        "2027-08-25",
        "2027-12-25",
    }
    assert "16.805" in r["fuente"] and "Censo" in r["nota"]


def test_dias_habiles_con_las_dos_definiciones():
    r = h.feriados(desde="2027-05-01", hasta="2027-05-31")
    assert r["dias_habiles"] == {
        "dias": 31,
        "lunes_a_viernes": 21,
        "sin_ningun_feriado": 20,
        "sin_feriados_pagos": 21,
    }
    assert [f["fecha"] for f in r["feriados"]] == ["2027-05-01", "2027-05-17"]  # el 1/5 es sábado


def test_un_solo_dia():
    r = h.feriados(desde="2025-04-19", hasta="2025-04-19")
    assert r["dias_habiles"]["lunes_a_viernes"] == 0
    assert {f["nombre"] for f in r["feriados"]} == {
        "Semana de Turismo",
        "Desembarco de los Treinta y Tres Orientales",
    }


@pytest.mark.parametrize(
    "args,motivo",
    [
        ({}, "anio"),
        ({"anio": 2027, "desde": "2027-01-01", "hasta": "2027-01-31"}, "anio"),
        ({"desde": "2027-01-01"}, "hasta"),
        ({"anio": 1999}, "16.805"),
        ({"desde": "01/05/2027", "hasta": "2027-05-31"}, "AAAA-MM-DD"),
        ({"desde": "2027-06-01", "hasta": "2027-05-01"}, "posterior"),
    ],
)
def test_rechazos_con_motivo(args, motivo):
    with pytest.raises(ValueError, match=motivo):
        h.feriados(**args)


@pytest.mark.anyio
async def test_por_el_servidor_devuelve_datos_estructurados():
    async with Client(servidor) as c:
        r = await c.call_tool("feriados", {"anio": 2026})
        malo = await c.call_tool("feriados", {"anio": 1999})
    assert not r.is_error and r.structured_content["anio"] == 2026
    assert malo.is_error and "16.805" in malo.content[0].text


class _BcuSinFeriados(BcuFalso):
    """Como el BCU real: no publica el 25 de agosto (martes en 2026, feriado pago)."""

    def __call__(self, moneda, desde, hasta, destino):
        from datetime import date, timedelta
        from pathlib import Path

        anio, mes = map(int, desde.split("-"))
        d, datos = date(anio, mes, 1), []
        while d.month == mes:
            if d.weekday() < 5 and d != date(2026, 8, 25) and d <= self.hasta:
                datos.append((d.isoformat(), moneda, 40.0))
            d += timedelta(days=1)
        p = Path(destino) / f"{moneda}_{desde}.xml"
        p.write_text(xml_bcu(datos), encoding="utf-8")
        return [p]


def test_la_cotizacion_sin_publicacion_dice_que_dia_es(monkeypatch, cache_temporal):
    """Antes decía «fin de semana, feriado o día sin cotización» sin distinguir: ahora lo sabe."""
    from datetime import date

    from uydatos import bcu

    monkeypatch.setattr(bcu, "descargar", BcuFalso(hasta=date(2026, 10, 9)))
    assert "es sábado" in h.cotizacion("USD", "2026-10-03", hoy=date(2026, 10, 9))["nota"]
    monkeypatch.setattr(bcu, "descargar", _BcuSinFeriados(hasta=date(2026, 10, 9)))
    r = h.cotizacion("USD", "2026-08-25", hoy=date(2026, 10, 9))
    assert r["valor_en_pesos"] is None
    assert "feriado nacional (Declaratoria de la Independencia)" in r["nota"]


def test_la_semana_trae_sus_feriados():
    r = h.semana("2027-05-19")  # la semana del traslado de Las Piedras al lunes 17
    assert [(f["fecha"], f["nombre"]) for f in r["feriados"]] == [("2027-05-17", "Batalla de Las Piedras")]
    assert h.semana("2027-06-09")["feriados"] == []
