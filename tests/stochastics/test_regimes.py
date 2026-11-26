"""Tasa corta con regímenes de Markov (spec 007 T006; revisión B4, I1)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tsinsurance.stochastics.regimes import MarkovShortRate, hamilton_filter


def _two_regimes(n: int = 2000, seed: int = 0) -> tuple[pd.Series, np.ndarray]:
    rng = np.random.default_rng(seed)
    c = np.array([0.0004, 0.0020])
    phi = np.array([0.99, 0.96])
    sig = np.array([0.0005, 0.0020])
    trans = np.array([[0.98, 0.02], [0.05, 0.95]])
    s = np.zeros(n, dtype=int)
    r = np.zeros(n)
    r[0] = 0.04
    for t in range(1, n):
        s[t] = rng.choice(2, p=trans[s[t - 1]])
        r[t] = c[s[t]] + phi[s[t]] * r[t - 1] + sig[s[t]] * rng.standard_normal()
    return pd.Series(r, index=pd.bdate_range("2000-01-03", periods=n)), s


@pytest.fixture(scope="module")
def fitted() -> tuple[pd.Series, np.ndarray, object]:
    r, s = _two_regimes()
    return r, s, MarkovShortRate.fit(r, search_reps=5)


def test_recovers_ordered_regimes(fitted: tuple) -> None:
    r, s, fit = fitted
    assert fit.sigma[0] < fit.sigma[1]
    assert fit.sigma[0] == pytest.approx(0.0005, rel=0.15)
    assert fit.sigma[1] == pytest.approx(0.0020, rel=0.15)
    assert fit.transition[0][0] == pytest.approx(0.98, abs=0.02)
    assert fit.prefers_regimes == {"aic": True, "bic": True}
    smooth_state = (fit.smoothed_probabilities[1] > 0.5).astype(int).to_numpy()
    assert np.mean(smooth_state == s[1:]) > 0.85
    assert fit.params_estimation_end == str(r.index[-1].date())


def test_fixed_parameter_filter_is_point_in_time_and_matches_statsmodels(fitted: tuple) -> None:
    r, _, fit = fitted
    full = fit.filter(r)
    part = fit.filter(r.iloc[:1200])
    np.testing.assert_allclose(full[: part.shape[0]], part, atol=1e-12)
    # Mismo filtro que statsmodels (salvo la condición inicial, olvidada tras unos pasos).
    np.testing.assert_allclose(
        full[50:, 1], fit.filtered_probabilities[1].to_numpy()[50:], atol=1e-6
    )


def test_simulation_uses_estimated_recursion(fitted: tuple) -> None:
    _, _, fit = fitted
    rates, states = fit.simulate(0.04, 2000, 200, rng=1, state0=0)
    share_high = states[:, 1:].mean()
    p01, p10 = fit.transition[0][1], fit.transition[1][0]
    assert share_high == pytest.approx(p01 / (p01 + p10), abs=0.05)
    assert rates.shape == (200, 2001) and np.all(np.isfinite(rates))


def test_hamilton_filter_sums_to_one() -> None:
    r, _ = _two_regimes(300, 3)
    out = hamilton_filter(
        r.to_numpy(),
        np.array([0.0004, 0.002]),
        np.array([0.99, 0.96]),
        np.array([0.0005, 0.002]),
        np.array([[0.98, 0.02], [0.05, 0.95]]),
    )
    np.testing.assert_allclose(out.sum(axis=1), 1.0)
