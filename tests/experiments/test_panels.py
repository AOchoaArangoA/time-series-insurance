"""Paneles en experimentos: punto en el tiempo, dos fases, memoria y α congelado (spec 006, US3)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.fixtures.synthetic_bundle import panel_bundle
from tsinsurance.data.bundle import Bundle
from tsinsurance.errors import TSInsuranceError
from tsinsurance.experiments.panels import Y, analyze_panel, build_panel, mde
from tsinsurance.experiments.spec import alpha_split, load_experiment

PANEL_EXPERIMENT = """
[experiment]
id = "panel_prueba"
hypothesis = "los sensibles caen tras subidas del spread"
registry = "registry.jsonl"

[data]
bundle = "data"
assets = ["U0", "U1", "U2", "U3", "U4", "U5"]

[validation]
seed = 3
train_end = "2015-12-31"

[[panels]]
name = "spread"
units = ["U0", "U1", "U2", "U3", "U4", "U5"]
regressors = ["SPREAD"]
transforms = { SPREAD = "diff" }
characteristics = { sensible = ["U0", "U1", "U2"] }
interactions = [["SPREAD", "sensible"]]
estimator = "twfe"
cov = "driscoll_kraay"
bootstrap_draws = 999
hypotheses = [{ coef = "SPREAD:sensible", sign = "-" }]
justification = "duración de los activos sensibles (fijada antes de mirar)"
"""


@pytest.fixture
def pdir(tmp_path: Path) -> Path:
    panel_bundle(tmp_path / "data")
    (tmp_path / "experiment.toml").write_text(PANEL_EXPERIMENT, encoding="utf-8")
    return tmp_path


def test_alpha_split_sums_alpha_and_renormalizes() -> None:
    full = alpha_split(0.05, strategies=True, regimes=True, panels=True)
    assert full == pytest.approx({"strategies": 0.035, "regimes": 0.0075, "panels": 0.0075})
    only = alpha_split(0.05, strategies=False, regimes=False, panels=True)
    assert only == {"panels": pytest.approx(0.05)}
    two = alpha_split(0.05, strategies=True, regimes=False, panels=True)
    assert sum(two.values()) == pytest.approx(0.05)
    assert two["strategies"] / two["panels"] == pytest.approx(0.7 / 0.15)


def test_spec_validation_rejects_bad_blocks(pdir: Path) -> None:
    path = pdir / "experiment.toml"
    path.write_text(PANEL_EXPERIMENT.replace('sign = "-"', 'sign = "neg"'))
    with pytest.raises(TSInsuranceError, match="signo"):
        load_experiment(path)
    path.write_text(PANEL_EXPERIMENT.replace('coef = "SPREAD:sensible"', 'coef = "VIX"'))
    with pytest.raises(TSInsuranceError, match="no está"):
        load_experiment(path)


def test_panel_is_point_in_time(pdir: Path) -> None:
    """Cambiar los datos posteriores a t no cambia los regresores en t."""
    bundle = Bundle.load(pdir / "data")
    spec = load_experiment(pdir / "experiment.toml").panels[0]
    full = build_panel(bundle, spec)
    cut = bundle.as_of("2014-06-30")
    early = build_panel(cut, spec)
    common = early.index.intersection(full.index)
    pd.testing.assert_series_equal(full.loc[common, "SPREAD"], early.loc[common, "SPREAD"])
    # y_next de la última decisión usa el mes siguiente, que en el paquete truncado no existe.
    assert early.index.get_level_values(1).max() < pd.Timestamp("2014-06-30")
    # Interacción: cero en las unidades sin la característica.
    assert (full.xs("U4", level=0)["SPREAD:sensible"] == 0).all()


def test_validation_window_targets_start_after_cut(pdir: Path) -> None:
    bundle = Bundle.load(pdir / "data")
    spec = load_experiment(pdir / "experiment.toml").panels[0]
    for cut in ("2015-12-31", "2015-12-15"):
        val = build_panel(bundle, spec, after=cut)
        first_target = val.index.get_level_values(1).min() + pd.offsets.MonthEnd(1)
        month_start = first_target - pd.offsets.MonthBegin(1)
        assert month_start > pd.Timestamp(cut)
    # En la calibración, el último mes objetivo termina en o antes del corte.
    cal = build_panel(bundle.as_of("2015-12-31"), spec)
    assert cal.index.get_level_values(1).max() + pd.offsets.MonthEnd(1) <= pd.Timestamp(
        "2015-12-31"
    )


def test_recovers_differential_effect(pdir: Path) -> None:
    bundle = Bundle.load(pdir / "data")
    spec = load_experiment(pdir / "experiment.toml").panels[0]
    run = analyze_panel(bundle, spec, seed=1)
    row = run.rows[0]
    assert not row.inconclusive and row.treated_clusters == 3
    assert row.estimate < 0 and row.p_one_sided < 0.05
    assert row.p_distribution.startswith("wild bootstrap DK")
    assert row.wcr_p_one_sided is not None and row.fixed_b_p_one_sided is not None
    assert row.stability_pvalue is not None and row.stability_pvalue > 0.01
    # Con TWFE, el efecto común de SPREAD queda absorbido por los efectos de tiempo.
    assert "SPREAD" not in run.params


def test_single_treated_unit_is_inconclusive(pdir: Path) -> None:
    path = pdir / "experiment.toml"
    path.write_text(PANEL_EXPERIMENT.replace('sensible = ["U0", "U1", "U2"]', 'sensible = ["U0"]'))
    spec = load_experiment(path).panels[0]
    run = analyze_panel(Bundle.load(pdir / "data"), spec, with_diagnostics=False)
    assert run.rows[0].inconclusive and "G₁" in run.rows[0].reason


def test_mde_uses_one_sided_family_level() -> None:
    from scipy import stats

    z = stats.norm.ppf
    assert mde(0.01, 96, 24) == pytest.approx((z(0.95) + z(0.80)) * 0.01 * 2)
    # α de la familia de paneles 0,0075 repartido entre 2 hipótesis (primera etapa de Holm).
    assert mde(0.01, 96, 24, alpha=0.0075, m=2) == pytest.approx(
        (z(1 - 0.00375) + z(0.80)) * 0.01 * 2
    )
    assert np.isnan(mde(0.01, 96, 0))


def test_two_phase_memory_and_frozen_alpha(pdir: Path) -> None:
    from tsinsurance.experiments import read_registry, run_experiment, validate_experiment

    path = pdir / "experiment.toml"
    cal = run_experiment(path)
    entry = cal.result["panels"]["spread"]
    assert entry["prior_tests_in_holm"] == 0 and entry["dependent"] == Y
    frozen = cal.result["calibration"]["frozen"]
    assert frozen["alpha_split"] == {"panels": pytest.approx(0.05)}
    assert [h["coef"] for h in frozen["panels"]["spread"]["hypotheses"]] == ["SPREAD:sensible"]
    rows = read_registry(pdir / "registry.jsonl")
    panel_lines = [r for r in rows if r["kind"] == "panel"]
    assert panel_lines and panel_lines[0]["universe"] == [f"U{i}" for i in range(6)]

    v = validate_experiment(path, cal.run_id).result
    out = v["validation"]["panels"]["spread"][0]
    assert out["eval_start"] >= "2015-12-31" and out["alpha_family"] == pytest.approx(0.05)
    assert np.isfinite(out["mde"]) and "p_holm" in out
    assert v["assumptions"]["panel_family"] == ["panel:spread:SPREAD:sensible-"]

    # Otra variante (otro estimador) sobre un universo parecido: cuenta en el Holm (I3).
    path.write_text(
        PANEL_EXPERIMENT.replace('estimator = "twfe"', 'estimator = "fe"').replace(
            'units = ["U0", "U1", "U2", "U3", "U4", "U5"]', 'units = ["U0", "U1", "U2", "U3", "U4"]'
        )
    )
    second = run_experiment(path).result
    assert second["panels"]["spread"]["prior_tests_in_holm"] == 1
