"""`resultados_electorales`, sin red: archivos sintéticos con la forma de los de la Corte en la caché."""

from __future__ import annotations

import pytest

from mcp_uruguay import herramientas as h

BALOTAJE = (
    "Departamento,CRV,Serie,TotalHabilitados,TotalVotosEmitidos,TotalVotosNoObservados,"
    "TotalVotosObservados,TotalAnulados,TotalEnBlanco,TotalOrsiCosse,TotalDelgadoRipoll"
)
TOTALES = (
    "Departamento,CRV,Serie,TotalHabilitados,TotalVotosEmitidos,TotalVotosNoObservados,"
    "TotalVotosObservados,TotalAnulados,TotalEnBlanco,TotalSoloSi,SiArt11,SiArt67"
)
DESGLOSE = "TipoRegistro,Departamento,CRV,Series,Lema,Descripcion1,CantidadVotos"


def _escribir(carpeta, nombre, encabezado, filas):
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / nombre).write_text("\ufeff" + "\n".join([encabezado, *filas]) + "\n", encoding="utf-8")


@pytest.fixture
def elecciones(cache_temporal):
    c = cache_temporal / "elecciones"
    _escribir(
        c,
        "balotaje-2024_totales.csv",
        BALOTAJE,
        ["SA,1,BAA,100,90,88,2,3,1,44,40", "SA,9001,BZZ,0,0,2,0,0,0,1,1", "MO,1,AAA,200,180,180,0,5,5,100,70"],
    )
    _escribir(
        c,
        "nacionales-2024_totales.csv",
        TOTALES,
        ["SA,1,BAA,100,90,90,0,4,6,1,10,20", "MO,1,AAA,200,180,180,0,5,5,2,30,40"],
    )
    _escribir(
        c,
        "nacionales-2024_desglose.csv",
        DESGLOSE,
        [
            "HOJA_EN,SA,1,BAA,Partido Frente Amplio,609,40",
            "VOTO_LEMA,SA,1,BAA,Partido Frente Amplio,609;90,2",
            "HOJA_EN,SA,1,BAA,Partido Nacional,40,38",
            "HOJA_EN,MO,1,AAA,Partido Colorado,15,170",
        ],
    )
    return c


class TestBalotaje:
    def test_pais_con_candidatos_y_mesas_de_observados(self, elecciones):
        r = h.resultados_electorales("balotaje-2024")
        assert r["mesas"] == {"comunes": 2, "de_observados": 1}
        assert r["opciones"] == [
            {"opcion": "TotalOrsiCosse", "votos": 145, "pct_sobre_emitidos": 53.7},
            {"opcion": "TotalDelgadoRipoll", "votos": 111, "pct_sobre_emitidos": 41.11},
        ]
        assert "observados" in r["nota"] and "localidad" in r["nota"]
        assert "escrutinio primario" in r["nota"] and "definitivo con observados" in r["nota"]

    def test_por_departamento(self, elecciones):
        r = h.resultados_electorales("balotaje-2024", "salto")
        assert (r["departamento"], r["habilitados"], r["emitidos"]) == ("SALTO", 100, 90)
        assert r["opciones"][0] == {"opcion": "TotalOrsiCosse", "votos": 45, "pct_sobre_emitidos": 50.0}


class TestNacionales:
    def test_partidos_suman_hoja_y_lema(self, elecciones):
        r = h.resultados_electorales("nacionales-2024", "Salto")
        assert r["partidos"][0] == {"lema": "Partido Frente Amplio", "votos": 42, "pct_sobre_emitidos": 46.67}
        assert [p["lema"] for p in r["partidos"]] == ["Partido Frente Amplio", "Partido Nacional"]

    def test_los_plebiscitos_van_como_opciones(self, elecciones):
        r = h.resultados_electorales("nacionales-2024")
        assert {o["opcion"] for o in r["opciones"]} == {"TotalSoloSi", "SiArt11", "SiArt67"}


class TestErrores:
    def test_eleccion_desconocida(self, elecciones):
        with pytest.raises(ValueError, match="balotaje-2024"):
            h.resultados_electorales("municipales-1999")

    def test_departamento_desconocido(self, elecciones):
        with pytest.raises(ValueError, match="SALTO"):
            h.resultados_electorales("balotaje-2024", "Saltoo")


def _fila(depto, codigo, crv, nivel, clase, lema, votos):
    return {
        "codigo_departamento": codigo,
        "departamento": depto,
        "crv": crv,
        "nivel": nivel,
        "clase": clase,
        "lema": lema,
        "hoja": str(crv),
        "municipio": None,
        "votos": votos,
    }


def test_el_desglose_compacto_da_los_mismos_votos_por_lema():
    """Medido el 2026-11-27: el desglose de 2024 son 354.176 filas y ~120 MB en memoria. La
    herramienta solo suma por lema, departamento y nivel: compactado por esa clave, el resultado es
    el mismo con cualquier filtro de departamento (nombre, código o sin tildes)."""
    from uydatos import elecciones

    from mcp_uruguay.herramientas.estado import _compactar_desglose

    filas = [
        _fila("SALTO", "SA", crv, nivel, clase, lema, votos)
        for crv in (1, 2, 3)
        for nivel, clase, lema, votos in [
            ("nacional", "hoja", "Partido Frente Amplio", 40),
            ("nacional", "lema", "Partido Frente Amplio", 2),
            ("nacional", "hoja", "Partido Nacional", 38 + crv),
            ("departamental", "hoja", "Partido Nacional", 7),
        ]
    ] + [_fila("PAYSANDÚ", "PA", 9, "nacional", "hoja", "Partido Colorado", 170)]
    compacto = _compactar_desglose(filas)
    assert len(compacto) < len(filas)
    for nivel in ("nacional", "departamental"):
        for departamento in ("", "salto", "SA", "Paysandu", "PA", "PAYSANDÚ"):
            assert elecciones.votos_por_lema(compacto, nivel, departamento) == elecciones.votos_por_lema(
                filas, nivel, departamento
            ), (nivel, departamento)


def test_la_herramienta_guarda_el_desglose_compacto(elecciones):
    from mcp_uruguay.herramientas import estado

    h.resultados_electorales("nacionales-2024")
    guardados = [v for (ruta, _), v in estado._elecciones.items() if ruta.endswith("_desglose.csv")]
    assert guardados and all(f["crv"] is None for f in guardados[-1])
