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
    "ventas_combustible",
    "paridad_combustibles",
    "clima",
    "observaciones_inumet",
    "estaciones_cercanas",
    "nivel_rio",
    "nivel_rio_comparado",
    "variacion_real",
    "validar_documento",
    "geocodificar_direccion",
    "ubicar_punto",
    "localidad",
    "resultados_electorales",
    "compras_estado",
    "asistencia_parlamentaria",
    "leyes",
    "pedidos_de_informes",
    "proyectos_parlamento",
    "semana",
    "recursos_catalogo",
    "buscar_indicador_social",
    "indicador_social",
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


def _rechazo(codigo: int) -> OSError:
    """Un error de red como los arma `uydatos.red`: un `OSError` con el `HTTPError` de causa."""
    import urllib.error

    causa = urllib.error.HTTPError("https://fuente.example/x.csv", codigo, "Forbidden", None, None)
    error = OSError(f"https://fuente.example/x.csv: el servidor respondio {codigo} Forbidden")
    error.__cause__ = causa
    return error


def test_un_4xx_no_manda_a_reintentar_y_un_corte_si():
    from mcp_uruguay.servidor import motivo_de_red

    rechazo = motivo_de_red("clima", _rechazo(403))
    assert "No se arregla reintentando" in rechazo and "más tarde" not in rechazo
    assert "Estado conocido" not in rechazo  # clima no está en la lista de caídas
    corte = motivo_de_red("clima", OSError("timed out"))
    assert "Probar de nuevo más tarde" in corte
    assert "Probar de nuevo más tarde" in motivo_de_red("clima", _rechazo(503))


async def test_una_fuente_caida_conocida_lo_dice_en_el_error(monkeypatch):
    from mcp_uruguay import guias
    from mcp_uruguay import herramientas as h

    def bloqueada(*args, **kwargs):
        raise _rechazo(403)

    monkeypatch.setattr(h, "leyes", bloqueada)
    async with Client(servidor) as c:
        r = await c.call_tool("leyes", {"buscar": "riego"})
    assert r.is_error
    texto = r.content[0].text
    assert "403" in texto and "No se arregla reintentando" in texto
    assert guias.CAIDAS["leyes"] in texto


async def test_el_esquema_de_salida_declara_los_campos():
    async with Client(servidor) as c:
        herramientas = {t.name: t for t in (await c.list_tools()).tools}
    campos = set(herramientas["semana"].output_schema["properties"])
    assert {"etiqueta", "desde", "hasta"} <= campos
    assert set(herramientas["validar_documento"].output_schema["properties"]) >= {"tipo", "valido"}


async def test_ninguna_herramienta_publica_un_esquema_vacio():
    """Si el modelo no sabe que campos devuelve una herramienta, los inventa.

    Con la anotacion de retorno en `dict[str, Any]` el SDK publica un esquema vacio y quien llama
    queda adivinando los nombres. Todas declaran su forma (un objeto con `properties`, o un array
    con `items`): ninguna puede volver a quedar muda.
    """
    async with Client(servidor) as c:
        herramientas = (await c.list_tools()).tools
    assert len(herramientas) == len(ESPERADAS)
    vacias = [
        t.name
        for t in herramientas
        if not ((t.output_schema or {}).get("properties") or (t.output_schema or {}).get("items"))
    ]
    assert not vacias, f"estas herramientas no declaran su salida: {vacias}"


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


@pytest.mark.red
async def test_clima_sin_fechas_no_rompe():
    """Sale a internet: baja la serie de INIA (unos 57 archivos). Por eso va con `-m red`."""
    async with Client(servidor) as c:
        r = await c.call_tool("clima", {})
    # no se afirma el valor (depende de internet): se afirma que contesta y que no explota
    assert not r.is_error or "No se pudo consultar" in r.content[0].text


async def test_clima_con_una_sola_fecha_lo_dice():
    async with Client(servidor) as c:
        r = await c.call_tool("clima", {"desde": "2026-01-01"})
    assert r.is_error
    assert "no se adivina" in r.content[0].text.lower()
