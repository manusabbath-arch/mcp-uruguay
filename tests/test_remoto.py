import pytest

pytest.importorskip("starlette")

from starlette.testclient import TestClient  # noqa: E402

from mcp_uruguay import herramientas as h  # noqa: E402
from mcp_uruguay.remoto import construir_app  # noqa: E402
from mcp_uruguay.servidor import servidor_piloto  # noqa: E402


def _rpc(cliente, metodo, params=None):
    return cliente.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": metodo, "params": params or {}},
        headers={"Accept": "application/json, text/event-stream"},
    )


def test_http_publica_solo_el_piloto_y_oculta_errores_locales(tmp_path, monkeypatch):
    def error(consulta, limite, pagina):
        raise OSError(str(tmp_path))

    monkeypatch.setattr(h, "buscar_datasets_catalogo", error)
    with TestClient(construir_app(servidor_piloto), base_url="http://127.0.0.1:8420") as cliente:
        assert cliente.get("/health").json() == {"estado": "ok"}
        herramientas = _rpc(cliente, "tools/list").json()["result"]["tools"]
        assert {t["name"] for t in herramientas} == {
            "buscar_datasets_catalogo",
            "recursos_catalogo",
            "clima",
            "nivel_rio",
            "calidad_agua",
        }
        r = _rpc(cliente, "tools/call", {"name": "buscar_datasets_catalogo", "arguments": {"consulta": "Salto"}})
        assert r.json()["result"]["isError"]
        assert tmp_path.name not in r.text
        assert "La consulta no pudo completarse" in r.text
        monkeypatch.setattr(
            h, "buscar_datasets_catalogo", lambda *args: {"datasets": [], "total": 0, "pagina": 1, "fuente": "prueba"}
        )
        bien = _rpc(cliente, "tools/call", {"name": "buscar_datasets_catalogo", "arguments": {"consulta": "Salto"}})
        assert bien.json()["result"]["structuredContent"]["total"] == 0
        r = _rpc(cliente, "tools/call", {"name": "diagnostico", "arguments": {}})
        assert r.json()["result"]["isError"]


def test_http_limita_rafaga_y_mantiene_salud(monkeypatch):
    monkeypatch.setenv("MCP_URUGUAY_RATE_LIMIT_RAFAGA", "1")
    with TestClient(construir_app(servidor_piloto), base_url="http://127.0.0.1:8420") as cliente:
        assert _rpc(cliente, "tools/list").status_code == 200
        r = _rpc(cliente, "tools/list")
        assert r.status_code == 429
        assert int(r.headers["Retry-After"]) >= 1
        assert cliente.get("/health").status_code == 200
