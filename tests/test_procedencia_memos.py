"""Las copias que se leen de un memo o de una caché vigente también son respaldo de la respuesta.

Medido el 2026-11-27 con `scripts/sonda.py`: `resultados_electorales` y `pedidos_de_informes`
respondían con `procedencia` vacía, y la de `compras_estado` traía las cotizaciones del BCU pero no
el ZIP de compras. Las tres leen con el patrón «bajar solo si venció»: la rama de la copia vigente
no anotaba nada.
"""

from __future__ import annotations

from mcp_uruguay import cache
from mcp_uruguay.herramientas import estado


def _archivo(carpeta, nombre, contenido=b"x"):
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / nombre).write_bytes(contenido)
    return carpeta / nombre


def test_archivo_electoral_vigente_queda_en_la_procedencia(cache_temporal, monkeypatch):
    _archivo(cache_temporal / "elecciones", "nacionales-2024_totales.csv")
    monkeypatch.setattr(estado.elecciones, "leer_totales", lambda ruta: [])
    for _ in range(2):  # la primera lee el archivo, la segunda sale del memo
        with cache.vigilar_procedencia() as leidas:
            estado._archivo_electoral("nacionales-2024", "totales")
        assert [c["archivo"] for c in leidas] == ["elecciones/nacionales-2024_totales.csv"]


def test_zip_de_compras_vigente_queda_en_la_procedencia(cache_temporal, monkeypatch):
    _archivo(cache_temporal / "compras", "2025.zip", b"PK\x03\x04")
    monkeypatch.setattr(estado.compras, "leer_adjudicaciones", lambda ruta: [])
    estado._compras_memo.clear()
    for _ in range(2):
        with cache.vigilar_procedencia() as leidas:
            estado._compras(2025)
        assert [c["archivo"] for c in leidas] == ["compras/2025.zip"]


def test_archivo_del_parlamento_vigente_queda_en_la_procedencia(cache_temporal):
    _archivo(cache_temporal / "parlamento", "pedidos-informes.csv")
    with cache.vigilar_procedencia() as leidas:
        estado._archivo_parlamento("pedidos-informes")
    assert [c["archivo"] for c in leidas] == ["parlamento/pedidos-informes.csv"]


def _adj(ocid, org, estado_, proveedor, items, fecha="2025-03-01"):
    from datetime import date as d

    return {
        "ocid": ocid,
        "fecha": d.fromisoformat(fecha),
        "comprador": {"id": org[:3], "nombre": org} if org else None,
        "proveedor": {"id": "1", "nombre": proveedor} if proveedor else None,
        "estado": estado_,
        "items": [
            {
                "descripcion": desc,
                "catalogo": "123",
                "esquema": "x",
                "cantidad": cant,
                "precio_unitario": precio,
                "moneda": moneda,
                "importe": round(cant * precio, 2),
            }
            for desc, cant, precio, moneda in items
        ],
        "importes": {},
        "sin_moneda": 0.0,
    }


def test_las_adjudicaciones_compactas_dan_el_mismo_resumen():
    """Medido el 2026-11-27: el ZIP de 2025 ocupa 343 MB leído tal cual y 142 MB compactado."""
    from uydatos import compras

    adjs = [
        _adj(
            "a", "Intendencia de Salto", "active", "Juan Pérez", [("Hormigón", 10, 5.5, "UYU"), ("Arena", 1, 3, "USD")]
        ),
        _adj("b", "Intendencia de Salto", "active", None, [("Hormigón armado", 2, 100, "UYU")]),
        _adj("c", "ANCAP", "cancelled", "SA", [("Gasoil", 1000, 1.2, "USD")]),
        _adj("d", "", "active", "X", [("Papel", 3, 2, None)]),
    ]
    compacto = estado._compactar_adjudicaciones(adjs)
    for organismo in ("", "intendencia de salto", "ANC", "nadie"):
        for buscar in ("", "hormigon", "PAPEL", "zzz"):
            assert compras.resumen(compacto, organismo, buscar) == compras.resumen(adjs, organismo, buscar)
    assert "Juan Pérez" not in repr(compacto)  # el nombre del proveedor no queda en memoria
    assert compacto[0]["comprador"] is compacto[1]["comprador"]  # el organismo se comparte
