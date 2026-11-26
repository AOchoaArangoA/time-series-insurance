"""Calibración Monte Carlo de la spec 007 (SC-001 a SC-007; research R8-R9)."""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest
from scipy import stats

from tsinsurance.portfolio_risk import backtest_var
from tsinsurance.sensitivities import BondPortfolio, FixedBond, approximate, measures
from tsinsurance.simulation import vasicek_discount_mc
from tsinsurance.stochastics import HullWhite, NodeCurve, VasicekP, zero_coupon
from tsinsurance.stochastics.regimes import MarkovShortRate
from tsinsurance.stochastics.short_rate import _simulate

pytestmark = pytest.mark.slow
DT = 1 / 252


def test_sc001_sigma_coverage_and_kappa_bias() -> None:
    k, th, s, n, reps = 0.5, 0.04, 0.01, 2500, 500
    rng = np.random.default_rng(7001)
    cover = {"kappa": 0, "theta": 0, "sigma": 0}
    kappas = []
    for i in range(reps):
        x = _simulate("vasicek", k, th, s, DT, th, n - 1, 1, rng)[0]
        fit = VasicekP.fit(x, DT, bootstrap=199, seed=i)
        kappas.append(fit.kappa)
        for name, true in (("kappa", k), ("theta", th), ("sigma", s)):
            lo, hi = fit.ci[name]
            cover[name] += lo <= true <= hi
    cov = {key: v / reps for key, v in cover.items()}
    bias = float(np.mean(kappas) - k)
    print(f"SC-001: cobertura {cov}; sesgo de κ {bias:+.3f} (≈ 4/T_años = {4 / (n * DT):.3f})")
    assert 0.92 <= cov["sigma"] <= 0.98
    assert bias > 0  # sesgo hacia arriba documentado (κT ≈ 5 < 50: sin aserción de cobertura)
    # Con el intervalo básico y θ re-simulado con κ corregido, la cobertura deja de ser
    # catastrófica (con percentiles: κ 49 %, θ 74 %). Se reporta; se exige un mínimo.
    assert cov["kappa"] >= 0.85 and cov["theta"] >= 0.85


def test_sc002_exact_simulation_moments() -> None:
    k, th, s, r0 = 0.5, 0.04, 0.01, 0.02
    paths = _simulate("vasicek", k, th, s, DT, r0, 252, 100_000, np.random.default_rng(7002))
    end = paths[:, -1]
    m = th + (r0 - th) * math.exp(-k)
    v = s**2 * (1 - math.exp(-2 * k)) / (2 * k)
    assert abs(end.mean() - m) < 3 * math.sqrt(v / end.size)
    se_var = v * math.sqrt(2 / (end.size - 1))
    assert abs(end.var(ddof=1) - v) < 3 * se_var


def test_sc003_regime_transition_recovery() -> None:
    from tests.stochastics.test_regimes import _two_regimes

    errs = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for seed in range(60):
            r, _ = _two_regimes(2000, 7100 + seed)
            fit = MarkovShortRate.fit(r, search_reps=3, seed=seed)
            p = np.array(fit.transition)
            errs.append(np.abs(p - np.array([[0.98, 0.02], [0.05, 0.95]])).mean())
    mae = float(np.mean(errs))
    print(f"SC-003: error absoluto medio de la matriz de transición {mae:.4f}")
    assert mae <= 0.05


def test_sc004_control_variate() -> None:
    r0, k, th, s, horizon = 0.03, 0.3, 0.04, 0.015, 10.0
    closed = float(zero_coupon("vasicek", {"kappa": k, "theta": th, "sigma": s}, r0, horizon))
    res = vasicek_discount_mc(r0, k, th, s, horizon, 10_000, rng=7004, method="control")
    print(f"SC-004: {res.summary()}")
    assert abs(res.estimate - closed) < 3 * res.se and res.reduction_factor >= 5


def test_sc005_hull_white_reproduces_curve() -> None:
    curve = NodeCurve.from_arrays([0.25, 2, 5, 10, 30], [0.045, 0.040, 0.038, 0.041, 0.044])
    hw = HullWhite(0.08, 0.012, curve)
    for t in (0.5, 3.0, 10.0, 25.0):
        d = hw.simulate_discount(t, 200_000, rng=int(t * 10))
        assert abs(d.mean() - float(curve.discount(t))) < 3 * d.std() / math.sqrt(d.size)


def test_sc006_delta_gamma_small_shock() -> None:
    curve = NodeCurve.from_arrays([0.25, 2, 5, 10, 30], [0.045, 0.040, 0.038, 0.041, 0.044])
    port = BondPortfolio.of([(FixedBond(7.0, 0.05), 10), (FixedBond(25.0, 0.045), 4)])
    rep = approximate(port, curve, np.full((1, 5), 0.001))  # 10 pb paralelo
    assert rep.errors["delta_gamma"]["mae"] <= 0.01 * rep.errors["delta"]["mae"]
    s = measures(port, curve)
    assert sum(s.krd.values()) == pytest.approx(s.duration_eff, rel=1e-10)


def test_sc007_var_backtest_size_and_power() -> None:
    reps, n = 500, 1000
    q = stats.norm.ppf(0.99)
    rng = np.random.default_rng(7007)
    size = power07 = power09 = dur_size = 0
    for _ in range(reps):
        sigma = 0.01 * np.exp(0.4 * np.sin(np.arange(n) / 40 + rng.uniform(0, 6)))
        loss = sigma * rng.standard_normal(n)
        oracle = backtest_var(loss, sigma * q, 0.99)
        size += oracle.kupiec["pvalue"] < 0.05
        d = oracle.duration["pvalue"]
        dur_size += bool(np.isfinite(d) and d < 0.05)
        power07 += backtest_var(loss, 0.7 * sigma * q, 0.99).kupiec["pvalue"] < 0.05
        power09 += backtest_var(loss, 0.9 * sigma * q, 0.99).kupiec["pvalue"] < 0.05
    print(
        f"SC-007: tamaño Kupiec {size / reps:.3f}, duraciones {dur_size / reps:.3f}, potencia "
        f"σ×0,7 {power07 / reps:.3f}, σ×0,9 {power09 / reps:.3f}"
    )
    assert 0.03 <= size / reps <= 0.07
    assert power07 / reps >= 0.80
