"""La evaluación de exactitud, sin red ni API: el verificador, el conjunto de preguntas y el ciclo del agente."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
import evaluar  # noqa: E402

pytestmark = pytest.mark.anyio


# --- El conjunto de preguntas ------------------------------------------------------------------------


def test_cada_pregunta_esta_completa_y_las_herramientas_existen():
    import anyio
    from mcp import Client

    from mcp_uruguay.servidor import servidor

    async def nombres():
        async with Client(servidor) as c:
            return {t.name for t in (await c.list_tools()).tools}

    reales = anyio.run(nombres)
    preguntas = evaluar.cargar()
    assert len({p["id"] for p in preguntas}) == len(preguntas), "ids repetidos"
    for p in preguntas:
        assert p["conjunto"] in ("desarrollo", "reservado"), p["id"]
        assert p["fuente"]["organismo"] and p["fuente"]["cita"], p["id"]
        assert set(p["herramientas_esperadas"]) <= reales, p["id"]
        if p["tipo"] == "numero":
            assert isinstance(p["esperado"], (int, float)) and p["tolerancia"] >= 0, p["id"]
        elif p["tipo"] == "texto":
            assert p["patron"], p["id"]
        else:
            assert p["tipo"] == "comportamiento" and p["debe_mencionar"], p["id"]


def test_hay_preguntas_reservadas_de_cada_lado():
    """Sin un conjunto que no se mira al ajustar, la evaluación mide cuánto se ajustó, no cuánto acierta."""
    assert evaluar.cargar("desarrollo") and evaluar.cargar("reservado")


# --- El verificador ----------------------------------------------------------------------------------

NUM = {"id": "n", "tipo": "numero", "esperado": 1101296, "tolerancia": 0}
PCT = {"id": "p", "tipo": "numero", "esperado": 49.84, "tolerancia": 0.05}


@pytest.mark.parametrize(
    "texto,valor",
    [
        ("blabla\nRESPUESTA: 1101296", 1101296),
        ("RESPUESTA: 1.101.296 votos", 1101296),
        ("RESPUESTA: 1,101,296", 1101296),
        ("**RESPUESTA:** 49,84 %", 49.84),
        ("RESPUESTA: 136.195", 136.195),  # un solo grupo: vale el punto decimal pedido
    ],
)
def test_numeros_en_los_formatos_que_escriben_los_modelos(texto, valor):
    assert evaluar.numero(evaluar.linea_respuesta(texto)) == pytest.approx(valor)


def test_numero_dentro_y_fuera_de_la_tolerancia():
    assert evaluar.verificar(PCT, "RESPUESTA: 49.8")["correcta"]
    assert not evaluar.verificar(PCT, "RESPUESTA: 49.7")["correcta"]
    assert evaluar.verificar(NUM, "RESPUESTA: 1101296")["correcta"]
    assert not evaluar.verificar(NUM, "RESPUESTA: 1101297")["correcta"]


def test_vale_la_ultima_linea_de_respuesta():
    assert evaluar.verificar(PCT, "RESPUESTA: 10\n...corrijo...\nRESPUESTA: 49.84")["correcta"]


def test_sin_linea_de_respuesta_o_sin_dato_no_acierta():
    assert evaluar.verificar(PCT, "fue 49,84%")["motivo"] == "no escribió la línea RESPUESTA:"
    assert not evaluar.verificar(PCT, "RESPUESTA: SIN DATO")["correcta"]


def test_texto_sin_tildes_ni_mayusculas():
    p = {"id": "t", "tipo": "texto", "patron": "2020-07-09"}
    assert evaluar.verificar(p, "RESPUESTA: 2020-07-09")["correcta"]
    assert not evaluar.verificar(p, "RESPUESTA: 2020-07-14")["correcta"]


def test_comportamiento_mira_la_respuesta_entera():
    p = next(q for q in evaluar.cargar() if q["id"] == "trampa-dolar-domingo")
    assert evaluar.verificar(p, "Ese día fue domingo: el BCU no publica.\nRESPUESTA: SIN DATO")["correcta"]
    assert not evaluar.verificar(p, "RESPUESTA: 41.2")["correcta"]


def test_la_trampa_de_la_turbidez_pide_hablar_de_los_limites_de_deteccion():
    p = next(q for q in evaluar.cargar() if q["id"] == "trampa-turbidez-promedio")
    assert evaluar.verificar(p, "Muchos valores son límites de detección (<0,2).\nRESPUESTA: SIN DATO")["correcta"]
    assert not evaluar.verificar(p, "RESPUESTA: 0.31")["correcta"]


# --- El ciclo del agente, con un cliente falso -------------------------------------------------------


def _respuesta(contenido, stop, entrada=100, salida=20):
    return NS(content=contenido, stop_reason=stop, usage=NS(input_tokens=entrada, output_tokens=salida))


class ClienteFalso:
    """Imita `AsyncAnthropic().messages.create`: devuelve las respuestas en orden y guarda los pedidos."""

    def __init__(self, respuestas):
        self.respuestas, self.pedidos = list(respuestas), []
        self.messages = self

    async def create(self, **kwargs):
        # Una copia de la lista: el agente la sigue agrandando después de cada pedido.
        self.pedidos.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.respuestas.pop(0)


async def test_el_agente_llama_a_la_herramienta_real_y_cuenta_todo():
    from mcp import Client

    from mcp_uruguay.servidor import servidor

    llamada = NS(type="tool_use", id="t1", name="validar_documento", input={"numero": "1.234.567-2", "tipo": "ci"})
    cliente = ClienteFalso(
        [
            _respuesta([llamada], "tool_use"),
            _respuesta([NS(type="text", text="Es válida.\nRESPUESTA: valida")], "end_turn"),
        ]
    )
    async with Client(servidor) as sesion:
        herramientas = await evaluar.herramientas_de(sesion)
        texto, m = await evaluar.preguntar(cliente, "¿es válida?", sesion=sesion, herramientas=herramientas)
    assert evaluar.linea_respuesta(texto) == "valida"
    assert (m["llamadas"], m["errores_herramienta"], m["turnos"], m["motivo_fin"]) == (
        ["validar_documento"],
        0,
        2,
        "end_turn",
    )
    assert (m["tokens_entrada"], m["tokens_salida"]) == (200, 40)
    # El resultado real de la herramienta vuelve al modelo, en un solo mensaje de usuario
    (resultado,) = cliente.pedidos[1]["messages"][-1]["content"]
    assert resultado["tool_use_id"] == "t1" and '"valido": true' in resultado["content"]
    assert {t["name"] for t in cliente.pedidos[0]["tools"]} >= {"validar_documento", "calidad_agua"}
    assert cliente.pedidos[0]["output_config"] == {"effort": "medium"}


async def test_un_error_de_la_herramienta_se_cuenta_y_el_agente_lo_ve():
    from mcp import Client

    from mcp_uruguay.servidor import servidor

    llamada = NS(type="tool_use", id="t1", name="semana", input={"fecha": "no-es-fecha"})
    cliente = ClienteFalso(
        [_respuesta([llamada], "tool_use"), _respuesta([NS(type="text", text="RESPUESTA: SIN DATO")], "end_turn")]
    )
    async with Client(servidor) as sesion:
        _, m = await evaluar.preguntar(cliente, "?", sesion=sesion, herramientas=await evaluar.herramientas_de(sesion))
    assert m["errores_herramienta"] == 1
    assert cliente.pedidos[1]["messages"][-1]["content"][0]["is_error"] is True


async def test_sin_servidor_no_hay_herramientas():
    cliente = ClienteFalso([_respuesta([NS(type="text", text="RESPUESTA: 49.8")], "end_turn")])
    texto, m = await evaluar.preguntar(cliente, "?")
    assert "tools" not in cliente.pedidos[0] and m["llamadas"] == []


async def test_la_corrida_marca_el_refusal_como_fallo():
    cliente = ClienteFalso([_respuesta([], "refusal")])
    p = next(q for q in evaluar.cargar() if q["id"] == "ipca-brasil-2024")
    (fila,) = await evaluar.correr(cliente, [p], ["sin"])
    assert (fila["correcta"], fila["motivo_fin"]) == (False, "refusal")
    assert "| sin | **todas** | 0/1 (0%)" in evaluar.resumen([fila])


# --- Trazas, presupuesto y costo --------------------------------------------------------------------


async def test_cada_paso_queda_en_la_traza():
    from mcp import Client

    from mcp_uruguay.servidor import servidor

    ok = NS(type="tool_use", id="t1", name="validar_documento", input={"numero": "1.234.567-2", "tipo": "ci"})
    mal = NS(type="tool_use", id="t2", name="semana", input={"fecha": "no-es-fecha"})
    cliente = ClienteFalso(
        [
            _respuesta([ok, mal], "tool_use", entrada=300, salida=50),
            _respuesta([NS(type="text", text="RESPUESTA: valida")], "end_turn", entrada=400, salida=10),
        ]
    )
    async with Client(servidor) as sesion:
        _, m = await evaluar.preguntar(cliente, "?", sesion=sesion, herramientas=await evaluar.herramientas_de(sesion))
    pasos = m["pasos"]
    assert [(p["turno"], p["herramienta"], p["error"]) for p in pasos] == [
        (1, "validar_documento", False),
        (1, "semana", True),
    ]
    assert pasos[0]["argumentos"] == {"numero": "1.234.567-2", "tipo": "ci"}
    assert all(p["segundos"] >= 0 and p["bytes_resultado"] > 0 for p in pasos)
    assert [(t["turno"], t["tokens_entrada"], t["tokens_salida"]) for t in m["turnos_detalle"]] == [
        (1, 300, 50),
        (2, 400, 10),
    ]


async def test_el_presupuesto_corta_antes_del_turno_siguiente():
    llamada = NS(type="tool_use", id="t1", name="semana", input={"fecha": "2026-01-01"})
    cliente = ClienteFalso([_respuesta([llamada], "tool_use", entrada=900, salida=200)])
    texto, m = await evaluar.preguntar(cliente, "?", presupuesto_tokens=1000)
    assert (m["motivo_fin"], m["presupuesto_agotado"], m["turnos"]) == ("presupuesto_agotado", True, 1)
    assert len(cliente.pedidos) == 1 and m["pasos"] == []


async def test_dentro_del_presupuesto_no_corta():
    cliente = ClienteFalso([_respuesta([NS(type="text", text="RESPUESTA: 1")], "end_turn", entrada=10, salida=5)])
    _, m = await evaluar.preguntar(cliente, "?", presupuesto_tokens=1000)
    assert (m["motivo_fin"], m["presupuesto_agotado"]) == ("end_turn", False)


def test_costo_con_precio_conocido_y_sin_precio():
    m = {
        "tokens_entrada": 1_000_000,
        "tokens_salida": 100_000,
        "tokens_cache_leidos": 2_000_000,
        "tokens_cache_escritos": 0,
    }
    precio = evaluar.PRECIOS["claude-opus-5-5"]
    esperado = precio["entrada"] + 0.1 * precio["salida"] + 2 * precio["cache_leido"]
    assert evaluar.costo_usd(m, "claude-opus-5-5") == pytest.approx(esperado)
    # Sin precio publicado no hay costo: nunca 0, que se leería como gratis.
    assert evaluar.costo_usd(m, "modelo-inventado") is None


def _fila(modo, correcta, costo, agotado=False):
    return {
        "modo": modo,
        "tipo": "numero",
        "correcta": correcta,
        "llamadas": [],
        "errores_herramienta": 0,
        "tokens_entrada": 10,
        "tokens_salida": 5,
        "costo_usd": costo,
        "presupuesto_agotado": agotado,
    }


def test_el_resumen_trae_costo_por_acierto():
    filas = [_fila("con", True, 0.2), _fila("con", False, 0.1, agotado=True), _fila("con", True, 0.3)]
    tabla = evaluar.resumen(filas)
    # US$ 0.60 en total, 2 aciertos -> US$ 0.30 por acierto; 1 de 3 cortadas por presupuesto
    assert "| con | **todas** | 2/3 (67%)" in tabla
    assert "| 0.2000 | 0.3000 | 1 |" in tabla


def test_el_resumen_sin_costo_dice_sin_dato():
    tabla = evaluar.resumen([_fila("sin", True, None)])
    assert "| s/d | s/d | 0 |" in tabla


# --- La confirmación contra la fuente ----------------------------------------------------------------

import confirmar  # noqa: E402


def _pregunta(id_):
    return next(q for q in evaluar.cargar() if q["id"] == id_)


@pytest.mark.parametrize(
    "id_,esperadas",
    [
        ("balotaje-2024-delgado-votos", {"1.101.296", "1,101,296", "1101296"}),
        ("balotaje-2024-orsi-pct", {"49,84", "49.84"}),
        ("ipc-argentina-2024", {"117,8", "117.8"}),
        ("ui-2025-01-01", {"6,1697", "6.1697"}),
        ("ley-19889-promulgacion", {"09/07/2020", "9/7/2020"}),
    ],
)
def test_las_formas_en_que_se_escribe_la_cifra(id_, esperadas):
    assert esperadas <= set(confirmar.formas(_pregunta(id_)))


def test_una_cifra_no_se_encuentra_dentro_de_otra():
    assert confirmar.aparece("4,83", "acumula 4,83 em 2024")
    assert not confirmar.aparece("4,83", "acumula 14,83 em 2024")
    assert not confirmar.aparece("4,83", "acumula 4,831")
    assert confirmar.aparece("4,83", "fecha o ano em 4,83.")  # el punto final de la oración no es un decimal


def test_confirma_en_html_y_si_no_esta_no_marca():
    p = _pregunta("ipca-brasil-2024")
    pagina = b"<html><script>var x=4.83</script><p>IPCA em dezembro vai a 0,52% e acumula 4,83% em 2024</p></html>"
    r = confirmar.confirmar(p, lambda url: pagina)
    assert (r["estado"], r["forma"]) == ("confirmada", "4,83")
    otra = b"<p>IPCA acumula 4,62% em 2023</p>"
    assert confirmar.confirmar(p, lambda url: otra)["estado"] == "no_aparece"


def test_prueba_las_otras_fuentes_si_la_primera_no_baja():
    p = _pregunta("nafta-super95-2025-01")

    def bajador(url):
        if "impo" in url:
            raise OSError("getaddrinfo ENOTFOUND")
        return "<p>pasó de $75,052 a $78,54 por litro</p>".encode()

    r = confirmar.confirmar(p, bajador)
    assert r["estado"] == "confirmada" and "elobservador" in r["url"]


def test_sin_red_no_confirma_nada():
    def caida(url):
        raise OSError("getaddrinfo ENOTFOUND")

    assert confirmar.confirmar(_pregunta("censo-2023-total"), caida)["estado"] == "no_se_pudo_bajar"


def test_las_de_calculo_y_las_trampas_no_se_buscan():
    assert confirmar.confirmar(_pregunta("cedula-valida"), None)["estado"] == "no_aplica"
    assert confirmar.confirmar(_pregunta("trampa-turbidez-promedio"), None)["estado"] == "no_aplica"


def test_las_respuestas_de_calculo_se_recalculan():
    """Las que dicen `via: cálculo` se comprueban acá, sin el servidor: si no, serían circulares."""
    from datetime import date

    assert date(2027, 1, 1).isocalendar()[:2] == (2026, 53)
    pesos = [2, 9, 8, 7, 6, 3, 4]
    suma = sum(int(c) * w for c, w in zip("1234567", pesos))
    assert (10 - suma % 10) % 10 == 2  # 1.234.567-2 es válida; -3 no


# --- Motor claude-cli (Claude Code headless), con eventos sintéticos ---------------------------------

import motor_claude_cli as cli  # noqa: E402

_EVENTOS = [
    (0.1, {"type": "system", "subtype": "init"}),
    (
        1.0,
        {
            "type": "assistant",
            "message": {
                "usage": {"input_tokens": 500, "output_tokens": 40},
                "content": [
                    {"type": "tool_use", "id": "a", "name": "mcp__uruguay__cotizacion", "input": {"moneda": "USD"}}
                ],
            },
        },
    ),
    (
        2.5,
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "tool_use_id": "a", "content": [{"text": "40.6"}]}]},
        },
    ),
    (
        3.0,
        {
            "type": "assistant",
            "message": {
                "usage": {"input_tokens": 600, "output_tokens": 20},
                "content": [{"type": "text", "text": "x"}],
            },
        },
    ),
    (
        3.1,
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "Vale 40.6\nRESPUESTA: 40.6",
            "total_cost_usd": 0.0123,
            "usage": {"input_tokens": 1100, "output_tokens": 60, "cache_read_input_tokens": 7000},
        },
    ),
]


def test_cli_la_traza_sale_del_stream():
    texto, m = cli.parsear_eventos(_EVENTOS)
    assert evaluar.linea_respuesta(texto) == "40.6"
    assert m["llamadas"] == ["cotizacion"]
    (paso,) = m["pasos"]
    assert (paso["turno"], paso["herramienta"], paso["argumentos"], paso["error"]) == (
        1,
        "cotizacion",
        {"moneda": "USD"},
        False,
    )
    assert paso["segundos"] == 1.5 and paso["bytes_resultado"] == 4
    assert paso["resultado"] == "40.6"  # el texto, no solo el tamaño: es lo que respalda la cifra
    assert (m["turnos"], m["motivo_fin"], m["costo_usd_cli"]) == (2, "success", 0.0123)
    assert (m["tokens_entrada"], m["tokens_salida"], m["tokens_cache_leidos"]) == (1100, 60, 7000)


def test_cli_presupuesto_corta_y_suma_los_turnos():
    _, m = cli.parsear_eventos(_EVENTOS, presupuesto_tokens=500)
    assert (m["motivo_fin"], m["presupuesto_agotado"], m["turnos"]) == ("presupuesto_agotado", True, 1)
    assert (m["tokens_entrada"], m["tokens_salida"], m["costo_usd_cli"]) == (500, 40, None)


def test_cli_un_error_de_autenticacion_no_cuenta_como_respuesta():
    ev = [(0.2, {"type": "result", "subtype": "success", "is_error": True, "result": "Failed to authenticate"})]
    _, m = cli.parsear_eventos(ev)
    assert m["motivo_fin"] == "error"


def test_cli_el_comando_aisla_al_agente():
    sin = cli.comando("SIS", con_servidor=False, modelo=None, esfuerzo=None, mcp_config=None)
    for bandera in ("--no-session-persistence", "--strict-mcp-config"):
        assert bandera in sin
    assert sin[sin.index("--tools") + 1] == "" and sin[sin.index("--setting-sources") + 1] == ""
    assert "--allowedTools" not in sin and "--mcp-config" not in sin
    con = cli.comando("SIS", con_servidor=True, modelo="m", esfuerzo="low", mcp_config=Path("/x/mcp.json"))
    assert con[con.index("--allowedTools") + 1] == "mcp__uruguay"
    assert con[con.index("--mcp-config") + 1] == str(Path("/x/mcp.json"))  # en Windows son barras invertidas
    assert con[con.index("--model") + 1] == "m" and con[con.index("--effort") + 1] == "low"


async def test_correr_con_motor_cli_usa_el_costo_del_cli():
    p = next(q for q in evaluar.cargar() if q["id"] == "ipca-brasil-2024")
    vistos = []

    def falso(pregunta, sistema, **kw):
        vistos.append(kw["con_servidor"])
        texto, m = cli.parsear_eventos(_EVENTOS)
        return texto, m

    filas = await evaluar.correr(None, [p], ["con", "sin"], motor="claude-cli", preguntar_cli=falso)
    assert vistos == [True, False]
    assert all(f["motor"] == "claude-cli" and f["costo_usd"] == 0.0123 for f in filas)
    assert "costo_usd_cli" not in filas[0]


async def test_correr_con_motor_cli_que_falla_cuenta_como_fallo():
    p = next(q for q in evaluar.cargar() if q["id"] == "ipca-brasil-2024")

    def falso(pregunta, sistema, **kw):
        return cli.parsear_eventos([(0.1, {"type": "result", "is_error": True, "result": "RESPUESTA: 4.83"})])

    (fila,) = await evaluar.correr(None, [p], ["sin"], motor="claude-cli", preguntar_cli=falso)
    assert (fila["correcta"], fila["motivo"]) == (False, "el agente no terminó (error)")


def test_cli_la_pregunta_va_despues_de_doble_guion():
    # `--allowedTools` acepta varios valores: sin `--`, la pregunta se lee como una herramienta más.
    capturado = {}

    class ProcesoFalso:
        stdout = iter([json.dumps({"type": "result", "result": "RESPUESTA: 1", "total_cost_usd": 0.0}) + "\n"])
        stderr = None

        def poll(self):
            return 0

        def wait(self):
            return 0

    def lanzar(args, **kw):
        capturado["args"] = args
        return ProcesoFalso()

    texto, _ = cli.preguntar_claude_cli("¿cuánto?", "SIS", con_servidor=True, lanzar=lanzar)
    assert capturado["args"][-2:] == ["--", "¿cuánto?"]
    assert evaluar.linea_respuesta(texto) == "1"


def test_cli_varios_eventos_del_mismo_mensaje_son_un_solo_turno():
    # Claude Code emite un evento `assistant` por bloque de contenido, con el mismo id de mensaje.
    def ev(seg, bloque, salida):
        msg = {"id": "msg_1", "usage": {"input_tokens": 2, "output_tokens": salida}, "content": [bloque]}
        return (seg, {"type": "assistant", "message": msg})

    eventos = [
        ev(1.0, {"type": "text", "text": "Busco."}, 8),
        ev(1.2, {"type": "tool_use", "id": "a", "name": "mcp__uruguay__semana", "input": {}}, 30),
        (1.5, {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "a", "content": "ok"}]}}),
    ]
    _, m = cli.parsear_eventos(eventos)
    assert m["turnos"] == 1 and len(m["turnos_detalle"]) == 1
    assert m["turnos_detalle"][0]["tokens_salida"] == 30
    assert [p["turno"] for p in m["pasos"]] == [1]


async def test_el_presupuesto_cuenta_la_cache():
    # Con caché de prompts la entrada nueva es casi cero: un tope sin la caché no cortaría nunca.
    llamada = NS(type="tool_use", id="t1", name="semana", input={"fecha": "2026-01-01"})
    r = _respuesta([llamada], "tool_use", entrada=2, salida=30)
    r.usage.cache_read_input_tokens = 11000
    cliente = ClienteFalso([r])
    _, m = await evaluar.preguntar(cliente, "?", presupuesto_tokens=10000)
    assert (m["motivo_fin"], m["presupuesto_agotado"]) == ("presupuesto_agotado", True)


def test_cli_el_presupuesto_cuenta_la_cache():
    msg = {"id": "m1", "usage": {"input_tokens": 2, "output_tokens": 30, "cache_creation_input_tokens": 11000}}
    _, m = cli.parsear_eventos(
        [(1.0, {"type": "assistant", "message": {**msg, "content": []}})], presupuesto_tokens=10000
    )
    assert m["presupuesto_agotado"] is True


def test_la_fila_dice_si_uso_la_herramienta_esperada():
    p = {"herramientas_esperadas": ["localidad"]}
    assert evaluar.uso_esperada(p, ["buscar_indicador_social", "localidad"]) is True
    assert evaluar.uso_esperada(p, ["buscar_indicador_social"]) is False
    assert evaluar.uso_esperada({"herramientas_esperadas": []}, []) is None


def test_el_resumen_muestra_el_uso_de_la_esperada():
    filas = [
        {**_fila("con", True, 0.1), "uso_esperada": True},
        {**_fila("con", False, 0.1), "uso_esperada": False},
    ]
    tabla = evaluar.resumen(filas)
    assert "usó la esperada" in tabla and "| 1/2 |" in tabla


def test_inestables_lista_las_preguntas_que_a_veces_aciertan():
    filas = [
        {"id": "a", "modo": "con", "correcta": True},
        {"id": "a", "modo": "con", "correcta": False},
        {"id": "b", "modo": "con", "correcta": True},
        {"id": "b", "modo": "con", "correcta": True},
    ]
    assert evaluar.inestables(filas) == {"con": ["a"]}


def test_un_intento_que_no_corrio_no_cuenta_como_fallo():
    filas = [
        {**_fila("con", False, None), "motivo_fin": "sin_resultado"},
        _fila("con", True, 0.1),
    ]
    tabla = evaluar.resumen(filas)
    assert "| 1/1 (100%) |" in tabla and "no corrió" in tabla
    assert evaluar.corrio({"motivo_fin": "sin_resultado"}) is False
    assert evaluar.corrio({"motivo_fin": "end_turn", "error_motor": "boom"}) is False
    assert evaluar.corrio({"motivo_fin": "end_turn"}) is True


# --- El respaldo del número en la traza (R3) ---------------------------------------------------------


def _paso(resultado=""):
    return {
        "turno": 1,
        "herramienta": "ventas_combustible",
        "argumentos": {},
        "segundos": 0.1,
        "error": False,
        "bytes_resultado": len(resultado.encode("utf-8")),
        "resultado": resultado,
    }


def test_un_numero_que_salio_de_una_herramienta_esta_respaldado():
    p = _pregunta("balotaje-2024-delgado-votos")
    texto = "Segun la Corte Electoral\nRESPUESTA: 1101296"
    assert evaluar.respaldado(p, texto, [_paso('{"votos": 1101296, "partido": "PN")}')]) is True


def test_un_numero_que_no_esta_en_la_traza_no_esta_respaldado():
    """El caso `leyes` 403: acertó el número sin haberlo leído de ninguna herramienta."""
    p = _pregunta("balotaje-2024-delgado-votos")
    texto = "RESPUESTA: 1101296"
    assert evaluar.respaldado(p, texto, [_paso('{"error": "403 Forbidden"}')]) is False


def test_el_respaldo_busca_las_formas_en_que_se_escribe_la_cifra():
    p = _pregunta("balotaje-2024-orsi-pct")
    assert evaluar.respaldado(p, "RESPUESTA: 49,84", [_paso('{"porcentaje": 49.84}')]) is True
    assert evaluar.respaldado(p, "RESPUESTA: 49.84", [_paso('"pct": 49,84')]) is True


def test_el_respaldo_no_encuentra_una_cifra_dentro_de_otra():
    p = _pregunta("balotaje-2024-orsi-pct")
    assert evaluar.respaldado(p, "RESPUESTA: 49.84", [_paso('{"porcentaje": 149.84}')]) is False


def test_el_respaldo_de_una_fecha_prueba_sus_formatos():
    p = _pregunta("ley-19889-promulgacion")
    assert evaluar.respaldado(p, "RESPUESTA: 2020-07-09", [_paso("Promulgada el 9/7/2020")]) is True


def test_una_pregunta_de_comportamiento_no_mide_respaldo():
    p = next(q for q in evaluar.cargar() if q["tipo"] == "comportamiento")
    assert evaluar.respaldado(p, "El domingo no hay cotizacion.\nRESPUESTA: SIN DATO", [_paso("{}")]) is None


def test_sin_dato_no_tiene_nada_que_respaldar():
    p = _pregunta("balotaje-2024-delgado-votos")
    assert evaluar.respaldado(p, "RESPUESTA: SIN DATO", [_paso('{"votos": 1}')]) is None


def test_contestar_sin_llamar_a_ninguna_herramienta_no_tiene_respaldo():
    p = _pregunta("balotaje-2024-delgado-votos")
    assert evaluar.respaldado(p, "RESPUESTA: 1101296", []) is False


def test_una_traza_vieja_sin_el_texto_no_se_puede_medir():
    """Las corridas guardadas antes de este campo no dicen si el número se respaldó: no se inventa."""
    p = _pregunta("balotaje-2024-delgado-votos")
    viejo = {"turno": 1, "herramienta": "x", "argumentos": {}, "segundos": 0.1, "error": False}
    assert evaluar.respaldado(p, "RESPUESTA: 1101296", [viejo]) is None


def test_el_resumen_muestra_el_respaldo_y_solo_con_servidor():
    filas = [
        {**_fila("con", True, 0.1), "respaldado": True},
        {**_fila("con", True, 0.1), "respaldado": False},
        {**_fila("con", False, 0.1), "respaldado": None},
        {**_fila("sin", True, 0.1), "respaldado": None},
    ]
    tabla = evaluar.resumen(filas)
    assert "respaldado" in tabla
    assert "| 1/2 |" in tabla  # dos mediciones, una respaldada
    assert "| sin | **todas** | 1/1 (100%)" in tabla and tabla.count("—") >= 1
