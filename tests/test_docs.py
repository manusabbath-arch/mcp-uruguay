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
