"""El manifiesto de la extensión de Claude Desktop (MCPB) dice lo mismo que el servidor."""

from __future__ import annotations

import json

from mcp_uruguay import manifiesto


def test_el_manifiesto_esta_al_dia():
    """Si falla, quedó viejo: correr `python -m mcp_uruguay.manifiesto`."""
    assert manifiesto.RUTA.exists(), "falta manifest.json: correr `python -m mcp_uruguay.manifiesto`"
    assert manifiesto.RUTA.read_text(encoding="utf-8") == manifiesto.texto()


def test_la_version_es_la_de_pyproject_y_server_json():
    m = json.loads(manifiesto.RUTA.read_text(encoding="utf-8"))
    server = json.loads((manifiesto.RAIZ / "server.json").read_text(encoding="utf-8"))
    assert m["version"] == manifiesto._version() == server["version"]


def test_corre_con_uv_y_el_punto_de_entrada_existe():
    """El tipo `uv` es el que no le pide Python instalado a quien usa Claude Desktop."""
    m = manifiesto.manifiesto()
    assert m["server"]["type"] == "uv"
    assert (manifiesto.RAIZ / m["server"]["entry_point"]).is_file()
