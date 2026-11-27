"""La evaluación de exactitud: preguntas con respuesta oficial, contestadas por un agente con y sin el servidor.

Sigue la guía de Anthropic para herramientas de agentes («Writing effective tools for agents»): tareas
realistas con un resultado verificable, un conjunto `reservado` que no se mira al ajustar, y por
pregunta las métricas que dicen dónde mejorar: acierto, llamadas a herramientas, errores de
herramienta, tokens y tiempo.

Tres tipos de pregunta:

- `numero`: el agente termina con `RESPUESTA: <número>` y se compara contra `esperado` ± `tolerancia`.
- `texto`: la línea `RESPUESTA:` tiene que contener `patron` (sin tildes ni mayúsculas).
- `comportamiento`: las trampas. Lo correcto no es un número sino avisar (no hay cotización un
  domingo, un `<0,2` no se promedia, el caudal viene con meses de atraso). Cada expresión de
  `debe_mencionar` tiene que aparecer en la respuesta completa.

Las respuestas esperadas salen de la publicación oficial, nunca de este servidor: medir contra lo
que devuelve el propio servidor sería circular. `preguntas.json` dice de dónde salió cada una.

Uso (necesita una clave de la API de Claude; cada corrida cuesta dinero, ver `evals/README.md`):

    uv run --with anthropic python evals/evaluar.py --modo con,sin --conjunto desarrollo
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

AQUI = Path(__file__).resolve().parent
PREGUNTAS = AQUI / "preguntas.json"
MODELO = "claude-opus-5-5"
MAX_TURNOS = 15
#: sin = solo el modelo; con = las herramientas; guiado = además las instrucciones y los recursos.
MODOS = ("con", "sin", "guiado", "sin_catalogo")
LECTOR = "leer_recurso"  # no es una herramienta del servidor: la agrega el modo guiado

SISTEMA = """\
Respondés preguntas sobre datos públicos de Uruguay y la región. Usá las herramientas cuando las \
tengas y citá de dónde sale cada número. Si no podés responder con un dato verificable, decilo: un \
número inventado es peor que no responder.

Terminá siempre con una última línea, sola, con este formato exacto:
RESPUESTA: <valor>
donde <valor> es un número sin separador de miles y con punto decimal (por ejemplo 1234.5), una \
fecha AAAA-MM-DD o un texto corto. Si no hay un dato verificable, escribí RESPUESTA: SIN DATO."""


# --- Verificación ------------------------------------------------------------------------------------


def _normal(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def linea_respuesta(texto: str) -> Optional[str]:
    """El valor de la última línea `RESPUESTA:`; None si el agente no la escribió."""
    encontradas = re.findall(r"^\s*\**RESPUESTA\**\s*:\s*(.+?)\s*$", texto, flags=re.M | re.I)
    return encontradas[-1].strip().strip("*`").strip() if encontradas else None


def numero(valor: str) -> Optional[float]:
    """Un número de la línea de respuesta. Acepta `1.234.567` y `49,84` además del formato pedido."""
    m = re.search(r"-?\d[\d.,]*", valor)
    if not m:
        return None
    t = m.group(0).rstrip(".,")
    # Separador de miles solo con dos grupos o más (1.101.296), que no puede ser decimal. Con un solo
    # grupo («136.195») vale el formato pedido, punto decimal: leerlo según lo esperado sería trampa.
    if re.fullmatch(r"-?\d{1,3}(\.\d{3}){2,}", t):
        t = t.replace(".", "")
    elif re.fullmatch(r"-?\d{1,3}(,\d{3}){2,}", t):
        t = t.replace(",", "")
    elif "," in t and "." not in t:  # 49,84: coma decimal
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def verificar(pregunta: dict, texto: str) -> dict:
    """{'correcta': bool, 'motivo': str, 'valor': ...} para la respuesta final del agente."""
    final = linea_respuesta(texto)
    tipo = pregunta["tipo"]
    if tipo == "comportamiento":
        normal = _normal(texto)
        faltan = [p for p in pregunta["debe_mencionar"] if not re.search(p, normal, flags=re.I)]
        return {
            "correcta": not faltan,
            "motivo": "menciona lo que tiene que mencionar" if not faltan else f"no menciona: {faltan}",
            "valor": final,
        }
    if final is None:
        return {"correcta": False, "motivo": "no escribió la línea RESPUESTA:", "valor": None}
    if tipo == "texto":
        ok = re.search(pregunta["patron"], _normal(final), flags=re.I) is not None
        return {"correcta": ok, "motivo": "coincide" if ok else f"esperaba {pregunta['patron']!r}", "valor": final}
    if tipo == "numero":
        v = numero(final)
        if v is None:
            return {"correcta": False, "motivo": f"la respuesta {final!r} no es un número", "valor": final}
        diferencia = abs(v - pregunta["esperado"])
        ok = diferencia <= pregunta["tolerancia"] + 1e-9
        return {
            "correcta": ok,
            "motivo": "dentro de la tolerancia"
            if ok
            else f"esperaba {pregunta['esperado']} ± {pregunta['tolerancia']}",
            "valor": v,
        }
    raise ValueError(f"{pregunta['id']}: tipo desconocido {tipo!r}")


def cargar(conjunto: str = "todos", ids: Optional[list[str]] = None, archivo: Optional[Path] = None) -> list[dict]:
    preguntas = json.loads((archivo or PREGUNTAS).read_text(encoding="utf-8"))["preguntas"]
    if conjunto != "todos":
        preguntas = [p for p in preguntas if p["conjunto"] == conjunto]
    if ids:
        preguntas = [p for p in preguntas if p["id"] in ids]
    return preguntas


# --- El agente ---------------------------------------------------------------------------------------


def _texto_de(resultado: Any) -> str:
    """El resultado de una herramienta MCP como texto: el contenido estructurado si lo hay."""
    estructurado = getattr(resultado, "structured_content", None)
    if estructurado is not None:
        return json.dumps(estructurado, ensure_ascii=False, default=str)
    partes = [getattr(c, "text", "") for c in (getattr(resultado, "content", None) or [])]
    return "\n".join(p for p in partes if p)


async def herramientas_de(sesion) -> list[dict]:
    """Las herramientas del servidor en el formato de la API de Claude."""
    lista = (await sesion.list_tools()).tools
    return [{"name": t.name, "description": t.description or "", "input_schema": t.input_schema} for t in lista]


async def lector_de_recursos(sesion) -> dict:
    """La herramienta con la que el agente lee los recursos del servidor, como lo haría un cliente."""
    recursos = sorted((await sesion.list_resources()).resources, key=lambda r: str(r.uri))
    indice = "\n".join(f"- {r.uri}: {r.description or r.name}" for r in recursos)
    return {
        "name": LECTOR,
        "description": f"Lee un recurso de referencia del servidor.\n{indice}",
        "input_schema": {
            "type": "object",
            "properties": {"uri": {"type": "string", "enum": [str(r.uri) for r in recursos]}},
            "required": ["uri"],
        },
    }


async def preguntar(
    cliente,
    pregunta: str,
    *,
    sesion=None,
    herramientas=None,
    instrucciones: Optional[str] = None,
    modelo=MODELO,
    esfuerzo="medium",
):
    """Corre el ciclo del agente sobre una pregunta y devuelve el texto final y las métricas.

    Con `sesion` (un cliente MCP conectado al servidor), las herramientas son las del servidor; sin
    sesión, el agente responde solo con lo que sabe. `instrucciones` se agrega al prompt de sistema.
    Ciclo propio y no el tool runner del SDK porque cada llamada se cuenta y se registra, y porque así
    se prueba con un cliente falso."""
    mensajes: list[dict] = [{"role": "user", "content": pregunta}]
    m = {
        "llamadas": [],
        "argumentos": [],
        "recursos_leidos": [],
        "errores_herramienta": 0,
        "tokens_entrada": 0,
        "tokens_salida": 0,
        "tokens_cache_leidos": 0,
        "turnos": 0,
    }
    parametros: dict[str, Any] = {
        "model": modelo,
        "max_tokens": 16000,
        "system": f"{SISTEMA}\n\nInstrucciones del servidor:\n{instrucciones}" if instrucciones else SISTEMA,
        "output_config": {"effort": esfuerzo},
        # Las definiciones de las herramientas (~7.400 tokens) y el sistema son iguales en cada turno y
        # en cada pregunta: la caché de prompts los cobra una vez y después a una fracción.
        "cache_control": {"type": "ephemeral"},
    }
    if herramientas:
        parametros["tools"] = herramientas
    # Solo se leen recursos si el lector se ofreció: en `con`, pedirlo es una herramienta desconocida.
    ofrecidas = {t["name"] for t in herramientas or []}
    con_lector = LECTOR in ofrecidas
    inicio = time.monotonic()
    texto, motivo_fin = "", ""
    while m["turnos"] < MAX_TURNOS:
        m["turnos"] += 1
        r = await cliente.messages.create(messages=mensajes, **parametros)
        m["tokens_entrada"] += r.usage.input_tokens
        m["tokens_salida"] += r.usage.output_tokens
        m["tokens_cache_leidos"] += getattr(r.usage, "cache_read_input_tokens", 0) or 0
        motivo_fin = r.stop_reason
        texto = "\n".join(b.text for b in r.content if b.type == "text")
        # El contenido completo, con los bloques de razonamiento, vuelve tal cual en el turno siguiente.
        mensajes.append({"role": "assistant", "content": r.content})
        if r.stop_reason == "pause_turn":
            continue
        if r.stop_reason != "tool_use":
            break
        resultados = []
        for b in r.content:
            if b.type != "tool_use":
                continue
            m["llamadas"].append(b.name)
            m["argumentos"].append({"herramienta": b.name, "argumentos": b.input})
            try:
                if b.name not in ofrecidas:
                    raise ValueError("herramienta no ofrecida en este modo")
                if con_lector and b.name == LECTOR:
                    uri = b.input["uri"]
                    res = await sesion.read_resource(uri)
                    es_error, contenido = False, "\n".join(getattr(c, "text", "") for c in res.contents)
                    m["recursos_leidos"].append(uri)
                else:
                    res = await sesion.call_tool(b.name, b.input)
                    es_error = bool(getattr(res, "is_error", False))
                    contenido = _texto_de(res)
            except Exception as e:  # la herramienta falló: el agente lo ve como error, la corrida sigue
                es_error, contenido = True, f"{type(e).__name__}: {e}"
            m["errores_herramienta"] += es_error
            resultados.append({"type": "tool_result", "tool_use_id": b.id, "content": contenido, "is_error": es_error})
        # Todos los resultados en un solo mensaje: separarlos desalienta las llamadas en paralelo.
        mensajes.append({"role": "user", "content": resultados})
    else:
        motivo_fin = "max_turnos"
    m["segundos"] = round(time.monotonic() - inicio, 1)
    m["motivo_fin"] = motivo_fin
    return texto, m


async def correr(cliente, preguntas: list[dict], modos: list[str], *, modelo=MODELO, esfuerzo="medium", repeticiones=1):
    """Cada pregunta, en cada modo, `repeticiones` veces. Devuelve una fila por intento."""
    from mcp import Client

    from mcp_uruguay.servidor import servidor

    filas = []
    async with Client(servidor) as sesion:
        herramientas = await herramientas_de(sesion)
        # Lo que recibe el agente en cada modo.
        servidor_en = {
            "sin": {},
            "con": {"sesion": sesion, "herramientas": herramientas},
            "sin_catalogo": {
                "sesion": sesion,
                "herramientas": [t for t in herramientas if t["name"] != "buscar_datasets_catalogo"],
            },
        }
        if "guiado" in modos:
            servidor_en["guiado"] = {
                "sesion": sesion,
                "herramientas": [*herramientas, await lector_de_recursos(sesion)],
                "instrucciones": sesion.instructions,
            }
        for p in preguntas:
            for modo in modos:
                for n in range(repeticiones):
                    texto, m = await preguntar(
                        cliente,
                        p["pregunta"],
                        **servidor_en[modo],
                        modelo=modelo,
                        esfuerzo=esfuerzo,
                    )
                    v = (
                        verificar(p, texto)
                        if m["motivo_fin"] != "refusal"
                        else {"correcta": False, "motivo": "el modelo declinó (refusal)", "valor": None}
                    )
                    filas.append(
                        {
                            "id": p["id"],
                            "conjunto": p["conjunto"],
                            "tipo": p["tipo"],
                            "modo": modo,
                            "categoria": p.get("categoria"),
                            "herramienta_correcta": (p["herramienta"] in m["llamadas"] if "herramienta" in p else None),
                            "intento": n + 1,
                            **v,
                            **m,
                            "respuesta": texto,
                        }
                    )
                    print(f"{p['id']:<34} {modo:<6} {'OK' if v['correcta'] else '--'}  {v['motivo']}", file=sys.stderr)
    return filas


def resumen_observatorio(filas: list[dict]) -> str:
    lineas = [
        "| modo | categoria | respuesta correcta | herramienta esperada | segundo p95 |",
        "|---|---|---:|---:|---:|",
    ]
    grupos = {(f["modo"], f["categoria"]) for f in filas if f.get("categoria")}
    for modo, categoria in sorted(grupos):
        grupo = [f for f in filas if f["modo"] == modo and f.get("categoria") == categoria]
        aciertos = sum(f["correcta"] for f in grupo)
        esperadas = [f["herramienta_correcta"] for f in grupo if f["herramienta_correcta"] is not None]
        eleccion = f"{sum(esperadas)}/{len(esperadas)}" if esperadas else "-"
        tiempos = sorted(f["segundos"] for f in grupo)
        p95 = tiempos[(95 * len(tiempos) + 99) // 100 - 1]
        lineas.append(f"| {modo} | {categoria} | {aciertos}/{len(grupo)} | {eleccion} | {p95:.1f} |")
    return "\n".join(lineas) + "\n"


def resumen(filas: list[dict]) -> str:
    """La tabla para el README: acierto por modo y tipo, llamadas y tokens."""
    lineas = [
        "| modo | tipo | aciertos | llamadas promedio | errores de herramienta | tokens promedio |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for modo in sorted({f["modo"] for f in filas}):
        for tipo in ["numero", "texto", "comportamiento", "todas"]:
            g = [f for f in filas if f["modo"] == modo and (tipo == "todas" or f["tipo"] == tipo)]
            if not g:
                continue
            ok = sum(f["correcta"] for f in g)
            llamadas = sum(len(f["llamadas"]) for f in g) / len(g)
            errores = sum(f["errores_herramienta"] for f in g)
            tokens = sum(f["tokens_entrada"] + f["tokens_salida"] for f in g) / len(g)
            nombre = f"**{tipo}**" if tipo == "todas" else tipo
            aciertos = f"{ok}/{len(g)} ({100 * ok / len(g):.0f}%)"
            lineas.append(f"| {modo} | {nombre} | {aciertos} | {llamadas:.1f} | {errores} | {tokens:,.0f} |")
    return "\n".join(lineas) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    import anyio

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--modo",
        default="con,sin",
        help="separados por coma: con, sin (con y sin el servidor) o guiado (además instrucciones y recursos)",
    )
    ap.add_argument("--conjunto", default="desarrollo", choices=["desarrollo", "reservado", "todos"])
    ap.add_argument("--archivo", type=Path, help="banco de preguntas aparte del conjunto habitual")
    ap.add_argument("--id", action="append", help="solo esta pregunta (se puede repetir)")
    ap.add_argument("--modelo", default=MODELO)
    ap.add_argument("--esfuerzo", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--repeticiones", type=int, default=1)
    ap.add_argument("--salida", type=Path, default=AQUI / "resultados")
    args = ap.parse_args(argv)
    modos = [m.strip() for m in args.modo.split(",") if m.strip()]
    if not modos or set(modos) - set(MODOS):
        ap.error(f"--modo {args.modo!r}: los modos válidos son {', '.join(MODOS)}")

    import anthropic  # solo para correr de verdad: los tests usan un cliente falso

    preguntas = cargar(args.conjunto, args.id, args.archivo)
    if not preguntas:
        print("ninguna pregunta con esos filtros", file=sys.stderr)
        return 2
    filas = anyio.run(
        lambda: correr(
            anthropic.AsyncAnthropic(),
            preguntas,
            modos,
            modelo=args.modelo,
            esfuerzo=args.esfuerzo,
            repeticiones=args.repeticiones,
        )
    )
    sello = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.salida.mkdir(parents=True, exist_ok=True)
    # `modelo:cloud` o `org/modelo` no sirven en un nombre de archivo: en NTFS el `:` abre un flujo
    # alternativo y queda un archivo vacío. El nombre exacto va dentro del JSON.
    nombre = re.sub(r"[^\w.-]", "-", args.modelo)
    destino = args.salida / f"{sello}-{nombre}-{args.conjunto}.json"
    destino.write_text(
        json.dumps(
            {"modelo": args.modelo, "esfuerzo": args.esfuerzo, "conjunto": args.conjunto, "filas": filas},
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(resumen(filas))
    if any(f.get("categoria") for f in filas):
        print(resumen_observatorio(filas))
    print(f"detalle: {destino}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
