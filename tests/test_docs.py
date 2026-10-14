"""La lista de herramientas y su documento no se pueden separar."""

from __future__ import annotations

import anyio

from mcp_uruguay import documentar


def test_el_documento_dice_lo_mismo_que_el_servidor():
    """Si falla, el documento quedo viejo: correr `python -m mcp_uruguay.documentar`."""
    if not documentar.RUTA.exists():
        raise AssertionError(f"falta {documentar.RUTA}: correr `python -m mcp_uruguay.documentar`")
    en_disco = documentar.RUTA.read_text(encoding="utf-8")
    assert en_disco == anyio.run(documentar.markdown), "correr `python -m mcp_uruguay.documentar`"


def test_la_tabla_del_readme_lista_las_mismas_herramientas():
    """La tabla del README es lo que se ve en GitHub y en PyPI: no puede listar herramientas que ya no
    existen ni faltarle las nuevas (pasó en la 0.3.0)."""
    import re
    from pathlib import Path

    from mcp import Client

    from mcp_uruguay.servidor import servidor

    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    # Solo la seccion de herramientas: los prompts y los recursos tienen sus propias tablas.
    seccion = readme.split("## Herramientas", 1)[1].split("\n## ", 1)[0]
    en_tabla = set(re.findall(r"^\| `([a-z_]+)` \|", seccion, flags=re.M))

    async def registradas():
        async with Client(servidor) as c:
            return {t.name for t in (await c.list_tools()).tools}

    assert en_tabla == anyio.run(registradas)
