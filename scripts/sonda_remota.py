"""Comprueba el piloto HTTP con una consulta estable y emite métricas sin datos."""

from __future__ import annotations

import argparse
import json
import sys
import time

import anyio
from mcp import Client

ESPERADAS = {"buscar_datasets_catalogo", "recursos_catalogo", "clima", "nivel_rio", "calidad_agua"}


async def medir(url: str) -> int:
    inicio = time.monotonic()
    try:
        with anyio.fail_after(45):
            async with Client(url) as cliente:
                nombres = {t.name for t in (await cliente.list_tools()).tools}
                if nombres != ESPERADAS:
                    raise RuntimeError("catalogo inesperado")
                r = await cliente.call_tool(
                    "nivel_rio", {"estacion": "Salto", "desde": "2026-09-01", "hasta": "2026-09-03"}
                )
                datos = r.structured_content
                if r.is_error or not datos or datos["cobertura"]["con_H"] != 288:
                    raise RuntimeError("cobertura inesperada")
    except Exception as error:
        print(json.dumps({"estado": "error", "tipo": type(error).__name__, "segundos": time.monotonic() - inicio}))
        return 1
    print(json.dumps({"estado": "ok", "herramientas": len(nombres), "segundos": time.monotonic() - inicio}))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="URL Streamable HTTP del piloto")
    sys.exit(anyio.run(medir, parser.parse_args().url))
