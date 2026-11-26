"""Diferencias en diferencias (spec 006 T006, US4; revisión I6)."""

import numpy as np
import pandas as pd

from tsinsurance.panel.did import diff_in_diff


def _did_panel(
    seed: int = 0,
    n: int = 20,
    t: int = 40,
    effect: float = 1.0,
    pre_slope: float = 0.0,
    treated_units: int = 10,
) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(seed)
    times = pd.date_range("2010-01-31", periods=t, freq="ME")
    event = times[t // 2]
    rows = []
    treated = {}
    for i in range(n):
        a = rng.normal()
        is_t = i < treated_units
        if is_t:
            treated[f"U{i:02d}"] = event
        for s, d in enumerate(times):
            trend = pre_slope * (s - t // 2) if is_t and s < t // 2 else 0.0
            y = a + 0.05 * s + (effect if is_t and d >= event else 0.0) + trend + rng.normal()
            rows.append((f"U{i:02d}", d, y))
    df = pd.DataFrame(rows, columns=["entity", "time", "y"]).set_index(["entity", "time"])
    return df, treated


def test_recovers_effect_under_parallel_trends() -> None:
    df, treated = _did_panel()
    res = diff_in_diff(df, "y", treated)
    assert res.se is not None and abs(res.atet - 1.0) < 3 * res.se and res.pvalue < 0.01
    assert res.pretrend_pvalue is not None and res.pretrend_pvalue > 0.01
    assert -1 not in res.event_study and 0 in res.event_study
    assert any("Roth" in a for a in res.assumptions)


def test_pretrend_test_detects_non_parallel_trends() -> None:
    df, treated = _did_panel(pre_slope=0.3, seed=2)
    res = diff_in_diff(df, "y", treated)
    assert res.pretrend_pvalue is not None and res.pretrend_pvalue < 0.01
    assert any("tendencias paralelas no se sostiene" in w for w in res.warnings)


def test_single_treated_unit_uses_permutation() -> None:
    df, treated = _did_panel(treated_units=1, effect=3.0, n=15)
    res = diff_in_diff(df, "y", treated, leads=2, lags=2)
    assert "permutación" in res.inference and res.se is None
    assert res.pvalue <= 1 / 15 + 1e-12  # el efecto real supera a todos los placebos


def test_staggered_adoption_warning() -> None:
    df, treated = _did_panel()
    first = next(iter(treated))
    treated[first] = pd.Timestamp("2011-03-31")
    res = diff_in_diff(df, "y", treated)
    assert any("Goodman-Bacon" in w for w in res.warnings)
