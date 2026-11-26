"""Calibración Monte Carlo de la spec 006 (SC-001, SC-003, SC-004 y SC-005; research R7-R9).

- SC-001: confusor constante por unidad (N = 50, T = 20, corr(α_i, x) = 0,5, β = 1, 500
  réplicas): sesgo medio de FE ≤ 0,02·|β| y del MCO agrupado ≥ 0,2·|β|.
- SC-003: Mundlak/CRE con N = 50, T = 20 (2 000 réplicas): tamaño 3-7 % sin correlación y
  potencia ≥ 80 % con corr(α_i, x̄_i) = 0,3. Con N = 11 se reporta el tamaño con F(q, G−1).
- SC-004: N = 11, factor común con cargas heterogéneas, regresor persistente (φ = 0,95),
  interacción x_t·D_i con G₁ ∈ {2, 5} y T ∈ {36, 300} (1 000 réplicas por celda): tamaño
  unilateral al 5 % de Driscoll-Kraay (corrección por grados de libertad + fixed-b) entre
  3 % y 7 % más 1,96 errores de Monte Carlo. Con G₁ = 1, 100 % no concluyente. El tamaño
  de los errores agrupados se reporta sin aserción.

  Hallazgo (R9): con t(T−1), como preveía el diseño, el tamaño con T = 36 era ~9 %.
- SC-005: diferencias en diferencias con N = 20 (10 tratadas), T = 40, evento en T/2:
  sesgo ≤ 5 % bajo tendencias paralelas; se reportan el tamaño de la prueba de tendencias
  previas y su potencia contra una violación que sesga el ATET en ~1 ee.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from tsinsurance.panel import fit_panel
from tsinsurance.panel.did import diff_in_diff
from tsinsurance.panel.inference import mundlak_test

pytestmark = pytest.mark.slow


def _mc_margin(reps: int, p: float = 0.05) -> float:
    return 1.96 * float(np.sqrt(p * (1 - p) / reps))


def _confounded(rng: np.random.Generator, n: int, t: int, rho: float) -> pd.DataFrame:
    a = rng.normal(size=n)
    x = rho * a[:, None] + np.sqrt(1 - rho**2) * rng.normal(size=(n, t))
    y = 1.0 * x + a[:, None] + rng.normal(size=(n, t))
    idx = pd.MultiIndex.from_product([range(n), range(t)], names=["entity", "time"])
    return pd.DataFrame({"y": y.ravel(), "x": x.ravel()}, index=idx)


def test_sc001_fixed_effects_remove_time_invariant_confounder() -> None:
    rng = np.random.default_rng(6001)
    fe, pooled = [], []
    for _ in range(500):
        df = _confounded(rng, 50, 20, 0.5)
        fe.append(fit_panel(df, "y", ["x"], estimator="fe", cov="unadjusted").params["x"])
        pooled.append(fit_panel(df, "y", ["x"], estimator="pooled", cov="unadjusted").params["x"])
    assert abs(np.mean(fe) - 1.0) <= 0.02
    assert abs(np.mean(pooled) - 1.0) >= 0.2


def _cre(rng: np.random.Generator, n: int, t: int, corr: float) -> pd.DataFrame:
    xbar = rng.normal(size=n)
    a = corr * xbar + np.sqrt(1 - corr**2) * rng.normal(size=n)
    x = xbar[:, None] + rng.normal(size=(n, t))
    y = 0.5 * x + a[:, None] + rng.normal(size=(n, t))
    idx = pd.MultiIndex.from_product([range(n), range(t)], names=["entity", "time"])
    return pd.DataFrame({"y": y.ravel(), "x": x.ravel()}, index=idx)


def test_sc003_mundlak_size_and_power() -> None:
    reps = 2000
    rng = np.random.default_rng(6003)
    size = np.mean(
        [
            mundlak_test(_cre(rng, 50, 20, 0.0), "y", ["x"]).mundlak_pvalue < 0.05
            for _ in range(reps)
        ]
    )
    power = np.mean(
        [
            mundlak_test(_cre(rng, 50, 20, 0.3), "y", ["x"]).mundlak_pvalue < 0.05
            for _ in range(reps)
        ]
    )
    small = np.mean(
        [mundlak_test(_cre(rng, 11, 20, 0.0), "y", ["x"]).mundlak_pvalue < 0.05 for _ in range(500)]
    )
    print(f"SC-003: tamaño {size:.3f}, potencia {power:.3f}, tamaño N=11 {small:.3f}")
    assert 0.03 <= size <= 0.07
    assert power >= 0.80


def _factor_panel(rng: np.random.Generator, t: int, g1: int, n: int = 11) -> pd.DataFrame:
    x = np.zeros(t)
    shocks = rng.normal(size=t)
    for s in range(1, t):
        x[s] = 0.95 * x[s - 1] + shocks[s]
    f = rng.normal(size=t)
    loadings = rng.uniform(0.5, 1.5, n)
    rows = []
    for i in range(n):
        y = rng.normal() + loadings[i] * f + rng.normal(size=t)
        rows.append(
            pd.DataFrame({"entity": f"U{i}", "time": np.arange(t), "y": y, "xd": x * (i < g1)})
        )
    return pd.concat(rows).set_index(["entity", "time"])


@pytest.mark.parametrize(("t", "g1"), [(36, 2), (36, 5), (300, 2), (300, 5)])
def test_sc004_driscoll_kraay_one_sided_size(t: int, g1: int) -> None:
    reps = 1000
    rng = np.random.default_rng(6004 + 10 * t + g1)
    rej_dk, rej_cl = 0, 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for _ in range(reps):
            df = _factor_panel(rng, t, g1)
            dk = fit_panel(df, "y", ["xd"], estimator="twfe", cov="driscoll_kraay")
            rej_dk += dk.pvalues["xd"] / 2 < 0.05 and dk.tstats["xd"] > 0
            cl = fit_panel(df, "y", ["xd"], estimator="twfe", cov="clustered_entity")
            rej_cl += stats.norm.sf(cl.tstats["xd"]) < 0.05
    size_dk, size_cl = rej_dk / reps, rej_cl / reps
    print(f"SC-004 T={t} G1={g1}: DK {size_dk:.3f} · agrupados {size_cl:.3f}")
    assert 0.03 - _mc_margin(reps) <= size_dk <= 0.07 + _mc_margin(reps)


def test_sc004_single_treated_unit_is_always_inconclusive() -> None:
    rng = np.random.default_rng(6040)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        flags = [
            "xd"
            in fit_panel(
                _factor_panel(rng, 36, 1), "y", ["xd"], estimator="twfe", cov="driscoll_kraay"
            ).inconclusive
            for _ in range(100)
        ]
    assert all(flags)


def _did(rng: np.random.Generator, slope: float) -> tuple[pd.DataFrame, dict[str, pd.Timestamp]]:
    n, t = 20, 40
    times = pd.date_range("2010-01-31", periods=t, freq="ME")
    event = times[t // 2]
    rows, treated = [], {}
    for i in range(n):
        a = rng.normal()
        is_t = i < 10
        if is_t:
            treated[f"U{i:02d}"] = event
        for s, d in enumerate(times):
            trend = slope * (s - t // 2) if is_t and s < t // 2 else 0.0
            y = a + 0.05 * s + (1.0 if is_t and d >= event else 0.0) + trend + rng.normal()
            rows.append((f"U{i:02d}", d, y))
    df = pd.DataFrame(rows, columns=["entity", "time", "y"]).set_index(["entity", "time"])
    return df, treated


def test_sc005_did_bias_and_pretrend_test() -> None:
    rng = np.random.default_rng(6005)
    atets, pre_null, pre_alt, bias_alt, se = [], [], [], [], []
    for _ in range(200):
        df, tr = _did(rng, 0.0)
        r = diff_in_diff(df, "y", tr)
        atets.append(r.atet)
        se.append(r.se)
        pre_null.append(r.pretrend_pvalue is not None and r.pretrend_pvalue < 0.05)
        df, tr = _did(rng, 0.02)
        r = diff_in_diff(df, "y", tr)
        bias_alt.append(r.atet - 1.0)
        pre_alt.append(r.pretrend_pvalue is not None and r.pretrend_pvalue < 0.05)
    bias = abs(np.mean(atets) - 1.0)
    print(
        f"SC-005: sesgo {bias:.4f}, tamaño prueba previa {np.mean(pre_null):.3f}, sesgo con "
        f"violación {np.mean(bias_alt):+.3f} (≈ {np.mean(bias_alt) / np.mean(se):.2f} ee), "
        f"potencia {np.mean(pre_alt):.3f}"
    )
    assert bias <= 0.05
