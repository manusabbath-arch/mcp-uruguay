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

import confirmar

AQUI = Path(__file__).resolve().parent
PREGUNTAS = AQUI / "preguntas.json"
MODELO = "claude-opus-5-5"
MAX_TURNOS = 15

#: US$ por millón de tokens. Solo modelos con precio publicado: uno que no está devuelve costo `None`
#: (sin dato), nunca 0. La caché se cobra como en la API de Claude: leer a 0,1x la entrada y escribir
#: (5 minutos) a 1,25x. `--precio ENTRADA,SALIDA` agrega uno para una corrida.
PRECIOS: dict[str, dict[str, float]] = {
    "claude-opus-5-5": {"entrada": 4.0, "salida": 20.0, "cache_leido": 0.4, "cache_escrito": 5.0},
}


def tokens_totales(m: dict) -> int:
    """Todo lo que el modelo procesó: entrada, salida y caché (leída y escrita).

    Es lo que cuenta el presupuesto: con caché de prompts la entrada nueva es casi cero y un tope que
    solo mirara entrada + salida no cortaría nunca."""
    return sum(m.get(k, 0) for k in ("tokens_entrada", "tokens_salida", "tokens_cache_leidos", "tokens_cache_escritos"))


def precio_de(entrada: float, salida: float) -> dict[str, float]:
    return {"entrada": entrada, "salida": salida, "cache_leido": entrada * 0.1, "cache_escrito": entrada * 1.25}


def costo_usd(m: dict, modelo: str) -> Optional[float]:
    """Lo que costó un intento según sus tokens; `None` si el modelo no tiene precio en `PRECIOS`."""
    p = PRECIOS.get(modelo)
    if p is None:
        return None
    return (
        m.get("tokens_entrada", 0) * p["entrada"]
        + m.get("tokens_salida", 0) * p["salida"]
        + m.get("tokens_cache_leidos", 0) * p["cache_leido"]
        + m.get("tokens_cache_escritos", 0) * p["cache_escrito"]
    ) / 1_000_000


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


def cargar(conjunto: str = "todos", ids: Optional[list[str]] = None) -> list[dict]:
    preguntas = json.loads(PREGUNTAS.read_text(encoding="utf-8"))["preguntas"]
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


async def preguntar(
    cliente,
    pregunta: str,
    *,
    sesion=None,
    herramientas=None,
    modelo=MODELO,
    esfuerzo="medium",
    presupuesto_tokens: Optional[int] = None,
):
    """Corre el ciclo del agente sobre una pregunta y devuelve el texto final y las métricas.

    Con `sesion` (un cliente MCP conectado al servidor), las herramientas son las del servidor; sin
    sesión, el agente responde solo con lo que sabe. Ciclo propio y no el tool runner del SDK porque
    cada llamada se cuenta y se registra, y porque así se prueba con un cliente falso.

    La traza queda en `pasos` (una entrada por llamada a herramienta: turno, argumentos, segundos, error
    y tamaño del resultado) y `turnos_detalle` (tokens y segundos de cada turno del modelo). Con
    `presupuesto_tokens`, cuando los tokens acumulados (`tokens_totales`) lo alcanzan el ciclo corta antes del turno
    siguiente (`motivo_fin = "presupuesto_agotado"`): un tope duro, no una estimación."""
    mensajes: list[dict] = [{"role": "user", "content": pregunta}]
    m = {
        "llamadas": [],
        "errores_herramienta": 0,
        "tokens_entrada": 0,
        "tokens_salida": 0,
        "tokens_cache_leidos": 0,
        "tokens_cache_escritos": 0,
        "turnos": 0,
        "pasos": [],
        "turnos_detalle": [],
        "presupuesto_agotado": False,
    }
    parametros: dict[str, Any] = {
        "model": modelo,
        "max_tokens": 16000,
        "system": SISTEMA,
        "output_config": {"effort": esfuerzo},
        # Las definiciones de las herramientas (~7.400 tokens) y el sistema son iguales en cada turno y
        # en cada pregunta: la caché de prompts los cobra una vez y después a una fracción.
        "cache_control": {"type": "ephemeral"},
    }
    if herramientas:
        parametros["tools"] = herramientas
    inicio = time.monotonic()
    texto, motivo_fin = "", ""
    while m["turnos"] < MAX_TURNOS:
        m["turnos"] += 1
        t0 = time.monotonic()
        r = await cliente.messages.create(messages=mensajes, **parametros)
        uso = {
            "turno": m["turnos"],
            "tokens_entrada": r.usage.input_tokens,
            "tokens_salida": r.usage.output_tokens,
            "tokens_cache_leidos": getattr(r.usage, "cache_read_input_tokens", 0) or 0,
            "tokens_cache_escritos": getattr(r.usage, "cache_creation_input_tokens", 0) or 0,
            "segundos": round(time.monotonic() - t0, 2),
        }
        m["turnos_detalle"].append(uso)
        for k in ("tokens_entrada", "tokens_salida", "tokens_cache_leidos", "tokens_cache_escritos"):
            m[k] += uso[k]
        motivo_fin = r.stop_reason
        texto = "\n".join(b.text for b in r.content if b.type == "text")
        # El contenido completo, con los bloques de razonamiento, vuelve tal cual en el turno siguiente.
        mensajes.append({"role": "assistant", "content": r.content})
        if r.stop_reason not in ("pause_turn", "tool_use"):
            break
        if presupuesto_tokens is not None and tokens_totales(m) >= presupuesto_tokens:
            motivo_fin, m["presupuesto_agotado"] = "presupuesto_agotado", True
            break
        if r.stop_reason == "pause_turn":
            continue
        resultados = []
        for b in r.content:
            if b.type != "tool_use":
                continue
            m["llamadas"].append(b.name)
            t1 = time.monotonic()
            try:
                res = await sesion.call_tool(b.name, b.input)
                es_error = bool(getattr(res, "is_error", False))
                contenido = _texto_de(res)
            except Exception as e:  # la herramienta falló: el agente lo ve como error, la corrida sigue
                es_error, contenido = True, f"{type(e).__name__}: {e}"
            m["errores_herramienta"] += es_error
            m["pasos"].append(
                {
                    "turno": m["turnos"],
                    "herramienta": b.name,
                    "argumentos": b.input,
                    "segundos": round(time.monotonic() - t1, 2),
                    "error": es_error,
                    "bytes_resultado": len(contenido.encode("utf-8")),
                    "resultado": contenido,
                }
            )
            resultados.append({"type": "tool_result", "tool_use_id": b.id, "content": contenido, "is_error": es_error})
        # Todos los resultados en un solo mensaje: separarlos desalienta las llamadas en paralelo.
        mensajes.append({"role": "user", "content": resultados})
    else:
        motivo_fin = "max_turnos"
    m["segundos"] = round(time.monotonic() - inicio, 1)
    m["motivo_fin"] = motivo_fin
    return texto, m


async def correr(
    cliente,
    preguntas: list[dict],
    modos: list[str],
    *,
    modelo=MODELO,
    esfuerzo="medium",
    repeticiones=1,
    presupuesto_tokens: Optional[int] = None,
    motor: str = "api",
    preguntar_cli=None,
):
    """Cada pregunta, en cada modo, `repeticiones` veces. Devuelve una fila por intento.

    `motor="claude-cli"` corre cada pregunta con Claude Code headless (`motor_claude_cli.py`) en vez de
    la API; el costo es el que informa Claude Code. `preguntar_cli` reemplaza ese motor en los tests."""
    from mcp import Client

    from mcp_uruguay.servidor import servidor

    if motor == "claude-cli" and preguntar_cli is None:
        from motor_claude_cli import preguntar_claude_cli as preguntar_cli
    import anyio

    filas = []
    async with Client(servidor) as sesion:
        herramientas = await herramientas_de(sesion)
        for p in preguntas:
            for modo in modos:
                for n in range(repeticiones):
                    con = modo == "con"
                    if preguntar_cli is not None:
                        texto, m = await anyio.to_thread.run_sync(
                            lambda: preguntar_cli(
                                p["pregunta"],
                                SISTEMA,
                                con_servidor=con,
                                modelo=modelo,
                                esfuerzo=esfuerzo,
                                presupuesto_tokens=presupuesto_tokens,
                            )
                        )
                        costo = m.pop("costo_usd_cli", None)
                    else:
                        texto, m = await preguntar(
                            cliente,
                            p["pregunta"],
                            sesion=sesion if con else None,
                            herramientas=herramientas if con else None,
                            modelo=modelo,
                            esfuerzo=esfuerzo,
                            presupuesto_tokens=presupuesto_tokens,
                        )
                        costo = costo_usd(m, modelo)
                    if m["motivo_fin"] == "refusal":
                        v = {"correcta": False, "motivo": "el modelo declinó (refusal)", "valor": None}
                    elif m["motivo_fin"] in ("error", "sin_resultado"):
                        v = {"correcta": False, "motivo": f"el agente no terminó ({m['motivo_fin']})", "valor": None}
                    else:
                        v = verificar(p, texto)
                    filas.append(
                        {
                            "id": p["id"],
                            "conjunto": p["conjunto"],
                            "tipo": p["tipo"],
                            "modo": modo,
                            "intento": n + 1,
                            "motor": motor,
                            **v,
                            **m,
                            "costo_usd": costo,
                            "uso_esperada": uso_esperada(p, m["llamadas"]) if con else None,
                            "respaldado": respaldado(p, texto, m["pasos"]) if con else None,
                            "respuesta": texto,
                        }
                    )
                    respaldo = ""
                    if filas[-1]["respaldado"] is False:
                        respaldo = "  (sin respaldo en la traza)"
                    print(
                        f"{p['id']:<34} {modo:<4} {'OK' if v['correcta'] else '--'}  {v['motivo']}{respaldo}",
                        file=sys.stderr,
                    )
    return filas


def uso_esperada(pregunta: dict, llamadas: list[str]) -> Optional[bool]:
    """True si llamó al menos a una de las herramientas esperadas; None si la pregunta no espera ninguna.

    Separa "el servidor no tiene el dato" de "el agente no eligió la herramienta"."""
    esperadas = set(pregunta.get("herramientas_esperadas") or [])
    if not esperadas:
        return None
    return bool(esperadas & set(llamadas))


def _formas_del_valor(pregunta: dict, valor: str) -> list[str]:
    """Las formas en que ese valor puede estar escrito en el texto de una herramienta, ya normalizadas.

    Las de `confirmar.formas`, pero armadas con **lo que respondió el agente**, no con lo esperado:
    un número equivocado también tiene que poder decir si salió de una herramienta."""
    if pregunta["tipo"] == "numero":
        v = numero(valor)
        return [] if v is None else [_normal(f) for f in confirmar.formas({"tipo": "numero", "esperado": v})]
    return [_normal(f) for f in confirmar.formas({"tipo": "texto", "patron": valor})]


def respaldado(pregunta: dict, texto: str, pasos: list[dict]) -> Optional[bool]:
    """¿El valor de `RESPUESTA:` aparece en lo que devolvieron las herramientas?

    Separa "acertó con el dato" de "acertó de memoria": un acierto sin respaldo en la traza pudo
    salir de lo que el modelo ya sabía, no del servidor. Mide lo que ya pasó, no adivina.

    `None` cuando no hay nada que verificar: las preguntas de comportamiento (ahí lo correcto es
    avisar, no citar una cifra), una respuesta `SIN DATO`, una respuesta sin valor reconocible, o una
    traza guardada antes de que los pasos llevaran el texto del resultado.

    `False` cuando contestó sin llamar a ninguna herramienta: ahí no hay nada que respalde el número.

    La comparación es la de `confirmar.aparece`, entera: `4,83` no aparece dentro de `14,83`.
    """
    if pregunta["tipo"] == "comportamiento":
        return None
    valor = linea_respuesta(texto)
    if valor is None or _normal(valor).strip() == "sin dato":
        return None
    if not pasos:
        return False
    textos = [_normal(p.get("resultado") or "") for p in pasos]
    if not any(textos):
        return None  # traza del formato anterior: el texto del resultado no se guardaba
    formas = _formas_del_valor(pregunta, valor)
    if not formas:
        return None
    return any(confirmar.aparece(forma, cuerpo) for cuerpo in textos for forma in formas)


def corrio(fila: dict) -> bool:
    """False si el intento no llegó a correr (el motor falló o no devolvió resultado): no es un fallo del
    agente, así que no entra en el porcentaje de acierto."""
    return fila.get("motivo_fin") != "sin_resultado" and not fila.get("error_motor")


def inestables(filas: list[dict]) -> dict[str, list[str]]:
    """Por modo, las preguntas con aciertos y fallos entre sus repeticiones."""
    vistos: dict[tuple[str, str], set[bool]] = {}
    for f in filas:
        if corrio(f):
            vistos.setdefault((f["modo"], f["id"]), set()).add(bool(f["correcta"]))
    salida: dict[str, list[str]] = {}
    for (modo, id_), resultados in sorted(vistos.items()):
        if len(resultados) > 1:
            salida.setdefault(modo, []).append(id_)
    return salida


def resumen(filas: list[dict]) -> str:
    """La tabla para el README: acierto por modo y tipo, llamadas, tokens, costo y cortes por presupuesto.

    El costo por acierto es el gasto total del grupo (los intentos fallidos también se pagan) dividido
    por los aciertos. Si algún intento no tiene precio, el grupo dice `s/d`: sumar solo los que tienen
    daría un costo menor al real."""
    lineas = [
        "| modo | tipo | aciertos | usó la esperada | llamadas promedio | errores de herramienta "
        "| tokens promedio | US$ promedio | US$ por acierto | cortadas por presupuesto | no corrió | respaldado |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for modo in sorted({f["modo"] for f in filas}):
        for tipo in ["numero", "texto", "comportamiento", "todas"]:
            todas = [f for f in filas if f["modo"] == modo and (tipo == "todas" or f["tipo"] == tipo)]
            g = [f for f in todas if corrio(f)]
            if not todas:
                continue
            n = max(len(g), 1)
            ok = sum(f["correcta"] for f in g)
            usadas = [f.get("uso_esperada") for f in g if f.get("uso_esperada") is not None]
            uso = f"{sum(usadas)}/{len(usadas)}"
            llamadas = sum(len(f["llamadas"]) for f in g) / n
            errores = sum(f["errores_herramienta"] for f in g)
            tokens = sum(f["tokens_entrada"] + f["tokens_salida"] for f in g) / n
            costos = [f.get("costo_usd") for f in g]
            if not g or any(c is None for c in costos):
                promedio, por_acierto = "s/d", "s/d"
            else:
                total = sum(c for c in costos if c is not None)
                promedio = f"{total / n:.4f}"
                por_acierto = f"{total / ok:.4f}" if ok else "s/d"
            cortadas = sum(bool(f.get("presupuesto_agotado")) for f in g)
            respaldadas = [f["respaldado"] for f in g if f.get("respaldado") is not None]
            respaldo = f"{sum(respaldadas)}/{len(respaldadas)}" if respaldadas else "—"
            nombre = f"**{tipo}**" if tipo == "todas" else tipo
            aciertos = f"{ok}/{len(g)} ({100 * ok / n:.0f}%)"
            lineas.append(
                f"| {modo} | {nombre} | {aciertos} | {uso} | {llamadas:.1f} | {errores} | {tokens:,.0f} "
                f"| {promedio} | {por_acierto} | {cortadas} | {len(todas) - len(g)} | {respaldo} |"
            )
    return "\n".join(lineas) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    import anyio

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--modo", default="con,sin", help="con, sin o con,sin (con y sin el servidor)")
    ap.add_argument("--conjunto", default="desarrollo", choices=["desarrollo", "reservado", "todos"])
    ap.add_argument("--id", action="append", help="solo esta pregunta (se puede repetir)")
    ap.add_argument("--modelo", default=MODELO)
    ap.add_argument("--esfuerzo", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--repeticiones", type=int, default=1)
    ap.add_argument(
        "--presupuesto-tokens",
        type=int,
        default=None,
        help="tope de tokens (entrada, salida y caché) por intento; al alcanzarlo el intento corta y cuenta como fallo",
    )
    ap.add_argument(
        "--precio",
        default=None,
        help="ENTRADA,SALIDA en US$ por millón de tokens, para un modelo que no está en PRECIOS",
    )
    ap.add_argument("--salida", type=Path, default=AQUI / "resultados")
    ap.add_argument(
        "--motor",
        default="api",
        choices=["api", "claude-cli"],
        help="api: la API de Claude (ANTHROPIC_API_KEY); claude-cli: Claude Code headless con su sesión",
    )
    args = ap.parse_args(argv)

    if args.precio:
        entrada, salida = (float(x) for x in args.precio.split(","))
        PRECIOS[args.modelo] = precio_de(entrada, salida)

    preguntas = cargar(args.conjunto, args.id)
    if not preguntas:
        print("ninguna pregunta con esos filtros", file=sys.stderr)
        return 2
    modos = [m.strip() for m in args.modo.split(",") if m.strip()]
    if args.motor == "api":
        import anthropic  # solo para correr de verdad: los tests usan un cliente falso

        cliente = anthropic.AsyncAnthropic()
    else:
        cliente = None
    filas = anyio.run(
        lambda: correr(
            cliente,
            preguntas,
            modos,
            modelo=args.modelo,
            esfuerzo=args.esfuerzo,
            repeticiones=args.repeticiones,
            presupuesto_tokens=args.presupuesto_tokens,
            motor=args.motor,
        )
    )
    sello = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.salida.mkdir(parents=True, exist_ok=True)
    destino = args.salida / f"{sello}-{args.motor}-{args.modelo}-{args.conjunto}.json"
    destino.write_text(
        json.dumps(
            {
                "motor": args.motor,
                "modelo": args.modelo,
                "esfuerzo": args.esfuerzo,
                "conjunto": args.conjunto,
                "filas": filas,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(resumen(filas))
    if args.repeticiones > 1:
        for modo, ids in inestables(filas).items():
            print(f"inestables ({modo}): {', '.join(ids)}")
    print(f"detalle: {destino}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
