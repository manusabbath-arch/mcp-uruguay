"""La versión que el servidor anuncia es la de `pyproject.toml` (de la 0.7.0 a la 0.10.0 no lo era)."""

from __future__ import annotations

import re
from pathlib import Path

import mcp_uruguay
from mcp_uruguay.servidor import servidor

RAIZ = Path(__file__).resolve().parents[1]


def _version_de_pyproject() -> str:
    return re.search(r'^version = "([^"]+)"', (RAIZ / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)


def test_el_paquete_dice_la_version_de_pyproject():
    assert mcp_uruguay.__version__ == _version_de_pyproject()


def test_el_servidor_se_anuncia_con_esa_version():
    assert servidor.version == _version_de_pyproject()
