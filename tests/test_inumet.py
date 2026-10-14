"""`observaciones_inumet`, sin red: un CSV sintético con la forma del real en la caché."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from mcp_uruguay import herramientas as h


def _csv(carpeta, variable, encabezado, filas):
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / f"inumet_{variable}.csv").write_text("\n".join([encabezado, *filas]) + "\n", encoding="utf-8")


def _horas(inicio: datetime, cantidad: int):
    return [inicio + timedelta(hours=i) for i in range(cantidad)]


@pytest.fixture
def temperatura(cache_temporal):
    """Salto G3: el 01/01 local completo (UTC 03:00 a 02:00 del día siguiente), el 02/01 con 5 horas."""
    filas = []
    for i, t in enumerate(_horas(datetime(2026, 1, 1, 3), 24)):
        filas.append(f"{t:%Y-%m-%d %H:%M};Salto G3;{10 + i}")
    for t in _horas(datetime(2026, 1, 2, 3), 5):
        filas.append(f"{t:%Y-%m-%d %H:%M};Salto G3;20")
    filas.append(f"{datetime(2026, 1, 1, 3):%Y-%m-%d %H:%M};Artigas G3;15")
    filas.append(";;")
    filas.append("; please try again later.;")
    _csv(cache_temporal / "inumet", "temperatura", "fecha;estacion_id;temp_aire", filas)
    return cache_temporal


def test_cobertura_sin_estacion(temperatura):
    r = h.observaciones_inumet("temperatura")
    salto = next(e for e in r["estaciones"] if e["estacion"] == "Salto G3")
    assert salto["filas"] == 29
    assert salto["dias"] == 2
    assert salto["dias_completos"] == 1
    assert salto["extremos"]["temp_aire"] == {"min": 10.0, "max": 33.0}
    assert r["lineas_sin_dato"] == 2
    assert {e["estacion"] for e in r["estaciones"]} == {"Salto G3", "Artigas G3"}
    assert r["fuente"] and r["bajado"]


def test_el_dia_es_el_local_no_el_utc(temperatura):
    r = h.observaciones_inumet("temperatura", "salto", "2026-01-01", "2026-01-02", "max")
    dias = {d["fecha"]: d for d in r["series"][0]["dias"]}
    # Las 24 horas de UTC 03:00 a 02:00 son un solo día local: el 01/01, con su máximo 33.
    assert dias["2026-01-01"]["valor"] == 33.0
    assert dias["2026-01-01"]["observaciones"] == 24


def test_un_dia_incompleto_es_null_no_un_total_parcial(temperatura):
    r = h.observaciones_inumet("temperatura", "Salto G3", "2026-01-01", "2026-01-02", "promedio")
    dias = {d["fecha"]: d for d in r["series"][0]["dias"]}
    assert dias["2026-01-02"]["valor"] is None
    assert dias["2026-01-02"]["observaciones"] == 5


def test_el_rango_recorta_los_dias(temperatura):
    r = h.observaciones_inumet("temperatura", "Salto", "2026-01-02", "2026-01-02", "max")
    assert [d["fecha"] for d in r["series"][0]["dias"]] == ["2026-01-02"]


def test_con_estacion_exige_las_fechas_y_la_agregacion(temperatura):
    with pytest.raises(ValueError, match="no se adivina"):
        h.observaciones_inumet("temperatura", "Salto", "2026-01-01", "2026-01-02")
    with pytest.raises(ValueError, match="no se adivina"):
        h.observaciones_inumet("temperatura", "Salto", agregacion="max")


def test_sin_estacion_rechaza_las_fechas(temperatura):
    with pytest.raises(ValueError, match="piden tambien"):
        h.observaciones_inumet("temperatura", desde="2026-01-01")


def test_estacion_ambigua_o_inexistente(temperatura):
    with pytest.raises(ValueError, match="0 coincidencias"):
        h.observaciones_inumet("temperatura", "Tacuarembo", "2026-01-01", "2026-01-02", "max")
    with pytest.raises(ValueError, match="7 coincidencias"):
        h.observaciones_inumet("temperatura", "G3", "2026-01-01", "2026-01-02", "max")


def test_rango_invertido_o_demasiado_largo(temperatura):
    with pytest.raises(ValueError, match="anterior"):
        h.observaciones_inumet("temperatura", "Salto", "2026-01-02", "2026-01-01", "max")
    with pytest.raises(ValueError, match="demasiado largo"):
        h.observaciones_inumet("temperatura", "Salto", "2024-01-01", "2026-01-01", "max")


def test_variable_desconocida_o_diaria():
    with pytest.raises(ValueError, match="desconocida"):
        h.observaciones_inumet("insolacion")
    with pytest.raises(ValueError, match="desconocida"):
        h.observaciones_inumet("nubosidad")


def test_el_viento_trae_dos_columnas_y_doce_por_dia(cache_temporal):
    filas = [
        f"{t:%Y-%m-%d %H:%M};Salto G3;{i * 10};{5 + i}" for i, t in enumerate(_horas(datetime(2026, 1, 1, 3), 24)[::2])
    ]
    _csv(cache_temporal / "inumet", "viento", "fecha;estacion_id;dir_viento;int_viento", filas)
    r = h.observaciones_inumet("viento", "Salto", "2026-01-01", "2026-01-01", "max")
    assert [s["columna"] for s in r["series"]] == ["dir_viento", "int_viento"]
    # 12 observaciones es el día completo del viento: medirlo contra 24 lo dejaría todo en null.
    assert r["series"][0]["dias"][0]["valor"] == 110.0
    assert r["series"][0]["dias"][0]["observaciones"] == 12
