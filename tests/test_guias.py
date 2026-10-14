"""Los prompts y los recursos: nombran herramientas que existen y se pueden leer de punta a punta."""

from __future__ import annotations

import pytest
from mcp import Client

from mcp_uruguay import guias
from mcp_uruguay.servidor import servidor

pytestmark = pytest.mark.anyio


async def _herramientas() -> set[str]:
    async with Client(servidor) as cliente:
        return {t.name for t in (await cliente.list_tools()).tools}


async def test_cada_herramienta_tiene_su_trampa_y_ninguna_sobra():
    reales = await _herramientas()
    assert set(guias.TRAMPAS) == reales


# Qué herramientas debe nombrar cada flujo (y con qué argumentos se pide).
FLUJOS = {
    "combustible_en_pesos_constantes": (
        {},
        {"combustible_ancap", "pesos_constantes", "variacion_real", "paridad_combustibles", "ventas_combustible"},
    ),
    "clima_de_salto": ({"desde": "2026-01-01", "hasta": "2026-01-31"}, {"clima", "observaciones_inumet"}),
    "el_rio_en_salto": ({}, {"nivel_rio_comparado", "nivel_rio"}),
    "compras_del_estado": ({"anio": 2025, "producto": "yerba"}, {"compras_estado"}),
    "real_o_nominal": (
        {"monto_inicial": 100.0, "mes_inicial": "2025-01", "monto_final": 110.0, "mes_final": "2026-01"},
        {"variacion_real"},
    ),
}


def test_hay_un_caso_por_cada_flujo():
    assert set(FLUJOS) == set(guias.PROMPTS)


@pytest.mark.parametrize("nombre", sorted(FLUJOS))
async def test_un_flujo_nombra_las_herramientas_esperadas_y_existen(nombre):
    argumentos, esperadas = FLUJOS[nombre]
    texto = guias.PROMPTS[nombre][0](**argumentos)
    reales = await _herramientas()
    assert esperadas <= reales
    for herramienta in esperadas:
        assert f"`{herramienta}`" in texto, f"{nombre} no nombra {herramienta}"


async def test_el_cliente_ve_los_prompts_y_los_recursos():
    async with Client(servidor) as cliente:
        prompts = {p.name for p in (await cliente.list_prompts()).prompts}
        recursos = {str(r.uri) for r in (await cliente.list_resources()).resources}
    assert prompts == set(guias.PROMPTS)
    assert recursos == set(guias.RECURSOS)


async def test_un_prompt_se_puede_pedir_con_sus_argumentos():
    async with Client(servidor) as cliente:
        r = await cliente.get_prompt("compras_del_estado", {"anio": "2025", "producto": "arroz"})
    texto = r.messages[0].content.text
    assert "arroz" in texto and "2025" in texto and "compras_estado" in texto


@pytest.mark.parametrize("uri", sorted(guias.RECURSOS))
async def test_un_recurso_se_puede_leer_y_no_esta_vacio(uri):
    async with Client(servidor) as cliente:
        r = await cliente.read_resource(uri)
    assert r.contents[0].text.strip()


async def test_el_recurso_de_fuentes_trae_todas_las_fuentes_del_servidor():
    async with Client(servidor) as cliente:
        texto = (await cliente.read_resource("uru://fuentes")).contents[0].text
    for linea in (v for k, v in vars(guias.h).items() if k.startswith("FUENTE_") and isinstance(v, str)):
        assert linea in texto
