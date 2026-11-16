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
        t = datetime(2026, 9, 15, 12, tzinfo=cache._zona()).timestamp()
        os.utime(ruta, (t, t))
        cache.bcu_serie(2225, date(2026, 9, 1), date(2026, 9, 30), hoy=date(2026, 10, 9))
        assert falso.bajadas == ["2026-09", "2026-09"]

    def test_bajado_despues_de_cerrar_no_se_vuelve_a_pedir(self, monkeypatch, cache_temporal):
        falso = BcuFalso()
        monkeypatch.setattr(bcu, "descargar", falso)
        cache.bcu_serie(2225, date(2026, 9, 1), date(2026, 9, 30), hoy=date(2026, 10, 9))
        cache.bcu_serie(2225, date(2026, 9, 1), date(2026, 9, 30), hoy=date(2026, 10, 9))
        assert falso.bajadas == ["2026-09"]


def _mes_viejo_y_vencido(monkeypatch, cache_temporal):
    """Un agosto bajado a mitad de mes: está incompleto, así que hoy toca refrescarlo."""
    from datetime import datetime

    monkeypatch.setattr(bcu, "descargar", BcuFalso())
    cache.bcu_serie(2225, date(2026, 8, 1), date(2026, 8, 31), hoy=date(2026, 10, 9))
    ruta = cache_temporal / "bcu" / "2225_2026-08.xml"
    t = datetime(2026, 8, 15, 12, tzinfo=cache._zona()).timestamp()
    os.utime(ruta, (t, t))
    return ruta


def _sin_red(*args, **kwargs):
    raise OSError("sin red")


class TestLaCopiaBuenaNoSeBorraAntesDeBajar:
    """M2: `bcu_serie` borraba la copia y recién después bajaba; si la bajada fallaba, no quedaba nada."""

    def test_si_la_descarga_falla_se_responde_con_la_copia_anterior(self, monkeypatch, cache_temporal):
        ruta = _mes_viejo_y_vencido(monkeypatch, cache_temporal)
        antes = ruta.read_bytes()
        monkeypatch.setattr(bcu, "descargar", _sin_red)
        serie, _ = cache.bcu_serie(2225, date(2026, 8, 1), date(2026, 8, 31), hoy=date(2026, 10, 9))
        assert serie  # salió de la copia vieja
        assert ruta.read_bytes() == antes

    def test_si_la_respuesta_viene_ilegible_se_responde_con_la_copia_anterior(self, monkeypatch, cache_temporal):
        ruta = _mes_viejo_y_vencido(monkeypatch, cache_temporal)
        antes = ruta.read_bytes()
        monkeypatch.setattr(bcu, "descargar", BcuFalso(respuesta_mala=True))
        serie, _ = cache.bcu_serie(2225, date(2026, 8, 1), date(2026, 8, 31), hoy=date(2026, 10, 9))
        assert serie
        assert ruta.read_bytes() == antes

    def test_sin_copia_anterior_el_error_sube_y_no_queda_nada(self, monkeypatch, cache_temporal):
        monkeypatch.setattr(bcu, "descargar", _sin_red)
        with pytest.raises(OSError, match="sin red"):
            cache.bcu_serie(2225, date(2026, 8, 1), date(2026, 8, 31), hoy=date(2026, 10, 9))
        assert not (cache_temporal / "bcu" / "2225_2026-08.xml").exists()

    def test_no_quedan_carpetas_temporales(self, monkeypatch, cache_temporal):
        _mes_viejo_y_vencido(monkeypatch, cache_temporal)
        monkeypatch.setattr(bcu, "descargar", _sin_red)
        cache.bcu_serie(2225, date(2026, 8, 1), date(2026, 8, 31), hoy=date(2026, 10, 9))
        assert not [p for p in (cache_temporal / "bcu").iterdir() if p.name.startswith(".nuevo-")]

    def test_dos_bajadas_a_la_vez_del_mismo_mes_no_se_pisan(self, monkeypatch, cache_temporal):
        """Dos clientes MCP comparten `~/.cache/mcp-uruguay`: antes escribían el mismo `.nuevo`."""
        from concurrent.futures import ThreadPoolExecutor

        monkeypatch.setattr(bcu, "descargar", BcuFalso())
        with ThreadPoolExecutor(max_workers=6) as pool:
            resultados = list(
                pool.map(
                    lambda _: cache.bcu_serie(2225, date(2026, 8, 1), date(2026, 8, 31), hoy=date(2026, 10, 9)),
                    range(12),
                )
            )
        assert all(r[0] for r in resultados)
        carpeta = cache_temporal / "bcu"
        assert bcu.leer_crudo(carpeta / "2225_2026-08.xml", 2225)
        assert not [p for p in carpeta.iterdir() if p.name.startswith(".nuevo-")]


class TestLaCopiaVencidaAvisa:
    """M3: una copia más vieja que su ttl, servida porque no se pudo refrescar, no pasa en silencio."""

    def test_archivo_anota_la_copia_vencida_que_sirvio(self, tmp_path):
        ruta = tmp_path / "x.txt"
        ruta.write_text("bueno", encoding="utf-8")
        _envejecer(ruta, 10_000)
        with cache.vigilar_copias() as vencidas:
            cache.archivo(ruta, _sin_red, lambda p: p.read_text(encoding="utf-8"), ttl=3600)
        assert len(vencidas) == 1

    def test_una_copia_fresca_no_se_anota(self, tmp_path):
        ruta = tmp_path / "x.txt"
        ruta.write_text("bueno", encoding="utf-8")
        with cache.vigilar_copias() as vencidas:
            cache.archivo(ruta, lambda p: p.write_text("otro"), lambda p: p.read_text(encoding="utf-8"), ttl=3600)
        assert vencidas == []

    def test_una_bajada_que_funciona_no_se_anota(self, tmp_path):
        ruta = tmp_path / "x.txt"
        ruta.write_text("viejo", encoding="utf-8")
        _envejecer(ruta, 10_000)
        with cache.vigilar_copias() as vencidas:
            dato, _ = cache.archivo(
                ruta, lambda p: p.write_text("nuevo", encoding="utf-8"), lambda p: p.read_text(encoding="utf-8"), 3600
            )
        assert dato == "nuevo" and vencidas == []

    def test_bcu_serie_anota_la_copia_vencida(self, monkeypatch, cache_temporal):
        _mes_viejo_y_vencido(monkeypatch, cache_temporal)
        monkeypatch.setattr(bcu, "descargar", _sin_red)
        with cache.vigilar_copias() as vencidas:
            cache.bcu_serie(2225, date(2026, 8, 1), date(2026, 8, 31), hoy=date(2026, 10, 9))
        assert vencidas and vencidas[0].startswith("2026-08-15T12:00")


class TestLaHoraEsLaDeUruguay:
    """M1: «hoy» y `bajado` no pueden depender de la zona horaria de la máquina."""

    def test_a_las_2330_de_montevideo_hoy_sigue_siendo_ese_dia(self, monkeypatch):
        """2026-11-01T02:30Z es el 31/10 a las 23:30 en Uruguay; en UTC ya sería noviembre."""
        from datetime import datetime, timezone

        instante = datetime(2026, 11, 1, 2, 30, tzinfo=timezone.utc).timestamp()
        monkeypatch.setattr(cache.time, "time", lambda: instante)
        assert cache.hoy() == date(2026, 10, 31)
        assert cache.ahora().isoformat() == "2026-10-31T23:30:00-03:00"

    def test_octubre_sigue_en_curso_a_las_2330_del_31(self, monkeypatch):
        """Con `hoy` mal calculado, el 31/10 de noche se pediría también noviembre."""
        from datetime import datetime, timezone

        utc = datetime(2026, 11, 1, 2, 30, tzinfo=timezone.utc)
        monkeypatch.setattr(cache, "ahora", lambda: utc.astimezone(cache._zona()))
        falso = BcuFalso(hasta=date(2026, 10, 31))
        monkeypatch.setattr(bcu, "descargar", falso)
        cache.bcu_serie(2225, date(2026, 10, 1), date(2026, 11, 5))
        assert falso.bajadas == ["2026-10"]

    def test_bajado_lleva_el_desplazamiento_de_uruguay(self, tmp_path):
        ruta = tmp_path / "x.txt"
        ruta.write_text("dato", encoding="utf-8")
        assert cache.sello(ruta).endswith("-03:00")

    def test_sin_base_de_zonas_horarias_se_usa_utc_menos_3(self, monkeypatch, tmp_path):
        from zoneinfo import ZoneInfoNotFoundError

        def sin_base(nombre):
            raise ZoneInfoNotFoundError(nombre)

        monkeypatch.setattr(cache, "ZoneInfo", sin_base)
        ruta = tmp_path / "x.txt"
        ruta.write_text("dato", encoding="utf-8")
        assert cache.sello(ruta).endswith("-03:00")
        assert cache.ahora().utcoffset().total_seconds() == -3 * 3600
