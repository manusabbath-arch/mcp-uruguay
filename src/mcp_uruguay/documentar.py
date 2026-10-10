"""Genera `docs/herramientas.md` a partir del servidor, para que la lista no se desincronice.

La lista de herramientas de un servidor MCP es su contrato con quien lo usa: un documento que
cita herramientas que ya no existen es peor que no tener documento. Este archivo NO se escribe a
mano: se genera con `python -m mcp_uruguay.documentar`, y hay un test que falla si quedo viejo.

La descripcion pasa por `inspect.cleandoc`: desde Python 3.13 el compilador ya le saca la sangria a
los docstrings y antes no, asi que sin normalizar el documento cambiaba segun la version de Python
con que se generara (paso en la 0.8.0: generado en 3.14, el CI en 3.10 a 3.12 fallaba).
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import anyio
from mcp import Client

from mcp_uruguay.servidor import servidor

RUTA = Path(__file__).resolve().parents[2] / "docs" / "herramientas.md"

CABECERA = """# Las herramientas del servidor

**Archivo generado. No se edita a mano**: se regenera con
`python -m mcp_uruguay.documentar`, y `tests/test_docs.py` falla si quedo viejo.
"""


def _tabla(esquema: dict) -> str:
    props = (esquema or {}).get("properties") or {}
    requeridos = set((esquema or {}).get("required") or [])
    if not props:
        return "_Sin parametros._"
    filas = ["| parametro | tipo | obligatorio |", "|---|---|---|"]
    for nombre, dato in props.items():
        tipo = dato.get("type") or " | ".join(t.get("type", "?") for t in dato.get("anyOf", []))
        filas.append(f"| `{nombre}` | `{tipo or '?'}` | {'si' if nombre in requeridos else 'no'} |")
    return "\n".join(filas)


async def markdown() -> str:
    """El markdown completo, tal como quedaria en disco."""
    async with Client(servidor) as c:
        herramientas = (await c.list_tools()).tools
    partes = [CABECERA]
    for t in sorted(herramientas, key=lambda x: x.name):
        descripcion = inspect.cleandoc(t.description or "")
        partes.append(f"\n## `{t.name}` — {t.title or ''}\n\n{descripcion}\n\n{_tabla(t.input_schema)}")
    return "\n".join(partes).rstrip() + "\n"


def escribir(ruta: Path = RUTA) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(anyio.run(markdown), encoding="utf-8")
    return ruta


def main() -> int:
    print(escribir())
    return 0


if __name__ == "__main__":
    sys.exit(main())
