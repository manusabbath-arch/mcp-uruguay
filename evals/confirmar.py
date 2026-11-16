"""Confirma cada respuesta esperada contra su fuente: baja la página o el PDF y busca la cifra en el texto.

Una pregunta pasa a `confirmada_en_fuente: true` solo si la cifra aparece escrita en la fuente que
cita (o en una de `otras_fuentes`), en alguna de las formas en que se escribe: `49,84`, `1.101.296`,
`09/07/2020`. Lo que no aparece no se marca, aunque la cifra sea correcta: el script no adivina, y
el que confirma a mano lo hace abriendo el enlace.

Hace falta red hacia los sitios del Estado y de la prensa, que desde la máquina donde se escribió
la evaluación no resolvían. Para los PDF usa `pypdf`:

    uv run --with pypdf python evals/confirmar.py            # informa, no toca nada
    uv run --with pypdf python evals/confirmar.py --marcar   # y marca las que encontró
"""

from __future__ import annotations

import argparse
import html
import io
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Callable, Optional

AQUI = Path(__file__).resolve().parent
PREGUNTAS = AQUI / "preguntas.json"
AGENTE = "mcp-uruguay-evals (verificacion de cifras oficiales)"


def bajar(url: str) -> bytes:
    # Las URL del INE llevan tildes («Estadísticaseconómicas»): urllib no acepta caracteres fuera de
    # ASCII, así que se codifican, sin tocar lo que ya viene codificado (%20).
    url = urllib.parse.quote(url, safe=":/?&=%#+,;@")
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pedido, timeout=30) as r:
        return r.read()


def texto_de(cuerpo: bytes) -> str:
    """El texto legible de una página HTML o de un PDF, sin tildes, en minúsculas y con un espacio."""
    if cuerpo[:5] == b"%PDF-":
        from pypdf import PdfReader  # solo si la fuente es un PDF

        crudo = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(cuerpo)).pages)
    else:
        crudo = cuerpo.decode("utf-8", errors="replace")
        crudo = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", crudo)
        crudo = html.unescape(re.sub(r"<[^>]+>", " ", crudo))
    sin_tildes = unicodedata.normalize("NFKD", crudo).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", sin_tildes)


def formas(pregunta: dict) -> list[str]:
    """Las formas en que la respuesta esperada puede estar escrita en la fuente."""
    if pregunta["tipo"] == "numero":
        v = pregunta["esperado"]
        decimales = len(repr(float(v)).split(".")[1].rstrip("0")) if isinstance(v, float) else 0
        en = f"{v:,.{decimales}f}"  # 1,101,296.5
        es = en.replace(",", "_").replace(".", ",").replace("_", ".")  # 1.101.296,5
        return sorted({es, en, f"{v:.{decimales}f}", es.replace(".", " ")}, key=len, reverse=True)
    if pregunta["tipo"] == "texto":
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", pregunta["patron"])
        if m:
            a, mes, d = m.groups()
            return [f"{d}/{mes}/{a}", f"{int(d)}/{int(mes)}/{a}", f"{a}-{mes}-{d}"]
        return [pregunta["patron"].strip("^\\b()").split("|")[0]]
    return []


def aparece(forma: str, texto: str) -> bool:
    """La forma, entera: `4,83` no tiene que encontrarse dentro de `14,83` ni de `4,831`."""
    return re.search(rf"(?<![\d.,]){re.escape(forma)}(?![\d]|[.,]\d)", texto) is not None


def confirmar(pregunta: dict, bajador: Callable[[str], bytes] = bajar) -> dict:
    """{'id', 'estado', 'url', 'forma', 'detalle'} para una pregunta. Estado: confirmada, no_aparece,
    no_se_pudo_bajar, sin_url o no_aplica (las de comportamiento y las de cálculo)."""
    f = pregunta["fuente"]
    base = {"id": pregunta["id"], "url": None, "forma": None, "detalle": ""}
    buscadas = formas(pregunta)
    if not buscadas or f.get("via") == "cálculo":
        return {**base, "estado": "no_aplica", "detalle": "no tiene una cifra que buscar en una página"}
    urls = [u for u in [f.get("url"), *f.get("otras_fuentes", [])] if u]
    if not urls:
        return {**base, "estado": "sin_url"}
    errores = []
    for url in urls:
        try:
            texto = texto_de(bajador(url))
        except Exception as e:  # una fuente caída no frena las demás
            errores.append(f"{url}: {type(e).__name__}: {e}")
            continue
        for forma in buscadas:
            if aparece(forma, texto):
                return {**base, "estado": "confirmada", "url": url, "forma": forma}
        errores.append(f"{url}: ninguna de {buscadas} aparece en el texto")
    sin_bajar = all("ninguna de" not in e for e in errores)
    return {**base, "estado": "no_se_pudo_bajar" if sin_bajar else "no_aparece", "detalle": " | ".join(errores)}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--marcar", action="store_true", help="pasa a true las que encontró, con la fecha y la URL")
    ap.add_argument("--id", action="append", help="solo esta pregunta (se puede repetir)")
    args = ap.parse_args(argv)

    datos = json.loads(PREGUNTAS.read_text(encoding="utf-8"))
    resultados = []
    for p in datos["preguntas"]:
        if args.id and p["id"] not in args.id:
            continue
        r = confirmar(p)
        resultados.append(r)
        print(f"{r['estado']:<17} {r['id']:<36} {r['forma'] or ''} {r['detalle']}".rstrip())
        if args.marcar and r["estado"] == "confirmada":
            p["fuente"].update(
                {"confirmada_en_fuente": True, "confirmada_el": date.today().isoformat(), "confirmada_en": r["url"]}
            )
    if args.marcar:
        PREGUNTAS.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    pendientes = [r for r in resultados if r["estado"] in ("no_aparece", "no_se_pudo_bajar", "sin_url")]
    print(
        f"\n{len(resultados) - len(pendientes)} sin pendientes, {len(pendientes)} para revisar a mano", file=sys.stderr
    )
    return 1 if pendientes else 0


if __name__ == "__main__":
    sys.exit(main())
