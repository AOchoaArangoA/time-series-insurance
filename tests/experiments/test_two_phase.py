"""Validación única en dos fases (spec 004, US2: T020-T025)."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures.synthetic_bundle import mutate_after
from tsinsurance.cli import main
from tsinsurance.data.bundle import seal_bundle
from tsinsurance.errors import ValidationPreconditionError
from tsinsurance.experiments import read_registry, run_experiment, validate_experiment
from tsinsurance.experiments.registry import prior_information_ratios, prior_trials_after

CUT = "2016-12-30"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _repo(exp: Path) -> Path:
    """Convierte la carpeta del experimento en un repositorio con todo confirmado."""
    (exp / ".gitignore").write_text("data/\n", encoding="utf-8")
    _git(exp, "init", "-q")
    _git(exp, "add", "-A")
    _git(exp, "commit", "-q", "-m", "base")
    return exp


def _commit(exp: Path) -> None:
    _git(exp, "add", "-A")
    _git(exp, "commit", "-q", "-m", "calibración")


def _calibrate(experiment_file: Path) -> str:
    return run_experiment(experiment_file).run_id


# --- SC-003: la calibración no ve nada posterior al corte ---------------------------------


def _comparable(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "ideas": r["ideas"],
        "econometric": {k: {**v, "notes": None} for k, v in r["econometric"].items()},
        "frozen": r["calibration"]["frozen"],
        "assumptions": r["assumptions"],
    }


def test_calibration_identical_after_mutating_post_cut_data(experiment_file: Path) -> None:
    bundle_dir = experiment_file.parent / "data"
    first = run_experiment(experiment_file, record=False).result
    assert mutate_after(bundle_dir, CUT) > 0
    second = run_experiment(experiment_file, record=False).result
    assert first["provenance"]["bundle"]["sha256"] != second["provenance"]["bundle"]["sha256"]
    assert _comparable(first) == _comparable(second)


def test_calibration_does_not_validate(experiment_file: Path) -> None:
    res = run_experiment(experiment_file)
    rows = read_registry(experiment_file.parent / "registry.jsonl")
    kinds = [r["kind"] for r in rows]
    assert "validation" not in kinds and kinds.count("calibration") == 1
    assert res.result["phase"] == "calibration"
    assert "validación fuera de muestra PENDIENTE" in res.report
    assert f"--calibration {res.run_id}" in res.report
    for r in rows:
        if r["kind"] in ("signal", "econometric"):
            assert r["eval_end"] <= CUT


# --- SC-004: precondiciones -------------------------------------------------------------


def test_validate_happy_path_in_git(experiment_file: Path) -> None:
    exp = _repo(experiment_file.parent)
    run_id = _calibrate(experiment_file)
    _commit(exp)
    v = validate_experiment(experiment_file, run_id)
    assert v.result["phase"] == "validation" and v.result["calibration_run_id"] == run_id
    # Sólo razones heredadas de la calibración (diagnósticos del modelo sintético; I1).
    assert all(r.startswith("calibración: ") for r in v.result["status"]["exploratory_reasons"])
    vals = [r for r in read_registry(exp / "registry.jsonl") if r["kind"] == "validation"]
    assert len(vals) == 2 + 1  # 2 activos × 1 idea + 1 modelo
    assert all("timing_ir_per_period" not in r for r in vals)  # nunca entran al DSR (I3)
    assert v.result["status"]["out_of_sample"] == "abierta"


def test_validate_requires_calibration(experiment_file: Path) -> None:
    with pytest.raises(ValidationPreconditionError, match="No hay una calibración"):
        validate_experiment(experiment_file, "no-existe")
    assert main(["experiment", "validate", str(experiment_file), "--calibration", "x"]) == 1


def test_validate_requires_declared_registry(experiment_file: Path, tmp_path: Path) -> None:
    run_id = _calibrate(experiment_file)
    with pytest.raises(ValidationPreconditionError, match="bitácora declarada"):
        validate_experiment(experiment_file, run_id, registry=tmp_path / "otra.jsonl")


def test_validate_rejects_changed_experiment(experiment_file: Path) -> None:
    run_id = _calibrate(experiment_file)
    experiment_file.write_text(experiment_file.read_text().replace("reps = 50", "reps = 60"))
    with pytest.raises(ValidationPreconditionError, match="cambió desde la calibración"):
        validate_experiment(experiment_file, run_id)


def test_validate_rejects_changed_pre_cut_data(experiment_file: Path) -> None:
    run_id = _calibrate(experiment_file)
    bundle_dir = experiment_file.parent / "data"
    csv = bundle_dir / "market_series.csv"
    lines = csv.read_text().splitlines()
    head, first = lines[0], lines[1].split(",")
    first[2] = str(float(first[2]) * 1.01)  # dato de 2010: anterior al corte
    csv.write_text("\n".join([head, ",".join(first), *lines[2:]]) + "\n")
    seal_bundle(bundle_dir)
    with pytest.raises(ValidationPreconditionError, match="paquete"):
        validate_experiment(experiment_file, run_id)


def test_validate_accepts_new_post_cut_data(experiment_file: Path) -> None:
    """Agregar o cambiar datos POSTERIORES al corte no invalida la calibración."""
    run_id = _calibrate(experiment_file)
    mutate_after(experiment_file.parent / "data", CUT)
    v = validate_experiment(experiment_file, run_id)
    assert v.result["phase"] == "validation"


def test_validate_rejects_uncommitted_and_untracked(experiment_file: Path) -> None:
    exp = _repo(experiment_file.parent)
    run_id = _calibrate(experiment_file)
    # Resultados y bitácora de la calibración sin confirmar.
    with pytest.raises(ValidationPreconditionError):
        validate_experiment(experiment_file, run_id)
    _commit(exp)
    (exp / "senal_nueva.py").write_text("x = 1\n")
    with pytest.raises(ValidationPreconditionError, match="no rastreados"):
        validate_experiment(experiment_file, run_id)


def test_without_git_validation_is_exploratory(experiment_file: Path) -> None:
    run_id = _calibrate(experiment_file)
    v = validate_experiment(experiment_file, run_id)
    assert any("sin repositorio git" in r for r in v.result["status"]["exploratory_reasons"])


# --- FR-009 / FR-009a: periodo ya visto (B1) ------------------------------------------------


def _seen_reasons(v: Any) -> list[str]:
    return [r for r in v.result["status"]["exploratory_reasons"] if "ya visto" in r]


def test_second_validation_is_flagged(experiment_file: Path) -> None:
    run_id = _calibrate(experiment_file)
    first = validate_experiment(experiment_file, run_id)
    assert not _seen_reasons(first)
    again = validate_experiment(experiment_file, run_id)
    assert _seen_reasons(again)


def test_renamed_experiment_cannot_hide_reopening(experiment_file: Path) -> None:
    validate_experiment(experiment_file, _calibrate(experiment_file))
    experiment_file.write_text(experiment_file.read_text().replace('id = "prueba"', 'id = "otra"'))
    v = validate_experiment(experiment_file, _calibrate(experiment_file))
    assert any("prueba" in r for r in _seen_reasons(v))


def test_extended_end_cannot_hide_reopening(experiment_file: Path) -> None:
    validate_experiment(experiment_file, _calibrate(experiment_file))
    experiment_file.write_text(
        experiment_file.read_text().replace(
            'assets = ["AAA", "BBB"]', 'assets = ["AAA", "BBB"]\nend = "2019-06-28"'
        )
    )
    v = validate_experiment(experiment_file, _calibrate(experiment_file))
    assert _seen_reasons(v)


def test_full_sample_run_counts_as_seen(experiment_file: Path) -> None:
    text = experiment_file.read_text()
    experiment_file.write_text(text.replace(f'train_end = "{CUT}"\n', ""))
    run_experiment(experiment_file)  # muestra completa: mira 2017-2019
    experiment_file.write_text(text)
    v = validate_experiment(experiment_file, _calibrate(experiment_file))
    assert {r.split(" de ")[1].split(" ")[0] for r in _seen_reasons(v)} == {"AAA", "BBB"}


# --- Modelos econométricos por fase (FR-010) ------------------------------------------------


def test_econometric_validation_uses_only_post_cut_forecasts(experiment_file: Path) -> None:
    run_id = _calibrate(experiment_file)
    v = validate_experiment(experiment_file, run_id)
    econ = v.result["validation"]["econometric"]["macro"]
    assert any("sólo con pronósticos" in n for n in econ["notes"])
    assert econ["n_forecasts"] <= 36  # 2017-2019 mensual
    cal = json.loads((experiment_file.parent / "results" / run_id / "result.json").read_text())
    assert cal["calibration"]["frozen"]["econometric"]["macro"]["n_specifications_counted"] == 1


# --- FR-009b: inferencia de la validación ---------------------------------------------------


def test_validation_inference(experiment_file: Path) -> None:
    run_id = _calibrate(experiment_file)
    v = validate_experiment(experiment_file, run_id).result
    frozen = json.loads((experiment_file.parent / "results" / run_id / "result.json").read_text())[
        "calibration"
    ]["frozen"]
    assert v["assumptions"]["family"] == frozen["family"]
    for row in v["validation"]["ideas"]["tendencia"]["assets"]:
        assert row["p_holm"] >= row["timing_p"]
        assert row["exposure_calibration"] == pytest.approx(
            frozen["ideas"]["tendencia"]["assets"][row["asset"]]["exposure_calibration"]
        )
        assert 0 <= row["p_vs_cash_hac"] <= 1


# --- FR-022a: ventana de las pruebas previas (I3) -------------------------------------------


def test_prior_split_by_window() -> None:
    rows = [
        {
            "kind": "signal",
            "key": "a",
            "asset": "X",
            "timing_ir_per_period": 0.1,
            "periods_per_year": 252,
            "eval_end": "2015-12-31",
        },
        {
            "kind": "signal",
            "key": "b",
            "asset": "X",
            "timing_ir_per_period": 0.2,
            "periods_per_year": 252,
            "eval_end": "2019-12-31",
        },
        {
            "kind": "econometric",
            "key": "c",
            "asset": "X",
            "timing_ir_per_period": 0.3,
            "periods_per_year": 252,
        },  # v0.1: sin ventana ⇒ posterior al corte
        {"kind": "validation", "key": "d", "asset": "X", "timing_ir_per_period": 9.9},
    ]
    v = prior_information_ratios(rows, periods_per_year=252, max_eval_end="2016-12-30")
    assert v == {"X": [0.1]}
    assert prior_trials_after(rows, periods_per_year=252, cut="2016-12-30") == {"X": 2}
    assert prior_information_ratios(rows, periods_per_year=252) == {"X": [0.1, 0.2, 0.3]}
    assert prior_trials_after(rows, cut=None) == {}  # sin declaradas de señal


def test_cli_validate(experiment_file: Path, tmp_path: Path) -> None:
    run_id = _calibrate(experiment_file)
    out = tmp_path / "out"
    code = main(
        [
            "experiment",
            "validate",
            str(experiment_file),
            "--calibration",
            run_id,
            "--output",
            str(out),
        ]
    )
    assert code == 0 and any(out.rglob("result.json"))
    shutil.rmtree(out)


# --- Regresiones de la revisión de implementación ------------------------------------------


def test_validation_statistic_depends_on_calibration_exposure() -> None:
    """B1: la prueba de validación es el IR de r − e·b, no una diferencia de Sharpe."""
    import numpy as np
    import pandas as pd

    from tsinsurance.experiments.validate import _active_ir_test

    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2015-01-01", periods=1500)
    bench = pd.Series(rng.normal(3e-4, 0.01, len(idx)), index=idx)
    strat = 0.5 * bench + pd.Series(rng.normal(1e-4, 0.004, len(idx)), index=idx)
    p_low = _active_ir_test(strat, bench, 0.3, 252)[1]
    p_true = _active_ir_test(strat, bench, 0.5, 252)[1]
    assert p_low != pytest.approx(p_true, abs=1e-3)


def test_portfolio_validation_marks_constituents_as_seen() -> None:
    """B2: una validación de cartera cuenta como periodo visto para cada constituyente."""
    from tsinsurance.experiments.validate import _seen_after

    rows = [
        {
            "kind": "validation",
            "asset": "U:A+B",
            "universe": ["A", "B"],
            "experiment_id": "rot",
            "run_id": "r1",
        },
    ]
    assert _seen_after(rows, "A", "2014-12-31", exclude_run="x")
    assert not _seen_after(rows, "C", "2014-12-31", exclude_run="x")


def test_code_change_between_phases_blocks_validation(experiment_file: Path) -> None:
    """I2: cambiar código Python entre calibración y validación impide validar."""
    exp = _repo(experiment_file.parent)
    run_id = _calibrate(experiment_file)
    _commit(exp)
    (exp / "mi_senal.py").write_text("def f():\n    return 1\n")
    _commit(exp)
    with pytest.raises(ValidationPreconditionError, match="código Python cambió"):
        validate_experiment(experiment_file, run_id)


def test_declared_signal_tests_count_in_n() -> None:
    """I3: las pruebas declaradas de tipo señal suman en N por activo."""
    rows = [
        {
            "kind": "declared_prior",
            "declared_kind": "signal",
            "assets": ["X", "Y"],
            "n_tests_per_asset": 3,
        }
    ]
    assert prior_trials_after(rows, cut="2016-12-30") == {"X": 3, "Y": 3}
    assert prior_trials_after(rows, cut=None) == {"X": 3, "Y": 3}


def test_declared_without_assets_is_rejected(experiment_file: Path) -> None:
    """I4: una prueba declarada debe decir a qué activos o universo se aplicó."""
    from tsinsurance.errors import TSInsuranceError
    from tsinsurance.experiments.spec import load_experiment

    experiment_file.write_text(
        experiment_file.read_text()
        + '\n[[declared_prior_tests]]\nkind = "regime"\nn_tests = 3\nperiod_start = "2010-01-01"'
        + '\nperiod_end = "2019-12-31"\nscript_sha256 = "x"\n'
    )
    with pytest.raises(TSInsuranceError, match="assets"):
        load_experiment(experiment_file)
