"""Monte Carlo de los criterios SC-003 y SC-004 (marca ``slow``)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from tsinsurance.backtest import PredictiveRegression, clark_west, deflated_sharpe

pytestmark = pytest.mark.slow


def _mc_se(p: float, reps: int) -> float:
    return math.sqrt(p * (1 - p) / reps)


def _dsr_best(rng: np.random.Generator, n_days: int, n_configs: int, skill_sr: float) -> float:
    """DSR del mejor de ``n_configs`` estrategias de timing sobre un activo sin deriva."""
    r = rng.normal(0.0, 0.01, n_days)
    # Señales aleatorias persistentes (régimen ~ 20 días): largo/efectivo.
    switches = rng.random((n_days, n_configs)) < 1 / 20
    state = np.cumsum(switches, axis=0) % 2
    strat = state * r[:, None]
    if skill_sr > 0:
        daily_sr = skill_sr / math.sqrt(252)
        strat[:, 0] = rng.normal(daily_sr * 0.01, 0.01, n_days)
    sd = strat.std(axis=0, ddof=1)
    sharpes = strat.mean(axis=0) / sd
    best = int(np.argmax(sharpes))
    return deflated_sharpe(strat[:, best], n_configs, float(np.var(sharpes, ddof=1))).dsr


def test_sc003_size_and_power_of_deflated_sharpe() -> None:
    reps, n_days, n_configs = 500, 2520, 100
    rng = np.random.default_rng(20261108)
    size = np.mean([_dsr_best(rng, n_days, n_configs, 0.0) > 0.95 for _ in range(reps)])
    assert size <= 0.05 + 2 * _mc_se(0.05, reps)
    power = np.mean([_dsr_best(rng, n_days, n_configs, 1.5) > 0.95 for _ in range(reps)])
    assert power >= 0.80


def _cw_rejects(
    rng: np.random.Generator,
    n: int,
    beta: float,
    rho: float,
    delta: float,
    model: PredictiveRegression,
) -> bool:
    v = rng.normal(size=n)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = rho * x[t - 1] + v[t]
    u = delta * v + math.sqrt(1 - delta**2) * rng.normal(size=n)
    y = np.zeros(n)
    y[1:] = beta * x[:-1] + u[1:]
    idx = pd.date_range("2000-01-31", periods=n, freq="ME")
    wf = model.walk_forward(pd.Series(y, idx, name="y"), pd.DataFrame({"x": x}, idx))
    m = wf.forecasts.notna() & wf.realized.notna()
    res = clark_west(wf.realized[m], wf.benchmark_forecasts[m], wf.forecasts[m])
    return res.rejects(0.05)


def test_sc004_clark_west_power_and_size() -> None:
    reps, n = 1000, 300
    model = PredictiveRegression(min_train=60)
    rng = np.random.default_rng(7)
    beta = math.sqrt(0.05 / 0.95)  # R² = 5 % con x y u de varianza 1
    power = np.mean([_cw_rejects(rng, n, beta, 0.0, 0.0, model) for _ in range(reps)])
    size = np.mean([_cw_rejects(rng, n, 0.0, 0.0, 0.0, model) for _ in range(reps)])
    assert power >= 0.80
    assert size <= 0.05 + 2 * _mc_se(0.05, reps)


def test_sc004c_persistent_regressor_size_is_reported(capsys: pytest.CaptureFixture[str]) -> None:
    """Regresor persistente (ρ=0,98, δ=−0,9) irrelevante: se mide y documenta el tamaño."""
    reps = 500
    model = PredictiveRegression(min_train=60)
    rng = np.random.default_rng(8)
    size = float(np.mean([_cw_rejects(rng, 300, 0.0, 0.98, -0.9, model) for _ in range(reps)]))
    print(f"SC-004(c) tamaño empírico de Clark-West con regresor persistente: {size:.3f}")
    assert 0.0 <= size <= 1.0
