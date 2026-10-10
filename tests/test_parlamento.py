"""Las herramientas del Parlamento, sin red: CSV sintéticos con la forma de los reales en la caché."""

from __future__ import annotations

import pytest

from mcp_uruguay import herramientas as h

ASISTENCIAS = (
    "Nombre,Citaciones,Asistencias,Porcentaje de asistencias,Faltas c/Aviso\t,Porcentaje de faltas,"
    "Cantidad de faltas sin aviso,Porcentaje de faltas s/ aviso,No citado por Licencia,"
    "Pasajes a Presidente de la República"
)
PROYECTOS = "Fecha,Asunto,Carpetas,Titulo"
LEYES = "Fecha,Numero_de_Ley,Texto_Original,Texto_Actualizado,Titulo,Asunto,Leyes_Referenciadas,Leyes_que_referencia"


def _escribir(carpeta, nombre, encabezado, filas):
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / nombre).write_text("\ufeff" + "\n".join([encabezado, *filas]) + "\n", encoding="utf-8")


@pytest.fixture
def parlamento(cache_temporal):
    c = cache_temporal / "parlamento"
    _escribir(
        c,
        "asistencias-senado-50.csv",
        ASISTENCIAS,
        [
            '"Uno, Titular",100,80,80,10,10,10,10,0,0',
            '"Dos, Titular",100,99,99,1,1,0,0,0,0',
            '"Suplente, Tres",2,0,0,2,100,0,0,0,0',
            '"Pérez, Julio",1,1,100,0,0,0,0,0,0',
            '"Pérez, Julio",45,44,98,1,2,0,0,0,0',
        ],
    )
    _escribir(
        c,
        "proyectos-49.csv",
        PROYECTOS,
        [
            '2024-05-02,10,"CSS : 1 / 2024","RIEGO. Se regula (PROYECTO DE LEY)"',
            '2024-06-01,11,,"OTRA COSA (PROYECTO DE RESOLUCION)"',
        ],
    )
    _escribir(
        c,
        "proyectos-50.csv",
        PROYECTOS,
        [
            '2025-03-02,10,"CSS : 1 / 2024","RIEGO. Se regula (PROYECTO DE LEY)"',
            '2025-04-02,12,,"Riego en el litoral (PROYECTO DE LEY)"',
        ],
    )
    for leg in (42, 43, 44, 45, 46, 47, 48):
        _escribir(c, f"proyectos-{leg}.csv", PROYECTOS, [f'19{leg + 43}-05-02,{leg},,"VIEJO (PROYECTO DE LEY)"'])
    _escribir(
        c,
        "leyes.csv",
        LEYES,
        [
            "2026-10-01,20531,https://p/20531,https://www.impo.com.uy/bases/leyes/20531-2026,"
            "RENDICIÓN DE CUENTAS. EJERCICIO 2025.,173797,2,0",
            "2025-12-01,20500,https://p/20500,https://www.impo.com.uy/bases/leyes/20500-2025,"
            "RIEGO CON DESTINO AGRARIO.,1,0,3",
            "2009-09-11,18547,u,v,CONVENIO.,36961,0,0",
            "2009-09-11,18547,u,v,CONVENIO.,36961,0,0",
        ],
    )
    return c


class TestAsistencia:
    def test_ranking_con_minimo_y_avisos(self, parlamento):
        r = h.asistencia_parlamentaria("senado", 50, minimo_citaciones=10)
        assert [f["nombre"] for f in r["menor_asistencia"]][:2] == ["Uno, Titular", "Pérez, Julio"]
        assert r["fuera_por_pocas_citaciones"] == 2
        assert r["nombres_repetidos"] == ["Pérez, Julio"]
        assert "suplentes" in r["nota"] and "homónimos" in r["nota"]

    def test_buscar_por_nombre(self, parlamento):
        r = h.asistencia_parlamentaria("senado", 50, nombre="perez")
        assert [f["citaciones"] for f in r["encontrados"]] == [1, 45]

    def test_legislatura_fuera_de_rango(self, parlamento):
        with pytest.raises(ValueError, match="46"):
            h.asistencia_parlamentaria("senado", 40)


class TestLeyes:
    def test_buscar_por_texto_sin_tildes(self, parlamento):
        r = h.leyes(buscar="rendicion")
        assert [x["numero"] for x in r["leyes"]] == [20531]
        assert r["leyes"][0]["texto_impo"].startswith("https://www.impo.com.uy")

    def test_por_numero_y_por_fechas(self, parlamento):
        assert h.leyes(numero=20500)["leyes"][0]["titulo"] == "RIEGO CON DESTINO AGRARIO."
        assert [x["numero"] for x in h.leyes(desde="2025-01-01", hasta="2025-12-31")["leyes"]] == [20500]

    def test_declara_lo_que_dejo_afuera(self, parlamento):
        r = h.leyes()
        assert r["total"] == 3 and r["duplicadas_descartadas"] == 1


class TestProyectos:
    def test_un_asunto_en_dos_legislaturas_cuenta_una_vez(self, parlamento):
        r = h.proyectos_parlamento(buscar="riego")
        assert r["total"] == 2
        diez = next(p for p in r["proyectos"] if p["asunto"] == 10)
        assert diez["legislaturas"] == [49, 50]

    def test_por_legislatura_y_tipo(self, parlamento):
        r = h.proyectos_parlamento(legislatura=49, tipo="resolucion")
        assert [p["asunto"] for p in r["proyectos"]] == [11]
