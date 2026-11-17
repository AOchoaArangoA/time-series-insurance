"""Bitácora a prueba de recortes: estado guardado en cada resultado (T009, SC-001, I14)."""

import json
import shutil
from pathlib import Path

import pytest

from tsinsurance.experiments import run_experiment
from tsinsurance.experiments.registry import (
    GENESIS,
    RegistryHead,
    append_trials,
    line_hash,
    read_registry,
    registry_head,
    verify_registry,
)


def _registry(tmp_path: Path, n: int) -> Path:
    reg = tmp_path / "registry.jsonl"
    append_trials(reg, [{"kind": "signal", "i": i} for i in range(n)])
    return reg


def _cut(reg: Path, keep: int, dest: Path) -> Path:
    lines = reg.read_text(encoding="utf-8").splitlines(keepends=True)
    dest.write_text("".join(lines[:keep]), encoding="utf-8")
    return dest


def test_head_of_missing_and_empty_registry(tmp_path: Path) -> None:
    assert registry_head(tmp_path / "nope.jsonl") == RegistryHead(0, GENESIS)
    (tmp_path / "empty.jsonl").write_text("", encoding="utf-8")
    assert registry_head(tmp_path / "empty.jsonl") == RegistryHead(0, GENESIS)


def test_head_points_to_last_line(tmp_path: Path) -> None:
    reg = _registry(tmp_path, 5)
    head = registry_head(reg)
    assert head.n_lines == 5
    assert head.last_hash == line_hash(read_registry(reg)[-1])
    assert RegistryHead.from_dict(head.to_dict()) == head


def test_result_records_head_before_and_after(experiment_file: Path) -> None:
    res = run_experiment(experiment_file)
    reg = experiment_file.parent / "registry.jsonl"
    before, after = res.result["registry_head_before"], res.result["registry_head"]
    assert before == {"n_lines": 0, "last_hash": GENESIS}
    assert after == registry_head(reg).to_dict()
    assert after["n_lines"] == len(read_registry(reg))
    rel = res.result["provenance"]["registry_relpath"]
    assert (res.output_dir / rel).resolve() == reg.resolve()


@pytest.mark.parametrize("removed", [1, 2, 5])
def test_tail_truncation_detected_against_results(experiment_file: Path, removed: int) -> None:
    run_experiment(experiment_file)
    reg = experiment_file.parent / "registry.jsonl"
    results = experiment_file.parent / "results"
    assert verify_registry(reg, results=results) == []
    n = len(read_registry(reg))
    _cut(reg, n - removed, reg)
    # La cadena sola no lo detecta (hallazgo de la revisión) ...
    assert verify_registry(reg) == []
    # ... el contraste con los resultados publicados sí.
    problems = verify_registry(reg, results=results)
    assert problems and "recorte" in problems[0] and "result.json" in problems[0]


def test_replaced_tail_detected(experiment_file: Path) -> None:
    """Recortar y volver a agregar líneas distintas con la cadena válida también se detecta."""
    run_experiment(experiment_file)
    reg = experiment_file.parent / "registry.jsonl"
    n = len(read_registry(reg))
    _cut(reg, n - 3, reg)
    append_trials(reg, [{"kind": "signal", "fake": i} for i in range(3)])
    assert verify_registry(reg) == []
    problems = verify_registry(reg, results=experiment_file.parent / "results")
    assert problems and "no coincide" in problems[0]


def test_results_of_other_registry_are_ignored(experiment_file: Path, tmp_path: Path) -> None:
    run_experiment(experiment_file)
    results = experiment_file.parent / "results"
    other = _registry(tmp_path, 1)  # bitácora distinta y más corta
    assert verify_registry(other, results=results) == []


def test_old_results_without_head_are_skipped(experiment_file: Path) -> None:
    res = run_experiment(experiment_file)
    path = res.output_dir / "result.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for k in ("registry_head", "registry_head_before"):
        data.pop(k)
    data["provenance"].pop("registry_relpath")
    path.write_text(json.dumps(data), encoding="utf-8")
    reg = experiment_file.parent / "registry.jsonl"
    _cut(reg, 2, reg)
    assert verify_registry(reg, results=experiment_file.parent / "results") == []


def test_results_moved_with_registry_still_match(experiment_file: Path, tmp_path: Path) -> None:
    """La ruta relativa permite verificar en otra máquina o carpeta (CI)."""
    run_experiment(experiment_file)
    moved = tmp_path / "moved"
    shutil.copytree(experiment_file.parent, moved)
    reg = moved / "registry.jsonl"
    assert verify_registry(reg, results=moved / "results") == []
    _cut(reg, 3, reg)
    assert verify_registry(reg, results=moved / "results")
