"""`ubicar_punto` y `localidad`, sin red: capas sintéticas en la caché e IDE.uy reemplazado."""

from __future__ import annotations

import json

import pytest
from uydatos import ideuy

from mcp_uruguay import herramientas as h


def _cuadrado(lon0, lat0, lado):
    return [[[[lon0, lat0], [lon0 + lado, lat0], [lon0 + lado, lat0 + lado], [lon0, lat0 + lado], [lon0, lat0]]]]


def _escribir(ruta, features):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")


@pytest.fixture
def capas(cache_temporal):
    deps = [
        {
            "type": "Feature",
            "properties": {"depto": i, "nombre": "SALTO" if i == 15 else f"DEPTO {i}", "cdepto_iso": f"UY{i:02d}"},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": _cuadrado(-58.3, -31.7, 0.6)
                if i == 15
                else _cuadrado(-58.4 + (i - 1) * 0.3, -33.5, 0.3),
            },
        }
        for i in range(1, 20)
    ]
    deps.append(
        {
            "type": "Feature",
            "properties": {"depto": 2, "nombre": "LIMITE CONTESTADO", "cdepto_iso": "UY02"},
            "geometry": {"type": "MultiPolygon", "coordinates": _cuadrado(-56.0, -30.4, 0.2)},
        }
    )
    _escribir(cache_temporal / "limites" / "departamentos.geojson", deps)

    def loc(cod, nombre, depto, lon, lat, pob, viv, capital=False):
        props = {
            "DEPTO": 15,
            "CODLOC": cod,
            "NOMBDEPTO": depto,
            "NOMBLOC": nombre,
            "pob_tot_23": pob,
            "viv_tot_23": viv,
            "capital": capital,
        }
        return {
            "type": "Feature",
            "properties": props,
            "geometry": {"type": "MultiPolygon", "coordinates": _cuadrado(lon, lat, 0.05)},
        }

    _escribir(
        cache_temporal / "limites" / "localidades.geojson",
        [
            loc(15020, "SALTO", "SALTO", -58.2, -31.45, 114043, 41536, True),
            loc(15939, "GARIBALDI", "SALTO", -57.95, -31.35, 549, 185),
            loc(15821, "ALBISU", "SALTO", -58.15, -31.55, 572, 167),
            loc(2020, "SAN ANTONIO", "SALTO", -58.0, -31.5, 300, 100),
            loc(3020, "SAN ANTONIO", "CANELONES", -55.9, -34.5, 900, 400),
        ],
    )


@pytest.fixture
def sin_ide(monkeypatch):
    monkeypatch.setattr(
        ideuy,
        "_consultar",
        lambda url: [
            {
                "type": "CALLEyPORTAL",
                "address": "URUGUAY 100",
                "localidad": "SALTO",
                "departamento": "SALTO",
                "lat": -31.42,
                "lng": -58.17,
            }
        ],
    )


class TestUbicarPunto:
    def test_adentro_de_una_localidad(self, capas, sin_ide):
        r = h.ubicar_punto(-31.42, -58.17)
        assert r["departamento"]["nombre"] == "SALTO"
        assert r["localidad"]["nombre"] == "SALTO" and r["localidad"]["adentro"] is True
        assert r["localidad"]["poblacion_2023"] == 114043
        assert r["direccion_mas_cercana"]["direccion"] == "URUGUAY 100"
        assert r["direccion_mas_cercana"]["distancia_km"] < 0.1

    def test_en_el_campo_da_la_localidad_mas_cercana_con_distancia(self, capas, sin_ide):
        r = h.ubicar_punto(-31.30, -58.0)
        assert r["departamento"]["nombre"] == "SALTO"
        assert r["localidad"]["adentro"] is False
        assert r["localidad"]["nombre"] == "GARIBALDI" and r["localidad"]["distancia_km"] > 1

    def test_en_el_mar_no_hay_departamento(self, capas, sin_ide):
        r = h.ubicar_punto(-36.5, -54.0)
        assert r["departamento"]["nombre"] is None
        assert "mar" in r["nota"] or "fuera" in r["departamento"]["nota"]

    def test_el_limite_contestado_se_dice(self, capas, sin_ide):
        r = h.ubicar_punto(-30.3, -55.9)
        assert r["departamento"]["tipo"] == "limite_contestado"
        assert r["departamento"]["asignado_a"] == "DEPTO 2"

    def test_coordenadas_imposibles(self, capas):
        with pytest.raises(ValueError, match="latitud"):
            h.ubicar_punto(-131.0, -57.0)

    def test_si_ide_no_responde_igual_da_departamento_y_localidad(self, capas, monkeypatch):
        def caida(url):
            raise TimeoutError("timed out")

        monkeypatch.setattr(ideuy, "_consultar", caida)
        r = h.ubicar_punto(-31.42, -58.17)
        assert r["departamento"]["nombre"] == "SALTO" and r["direccion_mas_cercana"] is None
        assert "IDE" in r["nota"]


class TestLocalidad:
    def test_por_nombre_sin_tildes_ni_mayusculas(self, capas):
        r = h.localidad("garibaldi")
        assert [x["nombre"] for x in r["localidades"]] == ["GARIBALDI"]
        assert r["localidades"][0]["poblacion_2023"] == 549

    def test_un_nombre_en_dos_departamentos_devuelve_los_dos(self, capas):
        r = h.localidad("San Antonio")
        assert {x["departamento"] for x in r["localidades"]} == {"SALTO", "CANELONES"}

    def test_el_departamento_desambigua(self, capas):
        r = h.localidad("San Antonio", "Canelones")
        assert [x["poblacion_2023"] for x in r["localidades"]] == [900]

    def test_solo_departamento_lista_por_poblacion(self, capas):
        r = h.localidad("", "salto")
        assert [x["nombre"] for x in r["localidades"]][:2] == ["SALTO", "ALBISU"]

    def test_inexistente_sugiere(self, capas):
        with pytest.raises(ValueError, match="GARIBALDI"):
            h.localidad("Garibaldy")

    def test_sin_nada(self, capas):
        with pytest.raises(ValueError):
            h.localidad("", "")
