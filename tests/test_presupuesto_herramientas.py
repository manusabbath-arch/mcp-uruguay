"""Las definiciones de herramientas viajan en cada turno: su tamaño es un costo fijo por pedido.

Si este test falla porque creció a propósito, subir el tope en el mismo commit y decir por qué en el
mensaje. Si bajó, bajarlo: el trinquete solo se mueve con intención.
"""

from __future__ import annotations

import json

import anyio
from mcp import Client

from mcp_uruguay.servidor import servidor

TOPE_CARACTERES = 19_713  # medido el 2026-11-21: 31 herramientas, descripción + input_schema
TOPE_HERRAMIENTAS = 31


async def _definiciones():
    async with Client(servidor) as s:
        return (await s.list_tools()).tools


def test_las_definiciones_no_crecen_sin_decidirlo():
    tools = anyio.run(_definiciones)
    tamano = sum(len(t.description or "") + len(json.dumps(t.input_schema)) for t in tools)
    assert len(tools) <= TOPE_HERRAMIENTAS, f"{len(tools)} herramientas (tope {TOPE_HERRAMIENTAS})"
    assert tamano <= TOPE_CARACTERES, f"{tamano} caracteres de definiciones (tope {TOPE_CARACTERES})"
