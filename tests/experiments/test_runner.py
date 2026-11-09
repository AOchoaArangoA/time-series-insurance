import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tsinsurance.backtest import TrialRegistry
from tsinsurance.backtest.sweep import evaluate_grid, holm, select
from tsinsurance.cli import main
from tsinsurance.errors import TSInsuranceError
from tsinsurance.experiments import (
    available_signals,
    load_experiment,
    prior_information_ratios,
    read_registry,
    register_signal,
    run_experiment,
)
from tsinsurance.experiments.registry import append_trials, verify_registry
from tsinsurance.experiments.signals import get_signal


def kinds(path: Path) -> list[str]:
    return [r["kind"] for r in read_registry(path)]


def test_run_outputs_preregistration_and_validation(experiment_file: Path) -> None:
    res = run_experiment(experiment_file)
    data = json.loads((res.output_dir / "result.json").read_text())
    assert data["result_version"] == "1.1" and data["experiment"]["sha256"]
    idea = data["ideas"]["tendencia"]
    assert idea["status"] == "evaluada"
    assert all(c["combinations"] == 2 and not c["failed"] for c in idea["lookahead"].values())
    # La selección sólo mira la calibración.
    assert all(str(d)[:10] <= "2016-12-30" for d in idea["selection"]["eval_end"].values())
    assert data["calibration"]["tendencia"]["times_opened_before"] == 0
    assert data["econometric"]["macro"]["n_specifications_counted"] == 1
    reg = experiment_file.parent / "registry.jsonl"
    k = kinds(reg)
    assert k[0] == "preregistration" and k.count("signal") == 4
    assert k.count("econometric") == 1 and k.count("validation") == 1
    assert verify_registry(reg) == []
    assert not res.exploratory and "Conclusión automática" in res.report


def test_repeat_does_not_inflate_but_reopened_validation_is_flagged(experiment_file: Path) -> None:
    first = run_experiment(experiment_file)
    n1 = first.result["ideas"]["tendencia"]["selection"]["n_trials"]
    again = run_experiment(experiment_file)
    assert again.result["ideas"]["tendencia"]["selection"]["n_trials"] == n1
    assert again.exploratory
    assert any("ya abierta" in r for r in again.result["status"]["exploratory_reasons"])
    assert again.result["econometric"]["macro"]["n_specifications_counted"] == 1
    text = experiment_file.read_text().replace("fast = [20, 50]", "fast = [20, 50, 100]")
    experiment_file.write_text(text.replace("min_train = 36", "min_train = 48"))
    wider = run_experiment(experiment_file)
    sel = wider.result["ideas"]["tendencia"]["selection"]["n_trials"]
    # previas distintas (econ. anterior) + 3 señales nuevas + 1 econ. nueva por activo
    assert sel["0"] == n1["0"] + 1 + 1
    assert wider.result["econometric"]["macro"]["n_specifications_counted"] == 2


def test_registry_tampering_detected(experiment_file: Path) -> None:
    run_experiment(experiment_file)
    reg = experiment_file.parent / "registry.jsonl"
    lines = reg.read_text().splitlines()
    reg.write_text("\n".join(lines[:2] + lines[3:]) + "\n")
    assert verify_registry(reg)
    with pytest.raises(TSInsuranceError, match="alterada"):
        run_experiment(experiment_file)


def test_flags_non_canonical_registry_and_unrecorded(experiment_file: Path, tmp_path: Path) -> None:
    alt = run_experiment(experiment_file, registry=tmp_path / "otra.jsonl")
    assert any("distinta" in r for r in alt.result["status"]["exploratory_reasons"])
    dry = run_experiment(experiment_file, record=False, output_root=tmp_path / "out")
    assert dry.n_trials_registered == 0 and dry.exploratory


def test_negative_drift_asset_random_timing_not_significant() -> None:
    """Revisión B1: contra comprar y mantener, estar en efectivo 'gana' a un activo que
    decae; el retorno de timing (vs exposición constante) no debe declararlo hábil."""
    rng = np.random.default_rng(5)
    idx = pd.bdate_range("2010-01-01", periods=2520)
    prices = pd.DataFrame(
        {f"D{i}": 100 * np.exp(np.cumsum(rng.normal(-6e-4, 0.015, len(idx)))) for i in range(3)},
        index=idx,
    )
    from tsinsurance.backtest.signals import sma_crossover

    def random_timing(p, seed):  # type: ignore[no-untyped-def]
        g = np.random.default_rng(seed)
        state = (np.cumsum(g.random(len(p)) < 1 / 20) % 2).astype(float)
        return pd.DataFrame(state, index=p.index, columns=p.columns)

    reg = TrialRegistry()
    _, cur = evaluate_grid(
        prices,
        random_timing,
        {"seed": list(range(10))},
        __import__("tsinsurance").backtest.ExecutionConfig(),
        risk_free=None,
        registry=reg,
        name="azar",
    )
    sel = select(reg, cur, reps=200)
    from tsinsurance.backtest.metrics import sharpe_per_period

    trials = [t for ts in cur.values() for t in ts]
    vs_bh = np.mean([sharpe_per_period(t.active_vs_buy_hold) for t in trials]) * np.sqrt(252)
    timing = np.mean([sharpe_per_period(t.active_returns) for t in trials]) * np.sqrt(252)
    assert vs_bh > 0.1  # frente a comprar y mantener "gana" sólo por exposición
    assert abs(timing) < 0.15  # el retorno de timing medio es ~0: sin habilidad
    assert not sel["significant"].any()
    assert sma_crossover is not None


def test_selection_independent_of_idea_order() -> None:
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2012-01-01", periods=1500)
    prices = pd.DataFrame({"A": 100 * np.exp(np.cumsum(rng.normal(2e-4, 0.01, 1500)))}, index=idx)
    from tsinsurance.backtest import ExecutionConfig

    a, b = get_signal("sma_crossover"), get_signal("tsmom")
    out = []
    for order in (
        (("t", a, {"fast": [20, 50], "slow": [150]}), ("m", b, {"lookback": [63, 126]})),
        (("m", b, {"lookback": [63, 126]}), ("t", a, {"fast": [20, 50], "slow": [150]})),
    ):
        reg, cur = TrialRegistry(), {}
        for name, fn, grid in order:
            cur[name] = evaluate_grid(
                prices, fn, grid, ExecutionConfig(), risk_free=None, registry=reg, name=name
            )[1]
        out.append({n: select(reg, c, reps=100)["dsr"].iloc[0] for n, c in cur.items()})
    assert out[0] == pytest.approx(out[1])


def test_holm() -> None:
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_prior_information_ratios_by_key_and_frequency(tmp_path: Path) -> None:
    reg = tmp_path / "r.jsonl"
    base = {"kind": "signal", "asset": "A", "periods_per_year": 252}
    append_trials(
        reg,
        [
            {**base, "key": "k1", "timing_ir_per_period": 0.01},
            {**base, "key": "k1", "timing_ir_per_period": 0.02},
            {**base, "key": "k2", "timing_ir_per_period": None},
            {**base, "key": "k3", "periods_per_year": 12, "timing_ir_per_period": 0.5},
            {"kind": "preregistration"},
        ],
    )
    rows = read_registry(reg)
    assert sorted(prior_information_ratios(rows, periods_per_year=252)["A"]) == [0.0, 0.02]
    assert prior_information_ratios(rows, exclude_keys=["k1", "k2"], periods_per_year=252) == {}
    assert verify_registry(reg) == []
    reg.write_text("{malo\n")
    with pytest.raises(ValueError):
        read_registry(reg)


def test_spec_validation(experiment_file: Path, tmp_path: Path) -> None:
    spec = load_experiment(experiment_file)
    assert spec.assets == ["AAA", "BBB"] and spec.calibrate_ideas == ["tendencia"]
    p = tmp_path / "bad.toml"
    p.write_text(
        experiment_file.read_text().replace('signal = "sma_crossover"', 'signal = "magia"')
    )
    with pytest.raises(TSInsuranceError, match="magia"):
        load_experiment(p)
    p.write_text(experiment_file.read_text().replace("[validation]", "[validation]\nalpha = 0.2"))
    with pytest.raises(TSInsuranceError, match="alpha"):
        load_experiment(p)
    p.write_text(
        experiment_file.read_text().replace("[validation]", '[validation]\ncalibrate_ideas = ["x"]')
    )
    with pytest.raises(TSInsuranceError, match="calibrate_ideas"):
        load_experiment(p)
    p.write_text('[experiment]\nid="x"\n[data]\nbundle="d"\nassets=["A"]\n')
    with pytest.raises(TSInsuranceError, match="no define"):
        load_experiment(p)


def test_signal_registry() -> None:
    assert {"sma_crossover", "tsmom", "ewma_vol_target", "tsmom_vol_target"} <= set(
        available_signals()
    )
    register_signal("siempre", lambda p: p.notna().astype(float))
    assert get_signal("siempre") is not None and "siempre" in available_signals()
    with pytest.raises(TSInsuranceError):
        get_signal("no_existe")


def test_cli(experiment_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = experiment_file.parent / "data"
    assert main(["bundle", "validate", str(data)]) == 0
    assert main(["bundle", "show", str(data)]) == 0
    assert main(["bundle", "template", str(tmp_path / "t")]) == 0
    assert main(["bundle", "seal", str(tmp_path / "t")]) == 0
    assert main(["bundle", "validate", str(tmp_path / "nada")]) == 1
    assert main(["experiment", "signals"]) == 0
    assert main(["experiment", "run", str(experiment_file), "--output", str(tmp_path / "o")]) == 0
    reg = str(experiment_file.parent / "registry.jsonl")
    assert main(["experiment", "verify", reg]) == 0
    assert main(["experiment", "list", reg]) == 0
    assert "línea(s) registradas" in capsys.readouterr().out
    assert main(["experiment", "run", str(tmp_path / "no.toml")]) == 2
