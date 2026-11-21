"""Modo remoto (M8): el limitador de pedidos por IP y la redacción de `diagnostico`.

Ver `docs/2026-11-18-plan-http.md` para las decisiones de diseño detrás de este archivo.
"""

from __future__ import annotations

from mcp_uruguay import herramientas as h
from mcp_uruguay.remoto import LimitadorPorIP


class TestDiagnosticoRemoto:
    def test_local_sigue_devolviendo_la_ruta_real(self, tmp_path, monkeypatch):
        """Comportamiento previo a M8: sin remoto=True, nada cambia."""
        monkeypatch.setenv("MCP_URUGUAY_CACHE", str(tmp_path))
        r = h.diagnostico()
        assert r["directorio"] == str(tmp_path)
        assert "remoto" not in r["nota"]

    def test_remoto_oculta_la_ruta(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_URUGUAY_CACHE", str(tmp_path))
        r = h.diagnostico(remoto=True)
        assert str(tmp_path) not in r["directorio"]
        assert r["directorio"] == "(oculto en modo remoto: ver nota)"
        assert "remoto" in r["nota"]

    def test_remoto_no_toca_los_archivos_relativos(self, tmp_path, monkeypatch):
        """Los nombres de archivo ya eran relativos antes de M8: no deberían cambiar."""
        monkeypatch.setenv("MCP_URUGUAY_CACHE", str(tmp_path))
        (tmp_path / "bcu").mkdir()
        (tmp_path / "bcu" / "USD_2026-11.json").write_text("{}")
        remoto = h.diagnostico(remoto=True)
        local = h.diagnostico(remoto=False)
        assert remoto["archivos"] == local["archivos"]
        assert remoto["archivos"][0]["archivo"] == "bcu/USD_2026-11.json"


class TestLimitadorPorIP:
    """El token bucket, probado directo (sin levantar un servidor HTTP real: determinista y rápido)."""

    def _limitador(self, por_minuto: int = 3, rafaga: int = 3) -> LimitadorPorIP:
        # BaseHTTPMiddleware exige una app de ASGI real en el constructor; no se llama en estos tests.
        return LimitadorPorIP(app=None, por_minuto=por_minuto, rafaga=rafaga)

    def test_dentro_de_la_rafaga_permite(self):
        lim = self._limitador(por_minuto=60, rafaga=3)
        for _ in range(3):
            permitido, _ = lim._permitido("1.2.3.4")
            assert permitido

    def test_pasada_la_rafaga_bloquea_con_espera_positiva(self):
        lim = self._limitador(por_minuto=60, rafaga=2)
        assert lim._permitido("1.2.3.4") == (True, 0.0)
        assert lim._permitido("1.2.3.4") == (True, 0.0)
        bloqueado, espera = lim._permitido("1.2.3.4")
        assert not bloqueado
        assert espera > 0

    def test_ips_distintas_no_comparten_cubeta(self):
        lim = self._limitador(por_minuto=60, rafaga=1)
        permitido_a, _ = lim._permitido("1.1.1.1")
        permitido_b, _ = lim._permitido("2.2.2.2")
        assert permitido_a and permitido_b

    def test_x_forwarded_for_usa_el_primer_ip(self):
        lim = self._limitador()

        class FalsoHeaders(dict):
            def get(self, k, default=None):  # dict.get normal alcanza, explicito por claridad
                return super().get(k, default)

        class FalsoCliente:
            host = "10.0.0.1"  # la IP del proxy, no la del cliente real

        class FalsoRequest:
            headers = FalsoHeaders({"x-forwarded-for": "9.9.9.9, 10.0.0.1"})
            client = FalsoCliente()

        assert lim._ip(FalsoRequest()) == "9.9.9.9"

    def test_sin_x_forwarded_for_usa_la_ip_del_cliente(self):
        lim = self._limitador()

        class FalsoCliente:
            host = "8.8.8.8"

        class FalsoRequest:
            headers: dict = {}
            client = FalsoCliente()

        assert lim._ip(FalsoRequest()) == "8.8.8.8"
