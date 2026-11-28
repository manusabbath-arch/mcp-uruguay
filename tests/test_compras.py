"""`compras_estado`, sin red: un ZIP sintético con la forma de los de la ARCE en la caché y el BCU falso."""

from __future__ import annotations

import json
import zipfile

import pytest
from conftest import BcuFalso
from uydatos import bcu

from mcp_uruguay import herramientas as h
from mcp_uruguay.herramientas import estado


def _item(descripcion, cantidad, precio, moneda="UYU"):
    valor = {"amount": precio}
    if moneda:
        valor["currency"] = moneda
    return {
        "id": 1,
        "quantity": cantidad,
        "classification": {"id": "1", "description": descripcion, "scheme": "x_catalogo_arce"},
        "unit": {"id": "22", "name": "UNIDAD", "value": valor},
    }


def _adj(ocid, comprador, items, estado="active", fecha="2025-03-05T10:00:00Z"):
    return {
        "tag": ["award"],
        "ocid": f"ocds-yfs5dr-{ocid}",
        "date": fecha,
        "buyer": {"id": comprador[0], "name": comprador[1]},
        "parties": [],
        "awards": [
            {
                "id": "R/210000000019",
                "status": estado,
                "items": items,
                "suppliers": [{"id": "R/210000000019", "name": "PERSONA FISICA DE PRUEBA"}],
            }
        ],
    }


UTE = ("1", "Administración Nacional de Usinas y Trasmisiones Eléctricas")
IM = ("98-1", "Intendencia de Montevideo")


@pytest.fixture
def compras_2025(cache_temporal, monkeypatch):
    monkeypatch.setattr(bcu, "descargar", BcuFalso(valor=lambda d: 40.0))
    carpeta = cache_temporal / "compras"
    carpeta.mkdir(parents=True)
    releases = [
        _adj(1, UTE, [_item("ALAMBRADO", 850000, 461611)]),
        _adj(2, IM, [_item("GUANTES DE LATEX", 100, 3), _item("SERVICIO DE LIMPIEZA", 1, 10000)]),
        _adj(3, IM, [_item("AMBULANCIA", 1, 1000, "USD")]),
        _adj(4, IM, [_item("CANCELADA", 1, 999999)], estado="cancelled"),
        _adj(5, IM, [_item("SIN MONEDA", 1, 77, None)]),
    ]
    with zipfile.ZipFile(carpeta / "2025.zip", "w") as z:
        z.writestr("2025/a-03-2025.json", json.dumps({"releases": releases}))
    return carpeta


class TestComprasEstado:
    def test_total_en_pesos_con_los_dolares_convertidos(self, compras_2025):
        r = h.compras_estado(2025, organismo="Intendencia de Montevideo", hoy=None)
        assert r["adjudicaciones"] == 3 and r["excluidas_por_estado"] == {"cancelled": 1}
        assert r["total_pesos"] == pytest.approx(300 + 10000 + 1000 * 40.0)
        assert r["sin_moneda"] == 77.0 and r["sin_convertir"] == {}

    def test_el_registro_imposible_se_ve_y_se_avisa(self, compras_2025, monkeypatch):
        monkeypatch.setattr(estado, "MINIMO_ITEMS_AVISO", 3)  # la constante se lee en el módulo donde vive
        r = h.compras_estado(2025)
        assert r["mayores_items"][0]["descripcion"] == "ALAMBRADO"
        assert r["mayores_items"][0]["pct_del_total"] > 99
        assert "un solo ítem" in r["aviso"]

    def test_sin_registros_dominantes_no_hay_aviso(self, compras_2025):
        r = h.compras_estado(2025, organismo="intendencia de montevideo")
        assert r["mayores_items"][0]["pct_del_total"] < 80
        r2 = h.compras_estado(2025, buscar="guantes")
        assert r2["aviso"] == "" and r2["total_pesos"] == 300.0

    def test_no_devuelve_nombres_de_proveedores(self, compras_2025):
        """Un proveedor puede ser una persona física: el servidor no expone su nombre."""
        assert "PERSONA FISICA" not in json.dumps(h.compras_estado(2025), ensure_ascii=False)

    def test_organismos_ordenados_por_pesos(self, compras_2025):
        r = h.compras_estado(2025)
        assert [o["nombre"] for o in r["organismos"]][:2] == [UTE[1], IM[1]]

    def test_anio_fuera_de_rango(self, compras_2025):
        with pytest.raises(ValueError, match="2002"):
            h.compras_estado(1995)


def _llamado(ocid, modalidad):
    return {
        "tag": ["tender"],
        "ocid": f"ocds-yfs5dr-{ocid}",
        "date": "2025-02-01T10:00:00Z",
        "tender": {"id": str(ocid), "procurementMethodDetails": modalidad},
    }


@pytest.fixture
def compras_con_modalidad(cache_temporal, monkeypatch):
    """Tres compras de la IM: una directa, una licitación y una sin llamado (modalidad desconocida)."""
    monkeypatch.setattr(bcu, "descargar", BcuFalso(valor=lambda d: 40.0))
    carpeta = cache_temporal / "compras"
    carpeta.mkdir(parents=True)
    adjs = [
        _adj(1, IM, [_item("PUBLICIDAD", 1, 1000)]),
        _adj(2, IM, [_item("ASFALTO", 1, 50000)]),
        _adj(3, IM, [_item("PUBLICIDAD", 1, 7000)]),
    ]
    llamados = [_llamado(1, "Compra Directa"), _llamado(2, "Licitación Abreviada")]
    with zipfile.ZipFile(carpeta / "2025.zip", "w") as z:
        z.writestr("2025/a-03-2025.json", json.dumps({"releases": adjs}))
        z.writestr("2025/l-02-2025.json", json.dumps({"releases": llamados}))
    return carpeta


class TestModalidad:
    def test_cuenta_por_modalidad_y_las_desconocidas_aparte(self, compras_con_modalidad):
        r = h.compras_estado(2025)
        assert r["por_modalidad"] == {"Compra Directa": 1, "Licitación Abreviada": 1}
        assert r["sin_modalidad"] == 1 and r["modalidad"] is None

    def test_filtra_por_modalidad_y_avisa_que_es_un_piso(self, compras_con_modalidad):
        """La compra 3 no trae llamado: puede haber sido directa. El total filtrado no es «todas»."""
        r = h.compras_estado(2025, modalidad="compra directa")
        assert r["adjudicaciones"] == 1 and r["total_pesos"] == 1000.0
        assert r["sin_modalidad"] == 1
        assert "piso" in r["aviso"] and "1 de 3" in r["aviso"]

    def test_una_modalidad_que_no_existe_se_rechaza_con_las_que_hay(self, compras_con_modalidad):
        with pytest.raises(ValueError, match="Licitación Abreviada"):
            h.compras_estado(2025, modalidad="a dedo")

    def test_sin_filtro_no_hay_aviso_de_modalidad(self, compras_con_modalidad):
        assert "piso" not in h.compras_estado(2025)["aviso"]


def _item_u(descripcion, precio, unidad, catalogo="37021"):
    it = _item(descripcion, 1, precio)
    it["classification"]["id"] = catalogo
    it["unit"]["name"] = unidad
    return it


@pytest.fixture
def compras_guantes(cache_temporal, monkeypatch):
    """Guantes por UNIDAD en dos organismos, una «caja» y un ítem sin moneda."""
    monkeypatch.setattr(bcu, "descargar", BcuFalso(valor=lambda d: 40.0))
    carpeta = cache_temporal / "compras"
    carpeta.mkdir(parents=True)
    adjs = [
        _adj(1, IM, [_item_u("GUANTES DE LATEX", 1.0, "UNIDAD")]),
        _adj(2, IM, [_item_u("GUANTES DE LATEX", 1.2, "UNIDAD")]),
        _adj(3, UTE, [_item_u("GUANTES DE LATEX", 1.4, "UNIDAD")]),
        _adj(4, IM, [_item_u("GUANTES DE LATEX", 113.0, "CAJA")]),
        _adj(5, IM, [_item("GUANTES DE LATEX", 1, 5, None)]),
    ]
    with zipfile.ZipFile(carpeta / "2025.zip", "w") as z:
        z.writestr("2025/a-03-2025.json", json.dumps({"releases": adjs}))
    return carpeta


class TestPreciosDeReferencia:
    def test_con_buscar_da_precios_unitarios_por_unidad_sin_mezclar(self, compras_guantes):
        r = h.compras_estado(2025, buscar="guantes de látex")
        g = r["precios_unitarios"]
        assert [(x["unidad"], x["n"], x["mediana"]) for x in g] == [("UNIDAD", 3, 1.2), ("CAJA", 1, 113.0)]
        assert g[0]["organismos"] == 2
        assert r["precios_excluidos"] == {"sin_moneda": 1}

    def test_sin_buscar_no_hay_precios_unitarios(self, compras_guantes):
        """Un precio de referencia de «todo lo que compró el Estado» no significa nada."""
        r = h.compras_estado(2025)
        assert r["precios_unitarios"] == [] and r["precios_excluidos"] == {}

    def test_los_precios_respetan_el_filtro_de_organismo(self, compras_guantes):
        r = h.compras_estado(2025, buscar="guantes", organismo="Intendencia de Montevideo")
        assert [(x["unidad"], x["n"]) for x in r["precios_unitarios"]] == [("UNIDAD", 2), ("CAJA", 1)]

    def test_no_devuelve_nombres_de_proveedores_en_los_atipicos(self, compras_guantes):
        assert "PERSONA FISICA" not in json.dumps(h.compras_estado(2025, buscar="guantes"), ensure_ascii=False)


class TestOrganismoQueNoFigura:
    def test_un_organismo_sin_compras_en_el_archivo_se_rechaza_con_motivo(self, compras_2025):
        """En 2025 cinco intendencias no figuran como compradoras: devolver 0 se leería como «no compró»."""
        with pytest.raises(ValueError, match="no figura como comprador") as e:
            h.compras_estado(2025, organismo="Intendencia de Maldonado")
        assert "no prueba" in str(e.value)

    def test_sugiere_compradores_parecidos(self, compras_2025):
        with pytest.raises(ValueError, match="Intendencia de Montevideo"):
            h.compras_estado(2025, organismo="Intendencia Montevideo")

    def test_organismo_que_figura_pero_sin_ese_producto_da_cero_sin_error(self, compras_2025):
        r = h.compras_estado(2025, organismo="Intendencia de Montevideo", buscar="submarino")
        assert r["adjudicaciones"] == 0


class TestModalidadPorOrganismo:
    def test_cada_organismo_dice_cuantas_no_traen_modalidad(self, compras_con_modalidad):
        (im,) = h.compras_estado(2025)["organismos"]
        assert im["nombre"] == IM[1] and im["sin_modalidad"] == 1


class TestCoherencia:
    def test_sin_modalidad_se_cuenta_sobre_las_mismas_adjudicaciones_del_organismo(self, cache_temporal, monkeypatch):
        """Un ocid con dos adjudicaciones (dos proveedores) cuenta una vez en las dos cifras."""
        monkeypatch.setattr(bcu, "descargar", BcuFalso(valor=lambda d: 40.0))
        carpeta = cache_temporal / "compras"
        carpeta.mkdir(parents=True)
        doble = _adj(1, IM, [_item("X", 1, 10)])
        doble["awards"].append({**doble["awards"][0], "id": "R/2"})
        adjs = [doble, _adj(2, IM, [_item("Y", 1, 10)])]
        with zipfile.ZipFile(carpeta / "2025.zip", "w") as z:
            z.writestr("2025/a-03-2025.json", json.dumps({"releases": adjs}))
            z.writestr("2025/l-02-2025.json", json.dumps({"releases": [_llamado(2, "Compra Directa")]}))
        (im,) = h.compras_estado(2025)["organismos"]
        assert (im["adjudicaciones"], im["sin_modalidad"]) == (2, 1)

    def test_la_sugerencia_con_mas_palabras_en_comun_va_primero(self, cache_temporal, monkeypatch):
        monkeypatch.setattr(bcu, "descargar", BcuFalso(valor=lambda d: 40.0))
        carpeta = cache_temporal / "compras"
        carpeta.mkdir(parents=True)
        adjs = [_adj(i, ("29-1", "Centro Departamental de Salto"), [_item("X", 1, 1)]) for i in range(5)]
        adjs.append(_adj(9, ("85-1", "Intendencia de Salto"), [_item("X", 1, 1)]))
        with zipfile.ZipFile(carpeta / "2025.zip", "w") as z:
            z.writestr("2025/a-03-2025.json", json.dumps({"releases": adjs}))
        with pytest.raises(ValueError, match="parecidos: Intendencia de Salto,"):
            h.compras_estado(2025, organismo="Intendencia Salto")
