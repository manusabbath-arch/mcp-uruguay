"""La caché: lo cerrado no se vuelve a pedir, lo vivo vence y lo roto no se queda."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from conftest import BcuFalso
from uydatos import bcu, salto_grande

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


class TestProcedencia:
    """R2: cada respuesta puede llevar el sha256 de las copias que la respaldan, para verificarla.

    El plan lo pide contra un número que el agente cita: sin el hash y la fecha de la copia, la
    respuesta se cree o no se cree. No se anota nada mientras nadie escucha: el hash de un CSV de
    122 MB no se paga en un script ni en un test.
    """

    def test_anota_la_copia_leida_con_su_sha256(self, tmp_path):
        import hashlib

        ruta = tmp_path / "x.txt"
        ruta.write_text("dato", encoding="utf-8")
        with cache.vigilar_procedencia() as leidas:
            cache.archivo(ruta, _sin_red, lambda p: p.read_text(encoding="utf-8"), ttl=3600)
        (copia,) = leidas
        assert copia["sha256"] == hashlib.sha256(b"dato").hexdigest()
        assert (copia["archivo"], copia["bytes"], copia["url"]) == ("x.txt", 4, None)
        assert copia["bajado"].endswith("-03:00")

    def test_el_camino_es_el_de_la_cache_y_no_el_del_disco(self, cache_temporal):
        """En modo remoto una ruta absoluta expondría el usuario del servidor."""
        ruta = cache_temporal / "bcu" / "2225_2026-08.xml"
        ruta.parent.mkdir(parents=True)
        ruta.write_text("<x/>", encoding="utf-8")
        with cache.vigilar_procedencia() as leidas:
            cache.archivo(ruta, _sin_red, lambda p: p.read_text(encoding="utf-8"), ttl=3600)
        assert leidas[0]["archivo"] == "bcu/2225_2026-08.xml"

    def test_dos_archivos_dos_entradas_y_cada_una_una_vez(self, cache_temporal):
        cache_temporal.mkdir(parents=True, exist_ok=True)
        a, b = cache_temporal / "a.txt", cache_temporal / "b.txt"
        a.write_text("A", encoding="utf-8")
        b.write_text("BB", encoding="utf-8")
        with cache.vigilar_procedencia() as leidas:
            for _ in range(2):  # leer dos veces el mismo archivo no duplica la entrada
                cache.archivo(a, _sin_red, lambda p: p.read_text(encoding="utf-8"), 3600)
                cache.archivo(b, _sin_red, lambda p: p.read_text(encoding="utf-8"), 3600)
        assert [(c["archivo"], c["bytes"]) for c in leidas] == [("a.txt", 1), ("b.txt", 2)]

    def test_sin_nadie_escuchando_no_se_anota_ni_se_hashea(self, tmp_path):
        ruta = tmp_path / "x.txt"
        ruta.write_text("dato", encoding="utf-8")
        cache.archivo(ruta, _sin_red, lambda p: p.read_text(encoding="utf-8"), 3600)
        assert cache._leidas.get() is None

    def test_la_url_va_solo_si_la_herramienta_la_conoce(self, cache_temporal):
        ruta = cache_temporal / "ose" / "fisicoquimico.csv"
        ruta.parent.mkdir(parents=True)
        ruta.write_text("x", encoding="utf-8")
        with cache.vigilar_procedencia() as leidas:
            cache.archivo(ruta, _sin_red, lambda p: p.read_text(encoding="utf-8"), 3600, url="https://ose.test/f.csv")
        assert leidas[0]["url"] == "https://ose.test/f.csv"

    def test_bcu_serie_anota_cada_mes_que_leyo(self, monkeypatch, cache_temporal):
        monkeypatch.setattr(bcu, "descargar", BcuFalso())
        with cache.vigilar_procedencia() as leidas:
            cache.bcu_serie(2225, date(2026, 8, 1), date(2026, 9, 30), hoy=date(2026, 10, 9))
        assert [c["archivo"] for c in leidas] == ["bcu/2225_2026-08.xml", "bcu/2225_2026-09.xml"]

    def test_el_hash_se_calcula_una_vez_por_copia(self, monkeypatch, cache_temporal):
        """430 ms por llamada sobre los 122 MB de OSE: el segundo pedido no los vuelve a pagar."""
        calculados = []
        monkeypatch.setattr(cache.procedencia, "sha256", lambda ruta: calculados.append(ruta) or "0" * 64)
        monkeypatch.setattr(cache, "_hashes", {})
        cache_temporal.mkdir(parents=True, exist_ok=True)
        ruta = cache_temporal / "x.txt"
        ruta.write_text("dato", encoding="utf-8")
        for _ in range(2):
            with cache.vigilar_procedencia() as leidas:
                cache.archivo(ruta, _sin_red, lambda p: p.read_text(encoding="utf-8"), 3600)
                assert leidas[0]["sha256"] == "0" * 64
        assert len(calculados) == 1

    def test_una_copia_nueva_se_vuelve_a_hashear(self, monkeypatch, cache_temporal):
        import os

        calculados = []
        monkeypatch.setattr(cache.procedencia, "sha256", lambda ruta: calculados.append(1) or "1" * 64)
        monkeypatch.setattr(cache, "_hashes", {})
        cache_temporal.mkdir(parents=True, exist_ok=True)
        ruta = cache_temporal / "x.txt"
        ruta.write_text("uno", encoding="utf-8")
        with cache.vigilar_procedencia():
            cache.archivo(ruta, _sin_red, lambda p: p.read_text(encoding="utf-8"), 3600)
        ruta.write_text("dos", encoding="utf-8")
        os.utime(ruta, (1, 1))  # otro mtime, como el de una copia recién publicada
        with cache.vigilar_procedencia() as leidas:
            cache.archivo(ruta, _sin_red, lambda p: p.read_text(encoding="utf-8"), 3600)
        assert len(calculados) == 2 and leidas[0]["sha256"] == "1" * 64


class TestUnTemporalPorDescarga:
    """R1: `cache.archivo`, `cache.sg_lecturas` y `agua._archivo_ose` escribían el mismo `<archivo>.nuevo`.

    Dos clientes MCP que comparten `~/.cache/mcp-uruguay` bajaban al mismo temporal: uno publicaba
    el archivo a medio escribir del otro.
    """

    def test_dos_bajadas_a_la_vez_no_publican_una_copia_a_medias(self, tmp_path):
        import threading

        ruta = tmp_path / "x.txt"
        barrera = threading.Barrier(2, timeout=10)
        enteras = {"A" * 800, "B" * 800}

        def bajar_en_dos_tandas(letra):
            def bajar(destino):
                with destino.open("wb") as f:
                    f.write((letra * 400).encode())
                    f.flush()
                    barrera.wait()  # el otro escribe la suya en el mismo temporal
                    f.write((letra * 400).encode())

            return bajar

        def leer(p):
            texto = p.read_text(encoding="utf-8")
            if texto not in enteras:  # la copia mezclada: no es ninguna de las dos versiones
                raise ValueError(f"copia a medias ({len(texto)} bytes)")
            return texto

        def bajar_y_leer(letra):
            try:
                return cache.archivo(ruta, bajar_en_dos_tandas(letra), leer, ttl=3600)[0]
            except Exception as e:  # noqa: BLE001 - el fallo es lo que se está midiendo
                return e

        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(bajar_y_leer, "AB"))

        assert all(isinstance(r, str) for r in resultados), resultados
        assert ruta.read_text(encoding="utf-8") in enteras

    def test_el_temporal_es_propio_de_cada_bajada(self, tmp_path):
        ruta = tmp_path / "x.txt"
        una, otra = cache._temporal(ruta), cache._temporal(ruta)
        assert una != otra
        assert una.parent == otra.parent == ruta.parent
        # el sufijo lo sigue ignorando `diagnostico`; el prefijo no choca con la copia buena
        assert una.name.endswith(".nuevo") and una.name != "x.txt.nuevo"

    def test_salto_grande_baja_a_un_temporal_propio(self, monkeypatch, cache_temporal):
        destinos = []

        def sin_red(estacion, desde, hasta, destino):
            destinos.append(destino)
            raise OSError("sin red")

        monkeypatch.setattr(salto_grande, "descargar_datos", sin_red)
        for _ in range(2):
            with pytest.raises(OSError, match="sin red"):
                cache.sg_lecturas("salto", date(2026, 10, 1), date(2026, 10, 31), hoy=date(2026, 11, 5))
        assert len(destinos) == 2 and destinos[0] != destinos[1]
        assert all(d.name != "salto_2026-10.xml.nuevo" for d in destinos)
