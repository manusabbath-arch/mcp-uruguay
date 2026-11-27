"""Transporte Streamable HTTP del piloto de Salto."""

from __future__ import annotations

import ipaddress
import logging
import os
import time
from collections import OrderedDict
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

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
        self._cubetas: OrderedDict[str, tuple[float, float]] = OrderedDict()  # ip -> (tokens, ultimo_chequeo)

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
                    try:
                        return str(ipaddress.ip_address(salto))
                    except ValueError:
                        return directa
        return directa

    def _permitido(self, ip: str) -> tuple[bool, float]:
        ahora = time.monotonic()
        vence = self.rafaga / self.tasa
        while self._cubetas and ahora - next(iter(self._cubetas.values()))[1] >= vence:
            self._cubetas.popitem(last=False)
        if ip not in self._cubetas and len(self._cubetas) >= 4096:
            return False, vence
        tokens, ultimo = self._cubetas.pop(ip, (float(self.rafaga), ahora))
        tokens = min(self.rafaga, tokens + (ahora - ultimo) * self.tasa)
        if tokens < 1.0:
            faltan = (1.0 - tokens) / self.tasa
            self._cubetas[ip] = (tokens, ahora)
            return False, faltan
        self._cubetas[ip] = (tokens - 1.0, ahora)
        return True, 0.0

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
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
        inicio = time.monotonic()
        respuesta = await call_next(request)
        logging.getLogger("uvicorn.error").info(
            "MCP HTTP estado=%s duracion=%.3fs", respuesta.status_code, time.monotonic() - inicio
        )
        return respuesta


#: Defaults conservadores (ver el plan, sección 2); se pueden ajustar sin tocar código.
POR_MINUTO_DEFAULT = 30
RAFAGA_DEFAULT = 5


async def salud(request: Request) -> JSONResponse:
    return JSONResponse({"estado": "ok"})


def construir_app(servidor: "MCPServer") -> "Starlette":
    """La app de Starlette del servidor MCP, con el limitador por IP ya puesto."""
    por_minuto = int(os.environ.get("MCP_URUGUAY_RATE_LIMIT_POR_MIN", POR_MINUTO_DEFAULT))
    rafaga = int(os.environ.get("MCP_URUGUAY_RATE_LIMIT_RAFAGA", RAFAGA_DEFAULT))
    app = servidor.streamable_http_app(stateless_http=True, json_response=True)
    app.routes.insert(0, Route("/health", salud))
    app.add_middleware(LimitadorPorIP, por_minuto=por_minuto, rafaga=rafaga)
    return app


def ejecutar_remoto(servidor: "MCPServer") -> None:
    """Arranca el servidor por streamable-http. Host/puerto por variables de entorno.

    Escucha en 127.0.0.1 por defecto a propósito: se asume un reverse proxy (nginx/Caddy) delante
    que termina TLS — este proceso nunca queda expuesto directo a internet (ver el plan).
    """
    import uvicorn

    puerto = int(os.environ.get("MCP_URUGUAY_HTTP_PORT", "8420"))
    app = construir_app(servidor)
    uvicorn.run(app, host="127.0.0.1", port=puerto, log_level="info", proxy_headers=False, access_log=False)
