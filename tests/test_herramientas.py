"""Las herramientas, sin red: el BCU se reemplaza por uno falso y ANCAP lee un CSV en la caché."""

from __future__ import annotations

from datetime import date

import pytest
from conftest import BcuFalso
from uydatos import bcu

from mcp_uruguay import herramientas as h

HOY = date(2026, 10, 9)  # viernes


@pytest.fixture
def bcu_falso(monkeypatch):
    falso = BcuFalso(valor=lambda d: 40.0 + d.day / 100, hasta=HOY)
    monkeypatch.setattr(bcu, "descargar", falso)
    return falso


class TestCotizacion:
    def test_dia_publicado(self, bcu_falso):
        r = h.cotizacion("USD", "2026-10-08", hoy=HOY)
        assert r["valor_en_pesos"] == pytest.approx(40.08)
        assert r["fecha_cotizacion"] == "2026-10-08"
        assert r["fuente"].startswith("Banco Central del Uruguay")
        assert r["bajado"]

    def test_sabado_sin_hacia_atras_es_null_y_lo_explica(self, bcu_falso):
        r = h.cotizacion("USD", "2026-10-03", hoy=HOY)
        assert r["valor_en_pesos"] is None
        assert "hacia_atras" in r["nota"]

    def test_sabado_hacia_atras_dice_que_dia_uso(self, bcu_falso):
        r = h.cotizacion("USD", "2026-10-03", hacia_atras=True, hoy=HOY)
        assert r["valor_en_pesos"] == pytest.approx(40.02)
        assert r["fecha_cotizacion"] == "2026-10-02"
        assert "2026-10-02" in r["nota"]

    def test_lunes_hacia_atras_cruza_el_mes(self, bcu_falso):
        """El 1.º de junio de 2026 es lunes: hacia atrás pide también mayo."""
        r = h.cotizacion("UI", "2026-06-01", hacia_atras=True, hoy=HOY)
        assert r["fecha_cotizacion"] == "2026-06-01"
        r = h.cotizacion("UI", "2026-08-01", hacia_atras=True, hoy=HOY)  # sábado
        assert r["fecha_cotizacion"] == "2026-07-31"

    def test_moneda_desconocida(self):
        with pytest.raises(ValueError, match="USD"):
            h.cotizacion("EUR", "2026-10-08")

    def test_fecha_mal_escrita(self):
        with pytest.raises(ValueError, match="AAAA-MM-DD"):
            h.cotizacion("USD", "08/10/2026")


class TestMensual:
    def test_el_mes_en_curso_va_marcado_incompleto(self, bcu_falso):
        r = h.cotizacion_mensual("USD", "2026-09", "2026-10", hoy=HOY)
        assert [(m["mes"], m["completo"]) for m in r["meses"]] == [("2026-09", True), ("2026-10", False)]
        assert r["meses"][1]["dias"] == 7

    def test_rango_demasiado_largo(self):
        with pytest.raises(ValueError, match="240"):
            h.cotizacion_mensual("USD", "1990-01", "2026-01")


class TestPesosConstantes:
    def test_lleva_a_pesos_del_mes_base(self, monkeypatch):
        ui = {8: 6.0, 9: 6.3}
        monkeypatch.setattr(bcu, "descargar", BcuFalso(valor=lambda d: ui[d.month], hasta=HOY))
        r = h.pesos_constantes({"2026-08": 100.0}, "2026-09", hoy=HOY)
        assert r["montos_en_pesos_de_la_base"] == {"2026-08": 105.0}
        assert r["ui_promedio_usada"] == {"2026-08": 6.0, "2026-09": 6.3}

    def test_vacio(self):
        with pytest.raises(ValueError, match="vacío"):
            h.pesos_constantes({}, "2026-09")


class TestAncap:
    @pytest.fixture(autouse=True)
    def csv_en_cache(self, cache_temporal):
        cache_temporal.mkdir(parents=True, exist_ok=True)
        (cache_temporal / "ancap.csv").write_text(
            "\ufeff\ufeffAño;Mes;Producto;Unidad;Valor\n"
            "2026;7;GASOIL 50-S *;58,68;$/lt\n"
            "2026;7;GASOIL 50-S *;58,68;$/lt\n"
            "2026;8;GASOIL 50-S *;S/C;S/C\n"
            "2026;7;SUPER 95 *;75,10;$/lt\n",
            encoding="utf-8-sig",
        )

    def test_sin_producto_lista_los_productos(self):
        assert h.combustible_ancap()["productos"] == ["GASOIL 50-S *", "SUPER 95 *"]

    def test_la_serie_viene_deduplicada(self):
        r = h.combustible_ancap("GASOIL 50-S *")
        assert r["precios"] == [
            {"mes": "2026-07", "precio": 58.68, "unidad": "$/lt"},
            {"mes": "2026-08", "precio": None, "unidad": ""},
        ]

    def test_un_mes(self):
        assert h.combustible_ancap("SUPER 95 *", 2026, 7)["precios"][0]["precio"] == 75.10

    def test_producto_inexistente_sugiere_parecidos(self):
        with pytest.raises(ValueError, match="GASOIL 50-S"):
            h.combustible_ancap("gasoil")


class TestSinRed:
    def test_rut_y_cedula(self):
        assert h.validar_documento("1.234.567-2", "ci")["valido"] is True
        r = h.validar_documento("1.234.567-3", "ci")
        assert (r["valido"], r["estado"]) == (False, "dv_no_valida")
        assert "DGI" in r["nota"]

    def test_semana(self):
        r = h.semana("2027-01-01")
        assert (r["etiqueta_con_anio"], r["desde"], r["hasta"]) == ("2026-W53", "2026-12-28", "2027-01-03")


class TestGeocodificar:
    def test_devuelve_calidad_coordenada_y_fuente(self, monkeypatch):
        from uydatos import ideuy

        respuesta = {
            "idTipoClasificacion": 1,
            "error": "",
            "puntoX": -56.18,
            "puntoY": -34.90,
            "direccion": {
                "calle": {"nombre_normalizado": "AVENIDA 18 DE JULIO"},
                "numero": {"nro_puerta": 1360},
                "localidad": {"nombre_normalizado": "MONTEVIDEO"},
            },
        }
        monkeypatch.setattr(ideuy, "_consultar", lambda url: [respuesta])
        r = h.geocodificar_direccion("Av. 18 de Julio 1360", "Montevideo", "Montevideo")
        assert (r["calidad"], r["lat"], r["lon"]) == ("puerta_exacta", -34.90, -56.18)
        assert r["fuente"].startswith("IDE.uy")

    def test_direccion_vacia(self):
        with pytest.raises(ValueError, match="vacía"):
            h.geocodificar_direccion("  ")


class TestVentasCombustible:
    @pytest.fixture(autouse=True)
    def ventas(self, cache_temporal):
        cache_temporal.mkdir(parents=True, exist_ok=True)
        (cache_temporal / "ancap_ventas.csv").write_text(
            "Mercado;Mes;Anio;FamiliaDeProducto;LineaDeProducto;Bandera;CantidadCorregida;Unidad\n"
            "INTERNO;01;2024;BLANCOS;GAS OIL;B/N;100,5;Miles de m3\n"
            "INTERNO;02;2024;BLANCOS;GAS OIL;B/N;90;Miles de m3\n"
            "Bunker;01;2024;BLANCOS;GAS OIL;B/E;10;Miles de m3\n"
            "Bunker;01;2024;BLANCOS;GAS OIL;B/N;5;Miles de m3\n"
            "INTERNO;01;2025;BLANCOS;GAS OIL;B/N;-0,5;Miles de m3\n"
            "INTERNO;01;2024;SOLVENTES;QUEROSENOS;B/N;1;Miles de m3\n"
            "INTERNO;01;2024;BLANCOS;QUEROSENO;B/N;2;Miles de m3\n"
            "INTERNO;02;2024;COMBUSTIBLES SÓLIDOS;PETCOKE;B/N;3000;Toneladas\n",
            encoding="utf-8",
        )

    def test_sin_linea_lista_productos_y_meses_que_faltan(self):
        r = h.ventas_combustible()
        assert {x["linea"] for x in r["lineas"]} == {"GAS OIL", "QUEROSENOS", "QUEROSENO", "PETCOKE"}
        assert next(x for x in r["lineas"] if x["linea"] == "PETCOKE")["unidad"] == "Toneladas"
        assert r["cobertura"]["2025"] == list(range(2, 13))

    def test_suma_banderas_y_mercados_y_dice_cuantos_meses_tiene_cada_anio(self):
        r = h.ventas_combustible("gas oil")
        assert r["ventas"][0] == {"mes": "2024-01", "cantidad": 115.5}
        assert r["por_anio"][0]["meses"] == 2 and r["por_anio"][1]["cantidad"] == -0.5

    def test_un_mercado_y_un_periodo(self):
        r = h.ventas_combustible("GAS OIL", "bunker", "2024-01", "2024-12")
        assert r["mercado"] == "Bunker" and r["ventas"] == [{"mes": "2024-01", "cantidad": 15.0}]

    def test_queroseno_y_querosenos_no_se_mezclan(self):
        assert h.ventas_combustible("QUEROSENO")["ventas"][0]["cantidad"] == 2.0

    def test_linea_o_mercado_inexistente_dicen_que_hay(self):
        with pytest.raises(ValueError, match="GAS OIL"):
            h.ventas_combustible("gasoil")
        with pytest.raises(ValueError, match="INTERNO"):
            h.ventas_combustible("GAS OIL", "Montevideo")


class TestIndicadorSocial:
    PAGINA = (
        "<html><head><title>Tasa de empleo según departamento. Total país | MIDES</title>"
        '<meta name="description" content="Ocupados sobre población en edad de trabajar." /></head><body>'
        '<input name="current_filters" value="{&quot;Departamento&quot;:{&quot;Salto&quot;:&quot;Salto&quot;},'
        '&quot;A\\u00f1o&quot;:{&quot;2023&quot;:&quot;2023&quot;,&quot;2024&quot;:&quot;2024&quot;}}" />'
        "<table><tr><th>Departamento</th><th>2023</th><th>2024</th></tr>"
        "<tr><td>Salto</td><td>50,1</td><td>-</td></tr><tr><td>Paysandú</td><td>52</td><td>53,5</td></tr>"
        "<tr><td>Total</td><td>57</td><td>57,9</td></tr></table>"
        "<h3>Fuente</h3><p>INE Encuesta Continua de Hogares</p><h3>Unidad de observación</h3><p>Por cien</p>"
        "<h3>Período</h3><ul><li>Año de inicio:\n2006</li><li>Año de fin:\n2024</li></ul>"
        "<footer></footer></body></html>"
    )

    @pytest.fixture(autouse=True)
    def sin_red(self, monkeypatch):
        import json

        from uydatos import observatorio

        monkeypatch.setattr(
            observatorio, "indice", lambda: ["tasa-empleo-segun-departamento-total-pais", "tasa-empleo-total-pais"]
        )
        monkeypatch.setattr(
            observatorio.red, "bajar", lambda url, ruta: ruta.write_text(self.PAGINA, encoding="utf-8") or ruta
        )
        self.json = json

    def test_buscar_devuelve_nombres_y_el_total(self):
        r = h.buscar_indicador_social("empleo departamento")
        assert r["indicadores"] == ["tasa-empleo-segun-departamento-total-pais"] and r["total"] == 2

    def test_lee_la_ficha_la_tabla_y_los_avisos(self):
        r = h.indicador_social("tasa-empleo-segun-departamento-total-pais")
        assert r["unidad"] == "Por cien" and r["fuente_del_dato"] == "INE Encuesta Continua de Hogares"
        assert r["filas"][0] == {"dimensiones": {"Departamento": "Salto"}, "valores": {"2023": 50.1, "2024": None}}
        assert any("filas de total" in a for a in r["avisos"])

    def test_el_filtro_compara_sin_tildes(self):
        r = h.indicador_social("tasa-empleo-segun-departamento-total-pais", "paysandu")
        assert [f["dimensiones"]["Departamento"] for f in r["filas"]] == ["Paysandú"] and r["filas_totales"] == 1

    def test_un_indicador_que_no_esta_en_el_indice_sugiere(self):
        with pytest.raises(ValueError, match="tasa-empleo-segun-departamento-total-pais"):
            h.indicador_social("tasa-empleo-segun-departamentos")

    def test_un_filtro_sin_filas_dice_que_valores_hay(self):
        with pytest.raises(ValueError, match="Salto"):
            h.indicador_social("tasa-empleo-segun-departamento-total-pais", "Rivera")
