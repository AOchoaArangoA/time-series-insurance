"""VaR/ES, backtesting, estrés y cobertura (spec 007 T012-T014)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from tsinsurance.errors import DataValidationError
from tsinsurance.portfolio_risk import (
    backtest_var,
    christoffersen,
    duration_test,
    immunize,
    kupiec,
    regime_conditional_scenarios,
    stress,
    var_es,
)
from tsinsurance.sensitivities import BondPortfolio, FixedBond, measures
from tsinsurance.stochastics import NodeCurve

CURVE = NodeCurve.from_arrays([0.25, 2, 5, 10, 30], [0.045, 0.040, 0.038, 0.041, 0.044])
PORT = BondPortfolio.of([(FixedBond(7.0, 0.05), 10), (FixedBond(25.0, 0.045), 4)])


def test_var_es_normal_reference_and_ci_cover() -> None:
    x = np.random.default_rng(0).standard_normal(20_000)
    rm = var_es(x, (0.99, 0.975), reps=300)
    q = stats.norm.ppf(0.99)
    assert rm.var["0.99"] == pytest.approx(q, abs=0.06)
    assert rm.es["0.975"] == pytest.approx(stats.norm.pdf(stats.norm.ppf(0.975)) / 0.025, abs=0.06)
    lo, hi = rm.var_ci["0.99"]
    assert lo < q < hi
    blk = var_es(x[:2000], ci="block", reps=200, monte_carlo=True)
    assert any("bloques" in n for n in blk.notes) and any("simulación" in n for n in blk.notes)


def test_kupiec_and_christoffersen_reference_values() -> None:
    hits = np.zeros(1000, dtype=int)
    hits[::100] = 1  # 10 excepciones, espaciadas: tasa correcta al 1 %
    k = kupiec(hits, 0.01)
    assert k["exceptions"] == 10 and k["lr"] == pytest.approx(0.0, abs=1e-9)
    clustered = np.zeros(1000, dtype=int)
    clustered[500:510] = 1  # mismas 10, agrupadas
    assert christoffersen(clustered, 0.01)["pvalue_ind"] < 0.001
    assert christoffersen(hits, 0.01)["pvalue_ind"] > 0.05
    assert duration_test(clustered)["pvalue"] < 0.01


def test_backtest_detects_underestimated_volatility_and_z2() -> None:
    rng = np.random.default_rng(1)
    n = 1000
    sigma = 0.01 * np.exp(0.3 * np.sin(np.arange(n) / 50))
    loss = sigma * rng.standard_t(5, n) / np.sqrt(5 / 3)
    q99 = stats.t.ppf(0.99, 5) / np.sqrt(5 / 3)
    good = backtest_var(loss, sigma * q99, 0.99)
    bad = backtest_var(loss, 0.7 * sigma * q99, 0.99)
    assert good.kupiec["pvalue"] > 0.01 and bad.kupiec["pvalue"] < 0.01
    # Z2 con la distribución predictiva guardada (escenarios) de cada día.
    base = rng.standard_t(5, 2000) / np.sqrt(5 / 3)
    es_unit = float(base[base >= np.quantile(base, 0.99)].mean())
    pred = [s * base for s in 0.7 * sigma]
    z = backtest_var(
        loss,
        0.7 * sigma * np.quantile(base, 0.99),
        0.99,
        es_forecasts=0.7 * sigma * es_unit,
        predictive=pred,
        reps=300,
    )
    assert z.z2["statistic"] > 0 and z.z2["pvalue"] < 0.05
    short = backtest_var(loss[:200], sigma[:200] * q99, 0.99)
    assert short.inconclusive and "NO CONCLUYENTE" in short.summary()


def test_stress_signs_and_regime_conditional() -> None:
    rep = stress(PORT, CURVE)
    assert rep.results["paralelo +"] < 0 < rep.results["paralelo −"]
    idx = pd.bdate_range("2020-01-01", periods=300)
    ch = pd.DataFrame(
        np.random.default_rng(2).normal(0, 1e-4, (300, 5)), index=idx, columns=list(CURVE.tenors)
    )
    prob = pd.Series(np.r_[np.zeros(200), np.ones(100)], index=idx)
    sc = regime_conditional_scenarios(ch, prob)
    assert sc.n == 100
    with pytest.raises(DataValidationError):
        regime_conditional_scenarios(ch, prob * 0.5)


def test_immunize_feasible_and_infeasible() -> None:
    hedges = [FixedBond(t, 0.0, 1) for t in (0.25, 2.0, 5.0, 10.0, 30.0)]  # uno por nodo
    res = immunize(PORT, hedges, CURVE)
    assert res.feasible and max(abs(v) for v in res.residual_exposure.values()) < 1e-6
    hedged = BondPortfolio.of([*PORT.positions, *zip(hedges, res.quantities, strict=True)])
    assert abs(measures(hedged, CURVE).dv01) < 1e-8
    only_long = immunize(PORT, hedges[:2], CURVE, bounds=(0.0, np.inf))
    assert not only_long.feasible
