"""Punta a punta de US1 (quickstart §1 y verificación de CI) sobre copias, sin red (T018)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tsinsurance.experiments.registry import append_trials

ROOT = Path(__file__).parents[2]
EJEMPLO = ROOT / "examples" / "integracion"
SCRIPT = ROOT / ".github" / "scripts" / "check-registry.sh"
CLI = [sys.executable, "-m", "tsinsurance.cli"]


def _run(*args: str | os.PathLike[str], cwd: Path, env: dict[str, str] | None = None) -> int:
    out = subprocess.run(
        [str(a) for a in args], cwd=cwd, capture_output=True, text=True, check=False, env=env
    )
    return out.returncode


def _keep(src: Path, dest: Path, n: int) -> None:
    lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
    dest.write_text("".join(lines[:n]), encoding="utf-8")


@pytest.fixture(scope="module")
def ran(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("integ") / "integracion"
    shutil.copytree(EJEMPLO, work, ignore=shutil.ignore_patterns("data", "results", "*.jsonl"))
    assert _run(sys.executable, "generar_paquete_sintetico.py", "data", cwd=work) == 0
    assert _run(*CLI, "experiment", "run", "experiment.toml", cwd=work) == 0
    return work


def test_quickstart_truncation_and_prefix(ran: Path) -> None:
    reg = ran / "registry.jsonl"
    n = len(reg.read_text(encoding="utf-8").splitlines())
    cut = ran / "recortada.jsonl"
    _keep(reg, cut, n - 3)
    # La cadena sola acepta la copia recortada...
    assert _run(*CLI, "experiment", "verify", cut, cwd=ran) == 0
    # ... los resultados publicados no (la copia ocupa el lugar de la bitácora).
    shutil.copy(reg, ran / "original.jsonl")
    shutil.copy(cut, reg)
    try:
        assert _run(*CLI, "experiment", "verify", reg, "--results", "results", cwd=ran) == 1
    finally:
        shutil.copy(ran / "original.jsonl", reg)
    assert _run(*CLI, "experiment", "verify", reg, "--results", "results", cwd=ran) == 0
    assert _run(*CLI, "experiment", "verify", reg, "--base", cut, cwd=ran) == 0
    assert _run(*CLI, "experiment", "verify", cut, "--base", reg, cwd=ran) == 1


@pytest.mark.skipif(shutil.which("git") is None, reason="requiere git")
def test_ci_script_fails_closed_and_detects_rewrites(ran: Path, tmp_path: Path) -> None:
    """El script de CI contra un remoto local: acepta agregar, rechaza recortar o editar."""
    env = {**os.environ, "TSINSURANCE_CMD": " ".join(CLI), "RUNNER_TEMP": str(tmp_path)}
    git = ["git", "-c", "user.email=ci@example.invalid", "-c", "user.name=ci"]
    remote, repo = tmp_path / "remote.git", tmp_path / "repo"
    assert _run("git", "init", "-q", "--bare", "-b", "main", remote, cwd=tmp_path) == 0
    assert _run("git", "clone", "-q", remote, repo, cwd=tmp_path) == 0
    (repo / "experiments").mkdir()
    reg = repo / "experiments" / "registry.jsonl"
    shutil.copy(ran / "registry.jsonl", reg)
    shutil.copytree(ran / "results", repo / "experiments" / "results")
    # results/<run>/ apunta a ../../registry.jsonl: la misma ruta relativa sirve aquí.
    assert _run("git", "checkout", "-q", "-b", "main", cwd=repo) == 0
    assert _run(*git, "add", "-A", cwd=repo) == 0
    assert _run(*git, "commit", "-q", "-m", "base", cwd=repo) == 0
    assert _run("git", "push", "-q", "origin", "main", cwd=repo) == 0

    assert _run("bash", SCRIPT, "main", cwd=repo, env=env) == 0
    append_trials(reg, [{"kind": "signal", "extra": True}])  # agregar una línea válida
    assert _run("bash", SCRIPT, "main", cwd=repo, env=env) == 0
    lines = reg.read_text(encoding="utf-8").splitlines(keepends=True)
    reg.write_text("".join(lines[:-3]), encoding="utf-8")  # recorte
    assert _run("bash", SCRIPT, "main", cwd=repo, env=env) == 1
    edited = "".join(lines).replace('"kind": "signal"', '"kind": "señal"', 1)
    reg.write_text(edited, encoding="utf-8")  # edición
    assert _run("bash", SCRIPT, "main", cwd=repo, env=env) == 1
    # Base inexistente: falla cerrado (no acepta por defecto).
    assert _run("bash", SCRIPT, "rama-que-no-existe", cwd=repo, env=env) != 0
