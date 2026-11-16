"""Genera `manifest.json`, el de la extensión de Claude Desktop (MCPB), a partir del servidor.

Con un `.mcpb`, Claude Desktop instala el servidor con un clic: el tipo `uv` del formato deja que la
aplicación resuelva Python y las dependencias desde `pyproject.toml`, así que quien lo usa no
necesita tener Python ni `uv` (MCPB, MANIFEST.md, «UV Runtime (v0.4+)»). Es la barrera que dejaba
afuera a quien no programa: periodistas, docentes, gente de los organismos.

Como `docs/herramientas.md`, el manifiesto **no se edita a mano**: se regenera con
`python -m mcp_uruguay.manifiesto`, y `tests/test_manifiesto.py` falla si quedó viejo. La lista de
herramientas que ve Claude Desktop antes de instalar es un contrato: no puede nombrar una que ya no
existe ni faltarle una nueva.

Los prompts no van en el manifiesto: MCPB pide su texto fijo con `${arguments.x}` y los de
`guias.py` se arman en código. Se declaran con `prompts_generated`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import anyio
from mcp import Client

from mcp_uruguay.servidor import servidor

RAIZ = Path(__file__).resolve().parents[2]
RUTA = RAIZ / "manifest.json"
REPO = "https://github.com/manusabbath-arch/mcp-uruguay"


def _version() -> str:
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version = "([^"]+)"', texto, re.M).group(1)


async def _herramientas() -> list[dict]:
    async with Client(servidor) as c:
        return [{"name": t.name, "description": t.title or t.name} for t in (await c.list_tools()).tools]


def manifiesto() -> dict:
    return {
        "manifest_version": "0.4",
        "name": "mcp-uruguay",
        "display_name": "Uruguay: datos públicos",
        "version": _version(),
        "description": (
            "Datos públicos de Uruguay y la región, de la fuente primaria y con la fecha de la copia: "
            "BCU, ANCAP, INIA, INUMET, el río Uruguay, OSE, Corte Electoral, Parlamento, compras del Estado."
        ),
        "long_description": (
            "Servidor MCP construido sobre [uydatos](https://github.com/manusabbath-arch/uy-datos-abiertos), "
            "lectores estrictos que **rechazan en vez de arreglar**: ante un dato que no cumple, devuelven el "
            "motivo y no un número plausible pero falso. Cada respuesta trae `fuente` y `bajado` para citar el "
            "dato. Es de solo lectura y no es un servicio oficial: si una cifra no coincide con la del "
            "organismo, vale la del organismo."
        ),
        "author": {"name": "Manu Martinez", "url": "https://github.com/manusabbath-arch"},
        "repository": {"type": "git", "url": f"{REPO}.git"},
        "homepage": REPO,
        "documentation": f"{REPO}/blob/main/docs/herramientas.md",
        "support": f"{REPO}/issues",
        "server": {
            "type": "uv",
            "entry_point": "src/mcp_uruguay/__main__.py",
            "mcp_config": {
                "command": "uv",
                "args": ["run", "--directory", "${__dirname}", "mcp-uruguay"],
            },
        },
        "tools": anyio.run(_herramientas),
        "prompts_generated": True,
        "keywords": ["uruguay", "datos-abiertos", "open-data", "bcu", "ancap", "ose", "elecciones", "clima"],
        "license": "MIT",
        "compatibility": {"platforms": ["darwin", "win32", "linux"], "runtimes": {"python": ">=3.10"}},
    }


def texto() -> str:
    return json.dumps(manifiesto(), ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    RUTA.write_text(texto(), encoding="utf-8", newline="\n")
    print(f"escrito {RUTA}", file=sys.stderr)


if __name__ == "__main__":
    main()
