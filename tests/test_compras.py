"""`compras_estado`, sin red: un ZIP sintético con la forma de los de la ARCE en la caché y el BCU falso."""

from __future__ import annotations

import json
import zipfile

import pytest
from conftest import BcuFalso
from uydatos import bcu

from mcp_uruguay import herramientas as h


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
        monkeypatch.setattr(h, "MINIMO_ITEMS_AVISO", 3)
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
