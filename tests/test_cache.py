"""La caché: lo cerrado no se vuelve a pedir, lo vivo vence y lo roto no se queda."""

from __future__ import annotations

import os
import time
from datetime import date

import pytest
from conftest import BcuFalso
from uydatos import bcu

from mcp_uruguay import cache


def _envejecer(ruta, segundos):
    t = time.time() - segundos
    os.utime(ruta, (t, t))


class TestArchivo:
    def test_baja_si_falta_y_despues_usa_la_copia(self, tmp_path):
        bajadas = []

        def bajar(p):
            bajadas.append(1)
            p.write_text("dato", encoding="utf-8")

        ruta = tmp_path / "x.txt"
        assert cache.archivo(ruta, bajar, lambda p: p.read_text(encoding="utf-8"), ttl=3600)[0] == "dato"
        cache.archivo(ruta, bajar, lambda p: p.read_text(encoding="utf-8"), ttl=3600)
        assert len(bajadas) == 1

    def test_una_descarga_ilegible_no_pisa_la_copia_buena(self, tmp_path):
        ruta = tmp_path / "x.txt"
        ruta.write_text("bueno", encoding="utf-8")
        _envejecer(ruta, 10_000)

        def leer(p):
            texto = p.read_text(encoding="utf-8")
            if texto != "bueno":
                raise ValueError("ilegible")
            return texto

        dato, _ = cache.archivo(ruta, lambda p: p.write_text("roto", encoding="utf-8"), leer, ttl=3600)
        assert dato == "bueno"
        assert ruta.read_text(encoding="utf-8") == "bueno"
        assert not ruta.with_name("x.txt.nuevo").exists()

    def test_sin_copia_previa_el_error_sube(self, tmp_path):
        def leer(p):
            raise ValueError("ilegible")

        with pytest.raises(ValueError, match="ilegible"):
            cache.archivo(tmp_path / "x.txt", lambda p: p.write_text("roto"), leer, ttl=3600)
        assert not (tmp_path / "x.txt").exists()


class TestBcuSerie:
    def test_un_mes_cerrado_no_se_vuelve_a_pedir(self, monkeypatch):
        falso = BcuFalso()
        monkeypatch.setattr(bcu, "descargar", falso)
        hoy = date(2026, 10, 9)
        cache.bcu_serie(2225, date(2026, 8, 1), date(2026, 8, 31), hoy=hoy)
        cache.bcu_serie(2225, date(2026, 8, 1), date(2026, 8, 31), hoy=hoy)
        assert falso.bajadas == ["2026-08"]

    def test_el_mes_en_curso_se_refresca_cuando_vence(self, monkeypatch, cache_temporal):
        falso = BcuFalso(hasta=date(2026, 10, 9))
        monkeypatch.setattr(bcu, "descargar", falso)
        hoy = date(2026, 10, 9)
        cache.bcu_serie(2225, date(2026, 10, 1), hoy, hoy=hoy)
        cache.bcu_serie(2225, date(2026, 10, 1), hoy, hoy=hoy)
        assert falso.bajadas == ["2026-10"]
        _envejecer(cache_temporal / "bcu" / "2225_2026-10.xml", 4 * 3600)
        cache.bcu_serie(2225, date(2026, 10, 1), hoy, hoy=hoy)
        assert falso.bajadas == ["2026-10", "2026-10"]

    def test_mes_en_curso_sin_publicaciones_no_es_error(self, monkeypatch):
        """El 1.º de enero todavía no hay cotización del mes: cero días, no una excepción."""
        monkeypatch.setattr(bcu, "descargar", BcuFalso(hasta=date(2026, 12, 31)))
        serie, _ = cache.bcu_serie(2225, date(2027, 1, 1), date(2027, 1, 1), hoy=date(2027, 1, 1))
        assert serie == {}

    def test_una_respuesta_mala_no_se_queda_en_la_cache(self, monkeypatch, cache_temporal):
        monkeypatch.setattr(bcu, "descargar", BcuFalso(respuesta_mala=True))
        with pytest.raises(bcu.BcuInvalido, match="104"):
            cache.bcu_serie(2225, date(2026, 8, 1), date(2026, 8, 31), hoy=date(2026, 10, 9))
        assert not (cache_temporal / "bcu" / "2225_2026-08.xml").exists()

    def test_el_futuro_se_rechaza(self):
        with pytest.raises(ValueError, match="futuro"):
            cache.bcu_serie(2225, date(2030, 1, 1), date(2030, 1, 31), hoy=date(2026, 10, 9))


class TestMesBajadoEnCurso:
    def test_un_mes_bajado_mientras_corria_se_vuelve_a_pedir_al_cerrar(self, monkeypatch, cache_temporal):
        """Bajado el 15/09 tiene medio mes: en octubre no está cerrado, está incompleto."""
        from datetime import datetime

        falso = BcuFalso()
        monkeypatch.setattr(bcu, "descargar", falso)
        cache.bcu_serie(2225, date(2026, 9, 1), date(2026, 9, 30), hoy=date(2026, 10, 9))
        ruta = cache_temporal / "bcu" / "2225_2026-09.xml"
        t = datetime(2026, 9, 15, 12).timestamp()
        os.utime(ruta, (t, t))
        cache.bcu_serie(2225, date(2026, 9, 1), date(2026, 9, 30), hoy=date(2026, 10, 9))
        assert falso.bajadas == ["2026-09", "2026-09"]

    def test_bajado_despues_de_cerrar_no_se_vuelve_a_pedir(self, monkeypatch, cache_temporal):
        falso = BcuFalso()
        monkeypatch.setattr(bcu, "descargar", falso)
        cache.bcu_serie(2225, date(2026, 9, 1), date(2026, 9, 30), hoy=date(2026, 10, 9))
        cache.bcu_serie(2225, date(2026, 9, 1), date(2026, 9, 30), hoy=date(2026, 10, 9))
        assert falso.bajadas == ["2026-09"]
