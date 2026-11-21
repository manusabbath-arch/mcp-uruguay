"""Transporte HTTP remoto (M8). Ver `docs/2026-11-18-plan-http.md` para las decisiones de diseño.

Los datos son públicos y de solo lectura: no hay autenticación. Lo único que agrega este módulo
sobre lo que ya trae el SDK (`MCPServer.streamable_http_app`) es un límite de pedidos por IP, para
que un cliente mal configurado no genere tráfico concurrente contra las fuentes reales.
"""

from __future__ import annotations

import ipaddress
import os
import time
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer
    from starlette.applications import Starlette


def _es_local(ip: str) -> bool:
    """Loopback (127.0.0.0/8, ::1): el único proxy en el que se confía. Un valor que no es IP no es local."""
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


class LimitadorPorIP(BaseHTTPMiddleware):
    """Token bucket en memoria de proceso, una cubeta por IP de cliente.

    En memoria de un solo proceso a propósito (ver el plan): con un worker uvicorn alcanza para el
    tráfico esperado de este nicho. Si algún día se corre con más de un worker o réplica, esto hay
    que moverlo a un almacén compartido (Redis) — no antes, sería resolver un problema que no existe.
    """

    def __init__(self, app, por_minuto: int, rafaga: int) -> None:
        super().__init__(app)
        self.por_minuto = max(1, por_minuto)
        self.rafaga = max(1, rafaga)
        self.tasa = self.por_minuto / 60.0  # tokens que se reponen por segundo
        self._cubetas: dict[str, tuple[float, float]] = {}  # ip -> (tokens, ultimo_chequeo)

    def _ip(self, request: Request) -> str:
        """La IP a limitar. `X-Forwarded-For` solo vale si el pedido llega de un proxy local.

        Sin esa condición, cualquiera manda el encabezado e inventa una IP distinta por pedido. Detrás
        del proxy, la lista se lee de derecha a izquierda salteando los saltos locales (cloudflared ->
        nginx agrega 127.0.0.1 al final): lo que el cliente haya escrito queda a la izquierda y no se usa.
        """
        cliente = request.client
        directa = cliente.host if cliente else "desconocida"
        if not _es_local(directa):
            return directa
        delante = request.headers.get("x-forwarded-for")
        if delante:
            for salto in reversed([s.strip() for s in delante.split(",") if s.strip()]):
                if not _es_local(salto):
                    return salto
        return directa

    def _permitido(self, ip: str) -> tuple[bool, float]:
        ahora = time.monotonic()
        tokens, ultimo = self._cubetas.get(ip, (float(self.rafaga), ahora))
        tokens = min(self.rafaga, tokens + (ahora - ultimo) * self.tasa)
        if tokens < 1.0:
            faltan = (1.0 - tokens) / self.tasa
            self._cubetas[ip] = (tokens, ahora)
            return False, faltan
        self._cubetas[ip] = (tokens - 1.0, ahora)
        return True, 0.0

    async def dispatch(self, request: Request, call_next):
        ip = self._ip(request)
        permitido, espera_s = self._permitido(ip)
        if not permitido:
            return JSONResponse(
                {
                    "error": "limite_de_pedidos",
                    "mensaje": (
                        f"Más de {self.por_minuto} pedidos por minuto desde esta IP. "
                        "No se arregla reintentando de inmediato."
                    ),
                },
                status_code=429,
                headers={"Retry-After": str(max(1, int(espera_s) + 1))},
            )
        return await call_next(request)


#: Defaults conservadores (ver el plan, sección 2); se pueden ajustar sin tocar código.
POR_MINUTO_DEFAULT = 30
RAFAGA_DEFAULT = 5


def construir_app(servidor: "MCPServer") -> "Starlette":
    """La app de Starlette del servidor MCP, con el limitador por IP ya puesto."""
    por_minuto = int(os.environ.get("MCP_URUGUAY_RATE_LIMIT_POR_MIN", POR_MINUTO_DEFAULT))
    rafaga = int(os.environ.get("MCP_URUGUAY_RATE_LIMIT_RAFAGA", RAFAGA_DEFAULT))
    app = servidor.streamable_http_app()
    app.add_middleware(LimitadorPorIP, por_minuto=por_minuto, rafaga=rafaga)
    return app


def ejecutar_remoto(servidor: "MCPServer") -> None:
    """Arranca el servidor por streamable-http. Host/puerto por variables de entorno.

    Escucha en 127.0.0.1 por defecto a propósito: se asume un reverse proxy (nginx/Caddy) delante
    que termina TLS — este proceso nunca queda expuesto directo a internet (ver el plan).
    """
    import uvicorn

    host = os.environ.get("MCP_URUGUAY_HTTP_HOST", "127.0.0.1")
    puerto = int(os.environ.get("MCP_URUGUAY_HTTP_PORT", "8420"))
    app = construir_app(servidor)
    uvicorn.run(app, host=host, port=puerto, log_level="info")
