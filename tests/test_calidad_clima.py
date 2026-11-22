"""Marcas de calidad en `clima_salto` (INIA): rango y sin dato en todo; plano solo en temperaturas."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from mcp_uruguay import herramientas as h
from mcp_uruguay.herramientas import rio_y_clima as rio

INICIO = date(2026, 3, 1)


def _dia(i: int, tmax=None, tmin=None, lluvia=None) -> dict:
    return {
        "fecha": INICIO + timedelta(days=i),
        "temperaturaMaxima": 25.0 + (i % 7) * 0.5 if tmax is None else tmax,
        "temperaturaMinima": 14.0 + (i % 5) * 0.4 if tmin is None else tmin,
        "pluviometro": 0.0 if lluvia is None else lluvia,
        "anom_tmax": 0.5,
        "anom_tmin": -0.2,
    }


@pytest.fixture
def clima_falso(monkeypatch):
    """Sirve `dias` en lugar del CSV de INIA: lo que se prueba es qué marca la herramienta."""

    def servir(dias: list[dict]):
        monkeypatch.setattr(rio, "_clima", lambda: ([{"fecha": dias[-1]["fecha"]}], "sello"))
        monkeypatch.setattr(rio.inia, "clima_diario", lambda serie: dias)
        return h.clima_salto(dias[0]["fecha"].isoformat(), dias[-1]["fecha"].isoformat())

    return servir


class TestCalidadClima:
    def test_una_serie_normal_sale_limpia_y_declara_que_probo(self, clima_falso):
        c = clima_falso([_dia(i) for i in range(30)])["calidad"]
        assert c["tmax"]["pruebas"] == ["rango", "plano", "sin_dato"]
        assert c["lluvia_mm"]["pruebas"] == ["rango", "sin_dato"]
        assert c["tmax"]["marcas"] == {"ok": 30, "rango": 0, "plano": 0, "sin_dato": 0}
        assert c["tmax"]["marcadas"] == [] and c["tmax"]["lecturas"] == 30

    def test_diez_dias_secos_no_son_un_sensor_trabado(self, clima_falso):
        """Medido: 1.028 rachas de 6 o más días en 0 mm en 56 años (53% de los días): es el clima."""
        c = clima_falso([_dia(i) for i in range(10)])["calidad"]
        assert c["lluvia_mm"]["marcas"] == {"ok": 10, "rango": 0, "sin_dato": 0}

    def test_una_temperatura_trabada_se_marca_desde_el_sexto_dia(self, clima_falso):
        """Medido: en 56 años la temperatura máxima nunca repitió el mismo valor más de 3 días seguidos."""
        c = clima_falso([_dia(i, tmax=30.0) for i in range(8)])["calidad"]
        assert c["tmax"]["marcas"]["plano"] == 3
        assert c["tmax"]["marcadas"][0] == {"fecha": "2026-03-06", "valor": 30.0, "marca": "plano"}
        assert c["tmin"]["marcas"]["plano"] == 0

    def test_un_dia_sin_dato_se_cuenta_y_se_lista(self, clima_falso):
        dias = [_dia(i) for i in range(10)]
        dias[4]["temperaturaMinima"] = None
        c = clima_falso(dias)["calidad"]
        assert c["tmin"]["marcas"]["sin_dato"] == 1
        assert c["tmin"]["marcadas"] == [{"fecha": "2026-03-05", "valor": None, "marca": "sin_dato"}]

    def test_una_temperatura_o_una_lluvia_imposibles_son_rango_y_siguen_en_los_dias(self, clima_falso):
        dias = [_dia(i) for i in range(10)]
        dias[2]["temperaturaMaxima"] = 60.0
        dias[6]["pluviometro"] = 450.0
        r = clima_falso(dias)
        assert r["calidad"]["tmax"]["marcas"]["rango"] == 1
        assert r["calidad"]["lluvia_mm"]["marcas"]["rango"] == 1
        assert r["dias"][2]["tmax"] == 60.0 and r["dias"][6]["lluvia_mm"] == 450.0  # marca, no descarta

    def test_las_marcadas_tienen_tope_y_el_conteo_es_completo(self, clima_falso):
        c = clima_falso([_dia(i, tmax=30.0) for i in range(40)])["calidad"]["tmax"]
        assert c["marcas"]["plano"] == 35 and len(c["marcadas"]) == rio.MAX_MARCADAS
        assert c["marcadas_omitidas"] == 35 - rio.MAX_MARCADAS

    def test_un_solo_dia_no_rompe(self, clima_falso):
        c = clima_falso([_dia(0)])["calidad"]
        assert c["tmax"]["lecturas"] == 1
