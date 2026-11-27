from __future__ import annotations

import pytest

from mcp_uruguay import cache, caru


def test_informe_registra_fuente_y_reutiliza_archivo(monkeypatch):
    consultas = []

    def bajar(url, destino):
        consultas.append(url)
        destino.write_bytes(b"ejemplo")

    def leer(pdf, url, bajado):
        assert pdf.read_bytes() == b"ejemplo"
        assert bajado.tzinfo is not None
        return {"playa": "Salto Chico", "fuente": url, "muestras": []}

    monkeypatch.setattr(caru.red, "bajar", bajar)
    for _ in range(2):
        with cache.vigilar_procedencia() as copias:
            resultado = caru._leer_informe(leer, "2025-02-03")
        assert resultado["semana_del_informe"] == "2025-02-03"
        assert resultado["fuente"] == copias[0]["url"]
        assert copias[0]["archivo"] == "caru/salto-chico-2025-02-03.pdf"
    assert consultas == [resultado["fuente"]]
    with pytest.raises(ValueError, match="Elegí"):
        caru._leer_informe(leer, "2025-02-04")
    assert len(consultas) == 1
