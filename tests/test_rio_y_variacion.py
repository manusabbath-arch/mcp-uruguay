"""`nivel_rio`, `nivel_rio_comparado` y `variacion_real`, sin red."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest
from conftest import BcuFalso, SgFalso
from uydatos import bcu, salto_grande

from mcp_uruguay import herramientas as h

FIXTURES = Path(__file__).parent / "fixtures"
HOY = date(2026, 10, 9)


@pytest.fixture
def estaciones(cache_temporal):
    """Salto, Puerto Concordia y Libertad, recortadas de la respuesta real del 04/10/2026."""
    cache_temporal.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / "salto_grande_estaciones_recorte.xml", cache_temporal / "salto_grande.xml")


class TestNivelRio:
    def test_resumen_diario_de_la_estacion_salto_por_nombre(self, estaciones, monkeypatch):
        monkeypatch.setattr(salto_grande, "descargar_datos", SgFalso(lambda f: 10.0 + f.day / 10, hasta=HOY))
        r = h.nivel_rio("salto", "2026-10-07", "2026-10-09", hoy=HOY)
        assert r["estacion"] == {"id": "A501258E", "nombre": "Salto"}
        assert [d["dia"] for d in r["dias"]] == ["2026-10-07", "2026-10-08", "2026-10-09"]
        assert r["dias"][0]["media"] == pytest.approx(10.7)
        assert r["cobertura"] == {"esperadas": 288, "recibidas": 288, "con_H": 288}
        assert r["ultima_lectura"]["fecha"] == "2026-10-09 23:45"
        assert r["variacion_en_el_periodo"] == pytest.approx(0.2)
        assert "unidad" in r["nota"]

    def test_por_defecto_los_ultimos_14_dias_de_salto(self, estaciones, monkeypatch):
        monkeypatch.setattr(salto_grande, "descargar_datos", SgFalso(hasta=HOY))
        r = h.nivel_rio(hoy=HOY)
        assert (r["dias"][0]["dia"], r["dias"][-1]["dia"], r["estacion"]["id"]) == (
            "2026-09-26",
            "2026-10-09",
            "A501258E",
        )

    def test_un_mes_cerrado_se_pide_una_sola_vez(self, estaciones, monkeypatch):
        falso = SgFalso(hasta=HOY)
        monkeypatch.setattr(salto_grande, "descargar_datos", falso)
        h.nivel_rio("Salto", "2026-09-01", "2026-09-10", hoy=HOY)
        h.nivel_rio("Salto", "2026-09-11", "2026-09-20", hoy=HOY)
        assert [p[1] for p in falso.pedidos] == [date(2026, 9, 1)]

    def test_estacion_desconocida_sugiere(self, estaciones):
        with pytest.raises(ValueError, match="Puerto Concordia"):
            h.nivel_rio("Concordia del Norte", hoy=HOY)

    def test_rango_demasiado_largo(self, estaciones):
        with pytest.raises(ValueError, match="92"):
            h.nivel_rio("Salto", "2026-01-01", "2026-10-01", hoy=HOY)


class TestNivelRioComparado:
    def test_ubica_el_nivel_actual_entre_los_anios_anteriores(self, estaciones, monkeypatch):
        alturas = {2026: 11.0, 2025: 4.0, 2024: 12.0}
        monkeypatch.setattr(salto_grande, "descargar_datos", SgFalso(lambda f: alturas.get(f.year, 6.0), hasta=HOY))
        r = h.nivel_rio_comparado("Salto", dias=7, hasta="2026-10-09", hoy=HOY)
        assert r["actual"]["media"] == pytest.approx(11.0)
        assert r["actual"]["desde"] == "2026-10-03"
        anios = {a["anio"]: a["media"] for a in r["anios_anteriores"]}
        assert anios[2025] == pytest.approx(4.0) and anios[2024] == pytest.approx(12.0)
        assert min(anios) == 2017
        assert r["posicion"] == {"lugar": 2, "de": 10, "orden": "de mayor a menor"}

    def test_un_anio_con_poca_cobertura_se_excluye_y_se_dice(self, estaciones, monkeypatch):
        def falso(estacion, desde, hasta, destino):
            if desde.year == 2020:
                return SgFalso(hasta=date(2020, 1, 1))(estacion, desde, hasta, destino)
            return SgFalso(hasta=HOY)(estacion, desde, hasta, destino)

        monkeypatch.setattr(salto_grande, "descargar_datos", falso)
        r = h.nivel_rio_comparado("Salto", dias=7, hasta="2026-10-09", hoy=HOY)
        assert 2020 in r["anios_excluidos"]
        assert 2020 not in {a["anio"] for a in r["anios_anteriores"]}


class TestVariacionReal:
    def test_con_la_ui(self, monkeypatch):
        ui = {2025: 6.0, 2026: 6.3}
        monkeypatch.setattr(bcu, "descargar", BcuFalso(valor=lambda d: ui[d.year], hasta=HOY))
        r = h.variacion_real(100.0, "2025-09", 126.0, "2026-09", indice="UI", hoy=HOY)
        assert r["variacion_nominal_pct"] == pytest.approx(26.0)
        assert r["inflacion_del_periodo_pct"] == pytest.approx(5.0)
        assert r["variacion_real_pct"] == pytest.approx(20.0)
        assert r["monto_inicial_en_moneda_final"] == pytest.approx(105.0)
        assert r["moneda"] == "pesos uruguayos"

    def test_con_el_ipc_argentino(self, cache_temporal):
        cache_temporal.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURES / "indec_ipc_nacional_2016-12_a_2017-12.json", cache_temporal / "indec_ipc.json")
        r = h.variacion_real(100.0, "2016-12", 110.0, "2017-01", indice="IPC_AR")
        assert r["inflacion_del_periodo_pct"] == pytest.approx(1.5859, abs=1e-3)
        assert r["moneda"] == "pesos argentinos"

    def test_un_mes_sin_indice_se_rechaza(self, cache_temporal):
        cache_temporal.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURES / "indec_ipc_nacional_2016-12_a_2017-12.json", cache_temporal / "indec_ipc.json")
        with pytest.raises(ValueError, match="2018-06"):
            h.variacion_real(100.0, "2017-01", 110.0, "2018-06", indice="IPC_AR")

    def test_monto_inicial_cero(self):
        with pytest.raises(ValueError, match="cero"):
            h.variacion_real(0.0, "2025-09", 10.0, "2026-09")
