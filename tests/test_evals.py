"""La evaluación de exactitud, sin red ni API: el verificador, el conjunto de preguntas y el ciclo del agente."""

from __future__ import annotations

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
