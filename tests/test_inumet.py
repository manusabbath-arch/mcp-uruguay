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


# --- calidad -----------------------------------------------------------------------------------------


def _dias_completos(variable: str, columna: str, valores: list[float], cache_temporal, estacion="Salto G3"):
    """Un día local completo por valor (24 horas de UTC 03:00 a 02:00), todas las horas con ese valor."""
    filas = []
    for d, valor in enumerate(valores):
        for t in _horas(datetime(2026, 1, 1, 3) + timedelta(days=d), 24):
            filas.append(f"{t:%Y-%m-%d %H:%M};{estacion};{valor}")
    _csv(cache_temporal / "inumet", variable, f"fecha;estacion_id;{columna}", filas)


def _calidad(variable: str, agregacion: str, dias: int = 8):
    r = h.observaciones_inumet(variable, "Salto G3", "2026-01-01", f"2026-01-{dias:02d}", agregacion)
    return r["series"][0].get("calidad")


def test_la_calidad_cuenta_el_dia_incompleto_como_sin_dato(temperatura):
    r = h.observaciones_inumet("temperatura", "Salto G3", "2026-01-01", "2026-01-02", "max")
    c = r["series"][0]["calidad"]
    assert c["pruebas"] == ["rango", "plano", "sin_dato"]
    assert c["marcas"] == {"ok": 1, "rango": 0, "plano": 0, "sin_dato": 1}
    assert c["marcadas"] == [{"fecha": "2026-01-02", "valor": None, "marca": "sin_dato"}]


def test_una_temperatura_diaria_trabada_se_marca(cache_temporal):
    """Medido: 0 rachas de 6 días iguales en 7 estaciones y 6,8 años de temperatura."""
    _dias_completos("temperatura", "temp_aire", [15.0] * 8, cache_temporal)
    c = _calidad("temperatura", "max")
    assert c["marcas"] == {"ok": 5, "rango": 0, "plano": 3, "sin_dato": 0}
    assert c["marcadas"][0] == {"fecha": "2026-01-06", "valor": 15.0, "marca": "plano"}


def test_la_humedad_maxima_saturada_no_es_un_sensor_trabado(cache_temporal):
    """Medido: la humedad máxima diaria estuvo en 100 durante 27 días seguidos (Paso de los Toros, 2025)."""
    _dias_completos("humedad", "hum_relativa", [100.0] * 8, cache_temporal)
    maximo, promedio = _calidad("humedad", "max"), _calidad("humedad", "promedio")
    assert maximo["pruebas"] == ["rango", "sin_dato"] and maximo["marcas"] == {"ok": 8, "rango": 0, "sin_dato": 0}
    assert promedio["pruebas"] == ["rango", "plano", "sin_dato"] and promedio["marcas"]["plano"] == 3


def test_ocho_dias_sin_lluvia_no_son_un_sensor_trabado(cache_temporal):
    _dias_completos("precipitacion", "precip_horario", [0.0] * 8, cache_temporal)
    c = _calidad("precipitacion", "suma")
    assert c["pruebas"] == ["rango", "sin_dato"] and c["marcas"] == {"ok": 8, "rango": 0, "sin_dato": 0}


def test_una_combinacion_sin_cotas_medidas_no_trae_calidad(temperatura):
    """La suma de temperaturas horarias no es una temperatura: sin cotas medidas no se inventa una prueba."""
    r = h.observaciones_inumet("temperatura", "Salto G3", "2026-01-01", "2026-01-02", "suma")
    assert "calidad" not in r["series"][0]


def test_el_viento_no_trae_calidad(cache_temporal):
    """La fuente del viento hoy trae dos recursos de datos y el lector la rechaza; la dirección es circular."""
    filas = [f"{t:%Y-%m-%d %H:%M};Salto G3;90;10" for t in _horas(datetime(2026, 1, 1, 3), 24)]
    _csv(cache_temporal / "inumet", "viento", "fecha;estacion_id;dir_viento;int_viento", filas)
    r = h.observaciones_inumet("viento", "Salto G3", "2026-01-01", "2026-01-01", "promedio")
    assert all("calidad" not in s for s in r["series"])


def test_toda_cota_de_inumet_apunta_a_una_columna_y_una_agregacion_que_existen():
    from uydatos import inumet

    columnas = {c for _, cols, _ in inumet.DATASETS.values() for c in cols}
    for columna, agregacion in h.rio_y_clima.CALIDAD_INUMET:
        assert columna in columnas and agregacion in inumet.AGREGACIONES
