"""Campos de la bitácora que usan las historias de la spec 004 (T005, revisión B6)."""

import math
from pathlib import Path

import pandas as pd

from tsinsurance.experiments import read_registry, run_experiment


def test_signal_and_econometric_lines_carry_window_fields(experiment_file: Path) -> None:
    run_experiment(experiment_file)
    rows = read_registry(experiment_file.parent / "registry.jsonl")
    trials = [r for r in rows if r["kind"] in ("signal", "econometric")]
    assert {r["kind"] for r in trials} == {"signal", "econometric"}
    for r in trials:
        for field in ("n_obs", "eval_start", "eval_end", "sharpe_se_hac", "periods_per_year"):
            assert field in r, (r["kind"], field)
        assert r["n_obs"] > 0
        assert r["sharpe_se_hac"] is None or math.isfinite(r["sharpe_se_hac"])


def test_econometric_n_obs_is_in_ratio_units_not_forecasts(experiment_file: Path) -> None:
    """El IR econométrico se calcula con retornos diarios: n_obs cuenta días, no meses."""
    res = run_experiment(experiment_file)
    rows = read_registry(experiment_file.parent / "registry.jsonl")
    econ = next(r for r in rows if r["kind"] == "econometric")
    n_forecasts = res.result["econometric"]["macro"]["n_forecasts"]
    assert econ["periods_per_year"] == 252
    assert econ["n_obs"] > 15 * n_forecasts  # ≈ 21 días hábiles por pronóstico mensual
    days = len(pd.bdate_range(econ["eval_start"], econ["eval_end"]))
    assert abs(econ["n_obs"] - days) <= 0.02 * days  # feriados del calendario sintético


def test_signal_n_obs_matches_its_window(experiment_file: Path) -> None:
    run_experiment(experiment_file)
    rows = read_registry(experiment_file.parent / "registry.jsonl")
    sig = next(r for r in rows if r["kind"] == "signal")
    days = len(pd.bdate_range(sig["eval_start"], sig["eval_end"]))
    assert sig["n_obs"] == days
