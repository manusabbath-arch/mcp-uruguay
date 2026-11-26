"""Las Agent Skills se generan desde `guias.py`: no se editan a mano ni se separan de él.

`scripts/generar_skills.py` es el único que escribe `skills/`. Si un prompt cambia y las skills no, estos
tests fallan: la receta que el cliente lee como prompt y la que lee como skill no pueden decir cosas distintas.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
from mcp import Client

from mcp_uruguay import guias
from mcp_uruguay.servidor import servidor

RAIZ = Path(__file__).resolve().parents[1]
SKILLS = RAIZ / "skills"
NOMBRE_VALIDO = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@pytest.fixture(scope="module")
def generador():
    """El script, cargado como módulo: no se importa `scripts` como paquete."""
    ruta = RAIZ / "scripts" / "generar_skills.py"
    assert ruta.exists(), "falta scripts/generar_skills.py"
    spec = importlib.util.spec_from_file_location("generar_skills", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _frontmatter(texto: str) -> tuple[list[str], str]:
    """Las líneas del frontmatter y el cuerpo, sin interpretar YAML."""
    lineas = texto.split("\n")
    assert lineas[0] == "---", "el archivo no empieza con el frontmatter"
    fin = lineas.index("---", 1)
    return lineas[1:fin], "\n".join(lineas[fin + 1 :])


def _leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def test_las_skills_commiteadas_son_las_que_genera_el_script(generador):
    esperadas = generador.skills()
    assert esperadas, "el generador no produce ninguna skill"

    for nombre, contenido in esperadas.items():
        ruta = SKILLS / nombre / "SKILL.md"
        assert ruta.exists(), f"falta {ruta}: correr `uv run python scripts/generar_skills.py`"
        assert _leer(ruta) == contenido, f"{ruta} quedó vieja: correr `uv run python scripts/generar_skills.py`"

    en_disco = {ruta.parent.name for ruta in SKILLS.glob("*/SKILL.md")}
    assert en_disco == set(esperadas), f"sobran o faltan skills en {SKILLS}"

    for nombre, contenido in esperadas.items():
        assert "\r\n" not in contenido, f"{nombre} no usa LF"
        assert contenido.endswith("\n"), f"{nombre} no termina en un salto de línea"


@pytest.mark.parametrize("nombre", sorted(guias.PROMPTS))
def test_cada_skill_tiene_frontmatter_valido(nombre, generador):
    skill = nombre.replace("_", "-")
    ruta = SKILLS / skill / "SKILL.md"
    assert ruta.exists(), f"falta {ruta}"
    texto = _leer(ruta)

    cabecera, cuerpo = _frontmatter(texto)
    pares = [linea.split(":", 1) for linea in cabecera]
    claves = [clave.strip() for clave, _ in pares]
    assert claves == ["name", "description"], f"{ruta}: el frontmatter lleva solo name y description"

    valor = {clave.strip(): dato.strip() for clave, dato in pares}
    assert valor["name"] == skill, f"{ruta}: name no coincide con el directorio"
    assert NOMBRE_VALIDO.fullmatch(valor["name"]), f"{ruta}: name inválido"
    assert len(valor["name"]) <= 64, f"{ruta}: name demasiado largo"

    descripcion = valor["description"].strip()
    assert descripcion.startswith('"') and descripcion.endswith('"'), f"{ruta}: description sin comillas dobles"
    assert json.loads(descripcion), f"{ruta}: description no es una cadena"
    assert len(json.loads(descripcion)) <= 250, f"{ruta}: description supera los 250 caracteres"
    assert "\n" not in json.loads(descripcion), f"{ruta}: description ocupa más de una línea"

    assert f"# {guias.PROMPTS[nombre][1]}" in cuerpo, f"{ruta}: falta el título del flujo"
    assert "guias.py" in cuerpo, f"{ruta}: no dice de dónde se genera"
    assert "no editar" in cuerpo.lower(), f"{ruta}: no avisa que no se edita a mano"

    funcion = guias.PROMPTS[nombre][0]
    for parametro in funcion.__code__.co_varnames[: funcion.__code__.co_argcount]:
        assert f"<{parametro}>" in cuerpo, f"{ruta}: no usa el marcador <{parametro}>"


@pytest.mark.anyio
async def test_cada_herramienta_nombrada_existe_en_el_servidor(generador):
    async with Client(servidor) as cliente:
        reales = {herramienta.name for herramienta in (await cliente.list_tools()).tools}

    for nombre in generador.skills():
        texto = _leer(SKILLS / nombre / "SKILL.md")
        nombradas = generador.herramientas_nombradas(texto)
        assert nombradas, f"{nombre}: no nombra ninguna herramienta"
        assert set(nombradas) <= reales, f"{nombre}: nombra herramientas que el servidor no tiene"

        esperadas = {herramienta for herramienta in guias.TRAMPAS if f"`{herramienta}`" in texto}
        assert set(nombradas) == esperadas, f"{nombre}: la sección de trampas no cubre todas las herramientas"
        for herramienta in nombradas:
            assert f"- `{herramienta}`: {guias.TRAMPAS[herramienta]}" in texto


def test_check_falla_con_un_archivo_modificado(tmp_path, generador):
    generador.escribir(tmp_path)
    assert generador.revisar(tmp_path) == []
    assert generador.main(["--check", "--destino", str(tmp_path)]) == 0

    ruta = tmp_path / "clima-de-salto" / "SKILL.md"
    original = ruta.read_bytes()
    ruta.write_bytes(original + b"\n")

    problemas = generador.revisar(tmp_path)
    assert any("desactualizado" in problema and "clima-de-salto" in problema for problema in problemas)
    assert generador.main(["--check", "--destino", str(tmp_path)]) == 1
    assert ruta.read_bytes() == original + b"\n", "--check no debe escribir"


def test_check_falla_con_finales_de_linea_de_windows(tmp_path, generador):
    """Leer como texto convierte CRLF en LF y el archivo pasa por al día: se comparan los bytes."""
    generador.escribir(tmp_path)
    ruta = tmp_path / "clima-de-salto" / "SKILL.md"
    ruta.write_bytes(ruta.read_bytes().replace(b"\n", b"\r\n"))

    assert generador.revisar(tmp_path) == ["desactualizado clima-de-salto/SKILL.md"]


def test_las_skills_no_viajan_en_el_paquete_mcpb():
    """Nada en el manifiesto las usa: dentro del paquete serían peso sin consumidor."""
    assert "skills/" in (RAIZ / ".mcpbignore").read_text(encoding="utf-8").splitlines()


def test_check_detecta_faltantes_y_sobrantes(tmp_path, generador):
    generador.escribir(tmp_path)
    (tmp_path / "clima-de-salto" / "SKILL.md").unlink()
    sobrante = tmp_path / "vieja" / "SKILL.md"
    sobrante.parent.mkdir()
    sobrante.write_text('---\nname: vieja\ndescription: "x"\n---\n', encoding="utf-8", newline="\n")

    problemas = generador.revisar(tmp_path)
    assert any("falta" in problema and "clima-de-salto" in problema for problema in problemas)
    assert any("sobra" in problema and "vieja" in problema for problema in problemas)
    assert generador.main(["--check", "--destino", str(tmp_path)]) == 1
