"""`mcp-uruguay --precalentar`: una fuente que falla no frena a las demás, y lo ya caído no es un error."""

from __future__ import annotations

import sys

import pytest

from mcp_uruguay import guias, precalentar
from mcp_uruguay import herramientas as h


def _correr(tareas):
    lineas: list[str] = []
    codigo = precalentar.precalentar(tareas, salida=lineas.append)
    return codigo, lineas


def test_todo_anda_y_termina_en_cero():
    codigo, lineas = _correr([("a", lambda: 1), ("b", lambda: 2)])
    assert codigo == 0
    assert "[1/2] a: listo" in lineas[1] and "[2/2] b: listo" in lineas[2]
    assert lineas[-1].startswith("2 listas")


def test_una_fuente_que_falla_no_frena_a_las_demas_y_el_codigo_es_uno():
    def rota():
        raise OSError("sin red")

    ejecutadas = []
    codigo, lineas = _correr([("a", rota), ("b", lambda: ejecutadas.append("b"))])
    assert codigo == 1
    assert ejecutadas == ["b"]
    assert "a: FALLÓ" in lineas[1] and "sin red" in lineas[1]
    assert "1 listas, 1 con error" in lineas[-1]


def test_una_fuente_ya_declarada_caida_no_hace_fallar_el_comando(monkeypatch):
    def caida():
        raise ValueError("403")

    monkeypatch.setitem(guias.CAIDAS, "leyes", "bloqueada")
    codigo, lineas = _correr([("leyes", caida), ("b", lambda: 1)])
    assert codigo == 0
    assert "ya estaba declarada caída" in lineas[1]
    assert "1 caídas conocidas" in lineas[-1]


def test_un_error_que_no_es_de_fuente_no_se_traga():
    """Un bug de este servidor (no un error de red ni un valor rechazado) tiene que verse, no resumirse."""

    def bug():
        raise KeyError("x")

    with pytest.raises(KeyError):
        _correr([("a", bug)])


def test_cada_tarea_apunta_a_una_herramienta_que_existe():
    """Si se renombra una herramienta, el precalentado no puede quedar llamando a la vieja."""
    for nombre, _ in precalentar._tareas():
        assert callable(getattr(h, nombre)), nombre


def test_main_con_precalentar_corre_y_termina_sin_levantar_el_servidor(monkeypatch):
    from mcp_uruguay import servidor

    monkeypatch.setattr(sys, "argv", ["mcp-uruguay", "--precalentar"])
    monkeypatch.setattr(precalentar, "precalentar", lambda: 0)
    monkeypatch.setattr(servidor.servidor, "run", lambda: pytest.fail("no debe levantar el servidor"))
    with pytest.raises(SystemExit) as salida:
        servidor.main()
    assert salida.value.code == 0


def test_precalienta_las_elecciones_y_las_capas_que_tardan_mas_de_50_segundos_en_frio():
    """Medido el 2026-11-27 con `scripts/sonda.py`: `resultados_electorales` (53 s, CSV de hasta
    21 MB por elección) y las capas de `ubicar_punto` (dos GeoJSON de 4,7 MB) no estaban en el
    precalentado. Claude Desktop y Cursor cortan a los ~60 s aunque haya avisos de progreso."""
    from uydatos import elecciones

    nombres = [n for n, _ in precalentar._tareas()]
    assert nombres.count("resultados_electorales") == len(elecciones.ELECCIONES)
    assert "ubicar_punto" in nombres


def test_precalentar_piloto_ejecuta_solo_las_tres_fuentes(monkeypatch):
    from mcp_uruguay import servidor

    monkeypatch.setattr(sys, "argv", ["mcp-uruguay", "--precalentar-piloto"])
    llamadas = []
    for nombre in ("clima", "calidad_agua", "nivel_rio"):
        monkeypatch.setattr(h, nombre, lambda *args, nombre=nombre: llamadas.append((nombre, args)))
    with pytest.raises(SystemExit) as salida:
        servidor.main()
    assert salida.value.code == 0
    assert llamadas == [("clima", ()), ("calidad_agua", ("Salto",)), ("nivel_rio", ("Salto",))]
