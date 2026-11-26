"""Sesiones aisladas: pruebas sobre repos Git temporales, nunca sobre el índice del usuario."""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sesiones.py"


def cargar():
    spec = importlib.util.spec_from_file_location("sesiones", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def git(raiz, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(
        ["git", "-C", str(raiz), *args], env=env, capture_output=True, encoding="utf-8", errors="replace", check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    raiz = tmp_path / "repo"
    raiz.mkdir()
    git(raiz, "init", "-b", "main")
    git(raiz, "config", "user.name", "Prueba")
    git(raiz, "config", "user.email", "prueba@example.invalid")
    git(raiz, "config", "commit.gpgsign", "false")
    (raiz / "dato.txt").write_text("base\n", encoding="utf-8")
    git(raiz, "add", "dato.txt")
    git(raiz, "commit", "-m", "base")
    return raiz


@pytest.fixture
def vinculada(repo, tmp_path):
    ruta = tmp_path / "sesion"
    git(repo, "worktree", "add", "-b", "agente/tarea", str(ruta), "main")
    return ruta


def test_comprobar_acepta_worktree_propio(vinculada):
    assert cargar().comprobar(vinculada) == "agente/tarea"


def test_comprobar_rechaza_detached(vinculada):
    git(vinculada, "checkout", "--detach")
    sesiones = cargar()
    with pytest.raises(sesiones.SesionInvalida, match="detached"):
        sesiones.comprobar(vinculada)


def test_git_no_hereda_el_indice_de_un_hook(repo, vinculada, monkeypatch):
    monkeypatch.setenv("GIT_INDEX_FILE", str(repo / ".git" / "index"))
    monkeypatch.setenv("GIT_DIR", str(repo / ".git"))
    assert cargar().comprobar(vinculada) == "agente/tarea"


def test_bloqueo_se_comparte_entre_worktrees_y_no_se_roba(repo, vinculada):
    sesiones = cargar()
    with sesiones.bloqueo(repo):
        with pytest.raises(sesiones.SesionInvalida, match="integración ocupada"):
            with sesiones.bloqueo(vinculada):
                pytest.fail("dos integradores entraron juntos")
    with sesiones.bloqueo(vinculada):
        pass


def test_verificar_sella_un_sha_y_sin_cambios(repo, vinculada, monkeypatch):
    sesiones = cargar()
    ejecutados = []
    monkeypatch.setattr(sesiones, "_validar", lambda raiz: ejecutados.append(raiz))
    recibo = sesiones.verificar(vinculada)
    assert recibo["head"] == git(vinculada, "rev-parse", "HEAD")
    assert recibo["main"] == git(repo, "rev-parse", "main")
    assert ejecutados == [vinculada]


def test_verificar_no_acepta_un_arbol_sucio(vinculada, monkeypatch):
    sesiones = cargar()
    monkeypatch.setattr(sesiones, "_validar", lambda raiz: pytest.fail("no debe validar trabajo sin commit"))
    (vinculada / "ajeno.txt").write_text("no tocar", encoding="utf-8")
    with pytest.raises(sesiones.SesionInvalida, match="sin commitear"):
        sesiones.verificar(vinculada)


def test_integrar_exige_verificacion_previa(repo, vinculada):
    sesiones = cargar()
    antes = git(repo, "rev-parse", "HEAD")
    with pytest.raises(sesiones.SesionInvalida, match="verificar"):
        sesiones.integrar(vinculada)
    assert git(repo, "rev-parse", "HEAD") == antes


def test_integrar_hace_fast_forward_sin_borrar_la_rama(repo, vinculada, monkeypatch):
    sesiones = cargar()
    (repo / ".git" / "info" / "exclude").write_text("local.txt\n", encoding="utf-8")
    (repo / "local.txt").write_text("ignorado ajeno sin colisión\n", encoding="utf-8")
    (vinculada / "dato.txt").write_text("cambio\n", encoding="utf-8")
    git(vinculada, "add", "dato.txt")
    git(vinculada, "commit", "-m", "cambio")
    monkeypatch.setattr(sesiones, "_validar", lambda raiz: None)
    esperado = sesiones.verificar(vinculada)["head"]
    assert sesiones.integrar(vinculada) == esperado
    assert git(repo, "rev-parse", "HEAD") == esperado
    assert git(repo, "status", "--porcelain") == ""
    assert git(vinculada, "branch", "--show-current") == "agente/tarea"
    assert (repo / "local.txt").read_text(encoding="utf-8") == "ignorado ajeno sin colisión\n"


@pytest.mark.parametrize("cambio", ["main", "rama", "sucio_principal", "sucio_propio"])
def test_integrar_rechaza_cambios_posteriores_sin_tocarlos(repo, vinculada, monkeypatch, cambio):
    sesiones = cargar()
    monkeypatch.setattr(sesiones, "_validar", lambda raiz: None)
    sesiones.verificar(vinculada)
    destino = repo if cambio in ("main", "sucio_principal") else vinculada
    (destino / "ajeno.txt").write_text("trabajo de otra sesión\n", encoding="utf-8")
    if cambio in ("main", "rama"):
        git(destino, "add", "ajeno.txt")
        git(destino, "commit", "-m", "otra sesión")
    antes = git(repo, "rev-parse", "HEAD")
    with pytest.raises(sesiones.SesionInvalida):
        sesiones.integrar(vinculada)
    assert git(repo, "rev-parse", "HEAD") == antes
    assert (destino / "ajeno.txt").read_text(encoding="utf-8") == "trabajo de otra sesión\n"


def test_verificacion_fallida_no_deja_un_recibo_anterior(vinculada, monkeypatch):
    sesiones = cargar()
    monkeypatch.setattr(sesiones, "_validar", lambda raiz: None)
    sesiones.verificar(vinculada)

    def falla(raiz):
        raise sesiones.SesionInvalida("fallaron los tests")

    monkeypatch.setattr(sesiones, "_validar", falla)
    with pytest.raises(sesiones.SesionInvalida):
        sesiones.verificar(vinculada)
    assert not sesiones._recibo(vinculada).exists()


def test_main_movida_durante_las_pruebas_no_se_sella(repo, vinculada, monkeypatch):
    sesiones = cargar()

    def mueve(raiz):
        (repo / "ajeno.txt").write_text("otro", encoding="utf-8")
        git(repo, "add", "ajeno.txt")
        git(repo, "commit", "-m", "otra sesión")

    monkeypatch.setattr(sesiones, "_validar", mueve)
    with pytest.raises(sesiones.SesionInvalida, match="durante las pruebas"):
        sesiones.verificar(vinculada)
    assert not sesiones._recibo(vinculada).exists()


def test_validadores_no_heredan_un_indice_ajeno(vinculada, monkeypatch):
    from types import SimpleNamespace

    sesiones = cargar()
    monkeypatch.setenv("GIT_INDEX_FILE", "indice-ajeno")
    llamadas = []

    def ejecutar(comando, **opciones):
        llamadas.append((comando, opciones))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(sesiones.subprocess, "run", ejecutar)
    sesiones._validar(vinculada)
    assert len(llamadas) == 3
    assert all("GIT_INDEX_FILE" not in opciones.get("env", os.environ) for _, opciones in llamadas)


def test_cli_rechaza_main_con_motivo(repo):
    import sys

    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    resultado = subprocess.run(
        [sys.executable, str(SCRIPT), "comprobar", "--repo", str(repo)],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert resultado.returncode == 1
    assert "BLOQUEADO" in resultado.stderr and "integración" in resultado.stderr


def test_fast_forward_imposible_no_deja_merge_pendiente(repo, vinculada, monkeypatch):
    sesiones = cargar()
    for destino, texto in [(repo, "main"), (vinculada, "rama")]:
        (destino / "dato.txt").write_text(texto, encoding="utf-8")
        git(destino, "add", "dato.txt")
        git(destino, "commit", "-m", texto)
    antes = git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(sesiones, "_validar", lambda raiz: None)
    sesiones.verificar(vinculada)
    with pytest.raises(sesiones.SesionInvalida):
        sesiones.integrar(vinculada)
    assert git(repo, "rev-parse", "HEAD") == antes
    assert not (repo / ".git" / "MERGE_HEAD").exists()
    assert (repo / "dato.txt").read_text(encoding="utf-8") == "main"


@pytest.mark.parametrize("nombre", ["ignorado.txt", "ignorado/sub.txt"])
def test_integrar_no_sobrescribe_archivos_ignorados_ajenos(repo, vinculada, monkeypatch, nombre):
    sesiones = cargar()
    (repo / ".gitignore").write_text("ignorado.txt\nignorado/\n", encoding="utf-8")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-m", "ignorar archivos locales")
    git(vinculada, "merge", "--ff-only", "main")
    propio = vinculada / nombre
    propio.parent.mkdir(parents=True, exist_ok=True)
    propio.write_text("contenido-rama\n", encoding="utf-8")
    git(vinculada, "add", "-f", nombre)
    git(vinculada, "commit", "-m", "incorporar ruta antes ignorada")
    ajeno = repo / nombre
    ajeno.parent.mkdir(parents=True, exist_ok=True)
    ajeno.write_text("trabajo-ajeno\n", encoding="utf-8")
    assert git(repo, "status", "--porcelain", "--untracked-files=all") == ""
    antes = git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(sesiones, "_validar", lambda raiz: None)
    sesiones.verificar(vinculada)
    with pytest.raises(sesiones.SesionInvalida):
        sesiones.integrar(vinculada)
    assert ajeno.read_text(encoding="utf-8") == "trabajo-ajeno\n"
    assert git(repo, "rev-parse", "HEAD") == antes
    assert not (repo / ".git" / "MERGE_HEAD").exists()


def test_comprobar_rechaza_el_arbol_compartido(repo):
    sesiones = cargar()
    with pytest.raises(sesiones.SesionInvalida, match="integración"):
        sesiones.comprobar(repo)
