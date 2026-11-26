"""Genera una Agent Skill por cada flujo de `guias.PROMPTS`, sin copiar el texto a mano.

    uv run python scripts/generar_skills.py            # escribe skills/
    uv run python scripts/generar_skills.py --check    # falla si difiere, sin escribir

`guias.py` es la fuente única: la skill lleva el mismo texto que el prompt, con marcadores legibles
(`<producto>`, `<desde>`) en lugar de valores de ejemplo, y la trampa de cada herramienta que nombra.
El directorio de la skill y su `name` son el nombre del prompt con guiones en vez de guiones bajos.
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
import sys
from pathlib import Path

from mcp_uruguay import guias

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "skills"

#: Una herramienta se nombra entre comillas invertidas, como en los prompts.
_ENTRE_COMILLAS = re.compile(r"`([^`\n]+)`")

_AVISO = (
    "> Archivo generado por `scripts/generar_skills.py` desde `src/mcp_uruguay/guias.py`. "
    "No editar a mano: se regenera y `--check` falla si difiere."
)


def nombre_skill(nombre_prompt: str) -> str:
    """El nombre del directorio y del frontmatter: el del prompt, con guiones."""
    return nombre_prompt.replace("_", "-")


def herramientas_nombradas(texto: str) -> list[str]:
    """Las herramientas de `guias.TRAMPAS` que el texto nombra, en orden de aparición."""
    vistas: list[str] = []
    for marca in _ENTRE_COMILLAS.finditer(texto):
        nombre = marca.group(1)
        if nombre in guias.TRAMPAS and nombre not in vistas:
            vistas.append(nombre)
    return vistas


def _marcadores(funcion) -> dict[str, str]:
    """Un valor legible por parámetro, para que el texto no lleve un ejemplo fijo."""
    return {nombre: f"<{nombre}>" for nombre in inspect.signature(funcion).parameters}


def _descripcion(funcion, titulo: str) -> str:
    """El título del flujo y su docstring, en una sola línea."""
    doc = " ".join((inspect.getdoc(funcion) or "").split())
    return f"{titulo}. {doc}" if doc else titulo


def _contenido(nombre_prompt: str) -> str:
    funcion, titulo = guias.PROMPTS[nombre_prompt]
    texto = funcion(**_marcadores(funcion))
    trampas = "\n".join(f"- `{nombre}`: {guias.TRAMPAS[nombre]}" for nombre in herramientas_nombradas(texto))
    if not trampas:
        trampas = "- El flujo no nombra herramientas."
    return (
        "---\n"
        f"name: {nombre_skill(nombre_prompt)}\n"
        f"description: {json.dumps(_descripcion(funcion, titulo), ensure_ascii=False)}\n"
        "---\n"
        "\n"
        f"# {titulo}\n"
        "\n"
        f"{_AVISO}\n"
        "\n"
        f"{texto}\n"
        "\n"
        "## Trampas de las herramientas que nombra\n"
        "\n"
        f"{trampas}\n"
    )


def skills() -> dict[str, str]:
    """Las skills que corresponden a `guias.PROMPTS`: nombre del directorio -> contenido."""
    return {nombre_skill(nombre): _contenido(nombre) for nombre in sorted(guias.PROMPTS)}


def escribir(destino: Path = DESTINO) -> list[Path]:
    """Escribe cada skill en `destino`, con UTF-8 y LF. Devuelve las rutas escritas."""
    destino = Path(destino)
    rutas = []
    for nombre, contenido in skills().items():
        ruta = destino / nombre / "SKILL.md"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(contenido, encoding="utf-8", newline="\n")
        rutas.append(ruta)
    return rutas


def revisar(destino: Path = DESTINO) -> list[str]:
    """Los problemas de `destino`, sin escribir: faltantes, viejos y sobrantes."""
    destino = Path(destino)
    esperadas = skills()
    problemas = []
    for nombre, contenido in esperadas.items():
        ruta = destino / nombre / "SKILL.md"
        if not ruta.is_file():
            problemas.append(f"falta {nombre}/SKILL.md")
        elif ruta.read_bytes() != contenido.encode("utf-8"):  # como texto, un CRLF pasaría por al día
            problemas.append(f"desactualizado {nombre}/SKILL.md")

    esperados = {f"{nombre}/SKILL.md" for nombre in esperadas}
    if destino.is_dir():
        for ruta in sorted(destino.rglob("*")):
            relativa = ruta.relative_to(destino).as_posix()
            if ruta.is_file() and relativa not in esperados:
                problemas.append(f"sobra {relativa}")
            elif ruta.is_dir() and not any(esperado.startswith(f"{relativa}/") for esperado in esperados):
                problemas.append(f"sobra {relativa}/")
    return problemas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera las Agent Skills desde `guias.py`.")
    parser.add_argument("--check", action="store_true", help="no escribe: falla si las skills no coinciden")
    parser.add_argument("--destino", type=Path, default=DESTINO, help="directorio de salida")
    args = parser.parse_args(argv)

    if args.check:
        problemas = revisar(args.destino)
        for problema in problemas:
            print(problema)
        if problemas:
            print(f"{len(problemas)} problemas en {args.destino}: correr sin --check para regenerar")
            return 1
        print(f"{len(skills())} skills al día en {args.destino}")
        return 0

    rutas = escribir(args.destino)
    print(f"escritas {len(rutas)} skills en {args.destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
