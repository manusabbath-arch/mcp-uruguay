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


def test_resultados_del_balotaje_en_salto():
    r = h.resultados_electorales("balotaje-2024", "Salto")
    assert r["mesas"]["comunes"] > 200 and r["participacion_pct"] > 80
    assert len(r["opciones"]) == 2


def test_compras_2025_con_aviso_de_concentracion():
    r = h.compras_estado(2025)
    assert r["adjudicaciones"] > 100_000 and r["total_pesos"] > 0
    assert r["mayores_items"] and r["aviso"]


def test_parlamento_senado_actual_y_leyes():
    r = h.asistencia_parlamentaria("senado", 50)
    assert r["personas"] > 31 and r["menor_asistencia"]
    assert h.leyes(numero=20531)["total"] == 1


def test_calidad_agua_de_salto_trae_los_36_trimestres():
    """Medido el 2026-10-25 en uydatos: 2017-T1 a 2025-T4 completos, sin un hueco."""
    r = h.calidad_agua("Salto")
    trimestres = [t["trimestre"] for t in r["trimestres"]]
    assert trimestres[0] == "2017-T1" and "2025-T4" in trimestres and len(trimestres) >= 36
    color = [p for t in r["trimestres"] for p in t["numericos"] if p["parametro"] == "COLOR VERDADERO"]
    assert sum(p["menor_que"] for p in color) > sum(p["exactos"] for p in color)  # 93,7% censurado en el país


def test_nivel_rio_ina_concordia_altura_reciente_y_niveles():
    r = h.nivel_rio_ina("Concordia", "H")
    assert r["puntos"] and -10 < r["puntos"][-1]["media"] < 25
    assert r["niveles"]["alerta"] is not None


def test_nivel_rio_ina_caudal_de_concordia_avisa_el_atraso():
    """Medido el 2026-10-27: la última fila del caudal de Concordia (serie 928) era del 15/07/2026."""
    r = h.nivel_rio_ina("Concordia", "Q", desde="2026-01-01")
    if r["dias_de_atraso"] > h.ATRASO_AVISO_INA:
        assert "ATENCIÓN" in r["nota"]
