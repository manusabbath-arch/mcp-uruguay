"""Motor alternativo de la evaluación: el agente es Claude Code en modo headless (`claude -p`).

Sirve para medir con la suscripción de Claude Code en vez de una clave de la API. Cada pregunta corre en
un proceso nuevo, sin sesión guardada, sin las herramientas propias de Claude Code (`--tools ""`), sin
la configuración del usuario (`--setting-sources ""`) y con el mismo prompt de sistema que el motor de
la API. Con servidor, la única herramienta disponible es `mcp-uruguay` por stdio.

La traza sale del stream de eventos (`--output-format stream-json`): cada `tool_use` y su `tool_result`
se cruzan por id; los segundos de cada paso son los que pasan entre los dos eventos. El costo es el que
informa Claude Code (`total_cost_usd`): con suscripción es nocional, lo que costaría por la API.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional

PREFIJO = "mcp__uruguay__"


def _texto_resultado(contenido) -> str:
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        return "\n".join(c.get("text", "") for c in contenido if isinstance(c, dict))
    return json.dumps(contenido, ensure_ascii=False, default=str)


def parsear_eventos(
    eventos: Iterable[tuple[float, dict]], presupuesto_tokens: Optional[int] = None
) -> tuple[str, dict]:
    """(texto final, métricas) a partir de los eventos `(segundo, evento)` del stream de Claude Code.

    Devuelve las mismas claves que `evaluar.preguntar`, más `costo_usd_cli`. Si el uso acumulado alcanza
    `presupuesto_tokens`, deja de leer y marca `presupuesto_agotado` (quien llama corta el proceso)."""
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
        "motivo_fin": "sin_resultado",
        "costo_usd_cli": None,
    }
    texto = ""
    ultimo_id: Optional[str] = None
    abiertos: dict[str, tuple[float, dict]] = {}
    for segundo, ev in eventos:
        tipo = ev.get("type")
        if tipo == "assistant":
            msg = ev.get("message", {})
            uso = msg.get("usage", {}) or {}
            detalle = {
                "tokens_entrada": uso.get("input_tokens", 0) or 0,
                "tokens_salida": uso.get("output_tokens", 0) or 0,
                "tokens_cache_leidos": uso.get("cache_read_input_tokens", 0) or 0,
                "tokens_cache_escritos": uso.get("cache_creation_input_tokens", 0) or 0,
                "segundos": round(segundo, 2),
            }
            # Un evento por bloque de contenido, con el mismo id: el turno es el mensaje, no el evento.
            id_msg = msg.get("id")
            if id_msg is None or id_msg != ultimo_id:
                m["turnos"] += 1
                m["turnos_detalle"].append({"turno": m["turnos"], **detalle})
            else:
                m["turnos_detalle"][-1].update(detalle)
            ultimo_id = id_msg
            for bloque in msg.get("content", []) or []:
                if bloque.get("type") == "text":
                    texto = bloque.get("text", "")
                elif bloque.get("type") == "tool_use":
                    nombre = bloque.get("name", "").removeprefix(PREFIJO)
                    m["llamadas"].append(nombre)
                    abiertos[bloque.get("id", "")] = (
                        segundo,
                        {"turno": m["turnos"], "herramienta": nombre, "argumentos": bloque.get("input", {})},
                    )
            usado = sum(d["tokens_entrada"] + d["tokens_salida"] for d in m["turnos_detalle"])
            if presupuesto_tokens is not None and usado >= presupuesto_tokens:
                m["presupuesto_agotado"], m["motivo_fin"] = True, "presupuesto_agotado"
                break
        elif tipo == "user":
            for bloque in ev.get("message", {}).get("content", []) or []:
                if not isinstance(bloque, dict) or bloque.get("type") != "tool_result":
                    continue
                inicio, paso = abiertos.pop(bloque.get("tool_use_id", ""), (segundo, {"turno": m["turnos"]}))
                contenido = _texto_resultado(bloque.get("content", ""))
                es_error = bool(bloque.get("is_error", False))
                m["errores_herramienta"] += es_error
                m["pasos"].append(
                    {
                        **paso,
                        "segundos": round(segundo - inicio, 2),
                        "error": es_error,
                        "bytes_resultado": len(contenido.encode("utf-8")),
                    }
                )
        elif tipo == "result":
            texto = ev.get("result", texto) or texto
            m["motivo_fin"] = "error" if ev.get("is_error") else ev.get("subtype", "success")
            m["costo_usd_cli"] = ev.get("total_cost_usd")
            uso = ev.get("usage", {}) or {}
            # El total del resultado manda sobre la suma de los turnos (incluye lo que no viaja por turno).
            m["tokens_entrada"] = uso.get("input_tokens", 0) or 0
            m["tokens_salida"] = uso.get("output_tokens", 0) or 0
            m["tokens_cache_leidos"] = uso.get("cache_read_input_tokens", 0) or 0
            m["tokens_cache_escritos"] = uso.get("cache_creation_input_tokens", 0) or 0
    if m["motivo_fin"] in ("sin_resultado", "presupuesto_agotado"):
        for k in ("tokens_entrada", "tokens_salida", "tokens_cache_leidos", "tokens_cache_escritos"):
            m[k] = sum(d[k] for d in m["turnos_detalle"])
    return texto, m


def comando(
    sistema: str, *, con_servidor: bool, modelo: Optional[str], esfuerzo: Optional[str], mcp_config: Optional[Path]
) -> list[str]:
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--tools",
        "",
        "--system-prompt",
        sistema,
    ]
    if modelo:
        cmd += ["--model", modelo]
    if esfuerzo:
        cmd += ["--effort", esfuerzo]
    if con_servidor and mcp_config is not None:
        cmd += ["--mcp-config", str(mcp_config), "--allowedTools", "mcp__uruguay"]
    return cmd


def _leer(proceso: subprocess.Popen, inicio: float) -> Iterator[tuple[float, dict]]:
    assert proceso.stdout is not None
    for linea in proceso.stdout:
        linea = linea.strip()
        if not linea:
            continue
        try:
            yield time.monotonic() - inicio, json.loads(linea)
        except json.JSONDecodeError:
            continue


def preguntar_claude_cli(
    pregunta: str,
    sistema: str,
    *,
    con_servidor: bool,
    modelo: Optional[str] = None,
    esfuerzo: Optional[str] = None,
    presupuesto_tokens: Optional[int] = None,
    lanzar: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> tuple[str, dict]:
    """Corre una pregunta con `claude -p` y devuelve (texto, métricas) con las claves de `evaluar.preguntar`."""
    with tempfile.TemporaryDirectory(prefix="evalcli-") as carpeta:
        config = None
        if con_servidor:
            ejecutable = Path(sys.executable).parent / "mcp-uruguay"
            config = Path(carpeta) / "mcp.json"
            config.write_text(json.dumps({"mcpServers": {"uruguay": {"command": str(ejecutable), "args": []}}}))
        cmd = comando(sistema, con_servidor=con_servidor, modelo=modelo, esfuerzo=esfuerzo, mcp_config=config)
        inicio = time.monotonic()
        proceso = lanzar(
            cmd + ["--", pregunta],  # `--allowedTools` toma varios valores: sin `--` se comería la pregunta
            cwd=carpeta,  # una carpeta vacía: ningún CLAUDE.md del usuario entra al contexto
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            texto, m = parsear_eventos(_leer(proceso, inicio), presupuesto_tokens)
        finally:
            if proceso.poll() is None:
                proceso.kill()
            proceso.wait()
        m["segundos"] = round(time.monotonic() - inicio, 1)
        if m["motivo_fin"] == "sin_resultado":
            error = proceso.stderr.read() if proceso.stderr else ""
            m["error_motor"] = error.strip()[-500:]
        return texto, m
