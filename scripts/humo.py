"""Prueba de humo del paquete instalado: cada herramienta, contra las fuentes reales, como un usuario.

No usa el código del repo: corre contra lo que `pip`/`uv` instalan desde PyPI, que es lo que recibe
quien lo usa. La corre cada semana `tests.yml` (job `instalado-desde-pypi`), y se puede correr a mano:

    uv run --isolated --no-project --with mcp-uruguay python scripts/humo.py

Sale con 1 si alguna herramienta falla o falta. Una fuente caída también la hace fallar: es un
aviso de que esa herramienta, hoy, no le responde a nadie.
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
    ("nivel_rio", {}),
    ("nivel_rio_comparado", {}),
    ("estaciones_cercanas", {"lat": -31.39, "lon": -57.96}),
    ("geocodificar_direccion", {"direccion": "Uruguay 1000", "localidad": "Salto", "departamento": "Salto"}),
    ("ubicar_punto", {"lat": -31.39, "lon": -57.96}),
    ("localidad", {"nombre": "Salto"}),
    ("resultados_electorales", {"eleccion": "nacionales-2024"}),
    ("compras_estado", {"anio": 2025}),
    ("asistencia_parlamentaria", {"camara": "senado"}),
    ("leyes", {"buscar": "presupuesto"}),
    ("proyectos_parlamento", {"buscar": "agua"}),
    ("pedidos_de_informes", {"organismo": "transporte", "cantidad": 3}),
    ("buscar_indicador_social", {"texto": "pobreza departamento"}),
    ("indicador_social", {"indicador": "tasa-desempleo-segun-quintil-ingreso-total-pais"}),
    ("recursos_catalogo", {"dataset": "inia-precipitacion-temps-extremas-sg"}),
    ("diagnostico", {}),
]


async def main():
    instalada = version("mcp-uruguay")
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
                resultados.append((nombre, "OK" if ok else "ERROR", time.time() - t0, txt))
            except Exception as e:  # noqa: BLE001
                resultados.append((nombre, "EXCEPCION", time.time() - t0, repr(e)[:200]))
    for n, estado, s, txt in resultados:
        print(f"{estado:9s} {s:6.1f}s  {n:26s} {txt}")
    bien = sum(r[1] == "OK" for r in resultados)
    print("RESUMEN", bien, "de", len(resultados))
    return bien == len(resultados) and not faltan and mcp_uruguay.__version__ == instalada


if __name__ == "__main__":
    sys.exit(0 if anyio.run(main) else 1)
