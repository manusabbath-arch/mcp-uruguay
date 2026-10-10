"""El servidor de punta a punta, con un cliente MCP real conectado en el mismo proceso."""

from __future__ import annotations

import pytest
from mcp import Client

from mcp_uruguay.servidor import servidor

pytestmark = pytest.mark.anyio

ESPERADAS = {
    "cotizacion",
    "cotizacion_mensual",
    "pesos_constantes",
    "ipc_argentina",
    "ipca_brasil",
    "combustible_ancap",
    "clima_salto",
    "clima_tendencia",
    "estaciones_cercanas",
    "validar_documento",
    "geocodificar_direccion",
    "semana",
    "recursos_catalogo",
    "diagnostico",
}


async def test_publica_las_herramientas_declaradas():
    async with Client(servidor) as c:
        herramientas = (await c.list_tools()).tools
    assert {t.name for t in herramientas} == ESPERADAS
    assert all(t.description for t in herramientas)


async def test_todas_son_de_solo_lectura():
    async with Client(servidor) as c:
        herramientas = (await c.list_tools()).tools
    assert all(t.annotations and t.annotations.read_only_hint for t in herramientas)
    assert not any(t.annotations.destructive_hint for t in herramientas)


async def test_una_llamada_devuelve_datos_estructurados():
    async with Client(servidor) as c:
        r = await c.call_tool("validar_documento", {"numero": "1.234.567-2", "tipo": "ci"})
    assert not r.is_error
    assert r.structured_content["valido"] is True


async def test_un_error_vuelve_como_error_con_el_motivo():
    async with Client(servidor) as c:
        r = await c.call_tool("semana", {"fecha": "09/10/2026"})
    assert r.is_error
    assert "AAAA-MM-DD" in r.content[0].text


async def test_el_esquema_de_salida_declara_los_campos():
    async with Client(servidor) as c:
        herramientas = {t.name: t for t in (await c.list_tools()).tools}
    campos = set(herramientas["semana"].output_schema["properties"])
    assert {"etiqueta", "desde", "hasta"} <= campos
    assert set(herramientas["validar_documento"].output_schema["properties"]) >= {"tipo", "valido"}


async def test_la_respuesta_no_se_recorta_a_lo_declarado():
    async with Client(servidor) as c:
        r = await c.call_tool("semana", {"fecha": "2026-10-09"})
    assert not r.is_error
    assert set(r.structured_content) >= {"etiqueta", "etiqueta_con_anio", "desde", "hasta", "de_total", "nota"}


async def test_diagnostico_sin_cache_no_falla(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_URUGUAY_CACHE", str(tmp_path))
    async with Client(servidor) as c:
        r = await c.call_tool("diagnostico", {})
    assert not r.is_error
    assert r.structured_content["archivos"] == []


async def test_diagnostico_muestra_lo_que_hay_y_de_cuando(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_URUGUAY_CACHE", str(tmp_path))
    (tmp_path / "bcu").mkdir()
    (tmp_path / "bcu" / "2225_2026-10.xml").write_bytes(b"<x/>")
    (tmp_path / "a-medio.nuevo").write_bytes(b"a medias")
    async with Client(servidor) as c:
        r = await c.call_tool("diagnostico", {})
    assert not r.is_error
    archivos = [a["archivo"] for a in r.structured_content["archivos"]]
    assert archivos == ["bcu/2225_2026-10.xml"]  # el .nuevo no cuenta: es una descarga en curso
    (uno,) = r.structured_content["archivos"]
    assert uno["bytes"] == 4 and uno["bajado"]
