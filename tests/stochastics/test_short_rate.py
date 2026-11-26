"""Vasicek y CIR bajo ℙ: MV exacta, simulación exacta y diagnósticos (spec 007 T002, T003)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from tsinsurance.errors import DataValidationError, TSInsuranceError
from tsinsurance.stochastics import CIRP, VasicekP
from tsinsurance.stochastics.short_rate import _simulate, conditional_variance

DT = 1 / 252


def _path(
    model: str, n: int, seed: int, k: float = 0.5, th: float = 0.04, s: float = 0.01
) -> np.ndarray:
    return _simulate(model, k, th, s, DT, th, n - 1, 1, np.random.default_rng(seed))[0]  # type: ignore[arg-type]


def test_vasicek_exact_simulation_moments() -> None:
    k, th, s, r0, h = 0.5, 0.04, 0.01, 0.02, 252
    paths = _simulate("vasicek", k, th, s, DT, r0, h, 50_000, np.random.default_rng(0))
    m = th + (r0 - th) * math.exp(-k * h * DT)
    v = s**2 * (1 - math.exp(-2 * k * h * DT)) / (2 * k)
    end = paths[:, -1]
    assert abs(end.mean() - m) < 4 * math.sqrt(v / end.size)
    assert end.var() == pytest.approx(v, rel=0.03)


def test_cir_exact_simulation_moments_and_positivity() -> None:
    k, th, s, r0, h = 0.8, 0.03, 0.15, 0.01, 126  # Feller violado: 2κθ/σ² ≈ 2,1? (=2.13)
    paths = _simulate("cir", k, th, s, DT, r0, h, 50_000, np.random.default_rng(1))
    end = paths[:, -1]
    m = th + (r0 - th) * math.exp(-k * h * DT)
    v = float(conditional_variance("cir", r0, k, th, s, h * DT))
    assert np.all(paths >= 0)
    assert abs(end.mean() - m) < 4 * math.sqrt(v / end.size)
    assert end.var() == pytest.approx(v, rel=0.04)
    # Distribución exacta: KS contra la χ² no central escalada.
    e = math.exp(-k * h * DT)
    c = 2 * k / (s**2 * (1 - e))
    df, nc = 4 * k * th / s**2, 2 * c * r0 * e
    assert stats.kstest(2 * c * end[:5000], "ncx2", args=(df, nc)).pvalue > 0.001


def test_vasicek_fit_recovers_sigma_and_bootstrap_covers() -> None:
    x = _path("vasicek", 5000, 3)
    fit = VasicekP.fit(x, DT, bootstrap=199, seed=1)
    assert fit.identified and fit.sigma == pytest.approx(0.01, rel=0.05)
    lo, hi = fit.ci["sigma"]
    assert lo < 0.01 < hi
    assert fit.ci["kappa"][0] < 0.5 < fit.ci["kappa"][1]
    assert any("κ·T" in w for w in fit.warnings)  # κT ≈ 10 < 50: sesgo advertido
    assert "Vasicek" in fit.summary()


def test_vasicek_random_walk_is_not_identified() -> None:
    rng = np.random.default_rng(4)
    rw = np.empty(1000)
    rw[0] = 0.01
    for t in range(1, 1000):  # explosivo: φ = 1,002 ⇒ φ̂ ≥ 1
        rw[t] = 1.002 * rw[t - 1] + rng.normal(0, 1e-5)
    fit = VasicekP.fit(rw, DT, bootstrap=0)
    assert not fit.identified and np.isnan(fit.kappa)
    with pytest.raises(TSInsuranceError):
        fit.simulate()


def test_jackknife_reduces_kappa_bias_on_average() -> None:
    raw, jk = [], []
    for seed in range(30):
        f = VasicekP.fit(_path("vasicek", 2520, 100 + seed), DT, bootstrap=0, jackknife=True)
        raw.append(f.kappa)
        jk.append(f.bias_corrected_kappa)
    assert abs(np.mean(jk) - 0.5) < abs(np.mean(raw) - 0.5)


def test_cir_fit_and_feller_and_nonpositive_rates() -> None:
    x = _path("cir", 4000, 5, k=0.6, th=0.04, s=0.05)
    fit = CIRP.fit(x, DT, bootstrap=20, seed=2)
    assert fit.sigma == pytest.approx(0.05, rel=0.07)
    assert fit.theta == pytest.approx(0.04, abs=0.015)
    assert fit.feller["ratio"] > 1 and "ci" in fit.feller
    with pytest.raises(DataValidationError, match="CIR no admite"):
        CIRP.fit(np.r_[x[:-1], -0.001], DT, bootstrap=0)
    floored = CIRP.fit(np.r_[x[:-1], 0.0], DT, bootstrap=0, floor=1e-5)
    assert any("Piso" in w for w in floored.warnings)


def test_simulate_antithetic_only_for_gaussian() -> None:
    fit = VasicekP.fit(_path("vasicek", 1000, 6), DT, bootstrap=0)
    p = fit.simulate(0.03, 10, 6, rng=1, antithetic=True)
    assert np.allclose(
        p[:3, 1] - fit.theta - (0.03 - fit.theta) * math.exp(-fit.kappa * DT),
        -(p[3:, 1] - fit.theta - (0.03 - fit.theta) * math.exp(-fit.kappa * DT)),
    )
    cir = CIRP.fit(_path("cir", 1000, 7, s=0.05), DT, bootstrap=0)
    with pytest.raises(TSInsuranceError, match="antitéticas"):
        cir.simulate(antithetic=True)


def test_diagnostics_on_correct_model() -> None:
    idx = pd.bdate_range("2000-01-03", periods=3000)
    x = pd.Series(_path("vasicek", 3000, 8, k=2.0), index=idx)
    d = VasicekP.fit(x, DT, bootstrap=0).diagnostics()
    assert d.integration_order == 0
    assert d.residual_tests["ARCH-LM"].p_value > 0.001
    assert d.walk_forward["n_forecasts"] > 50 and "dm_pvalue" in d.walk_forward
    assert "Diagnósticos" in d.summary()
