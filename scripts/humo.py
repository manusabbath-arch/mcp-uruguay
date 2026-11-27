"""Prueba de humo del paquete instalado: cada herramienta, contra las fuentes reales, como un usuario.

No usa el código del repo: corre contra lo que `pip`/`uv` instalan desde PyPI, que es lo que recibe
quien lo usa. La corre cada semana `tests.yml` (job `instalado-desde-pypi`), y se puede correr a mano:

    uv run --isolated --no-project --with mcp-uruguay python scripts/humo.py

Sale con 1 si alguna herramienta falla o falta. Una fuente caída también la hace fallar: es un
aviso de que esa herramienta, hoy, no le responde a nadie.

La excepción es `CAIDAS_CONOCIDAS`: una fuente que ya se sabe caída, con su issue abierto, se informa
como `CAIDA` y no pone la corrida en rojo. Un rojo todos los lunes por lo mismo deja de mirarse, y
tapa la caída siguiente. Si una de esas vuelve a responder, la corrida falla con `VOLVIO`: hay que
sacarla de la lista y cerrar el issue.
"""

import json
import sys
import time
from importlib.metadata import version

import anyio
from mcp import Client

import mcp_uruguay
from mcp_uruguay.servidor import servidor

LLAMADAS = [
    ("validar_documento", {"numero": "1.234.567-2", "tipo": "ci"}),
    ("semana", {"fecha": "2026-10-11"}),
    ("feriados", {"anio": 2027}),
    ("cotizacion", {"moneda": "USD", "fecha": "2026-10-09"}),
    ("cotizacion_mensual", {"moneda": "USD", "desde": "2026-08", "hasta": "2026-09"}),
    ("pesos_constantes", {"montos": {"2025-01": 1000}, "base": "2026-08"}),
    ("variacion_real", {"monto_inicial": 1000, "mes_inicial": "2025-01", "monto_final": 1100, "mes_final": "2026-08"}),
    ("ipc_argentina", {"desde": "2026-01", "hasta": "2026-03"}),
    ("ipca_brasil", {"desde": "2026-01", "hasta": "2026-03"}),
    ("combustible_ancap", {}),
    ("ventas_combustible", {"linea": "GAS OIL", "mercado": "INTERNO", "desde": "2026-01"}),
    ("paridad_combustibles", {}),
    ("clima", {}),
    ("observaciones_inumet", {"variable": "temperatura"}),
    ("nivel_rio", {}),
    ("nivel_rio_comparado", {}),
    ("nivel_rio_ina", {}),
    ("estaciones_cercanas", {"lat": -31.39, "lon": -57.96}),
    ("geocodificar_direccion", {"direccion": "Uruguay 1000", "localidad": "Salto", "departamento": "Salto"}),
    ("ubicar_punto", {"lat": -31.39, "lon": -57.96}),
    ("localidad", {"nombre": "Salto"}),
    ("calidad_agua", {"localidad": "Salto", "parametro": "turbidez", "desde": "2025"}),
    ("resultados_electorales", {"eleccion": "nacionales-2024"}),
    ("compras_estado", {"anio": 2025}),
    ("asistencia_parlamentaria", {"camara": "senado"}),
    ("leyes", {"buscar": "presupuesto"}),
    ("proyectos_parlamento", {"buscar": "agua"}),
    ("pedidos_de_informes", {"organismo": "transporte", "cantidad": 3}),
    ("buscar_indicador_social", {"texto": "pobreza departamento"}),
    ("indicador_social", {"indicador": "tasa-desempleo-segun-quintil-ingreso-total-pais"}),
    ("buscar_datasets_catalogo", {"consulta": "Salto", "limite": 3}),
    ("recursos_catalogo", {"dataset": "inia-precipitacion-temps-extremas-sg"}),
    ("diagnostico", {}),
]

# herramienta -> número del issue que la sigue. La misma lista que `mcp_uruguay.guias.CAIDAS`: está
# repetida porque este script corre contra el paquete de PyPI, que puede ser anterior a la lista.
CAIDAS_CONOCIDAS: dict[str, int] = {"leyes": 2}


def clasificar(nombre: str, ok: bool, vencida: bool = False) -> str:
    """`OK` o `ERROR`; para una caída conocida, `CAIDA` si sigue caída y `VOLVIO` si ya responde.

    `vencida`: la respuesta salió de una copia guardada porque la fuente no respondió
    (`copia_vencida`). No cuenta como respuesta de la fuente: es `VENCIDA`, o `CAIDA` si ya se sabía.
    """
    if nombre in CAIDAS_CONOCIDAS:
        return "VOLVIO" if ok and not vencida else "CAIDA"
    if not ok:
        return "ERROR"
    return "VENCIDA" if vencida else "OK"


def _version_del_repo() -> str:
    """La versión de `pyproject.toml` de este repo: la que todavía puede no estar en PyPI."""
    import re
    from pathlib import Path

    texto = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version = "([^"]+)"', texto, re.M).group(1)


def _tupla(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split(".") if x.isdigit())


async def main():
    instalada = version("mcp-uruguay")
    # Una herramienta que el repo ya tiene y PyPI todavía no (la versión del repo es más nueva que la
    # publicada) no es una falla del paquete: es la próxima versión. Pasó el 2026-11-16 con
    # `calidad_agua` y `nivel_rio_ina`, de la 0.14.0, contra la 0.13.2 publicada.
    del_repo = _version_del_repo()
    sin_publicar_aun = _tupla(del_repo) > _tupla(instalada)
    print("mcp-uruguay", instalada, "anuncia", mcp_uruguay.__version__, "· python", sys.version.split()[0])
    resultados = []
    async with Client(servidor) as c:
        herramientas = {t.name: t for t in (await c.list_tools()).tools}
        print("herramientas publicadas:", len(herramientas))
        faltan = sorted(set(herramientas) - {n for n, _ in LLAMADAS})
        if faltan:
            print("SIN PROBAR:", faltan)
        for nombre, args in LLAMADAS:
            if nombre not in herramientas:
                if sin_publicar_aun:
                    resultados.append((nombre, "SIN PUBLICAR", 0, f"está en {del_repo} (repo), no en {instalada}"))
                else:
                    resultados.append((nombre, "NO EXISTE", 0, ""))
                continue
            esquema = herramientas[nombre].input_schema.get("properties", {})
            malos = set(args) - set(esquema)
            if malos:
                resultados.append((nombre, "ARGS", 0, f"parametros reales: {list(esquema)}"))
                continue
            t0 = time.time()
            try:
                r = await c.call_tool(nombre, args)
                ok = not r.is_error and r.structured_content is not None
                txt = json.dumps(r.structured_content, ensure_ascii=False)[:110] if ok else str(r.content)[:200]
                vencida = ok and bool(r.structured_content.get("copia_vencida"))
                resultados.append((nombre, clasificar(nombre, ok, vencida), time.time() - t0, txt))
            except Exception as e:  # noqa: BLE001
                resultados.append((nombre, "EXCEPCION", time.time() - t0, repr(e)[:200]))
    for n, estado, s, txt in resultados:
        print(f"{estado:12s} {s:6.1f}s  {n:26s} {txt}")
    # Ni una herramienta sin publicar todavía ni una caída conocida son fallas del paquete.
    probadas = [r for r in resultados if r[1] != "SIN PUBLICAR"]
    bien = sum(r[1] == "OK" for r in probadas)
    caidas = [r[0] for r in probadas if r[1] == "CAIDA"]
    print("RESUMEN", bien, "de", len(probadas), f"(y {len(resultados) - len(probadas)} sin publicar todavía)")
    for n in caidas:
        print(f"CAIDA CONOCIDA {n}: issue #{CAIDAS_CONOCIDAS[n]}")
    for n in (r[0] for r in probadas if r[1] == "VOLVIO"):
        print(f"VOLVIO {n}: sacarla de CAIDAS_CONOCIDAS y de guias.CAIDAS, y cerrar el issue #{CAIDAS_CONOCIDAS[n]}")
    return bien + len(caidas) == len(probadas) and not faltan and mcp_uruguay.__version__ == instalada


if __name__ == "__main__":
    sys.exit(0 if anyio.run(main) else 1)
