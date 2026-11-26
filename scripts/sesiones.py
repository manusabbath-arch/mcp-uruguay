"""Herramientas locales para trabajar en worktrees y reservar el árbol principal para integración."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path


class SesionInvalida(RuntimeError):
    """La operación no puede continuar sin poner en riesgo otra sesión."""


def git(raiz: Path, *args: str) -> str:
    # Un hook de commit puede exportar GIT_INDEX_FILE/GIT_DIR: no llevarlos a otro worktree.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    resultado = subprocess.run(
        ["git", "-C", str(raiz), *args],
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if resultado.returncode:
        raise SesionInvalida(resultado.stderr.strip() or "Git no pudo comprobar el estado")
    return resultado.stdout.strip()


@contextmanager
def bloqueo(raiz: Path):
    """Solo un integrador cooperante por repo. Nunca se roba ni se borra un bloqueo ajeno."""
    comun = Path(git(raiz, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    candado = comun / "mcp-integracion.lock"
    try:
        candado.mkdir()
    except FileExistsError as e:
        raise SesionInvalida("integración ocupada: esperar al integrador; no borrar su bloqueo") from e
    try:
        (candado / "propietario.txt").write_text(f"pid={os.getpid()}\n", encoding="utf-8")
        yield
    finally:
        (candado / "propietario.txt").unlink(missing_ok=True)
        candado.rmdir()


def comprobar(raiz: Path) -> str:
    rama = git(raiz, "branch", "--show-current")
    comun = Path(git(raiz, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    propio = Path(git(raiz, "rev-parse", "--absolute-git-dir"))
    if propio.resolve() == comun.resolve() or rama == "main":
        raise SesionInvalida("Árbol de integración: crear un worktree y una rama propios antes de escribir o commitear")
    if not rama:
        raise SesionInvalida("HEAD detached: crear una rama propia antes de trabajar")
    return rama


def _limpio(raiz: Path) -> None:
    if git(raiz, "status", "--porcelain", "--untracked-files=all"):
        raise SesionInvalida("Hay cambios sin commitear: no mover, limpiar ni guardar trabajo ajeno")
    for estado in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "sequencer"):
        if Path(git(raiz, "rev-parse", "--path-format=absolute", "--git-path", estado)).exists():
            raise SesionInvalida(f"Operación Git pendiente ({estado}): no abortarla si no es propia")


def _recibo(raiz: Path) -> Path:
    return Path(git(raiz, "rev-parse", "--absolute-git-dir")) / "mcp-verificado.json"


def _validar(raiz: Path) -> None:
    for comando in (
        ["uvx", "ruff", "check", "scripts", "src", "tests"],
        ["uvx", "ruff", "format", "--check", "scripts", "src", "tests"],
        ["uv", "run", "--extra", "test", "pytest", "-q"],
    ):
        print("Verificando:", " ".join(comando), flush=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        if subprocess.run(comando, cwd=raiz, env=env, timeout=600).returncode:
            raise SesionInvalida("La verificación falló: no hay autorización de integración")


def verificar(raiz: Path) -> dict:
    comprobar(raiz)
    ruta = _recibo(raiz)
    ruta.unlink(missing_ok=True)  # una corrida fallida invalida cualquier permiso anterior
    _limpio(raiz)
    recibo = {"head": git(raiz, "rev-parse", "HEAD"), "main": git(raiz, "rev-parse", "refs/heads/main")}
    _validar(raiz)
    _limpio(raiz)
    if recibo != {"head": git(raiz, "rev-parse", "HEAD"), "main": git(raiz, "rev-parse", "refs/heads/main")}:
        raise SesionInvalida("HEAD o main cambió durante las pruebas: repetir la verificación")
    ruta.write_text(json.dumps(recibo), encoding="utf-8")
    return recibo


def _integracion(raiz: Path) -> Path:
    camino = None
    for campo in git(raiz, "worktree", "list", "--porcelain", "-z").split("\0"):
        if campo.startswith("worktree "):
            camino = Path(campo.removeprefix("worktree "))
        elif campo == "branch refs/heads/main" and camino is not None:
            return camino
    raise SesionInvalida("main no está en un worktree: no se elige un árbol de integración por suposición")


def integrar(raiz: Path) -> str:
    comprobar(raiz)
    with bloqueo(raiz):
        try:
            recibo = json.loads(_recibo(raiz).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise SesionInvalida("Falta verificar esta rama: ejecutar sesiones.py verificar") from e
        _limpio(raiz)
        esperado = {"head": git(raiz, "rev-parse", "HEAD"), "main": git(raiz, "rev-parse", "refs/heads/main")}
        if recibo != esperado:
            raise SesionInvalida("HEAD o main cambió desde las pruebas: actualizar la rama y volver a verificar")
        destino = _integracion(raiz)
        _limpio(destino)
        if git(destino, "branch", "--show-current") != "main" or git(destino, "rev-parse", "HEAD") != esperado["main"]:
            raise SesionInvalida("El árbol de integración cambió: no se toca")
        # Un SHA, no una rama móvil. --ff-only no deja una resolución de merge pendiente.
        git(destino, "merge", "--ff-only", "--no-edit", esperado["head"])
        _limpio(destino)
        if git(destino, "rev-parse", "HEAD") != esperado["head"]:
            raise SesionInvalida("HEAD de integración inesperado: inspeccionar sin resetear trabajo ajeno")
        _recibo(raiz).unlink(missing_ok=True)
        return esperado["head"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accion", choices=["estado", "comprobar", "verificar", "integrar"])
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        if args.accion == "estado":
            print(git(args.repo, "worktree", "list", "--porcelain"))
            print("hooks:", git(args.repo, "config", "--get", "--default", "(no instalado)", "core.hooksPath"))
        elif args.accion == "comprobar":
            print("OK: worktree propio, rama", comprobar(args.repo))
        elif args.accion == "verificar":
            print(json.dumps(verificar(args.repo), ensure_ascii=False))
        else:
            print("Integrado y verificado:", integrar(args.repo))
        return 0
    except (SesionInvalida, OSError, subprocess.SubprocessError) as error:
        print(f"BLOQUEADO: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
