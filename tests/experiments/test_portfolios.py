"""Ideas de cartera declarativas y registradas (spec 005, US1; revisión B2-B4, I2)."""

from pathlib import Path

import pandas as pd
import pytest

from tests.experiments.conftest import EXPERIMENT
from tsinsurance.errors import TSInsuranceError
from tsinsurance.experiments import read_registry, run_experiment, validate_experiment
from tsinsurance.experiments.portfolio_signals import register_portfolio_signal
from tsinsurance.experiments.registry import jaccard, prior_portfolio_trials
from tsinsurance.experiments.spec import load_experiment

PORTFOLIO = """
[[portfolios]]
name = "rotacion"
universe = ["BBB", "AAA"]
signal = "cross_sectional_momentum"
  [portfolios.grid]
  lookback_m = [6, 12]
  top_k = [1]
"""
DECLARED = """
[[declared_prior_tests]]
kind = "portfolio"
n_tests = 4
universe = ["AAA", "BBB"]
period_start = "2010-01-01"
period_end = "2019-12-31"
script_sha256 = "abc123"
description = "script exploratorio"
"""


@pytest.fixture
def exp(experiment_file: Path) -> Path:
    experiment_file.write_text(EXPERIMENT + PORTFOLIO, encoding="utf-8")
    return experiment_file


def _portfolio_lines(path: Path) -> list[dict]:  # type: ignore[type-arg]
    return [r for r in read_registry(path.parent / "registry.jsonl") if r["kind"] == "portfolio"]


def test_calibration_registers_each_configuration(exp: Path) -> None:
    res = run_experiment(exp)
    lines = _portfolio_lines(exp)
    assert len(lines) == 2
    assert {ln["asset"] for ln in lines} == {"U:AAA+BBB"}  # orden declarado irrelevante
    assert all(ln["eval_end"] <= "2016-12-30" for ln in lines)
    entry = res.result["portfolios"]["rotacion"]
    assert "equal_weight" in entry["benchmark"] and entry["min_history_m"] == 13
    # Ventana común: el benchmark exige 13 cierres de mes de historia.
    assert entry["window_start"] >= "2011-01-01"
    frozen = res.result["calibration"]["frozen"]
    assert frozen["portfolios"]["rotacion"]["universe_id"] == "U:AAA+BBB"
    assert "cartera:rotacion" in frozen["family"]


def test_monthly_rebalancing_is_forced(exp: Path) -> None:
    text = exp.read_text().replace("[execution]\n", '[execution]\nrebalance = "every_bar"\n')
    exp.write_text(text)
    res = run_experiment(exp)
    turnover = [c["turnover_mean"] for c in res.result["portfolios"]["rotacion"]["configurations"]]
    assert all(t < 0.2 for t in turnover)  # sin rotación diaria


def test_second_run_counts_previous_trials(exp: Path) -> None:
    first = run_experiment(exp).result["portfolios"]["rotacion"]
    exp.write_text(exp.read_text().replace("top_k = [1]", "top_k = [1]\n  skip_m = [0]"))
    second = run_experiment(exp).result["portfolios"]["rotacion"]
    n1 = first["selection"]["n_trials"]["0"]
    n2 = second["selection"]["n_trials"]["0"]
    assert n1 == 2 and n2 == 4  # las 2 previas + las 2 nuevas


def test_declared_prior_tests_count_once(exp: Path) -> None:
    exp.write_text(exp.read_text() + DECLARED)
    first = run_experiment(exp).result["portfolios"]["rotacion"]
    assert first["selection"]["n_trials"]["0"] == 2 + 4
    run_experiment(exp)
    declared = [
        r for r in read_registry(exp.parent / "registry.jsonl") if r["kind"] == "declared_prior"
    ]
    assert len(declared) == 1  # idempotente


def test_jaccard_memory_survives_universe_changes() -> None:
    nine = [f"S{i}" for i in range(9)]
    eleven = [*nine, "S9", "S10"]
    rows = [
        {
            "kind": "portfolio",
            "key": "k1",
            "universe": nine,
            "timing_ir_per_period": 0.1,
            "periods_per_year": 252,
            "eval_end": "2014-12-31",
        },
        {
            "kind": "portfolio",
            "key": "k2",
            "universe": ["X", "Y"],
            "timing_ir_per_period": 0.2,
            "periods_per_year": 252,
            "eval_end": "2014-12-31",
        },
        {
            "kind": "portfolio",
            "key": "k3",
            "universe": nine,
            "timing_ir_per_period": 0.3,
            "periods_per_year": 252,
            "eval_end": "2020-12-31",
        },
        {"kind": "declared_prior", "declared_kind": "portfolio", "universe": nine, "n_tests": 4},
    ]
    assert jaccard(nine, eleven) == pytest.approx(9 / 11)
    ratios, extra = prior_portfolio_trials(rows, eleven, periods_per_year=252, cut="2016-12-30")
    assert ratios == [0.1] and extra == 1 + 4  # k3 pasa el corte; k2 es otro universo


def test_lookahead_portfolio_signal_is_rejected(exp: Path) -> None:
    def cheat(prices: pd.DataFrame, top_k: int = 1) -> pd.DataFrame:
        fut = prices.shift(-21) / prices - 1
        return (fut.rank(axis=1, ascending=False) <= top_k).astype(float)

    register_portfolio_signal("trampa", cheat)
    text = exp.read_text().replace('"cross_sectional_momentum"', '"trampa"')
    exp.write_text(text.replace("lookback_m = [6, 12]\n", ""))
    res = run_experiment(exp)
    entry = res.result["portfolios"]["rotacion"]
    assert entry["rejected_lookahead"] and entry["best_params"] is None
    assert "RECHAZADA por anticipación" in res.report


def test_validation_flags_seen_constituents(exp: Path) -> None:
    cal = run_experiment(exp)
    v = validate_experiment(exp, cal.run_id)
    port = v.result["validation"]["portfolios"]["rotacion"]
    assert port["universe_id"] == "U:AAA+BBB" and "p_holm" in port
    assert "cartera:rotacion" in v.result["assumptions"]["family"]
    # La idea 'tendencia' del mismo experimento validó AAA y BBB: una segunda validación
    # ve los constituyentes.
    again = validate_experiment(exp, cal.run_id)
    assert any("ya visto" in r for r in again.result["status"]["exploratory_reasons"])


def test_universe_needs_two_assets(experiment_file: Path) -> None:
    experiment_file.write_text(
        EXPERIMENT + PORTFOLIO.replace('universe = ["BBB", "AAA"]', 'universe = ["AAA"]')
    )
    with pytest.raises(TSInsuranceError, match="al menos 2 activos"):
        load_experiment(experiment_file)
