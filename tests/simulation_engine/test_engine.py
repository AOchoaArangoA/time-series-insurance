"""Factores, escenarios y reducción de varianza (spec 007 T007-T009)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from tsinsurance.simulation import (
    factor_mc,
    filtered_historical,
    fit_factors,
    historical,
    nelson_siegel_loadings,
    short_rate_mc,
    vasicek_discount_mc,
)
from tsinsurance.stochastics import VasicekP, zero_coupon
from tsinsurance.stochastics.regimes import MarkovShortRate

TENORS = [0.25, 5.0, 10.0, 30.0]


def _curve_levels(n: int = 1500, seed: int = 0, vol_break: bool = False) -> pd.DataFrame:
    """Niveles de 4 nodos generados por nivel, pendiente y curvatura (Nelson-Siegel)."""
    rng = np.random.default_rng(seed)
    load = nelson_siegel_loadings(np.array(TENORS))
    scale = np.where(np.arange(n) > n - 250, 3.0, 1.0) if vol_break else np.ones(n)
    shocks = rng.normal(size=(n, 3)) * np.array([6e-4, 4e-4, 2e-4]) * scale[:, None]
    f = np.array([0.04, -0.01, 0.0]) + np.cumsum(shocks, axis=0)
    levels = f @ load.T + rng.normal(0, 1e-6, (n, 4))
    return pd.DataFrame(levels, index=pd.bdate_range("2015-01-01", periods=n), columns=TENORS)


def test_pca_recovers_level_slope_curvature_with_signs() -> None:
    fm = fit_factors(_curve_levels().diff().dropna(), "pca", 3)
    assert fm.labels == ("nivel", "pendiente", "curvatura")
    assert np.all(fm.loadings[:, 0] > 0) and fm.loadings[-1, 1] > fm.loadings[0, 1]
    assert sum(fm.explained) == pytest.approx(1.0, abs=1e-3)
    shock = np.zeros((1, 3))
    shock[0, 0] = 10.0
    assert fm.reconstruct(shock).shape == (1, 4)


def test_diebold_li_fixed_lambda_warns_on_dof() -> None:
    fm = fit_factors(_curve_levels().diff().dropna(), "diebold_li", 3)
    assert any("grado(s) de libertad" in w for w in fm.warnings)
    assert max(fm.residual_sd_bp.values()) < 0.05  # el DGP es Nelson-Siegel con λ fija


def test_historical_and_filtered_historical_are_point_in_time() -> None:
    lv = _curve_levels(vol_break=True)
    asof = lv.index[-300]
    h = historical(lv, horizon=1, window=500, asof=asof)
    later = lv.copy()
    later.iloc[-200:] += 0.01  # alterar lo posterior a asof no cambia los escenarios
    np.testing.assert_array_equal(
        h.values, historical(later, horizon=1, window=500, asof=asof).values
    )
    f1 = filtered_historical(lv, n=2000, asof=asof, seed=1)
    f2 = filtered_historical(later, n=2000, asof=asof, seed=1)
    np.testing.assert_array_equal(f1.values, f2.values)
    # Tras el aumento de volatilidad, la FHS al final escala los escenarios hacia arriba.
    recent = filtered_historical(lv, n=4000, seed=2)
    plain = historical(lv, window=1000)
    last = historical(lv, window=200)  # sólo el periodo de volatilidad alta
    assert recent.values[:, 0].std() > 1.3 * plain.values[:, 0].std()
    assert recent.values[:, 0].std() == pytest.approx(last.values[:, 0].std(), rel=0.25)
    path = filtered_historical(lv, n=2000, horizon=10, seed=3)
    assert path.horizon_days == 10 and "trayectoria" in path.notes[0]


def test_factor_mc_matches_factor_covariance() -> None:
    fm = fit_factors(_curve_levels().diff().dropna(), "pca", 3)
    sc = factor_mc(fm, n=40_000, seed=4)
    emp = np.cov(sc.values * 1e4, rowvar=False)
    target = fm.loadings @ fm.cov @ fm.loadings.T
    np.testing.assert_allclose(emp, target, rtol=0.05, atol=1e-3)
    t = factor_mc(fm, n=40_000, seed=5, dist="t")
    assert t.values[:, 2].std() == pytest.approx(sc.values[:, 2].std(), rel=0.06)


def test_short_rate_mc_declares_measures() -> None:
    rng = np.random.default_rng(6)
    k, th, s = 0.5, 0.04, 0.01
    x = np.empty(3000)
    x[0] = th
    e = math.exp(-k / 252)
    for t in range(1, 3000):
        x[t] = (
            th + (x[t - 1] - th) * e + s * math.sqrt((1 - e**2) / (2 * k)) * rng.standard_normal()
        )
    fit = VasicekP.fit(x, bootstrap=0)
    sc = short_rate_mc(fit, TENORS, horizon=21, n=2000, seed=1)
    assert sc.state_measure == "P" and "λ = 0" in sc.pricing_measure
    pq = {"kappa": fit.kappa, "theta": fit.theta + 0.01, "sigma": fit.sigma}
    sq = short_rate_mc(fit, TENORS, horizon=21, n=2000, seed=1, params_q=pq)
    assert "λ calibrado" in sq.pricing_measure
    # Un factor: los cambios de los nodos son funciones monótonas de r_T.
    assert np.corrcoef(sq.values[:, 0], sq.values[:, -1])[0, 1] > 0.999


def test_short_rate_mc_with_regimes_requires_q_and_r0() -> None:
    from tsinsurance.errors import DataValidationError
    from tests.stochastics.test_regimes import _two_regimes

    r, _ = _two_regimes(800, 1)
    fit = MarkovShortRate.fit(r, search_reps=2)
    with pytest.raises(DataValidationError):
        short_rate_mc(fit, TENORS, horizon=5, n=100)
    sc = short_rate_mc(
        fit,
        TENORS,
        horizon=5,
        n=100,
        params_q={"kappa": 0.5, "theta": 0.04, "sigma": 0.01},
        r0=float(r.iloc[-1]),
    )
    assert "regímenes" in sc.method


def test_control_variate_sc004_unbiased_and_reduces_variance() -> None:
    r0, k, th, s, horizon = 0.03, 0.3, 0.04, 0.015, 10.0
    closed = float(zero_coupon("vasicek", {"kappa": k, "theta": th, "sigma": s}, r0, horizon))
    cv = vasicek_discount_mc(r0, k, th, s, horizon, 10_000, rng=7, method="control")
    assert abs(cv.estimate - closed) < 3 * cv.se
    assert cv.reduction_factor >= 5
    anti = vasicek_discount_mc(r0, k, th, s, horizon, 10_000, rng=8, method="antithetic")
    assert abs(anti.estimate - closed) < 3 * anti.se and anti.reduction_factor > 1
