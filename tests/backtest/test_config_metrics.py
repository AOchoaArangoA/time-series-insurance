import numpy as np
import pandas as pd
import pytest

from tsinsurance.backtest import ExecutionConfig, infer_periods_per_year, performance_metrics
from tsinsurance.errors import TSInsuranceError


def test_config_validation_and_notes() -> None:
    assert ExecutionConfig().lag == 1 and ExecutionConfig().notes == ()
    assert "optimista" in ExecutionConfig(lag=0).notes[0]
    for bad in (
        {"lag": -1},
        {"cost_bps": -1},
        {"rebalance": "Q"},
        {"max_gross": 0},
        {"financing_spread_bps": -1},
    ):
        with pytest.raises(TSInsuranceError):
            ExecutionConfig(**bad)  # type: ignore[arg-type]
    cfg = ExecutionConfig(cost_bps={"TLT": 2.0}, slippage_bps=1.0, default_cost_bps=10.0)
    assert cfg.cost_rate(["TLT", "HYG"]) == pytest.approx([3e-4, 11e-4])
    assert "TLT" in cfg.describe()


def test_infer_periods_per_year() -> None:
    assert infer_periods_per_year(pd.bdate_range("2020-01-01", periods=10)) == 252
    assert infer_periods_per_year(pd.date_range("2020-01-03", periods=10, freq="W-FRI")) == 52
    assert infer_periods_per_year(pd.date_range("2020-01-31", periods=10, freq="ME")) == 12
    with pytest.raises(TSInsuranceError):
        infer_periods_per_year(pd.bdate_range("2020-01-01", periods=2))


def test_metrics_hand_computed() -> None:
    r = pd.Series([0.10, -0.05, 0.02, 0.0])
    m = performance_metrics(r, 12, turnover=pd.Series([1.0, 0.0, 0.5, 0.0]))
    growth = 1.1 * 0.95 * 1.02
    assert m.annual_return == pytest.approx(growth ** (12 / 4) - 1)
    assert m.max_drawdown == pytest.approx(-0.05)
    assert m.sharpe == pytest.approx(r.mean() / r.std(ddof=1) * np.sqrt(12))
    downside = np.sqrt(np.mean(np.minimum(r, 0) ** 2))
    assert m.sortino == pytest.approx(r.mean() / downside * np.sqrt(12))
    assert m.hit_rate == pytest.approx(2 / 3)  # los ceros no cuentan
    assert m.avg_turnover == pytest.approx(0.375)
    assert "Sharpe" in m.summary()
    empty = performance_metrics(pd.Series([], dtype=float), 252)
    assert empty.n_periods == 0 and np.isnan(empty.sharpe)
