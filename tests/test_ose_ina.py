"""`calidad_agua` (OSE) y `nivel_rio_ina` (INA), sin red: los CSV se arman con la forma real."""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from uydatos import ina, ose, red

from mcp_uruguay import herramientas as h

# --- OSE ---------------------------------------------------------------------------------------------

CABECERA_OSE = ";".join(f'"{c}"' for c in ose.COLUMNAS)


def _fila_ose(anio, tri, dep, loc, lab, area, param, valor, muestra):
    campos = [str(anio), f"trimestre {tri}", dep, loc, lab, area, param, "M", muestra, valor]
    return ";".join(f'"{c}"' for c in campos)


FISICO = [
    # Salto, 2024-T1: pH con coma, turbidez exacta y censurada, color censurado
    _fila_ose(2024, 1, "Salto", "Salto", "Lab. Salto", "Fisicoquímico", "PH", "7,2", "S1"),
    _fila_ose(2024, 1, "Salto", "Salto", "Lab. Salto", "Fisicoquímico", "PH", "7,6", "S2"),
    _fila_ose(2024, 1, "Salto", "Salto", "Lab. Salto", "Fisicoquímico", "TURBIDEZ", "0,4", "S1"),
    _fila_ose(2024, 1, "Salto", "Salto", "Lab. Salto", "Fisicoquímico", "TURBIDEZ", "<0,2", "S2"),
    _fila_ose(2024, 1, "Salto", "Salto", "Lab. Salto", "Fisicoquímico", "COLOR VERDADERO", "<5", "S1"),
    # Salto, 2024-T2: un valor con el signo al revés
    _fila_ose(2024, 2, "Salto", "Salto", "Lab. Salto", "Fisicoquímico", "TURBIDEZ", ">0,2", "S3"),
    # Montevideo usa punto decimal
    _fila_ose(2024, 1, "Montevideo", "Montevideo", "Lab. Central", "Fisicoquímico", "PH", "7.1", "M1"),
    # Paysandú solo está en fisicoquímico
    _fila_ose(2023, 4, "Paysandú", "Paysandú", "Lab. Paysandú", "Fisicoquímico", "PH", "7,0", "P1"),
]
BACTERIO = [
    _fila_ose(2024, 1, "Salto", "Salto", "Lab. Salto", "Bacteriología", "ESCHERICHIA COLI", "Ausencia", "S1"),
    _fila_ose(2024, 1, "Salto", "Salto", "Lab. Central", "Bacteriología", "ESCHERICHIA COLI", "Ausencia", "S1"),
    _fila_ose(2024, 1, "Salto", "Salto", "Lab. Salto", "Bacteriología", "COLIFORMES TOTALES", "Presencia", "S2"),
    _fila_ose(2024, 1, "Montevideo", "Montevideo", "Lab. Central", "Bacteriología", "ESCHERICHIA COLI", "<1", "M1"),
]
CSV_OSE = {
    "fisicoquimico": "\n".join([CABECERA_OSE, *FISICO]) + "\n",
    "bacteriologia": "\n".join([CABECERA_OSE, *BACTERIO]) + "\n",
}


class OseFalso:
    """Reemplaza CKAN y la descarga de OSE, y cuenta qué se pidió."""

    def __init__(self, monkeypatch, csv=CSV_OSE):
        self.csv, self.bajadas, self.consultas = csv, [], 0
        monkeypatch.setattr(ose, "recursos_vigentes", self.vigentes)
        monkeypatch.setattr(red, "bajar", self.bajar)

    def vigentes(self):
        self.consultas += 1
        return {
            area: {"url": f"https://ose.test/{area}.csv", "bytes": len(texto.encode()), "modificado": "2026-03-01"}
            for area, texto in self.csv.items()
        }

    def bajar(self, url, destino):
        area = url.rsplit("/", 1)[-1].removesuffix(".csv")
        self.bajadas.append(area)
        Path(destino).write_text(self.csv[area], encoding="utf-8")
        return Path(destino)


class TestCalidadAgua:
    def test_sin_localidad_lista_las_de_los_dos_archivos(self, monkeypatch):
        OseFalso(monkeypatch)
        r = h.calidad_agua()
        assert {"localidad": "Paysandú", "departamento": "Paysandú"} in r["localidades"]
        assert [x["localidad"] for x in r["localidades"]] == ["Montevideo", "Paysandú", "Salto"]
        assert r["fuente"] == h.FUENTE_OSE and r["bajado"]

    def test_un_censurado_no_entra_al_minimo_ni_al_maximo(self, monkeypatch):
        OseFalso(monkeypatch)
        r = h.calidad_agua("salto", desde="2024-T1", hasta="2024-T1")
        (t,) = r["trimestres"]
        assert t["trimestre"] == "2024-T1"
        turbidez = next(p for p in t["numericos"] if p["parametro"] == "TURBIDEZ")
        assert (turbidez["exactos"], turbidez["menor_que"]) == (1, 1)
        assert turbidez["min_exacto"] == turbidez["max_exacto"] == 0.4
        assert turbidez["limites_de_deteccion"] == [0.2]
        color = next(p for p in t["numericos"] if p["parametro"] == "COLOR VERDADERO")
        assert (color["exactos"], color["min_exacto"], color["unidad"]) == (0, None, "UC")

    def test_muestras_no_son_analisis(self, monkeypatch):
        """S1 se analizó en dos laboratorios: dos filas de E. coli, una muestra."""
        OseFalso(monkeypatch)
        (t,) = h.calidad_agua("Salto", desde="2024-T1", hasta="2024-T1")["trimestres"]
        coli = next(p for p in t["categoricos"] if p["parametro"] == "ESCHERICHIA COLI")
        assert coli == {"parametro": "ESCHERICHIA COLI", "analisis": 2, "categorias": {"Ausencia": 2}}
        assert t["muestras"] == 2  # S1 y S2

    def test_el_signo_al_reves_se_cuenta_aparte(self, monkeypatch):
        OseFalso(monkeypatch)
        (t,) = h.calidad_agua("Salto", "turbidez", "2024-T2", "2024-T2")["trimestres"]
        (turbidez,) = t["numericos"]
        assert (turbidez["mayor_que"], turbidez["exactos"], turbidez["min_exacto"]) == (1, 0, None)
        assert "signo al revés" in h.calidad_agua("Salto")["nota"]

    def test_los_dos_separadores_decimales(self, monkeypatch):
        OseFalso(monkeypatch)
        (t,) = h.calidad_agua("Montevideo", "ph")["trimestres"]
        assert t["numericos"][0]["min_exacto"] == 7.1

    def test_una_localidad_que_esta_en_un_solo_archivo(self, monkeypatch):
        OseFalso(monkeypatch)
        r = h.calidad_agua("Paysandu")
        assert r["localidad"] == "Paysandú" and r["trimestres"][0]["trimestre"] == "2023-T4"

    def test_localidad_desconocida_sugiere(self, monkeypatch):
        OseFalso(monkeypatch)
        with pytest.raises(ValueError, match="Parecidas: \\['Salto'\\]"):
            h.calidad_agua("Salto Nuevo")

    def test_parametro_desconocido_dice_los_que_hay(self, monkeypatch):
        OseFalso(monkeypatch)
        with pytest.raises(ValueError, match="TURBIDEZ"):
            h.calidad_agua("Salto", "cloro")

    def test_periodo_mal_escrito(self, monkeypatch):
        OseFalso(monkeypatch)
        with pytest.raises(ValueError, match="AAAA-Tn"):
            h.calidad_agua("Salto", desde="2024-03")
        with pytest.raises(ValueError, match="posterior"):
            h.calidad_agua("Salto", desde="2025", hasta="2024")

    def test_se_baja_una_vez_y_se_reusa(self, monkeypatch):
        falso = OseFalso(monkeypatch)
        h.calidad_agua("Salto")
        h.calidad_agua("Montevideo")
        assert sorted(falso.bajadas) == ["bacteriologia", "fisicoquimico"]

    def test_vencida_con_el_mismo_tamano_no_se_vuelve_a_bajar(self, monkeypatch, cache_temporal):
        falso = OseFalso(monkeypatch)
        h.calidad_agua("Salto")
        viejo = time.time() - 40 * 86400
        for area in ose.ARCHIVOS:
            os.utime(cache_temporal / "ose" / f"{area}.csv", (viejo, viejo))
        h.calidad_agua("Salto")
        assert len(falso.bajadas) == 2  # CKAN declaró el mismo tamaño: solo se renovó la fecha
        assert (cache_temporal / "ose" / "fisicoquimico.csv").stat().st_mtime > viejo

    def test_una_bajada_que_no_se_lee_no_entra_a_la_cache(self, monkeypatch, cache_temporal):
        OseFalso(monkeypatch, csv={**CSV_OSE, "fisicoquimico": "ANIO;OTRA\n1;2\n"})
        with pytest.raises(ose.OseInvalido):
            h.calidad_agua("Salto")
        assert not (cache_temporal / "ose" / "fisicoquimico.csv").exists()


# --- INA ---------------------------------------------------------------------------------------------

HOY = date(2026, 10, 27)
CABECERA_INA = ",".join(ina.COLUMNAS)


def _z(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def csv_ina(serie: int, desde: date, hasta: date, valor=lambda d: 5.0, carga_horas: int = 7) -> str:
    """Una lectura diaria a las 10Z (la hora más común medida) de `desde` a `hasta`."""
    filas, d, n = [CABECERA_INA], desde, 1
    while d <= hasta:
        t = datetime(d.year, d.month, d.day, 10, tzinfo=timezone.utc)
        carga = t + timedelta(hours=carga_horas)
        filas.append(f"{n},puntual,{serie},{_z(t)},{_z(t)},{ina.NOMBRE_FUENTE},,,{_z(carga)},{valor(d)}")
        d, n = d + timedelta(days=1), n + 1
    return "\n".join(filas) + "\n"


class InaFalso:
    """Reemplaza el API del INA: sirve una lectura diaria hasta `ultimo` y la metadata de la escala."""

    def __init__(self, monkeypatch, ultimo: date = HOY, valor=lambda d: 5.0):
        self.ultimo, self.valor, self.pedidos, self.metas = ultimo, valor, [], 0
        monkeypatch.setattr(red, "bajar", self.bajar)
        monkeypatch.setattr(ina, "metadata", self.metadata)

    def bajar(self, url, destino):
        from urllib.parse import parse_qs, urlparse

        q = parse_qs(urlparse(url).query)
        serie = int(q["series_id"][0])
        desde = date.fromisoformat(q["timestart"][0][:10])
        hasta = min(date.fromisoformat(q["timeend"][0][:10]), self.ultimo)
        self.pedidos.append((serie, desde, hasta))
        Path(destino).write_text(csv_ina(serie, desde, hasta, self.valor), encoding="utf-8")
        return Path(destino)

    def metadata(self, serie):
        self.metas += 1
        return {"serie_id": serie, "nivel_alerta": 11.0, "nivel_evacuacion": 12.0, "nivel_aguas_bajas": None}


class TestNivelRioIna:
    def test_por_defecto_concordia_altura_los_ultimos_30_dias(self, monkeypatch):
        falso = InaFalso(monkeypatch, valor=lambda d: 5.0 + d.day / 100)
        r = h.nivel_rio_ina(hoy=HOY)
        assert (r["escala"], r["variable"], r["unidad"], r["serie_id"]) == ("Concordia", "H", "m", 79)
        assert falso.pedidos == [(79, HOY - timedelta(days=30), HOY)]
        assert r["agregacion"] == "diaria" and len(r["puntos"]) == 31
        assert r["puntos"][-1] == {"periodo": "2026-10-27", "min": 5.27, "media": 5.27, "max": 5.27, "lecturas": 1}
        assert r["niveles"] == {"alerta": 11.0, "evacuacion": 12.0, "aguas_bajas": None}
        assert (r["dias_de_atraso"], r["ultima_carga"]) == (0, "2026-10-27 17:00Z")
        assert "ATENCIÓN" not in r["nota"]

    def test_caudal_de_salto_grande_arriba(self, monkeypatch):
        InaFalso(monkeypatch)
        r = h.nivel_rio_ina("salto grande arriba", "Q", "2026-10-01", "2026-10-10", hoy=HOY)
        assert (r["serie_id"], r["unidad"]) == (926, "m³/s")

    def test_una_serie_atrasada_lo_dice(self, monkeypatch):
        """El caudal de Concordia trae meses de atraso (medido: última fila del 15/07/2026)."""
        InaFalso(monkeypatch, ultimo=date(2026, 7, 15))
        r = h.nivel_rio_ina("Concordia", "Q", "2026-07-01", hoy=HOY)
        assert r["dias_de_atraso"] == 104
        assert "ATENCIÓN" in r["nota"] and "104 días" in r["nota"]

    def test_un_rango_largo_se_agrega_por_mes(self, monkeypatch):
        InaFalso(monkeypatch)
        r = h.nivel_rio_ina("Concordia", "H", "2024-01-01", "2025-12-31", hoy=HOY)
        assert r["agregacion"] == "mensual" and len(r["puntos"]) == 24
        assert r["puntos"][0]["periodo"] == "2024-01" and r["puntos"][0]["lecturas"] == 31

    def test_un_rango_cerrado_se_pide_una_sola_vez(self, monkeypatch):
        falso = InaFalso(monkeypatch)
        h.nivel_rio_ina("Concordia", "H", "2025-01-01", "2025-02-01", hoy=HOY)
        h.nivel_rio_ina("Concordia", "H", "2025-01-01", "2025-02-01", hoy=HOY)
        assert len(falso.pedidos) == 1 and falso.metas == 1

    def test_escala_desconocida_dice_las_que_hay(self, monkeypatch):
        InaFalso(monkeypatch)
        with pytest.raises(ValueError, match="Concordia"):
            h.nivel_rio_ina("Paysandú", hoy=HOY)

    def test_rango_invertido_o_antes_de_1931(self, monkeypatch):
        InaFalso(monkeypatch)
        with pytest.raises(ValueError, match="anterior"):
            h.nivel_rio_ina(desde="2026-10-10", hasta="2026-10-01", hoy=HOY)
        with pytest.raises(ValueError, match="1931"):
            h.nivel_rio_ina(desde="1920-01-01", hasta="1921-01-01", hoy=HOY)

    def test_un_cuerpo_vacio_se_rechaza_y_no_queda_en_la_cache(self, monkeypatch, cache_temporal):
        InaFalso(monkeypatch)
        monkeypatch.setattr(red, "bajar", lambda url, destino: Path(destino).write_text("", encoding="utf-8"))
        with pytest.raises(ina.InaInvalido):
            h.nivel_rio_ina("Concordia", "H", "2025-01-01", "2025-02-01", hoy=HOY)
        assert not list((cache_temporal / "ina").glob("serie_*.csv"))
