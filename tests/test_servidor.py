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
    "nivel_rio_ina",
    "variacion_real",
    "validar_documento",
    "geocodificar_direccion",
    "ubicar_punto",
    "localidad",
    "calidad_agua",
    "resultados_electorales",
    "compras_estado",
    "asistencia_parlamentaria",
    "leyes",
    "pedidos_de_informes",
    "proyectos_parlamento",
    "semana",
    "feriados",
    "buscar_datasets_catalogo",
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


async def test_una_descarga_cortada_vuelve_con_su_motivo(monkeypatch):
    """`IncompleteRead` no es un `OSError`: salía como «Error executing tool», sin motivo."""
    import http.client

    from mcp_uruguay import herramientas as h

    def cortada(*args, **kwargs):
        raise http.client.IncompleteRead(b"x" * 10, 5)

    monkeypatch.setattr(h, "compras_estado", cortada)
    async with Client(servidor) as c:
        r = await c.call_tool("compras_estado", {"anio": 2025})
    assert r.is_error
    texto = r.content[0].text
    assert "No se pudo consultar la fuente" in texto and "IncompleteRead" in texto
    assert "Probar de nuevo más tarde" in texto


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
    (tmp_path / ".bcu.2225_2026-10.xml.k2j4h.nuevo").write_bytes(b"a medias")  # temporal de `_temporal`
    (tmp_path / ".nuevo-xyz").mkdir()
    (tmp_path / ".nuevo-xyz" / "2225_2026-09.xml").write_bytes(b"<x/>")  # carpeta de `_refrescar_mes_bcu`
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


def test_el_servidor_valida_tls_con_el_almacen_del_sistema(monkeypatch):
    """En Windows, Python no ve las raíces que el sistema baja a demanda (pasó con OSE el 16/11/2026)."""
    import truststore

    from mcp_uruguay import servidor as modulo

    orden = []
    monkeypatch.setattr(truststore, "inject_into_ssl", lambda: orden.append("truststore"))
    monkeypatch.setattr(modulo.servidor, "run", lambda: orden.append("run"))
    modulo.main()
    assert orden == ["truststore", "run"]


async def test_una_copia_vencida_servida_lo_dice_en_la_respuesta(monkeypatch, cache_temporal):
    """M3: si no se pudo refrescar y se usó la copia vieja, la respuesta lleva `copia_vencida` y `aviso`."""
    import os
    from datetime import date, datetime

    from conftest import BcuFalso
    from uydatos import bcu

    from mcp_uruguay import cache

    monkeypatch.setattr(bcu, "descargar", BcuFalso())
    cache.bcu_serie(2225, date(2026, 8, 1), date(2026, 8, 31), hoy=date(2026, 10, 9))
    t = datetime(2026, 8, 15, 12, tzinfo=cache._zona()).timestamp()  # bajado a mitad de mes: incompleto, toca refrescar
    os.utime(cache_temporal / "bcu" / "2225_2026-08.xml", (t, t))

    def cortada(*args, **kwargs):
        raise OSError("sin red")

    monkeypatch.setattr(bcu, "descargar", cortada)
    async with Client(servidor) as c:
        r = await c.call_tool("cotizacion", {"moneda": "USD", "fecha": "2026-08-10"})
    assert not r.is_error
    datos = r.structured_content
    assert datos["copia_vencida"] is True
    assert "No se pudo refrescar" in datos["aviso"] and "2026-08-15" in datos["aviso"]
    assert datos["valor_en_pesos"] == 40.0  # el dato sigue llegando


async def test_una_respuesta_normal_no_trae_aviso(monkeypatch):
    from conftest import BcuFalso
    from uydatos import bcu

    monkeypatch.setattr(bcu, "descargar", BcuFalso())
    async with Client(servidor) as c:
        r = await c.call_tool("cotizacion", {"moneda": "USD", "fecha": "2026-08-10"})
    assert "copia_vencida" not in r.structured_content and "aviso" not in r.structured_content


async def test_el_contexto_no_aparece_en_el_esquema_de_entrada():
    """El `ctx` del latido lo inyecta el SDK: no es un argumento que el cliente tenga que pasar."""
    async with Client(servidor) as c:
        herramientas = (await c.list_tools()).tools
    assert herramientas
    for t in herramientas:
        assert "ctx" not in t.input_schema.get("properties", {}), t.name
        assert "ctx" not in t.input_schema.get("required", []), t.name


def _lenta(monkeypatch, segundos):
    """`validar_documento` real, pero que tarda: lo que `clima` o `leyes` hacen con la caché fría."""
    import time

    from mcp_uruguay import herramientas as h

    real = h.validar_documento

    def con_espera(*args, **kwargs):
        time.sleep(segundos)
        return real(*args, **kwargs)

    monkeypatch.setattr(h, "validar_documento", con_espera)


async def test_una_herramienta_lenta_avisa_que_sigue_trabajando(monkeypatch):
    """M7: con la caché fría una primera llamada tarda de 40 a 75 s; sin avisos no se distingue de una colgada."""
    from mcp_uruguay import servidor as modulo

    _lenta(monkeypatch, 0.5)
    monkeypatch.setattr(modulo, "LATIDO_S", 0.1)
    avisos = []

    async def al_progreso(progreso, total, mensaje):
        avisos.append((progreso, mensaje))

    async with Client(servidor) as c:
        r = await c.call_tool(
            "validar_documento", {"numero": "1.234.567-2", "tipo": "ci"}, progress_callback=al_progreso
        )
    assert not r.is_error
    assert len(avisos) >= 2
    assert [a[0] for a in avisos] == sorted(a[0] for a in avisos)  # el progreso solo avanza
    assert all("validar_documento" in a[1] for a in avisos)


async def test_una_herramienta_rapida_no_manda_avisos(monkeypatch):
    from mcp_uruguay import servidor as modulo

    monkeypatch.setattr(modulo, "LATIDO_S", 5.0)
    avisos = []

    async def al_progreso(progreso, total, mensaje):
        avisos.append(progreso)

    async with Client(servidor) as c:
        r = await c.call_tool(
            "validar_documento", {"numero": "1.234.567-2", "tipo": "ci"}, progress_callback=al_progreso
        )
    assert not r.is_error and avisos == []


async def test_sin_pedir_progreso_la_herramienta_lenta_responde_igual(monkeypatch):
    from mcp_uruguay import servidor as modulo

    _lenta(monkeypatch, 0.3)
    monkeypatch.setattr(modulo, "LATIDO_S", 0.05)
    async with Client(servidor) as c:
        r = await c.call_tool("validar_documento", {"numero": "1.234.567-2", "tipo": "ci"})
    assert not r.is_error and r.structured_content["valido"] is True


async def test_un_error_de_una_herramienta_lenta_sigue_saliendo_con_su_motivo(monkeypatch):
    """El latido no puede tragarse ni envolver el error: sigue siendo un `ToolError` con el motivo."""
    import time

    from mcp_uruguay import herramientas as h
    from mcp_uruguay import servidor as modulo

    def lenta_y_rota(*args, **kwargs):
        time.sleep(0.3)
        raise ValueError("producto inexistente")

    monkeypatch.setattr(h, "compras_estado", lenta_y_rota)
    monkeypatch.setattr(modulo, "LATIDO_S", 0.05)
    async with Client(servidor) as c:
        r = await c.call_tool("compras_estado", {"anio": 2025})
    assert r.is_error and "producto inexistente" in r.content[0].text


async def test_la_respuesta_lleva_el_sha256_de_la_copia_que_la_respalda(monkeypatch, tmp_path):
    """R2: con la copia y su hash, un número se puede verificar contra los bytes que leyó el servidor."""
    import hashlib

    monkeypatch.setenv("MCP_URUGUAY_CACHE", str(tmp_path))
    csv = "\ufeff\ufeffAño;Mes;Producto;Unidad;Valor\n2026;7;SUPER 95 *;75,10;$/lt\n"
    (tmp_path / "ancap.csv").write_text(csv, encoding="utf-8-sig")
    async with Client(servidor) as c:
        r = await c.call_tool("combustible_ancap", {"producto": "SUPER 95 *"})
    assert not r.is_error
    (copia,) = r.structured_content["procedencia"]
    assert copia["archivo"] == "ancap.csv"
    assert copia["sha256"] == hashlib.sha256((tmp_path / "ancap.csv").read_bytes()).hexdigest()
    assert copia["bytes"] == (tmp_path / "ancap.csv").stat().st_size


async def test_una_herramienta_sin_cache_no_lleva_procedencia():
    """La geocodificación no lee copias del disco: un bloque vacío sería ruido en cada respuesta."""
    async with Client(servidor) as c:
        r = await c.call_tool("validar_documento", {"numero": "1.234.567-2", "tipo": "ci"})
    assert not r.is_error and "procedencia" not in r.structured_content


async def test_los_esquemas_declarados_anuncian_la_procedencia():
    """El SDK descarta las claves que el esquema no declara: sin esto el campo no llegaría al cliente."""
    async with Client(servidor) as c:
        esquemas = {t.name: t.output_schema or {} for t in (await c.list_tools()).tools}
    con_cache = [
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
        "nivel_rio_ina",
        "calidad_agua",
        "variacion_real",
        "ubicar_punto",
        "localidad",
        "resultados_electorales",
        "compras_estado",
        "asistencia_parlamentaria",
        "pedidos_de_informes",
        "leyes",
        "proyectos_parlamento",
        "indicador_social",
        "buscar_indicador_social",
    ]
    sin_procedencia = sorted(n for n in con_cache if "procedencia" not in esquemas[n].get("properties", {}))
    assert not sin_procedencia, f"estos esquemas no declaran procedencia: {sin_procedencia}"
    assert "procedencia" not in esquemas["validar_documento"]["properties"]


def test_la_copia_vencida_no_borra_el_aviso_propio_de_la_herramienta():
    """`compras_estado` trae su propio `aviso` (un ítem domina el total). Si además se sirvió una
    copia vencida, la respuesta tiene que conservar los dos: antes el de la copia pisaba al otro."""
    from mcp_uruguay.servidor import _con_aviso_de_copia

    propio = "Atención: un solo ítem es el 28.7% del total."
    r = _con_aviso_de_copia({"total": 1, "aviso": propio}, ["2026-10-11T18:49-03:00"])
    assert r["copia_vencida"] is True
    assert propio in r["aviso"]
    assert "No se pudo refrescar" in r["aviso"] and "2026-10-11T18:49-03:00" in r["aviso"]


def test_un_aviso_propio_vacio_no_deja_separadores_sueltos():
    from mcp_uruguay.servidor import _con_aviso_de_copia

    r = _con_aviso_de_copia({"aviso": ""}, ["2026-10-11T18:49-03:00"])
    assert r["aviso"].startswith("No se pudo refrescar")
