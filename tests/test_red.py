"""Contra las fuentes reales. **Salen a internet**: `pytest -m red`."""

from __future__ import annotations

import pytest

from mcp_uruguay import herramientas as h

pytestmark = pytest.mark.red


def test_cotizacion_del_dolar_de_un_viernes():
    r = h.cotizacion("USD", "2026-09-04")
    assert 30 < r["valor_en_pesos"] < 60
    assert r["fecha_cotizacion"] == "2026-09-04"


def test_pesos_constantes():
    r = h.pesos_constantes({"2025-09": 100.0}, "2026-09")
    assert 100 < r["montos_en_pesos_de_la_base"]["2025-09"] < 115


def test_ipc_argentina_base_100():
    assert h.ipc_argentina("2016-12", "2016-12")["puntos"][0]["valor"] == pytest.approx(100.0)


def test_ipca_brasil():
    assert h.ipca_brasil("1993-12", "1993-12")["puntos"][0]["valor"] == 100


def test_combustibles():
    assert h.combustible_ancap()["productos"]


def test_estacion_salto_a_menos_de_5_km():
    r = h.estaciones_cercanas(-31.383, -57.960, 1)
    assert r["estaciones"][0]["distancia_km"] < 5


def test_clima_y_tendencia():
    r = h.clima_salto("2025-01-01", "2025-01-31")
    assert len(r["dias"]) == 31
    assert h.clima_tendencia()["dias"] > 20000


def test_geocodificar_un_edificio_publico():
    r = h.geocodificar_direccion("Avenida 18 de Julio 1360", "Montevideo", "Montevideo")
    assert r["calidad"] == "puerta_exacta"


def test_nivel_rio_en_salto():
    r = h.nivel_rio("Salto", "2026-09-01", "2026-09-03")
    assert len(r["dias"]) == 3 and all(d["media"] is not None for d in r["dias"])


def test_variacion_real_con_la_ui():
    r = h.variacion_real(100.0, "2025-09", 130.0, "2026-09")
    assert 0 < r["inflacion_del_periodo_pct"] < 10


def test_ubicar_un_punto_en_el_centro_de_salto():
    r = h.ubicar_punto(-31.3833, -57.9606)
    assert r["departamento"]["nombre"] == "SALTO" and r["localidad"]["nombre"] == "SALTO"
    assert r["localidad"]["adentro"] and r["localidad"]["poblacion_2023"] > 100_000


def test_localidad_con_nombre_repetido():
    r = h.localidad("San Antonio")
    assert len({x["departamento"] for x in r["localidades"]}) >= 2
