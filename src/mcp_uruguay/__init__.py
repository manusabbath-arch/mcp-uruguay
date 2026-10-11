"""mcp-uruguay — servidor MCP con datos públicos de Uruguay y la región, sobre `uydatos`."""

from importlib.metadata import PackageNotFoundError, version

# La versión sale del paquete instalado, no de una constante: de la 0.7.0 a la 0.10.0 la constante
# quedó en "0.7.0" y el servidor se anunciaba con esa versión a los clientes, fuera cual fuera la
# instalada. `tests/test_version.py` la ata a `pyproject.toml`.
try:
    __version__ = version("mcp-uruguay")
except PackageNotFoundError:  # corriendo desde el código sin instalar
    __version__ = "0+sin-instalar"
