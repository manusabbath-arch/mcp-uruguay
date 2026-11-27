"""Corre las herramientas contra las fuentes reales y guarda la respuesta completa de cada una.

    uv run --quiet --with-editable . python scripts/sonda.py --salida sonda.json

`scripts/humo.py` prueba que respondan; éste guarda **qué** responden. Es la materia prima de un
documento: sin el payload completo, una tabla de «qué puede responder el servidor» es una lista de
deseos. Tarda minutos (la primera corrida de clima baja 57 archivos de INIA).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import anyio  # noqa: E402
from humo import LLAMADAS  # noqa: E402
from mcp import Client, StdioServerParameters  # noqa: E402
from mcp.types import TextContent  # noqa: E402

from mcp_uruguay.servidor import servidor  # noqa: E402


def _textos(resultado) -> list[str]:
    """El texto de la respuesta, que es donde vienen los avisos del lector."""
    return [bloque.text for bloque in resultado.content if isinstance(bloque, TextContent)]


async def main(salida: Path, herramientas: list[str], stdio: bool) -> int:
    registros = []
    transporte = StdioServerParameters(command=sys.executable, args=["-m", "mcp_uruguay"]) if stdio else servidor
    async with Client(transporte) as c:
        for nombre, args in LLAMADAS:
            if herramientas and nombre not in herramientas:
                continue
            t0 = time.time()
            try:
                r = await c.call_tool(nombre, args)
                registros.append(
                    {
                        "herramienta": nombre,
                        "args": args,
                        "segundos": round(time.time() - t0, 2),
                        "error": bool(r.is_error),
                        "texto": None if r.is_error else _textos(r),
                        "datos": None if r.is_error else r.structured_content,
                    }
                )
            except Exception as e:  # noqa: BLE001
                registros.append(
                    {
                        "herramienta": nombre,
                        "args": args,
                        "segundos": round(time.time() - t0, 2),
                        "error": True,
                        "excepcion": repr(e),
                    }
                )
            ultimo = registros[-1]
            estado = "ERROR" if ultimo["error"] else "OK"
            print(f"{estado:5s} {ultimo['segundos']:6.1f}s {nombre}", flush=True)
    salida.write_text(json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8")
    print("escrito", salida, "·", len(registros), "herramientas")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Sonda de las herramientas contra las fuentes reales.")
    ap.add_argument("--salida", type=Path, default=Path("sonda.json"))
    ap.add_argument(
        "--herramienta",
        action="append",
        default=[],
        choices=[nombre for nombre, _ in LLAMADAS],
        help="limita la sonda a las herramientas indicadas (repetible)",
    )
    ap.add_argument("--stdio", action="store_true", help="inicia el paquete como un proceso MCP por stdio")
    opciones = ap.parse_args()
    sys.exit(anyio.run(main, opciones.salida, opciones.herramienta, opciones.stdio))
