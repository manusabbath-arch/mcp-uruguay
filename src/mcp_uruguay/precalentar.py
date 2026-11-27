"""`mcp-uruguay --precalentar`: baja de una vez lo que con la caché fría tarda de 40 a 75 segundos.

La primera llamada a `leyes`, `compras_estado`, `proyectos_parlamento`, `clima`, `resultados_electorales`
o `ubicar_punto` baja archivos grandes (57 de INIA, 27 MB de compras, CSV electorales de hasta 21 MB, dos
GeoJSON de 4,7 MB) y muchos clientes MCP cortan cerca de los 60 s. Este comando se corre una
vez en la terminal, después de instalar, y deja la caché lista: las llamadas siguientes salen del disco.

Una fuente que no responde no frena a las demás: se anota y se sigue. Las que `guias.CAIDAS` ya declara
caídas (hoy, el Parlamento) se informan como tales y no hacen fallar el comando.
"""

from __future__ import annotations

import functools
import http.client
import time
from typing import Callable

from uydatos import elecciones

from mcp_uruguay import cache, guias
from mcp_uruguay import herramientas as h


def _tareas() -> list[tuple[str, Callable[[], object]]]:
    """Qué herramienta y con qué argumentos: los más baratos que igual bajan el archivo entero."""
    # El año anterior: la tabla de compras del año en curso todavía no existe en la fuente.
    anio = cache.hoy().year - 1
    return [
        ("clima", lambda: h.clima()),
        ("compras_estado", lambda: h.compras_estado(anio, cantidad=1)),
        ("combustible_ancap", lambda: h.combustible_ancap()),
        ("ventas_combustible", lambda: h.ventas_combustible()),
        ("paridad_combustibles", lambda: h.paridad_combustibles()),
        ("ipc_argentina", lambda: h.ipc_argentina(f"{anio}-01", f"{anio}-12")),
        ("ipca_brasil", lambda: h.ipca_brasil(f"{anio}-01", f"{anio}-12")),
        ("localidad", lambda: h.localidad(departamento="Salto", cantidad=1)),
        ("calidad_agua", lambda: h.calidad_agua("Salto")),
        ("nivel_rio_ina", lambda: h.nivel_rio_ina("Concordia", "H")),
        ("leyes", lambda: h.leyes(cantidad=1)),
        ("proyectos_parlamento", lambda: h.proyectos_parlamento(cantidad=1)),
        ("asistencia_parlamentaria", lambda: h.asistencia_parlamentaria("senado")),
        ("pedidos_de_informes", lambda: h.pedidos_de_informes(cantidad=1)),
        # Medido el 2026-11-27: 53 s en frío (CSV de hasta 21 MB) y dos GeoJSON de 4,7 MB.
        *[
            ("resultados_electorales", functools.partial(h.resultados_electorales, eleccion))
            for eleccion in elecciones.ELECCIONES
        ],
        ("ubicar_punto", lambda: h.ubicar_punto(-31.39, -57.96)),
    ]


def tareas_piloto() -> list[tuple[str, Callable[[], object]]]:
    """Llena la cache que usan las tres herramientas de datos del piloto."""
    return [(nombre, tarea) for nombre, tarea in _tareas() if nombre in {"clima", "calidad_agua"}] + [
        ("nivel_rio", lambda: h.nivel_rio("Salto"))
    ]


def precalentar(
    tareas: list[tuple[str, Callable[[], object]]] | None = None,
    salida: Callable[[str], None] = print,
) -> int:
    """Corre cada tarea y cuenta lo que pasó. Devuelve 0 si todo anduvo o solo falló lo ya declarado
    caído, y 1 si alguna fuente falló sin estar en `guias.CAIDAS`."""
    tareas = _tareas() if tareas is None else tareas
    salida(f"Precalentando la caché en {cache.directorio()}")
    inicio = time.monotonic()
    bien = caidas = fallas = 0
    for i, (nombre, tarea) in enumerate(tareas, 1):
        t0 = time.monotonic()
        try:
            tarea()
        except (ValueError, OSError, http.client.HTTPException) as e:
            segundos = time.monotonic() - t0
            if nombre in guias.CAIDAS:
                caidas += 1
                salida(f"[{i}/{len(tareas)}] {nombre}: no responde ({segundos:.0f} s), ya estaba declarada caída")
            else:
                fallas += 1
                salida(f"[{i}/{len(tareas)}] {nombre}: FALLÓ ({segundos:.0f} s): {str(e)[:160]}")
        else:
            bien += 1
            salida(f"[{i}/{len(tareas)}] {nombre}: listo ({time.monotonic() - t0:.1f} s)")
    total = time.monotonic() - inicio
    resumen = f"{bien} listas"
    if caidas:
        resumen += f", {caidas} caídas conocidas"
    if fallas:
        resumen += f", {fallas} con error"
    salida(f"{resumen}, en {total:.0f} s.")
    return 1 if fallas else 0
