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


@pytest.fixture(autouse=True)
def sin_descargas_censo(monkeypatch):
    from uydatos import censo

    def sin_red(cuadro, destino):
        raise OSError("sin red en los tests de unidad")

    monkeypatch.setattr(censo, "descargar", sin_red)


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

    def test_sin_nada_es_el_pais(self, capas):
        """Sin nombre ni departamento: las localidades más pobladas y los departamentos de todas ellas.
        Antes era un error, y no había forma de preguntar el total del país ni la población de cada
        departamento sin una llamada por departamento."""
        r = h.localidad()
        assert r["total"] == 5 and len(r["localidades"]) == 5
        assert [x["nombre"] for x in r["localidades"]][:2] == ["SALTO", "SAN ANTONIO"]
        assert {d["departamento"] for d in r["departamentos"]} == {"SALTO", "CANELONES"}

    def test_sin_nada_trae_el_total_del_pais(self, capas, censo_en_cache):
        """El total es la suma de los departamentos del cuadro 12, no la de las localidades."""
        r = h.localidad()
        assert r["poblacion_oficial_total"] == 608960 + 136195
        assert [(d["departamento"], d["poblacion_oficial_2023"]) for d in r["departamentos"]] == [
            ("CANELONES", 608960),
            ("SALTO", 136195),
        ]

    def test_el_total_no_sale_de_un_cuadro_a_medias(self, capas, censo_en_cache):
        """Con el cuadro 12 caído el total queda en null: una suma parcial es un número plausible y falso."""
        (censo_en_cache / "departamentos.xlsx").unlink()
        r = h.localidad("Salto", "Salto")
        assert r["poblacion_oficial_total"] is None
        assert r["localidades"][0]["poblacion_oficial_2023"] == 112527

    def test_avisa_que_la_poblacion_de_la_capa_no_es_la_oficial(self, capas):
        nota = h.localidad("garibaldi")["nota"]
        assert "poblacion_oficial_2023" in nota and "difieren" in nota


@pytest.fixture
def censo_en_cache(cache_temporal):
    """Los dos tabulados del INE ya en la caché, con la forma real (encabezado en la fila 4)."""
    openpyxl = pytest.importorskip("openpyxl")
    carpeta = cache_temporal / "censo"
    carpeta.mkdir(parents=True, exist_ok=True)

    def guardar(nombre, filas):
        libro = openpyxl.Workbook()
        for f in filas:
            libro.active.append(list(f))
        libro.save(carpeta / nombre)

    guardar(
        "departamentos.xlsx",
        [
            ("CUADRO 12",),
            ("Población, área (km2) y densidad por departamento. Total País.",),
            (None,),
            ("Código Localidad INE 2023", "Departamento", "Población Total", "Área (Km2)", "Densidad (Hb/km2)"),
            ("03", "CANELONES", 608960, 4536, 134.2),
            ("15", "SALTO", 136195, 14163, 9.6),
        ],
    )
    guardar(
        "localidades.xlsx",
        [
            ("CUADRO 13",),
            ("Población por departamento y localidad. Total País.",),
            (None,),
            ("Código localidad INE", "Nombre departamento", "Nombre localidad", "Población Total"),
            (None,),
            ("Total", None, None, 112527 + 545),
            ("15020", "SALTO", "SALTO", 112527),
            ("15939", "SALTO", "GARIBALDI", 545),
        ],
    )
    return carpeta


class TestPoblacionOficial:
    def test_procedencia_incluye_la_capa_y_ambos_tabulados(self, capas, censo_en_cache):
        from mcp_uruguay import cache

        # También la capa ya leída en memoria tiene que figurar como respaldo.
        h.localidad("Salto", "Salto")
        with cache.vigilar_procedencia() as leidas:
            h.localidad("Salto", "Salto")
        assert {c["archivo"] for c in leidas} == {
            "limites/localidades.geojson",
            "censo/localidades.xlsx",
            "censo/departamentos.xlsx",
        }
        assert all(c["url"] for c in leidas if c["archivo"].startswith("censo/"))

    def test_cada_localidad_trae_la_cifra_oficial_del_ine(self, capas, censo_en_cache):
        r = h.localidad("Salto", "Salto")
        loc = r["localidades"][0]
        assert loc["poblacion_2023"] == 114043 and loc["poblacion_oficial_2023"] == 112527

    def test_una_localidad_que_no_esta_en_el_tabulado_queda_sin_dato(self, capas, censo_en_cache):
        loc = h.localidad("Albisu")["localidades"][0]
        assert loc["poblacion_oficial_2023"] is None

    def test_el_departamento_trae_su_poblacion_oficial(self, capas, censo_en_cache):
        r = h.localidad("", "salto")
        assert r["departamentos"] == [{"departamento": "SALTO", "poblacion_oficial_2023": 136195}]

    @pytest.mark.parametrize("faltante", ["localidades", "departamentos"])
    def test_un_tabulado_caido_no_borra_el_otro(self, capas, censo_en_cache, faltante):
        (censo_en_cache / f"{faltante}.xlsx").unlink()
        r = h.localidad("Salto", "Salto")
        if faltante == "localidades":
            assert r["departamentos"][0]["poblacion_oficial_2023"] == 136195
            assert r["localidades"][0]["poblacion_oficial_2023"] is None
        else:
            assert r["localidades"][0]["poblacion_oficial_2023"] == 112527
            assert r["departamentos"][0]["poblacion_oficial_2023"] is None
        assert faltante in r["nota"]

    def test_sin_el_tabulado_la_herramienta_igual_responde(self, capas, monkeypatch):
        from uydatos import censo

        def caida(cuadro, destino):
            raise OSError("sin red")

        monkeypatch.setattr(censo, "descargar", caida)
        r = h.localidad("Salto", "Salto")
        assert r["localidades"][0]["poblacion_oficial_2023"] is None
        assert "no se pudo" in r["nota"].lower()

    def test_ubicar_punto_trae_la_cifra_oficial_de_la_localidad(self, capas, censo_en_cache, sin_ide):
        """El punto cae en Salto: la capa dice 114.043 y el INE publica 112.527. La respuesta lleva las dos
        y la nota dice cuál se cita; antes llevaba solo la de la capa, que no es la oficial."""
        r = h.ubicar_punto(-31.42, -58.17)
        loc = r["localidad"]
        assert loc["nombre"] == "SALTO" and loc["poblacion_2023"] == 114043
        assert loc["poblacion_oficial_2023"] == 112527
        assert "112.527 oficial" in r["nota"] and "Censo" in r["fuente"]

    def test_sin_el_tabulado_ubicar_punto_igual_responde(self, capas, sin_ide):
        r = h.ubicar_punto(-31.42, -58.17)
        assert r["localidad"]["poblacion_2023"] == 114043
        assert r["localidad"]["poblacion_oficial_2023"] is None
        assert "no se pudo" in r["nota"].lower()
