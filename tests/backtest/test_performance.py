"""SC-006: barrido 8 activos × 20 configuraciones × 10 años diarios en < 60 s."""

import time

import pytest

from tests.backtest.conftest import make_prices
from tsinsurance.backtest import ExecutionConfig, ewma_volatility, sma_crossover, sweep, vol_target

pytestmark = pytest.mark.slow


def test_sc006_sweep_runtime() -> None:
    prices = make_prices(seed=3, n=2520, assets=8)

    def idea(p, fast, slow, target):  # type: ignore[no-untyped-def]
        vol = ewma_volatility(p.pct_change())
        return vol_target(sma_crossover(p, fast, slow, normalize=False), vol, target=target)

    grid = {"fast": [10, 20, 50, 100, 150], "slow": [200, 250], "target": [0.05, 0.10]}
    start = time.perf_counter()
    res = sweep(prices, idea, grid, ExecutionConfig(), reps=500)
    elapsed = time.perf_counter() - start
    print(f"SC-006: {res.registry.n_trials} pruebas en {elapsed:.1f} s")
    assert res.registry.n_trials == 160
    assert elapsed < 60
