"""Las definiciones de herramientas viajan en cada turno: su tamaño es un costo fijo por pedido.

Si este test falla porque creció a propósito, subir el tope en el mismo commit y decir por qué en el
mensaje. Si bajó, bajarlo: el trinquete solo se mueve con intención.
"""

from __future__ import annotations

import json

import anyio
from mcp import Client

from mcp_uruguay.servidor import servidor

TOPE_CARACTERES = 20_650  # 2026-11-26: 19.849 + 105 de `localidad` sin argumentos (total del país)
TOPE_HERRAMIENTAS = 32


async def _definiciones():
    async with Client(servidor) as s:
        return (await s.list_tools()).tools


def test_las_definiciones_no_crecen_sin_decidirlo():
    tools = anyio.run(_definiciones)
    tamano = sum(len(t.description or "") + len(json.dumps(t.input_schema)) for t in tools)
    assert len(tools) <= TOPE_HERRAMIENTAS, f"{len(tools)} herramientas (tope {TOPE_HERRAMIENTAS})"
    assert tamano <= TOPE_CARACTERES, f"{tamano} caracteres de definiciones (tope {TOPE_CARACTERES})"


def test_las_descripciones_viajan_sin_la_sangria_del_docstring():
    """Antes de Python 3.13 el docstring conserva la sangría del código: 360 espacios de más por turno
    en 31 herramientas (medido el 2026-11-21: 11.140 caracteres en 3.11 contra 10.780 en 3.13)."""
    tools = anyio.run(_definiciones)
    con_sangria = [t.name for t in tools if any(linea.startswith(" ") for linea in (t.description or "").splitlines())]
    assert not con_sangria, con_sangria
