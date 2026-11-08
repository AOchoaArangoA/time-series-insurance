import numpy as np
import pandas as pd
import pytest

from tsinsurance.backtest import ExecutionConfig, run_backtest, run_with_bt
from tsinsurance.errors import DataValidationError


def series(values: list[float]) -> pd.Series:
    return pd.Series(values, index=pd.bdate_range("2024-01-01", periods=len(values)), name="X")


def test_execution_lag_and_costs_by_hand() -> None:
    px = series([100.0, 110.0, 121.0, 108.9])
    w = series([1.0, 1.0, 1.0, 1.0])  # decidido desde el cierre del día 0
    res = run_backtest(px, w, ExecutionConfig(lag=1, cost_bps=10))
    # Día 0 sin posición; ejecución al cierre del día 1 (costo 10 pb sobre rotación 1).
    assert res.returns.iloc[0] == 0.0
    assert res.returns.iloc[1] == pytest.approx(-0.001)
    assert res.returns.iloc[2] == pytest.approx(0.10)
    assert res.returns.iloc[3] == pytest.approx(-0.10)
    assert res.turnover.sum() == pytest.approx(1.0)
    assert res.warmup_end == px.index[2]
    zero = run_backtest(px, w, ExecutionConfig(lag=0, cost_bps=0))
    assert zero.returns.iloc[1] == pytest.approx(0.10)
    assert any("optimista" in n for n in zero.notes)


def test_drift_between_rebalances_and_monthly_rebalance(prices: pd.DataFrame) -> None:
    w = pd.DataFrame(0.5, index=prices.index, columns=prices.columns)
    daily = run_backtest(prices, w, ExecutionConfig(cost_bps=0))
    monthly = run_backtest(prices, w, ExecutionConfig(cost_bps=0, rebalance="M"))
    held = monthly.weights.iloc[30:60]
    assert held["A0"].std() > 0  # los pesos derivan entre rebalanceos
    np.testing.assert_allclose(daily.weights.iloc[5:].sum(axis=1), 1.0)
    assert monthly.turnover.astype(bool).sum() < daily.turnover.astype(bool).sum()


def test_risk_free_lagged_on_cash() -> None:
    px = series([100.0] * 5)
    rf = series([0.001, 0.002, 0.003, 0.004, 0.005])
    res = run_backtest(px, series([0.0] * 5), ExecutionConfig(), risk_free=rf)
    # El retorno del periodo t usa la tasa conocida en t-1.
    np.testing.assert_allclose(res.returns.iloc[1:], [0.001, 0.002, 0.003, 0.004])
    np.testing.assert_allclose(res.excess_returns, 0.0, atol=1e-15)


def test_leverage_financing_and_gross_clip() -> None:
    px = series([100.0, 100.0, 101.0, 102.0])
    rf = series([0.0] * 4)
    cfg = ExecutionConfig(max_gross=2.0, cost_bps=0, financing_spread_bps=252e4 * 0.001)
    res = run_backtest(px, series([3.0] * 4), cfg, risk_free=rf)
    assert res.weights.iloc[2, 0] == pytest.approx(2.0)
    assert any("recortada" in n for n in res.notes)
    # Retorno = 2 × 1 % menos financiación del efectivo negativo (−1 × 0,1 %).
    assert res.returns.iloc[2] == pytest.approx(2 * 0.01 - 0.001)


def test_validation_errors(prices: pd.DataFrame) -> None:
    with pytest.raises(DataValidationError, match="negativos"):
        run_backtest(prices, -0.5 * prices.notna().astype(float), ExecutionConfig())
    with pytest.raises(DataValidationError, match="sin precio"):
        run_backtest(prices[["A0"]], prices.notna().astype(float), ExecutionConfig())
    with pytest.raises(DataValidationError, match="creciente"):
        run_backtest(prices.iloc[::-1], prices.notna().astype(float))


def test_per_asset_start_and_benchmark() -> None:
    px = pd.DataFrame(
        {"OLD": np.linspace(100, 120, 20), "NEW": [np.nan] * 10 + list(np.linspace(50, 55, 10))},
        index=pd.bdate_range("2024-01-01", periods=20),
    )
    res = run_backtest(px, pd.DataFrame(0.5, index=px.index, columns=px.columns))
    assert (res.weights["NEW"].iloc[:11] == 0).all()
    assert any("sin precio" in n for n in res.notes)
    assert res.benchmark_metrics is not None and "Benchmark" in res.summary()
    assert any("supervivencia" in n for n in res.notes)


def test_short_and_custom_benchmark(prices: pd.DataFrame) -> None:
    px = prices["A0"]
    res = run_backtest(
        px, -px.notna().astype(float), ExecutionConfig(allow_short=True), benchmark=px.pct_change()
    )
    assert res.weights.iloc[-1, 0] == pytest.approx(-1.0, rel=0.1)
    assert run_backtest(px, px * 0 + 1.0, benchmark=None).benchmark_metrics is None
    with pytest.raises(DataValidationError):
        run_backtest(px, px * 0 + 1.0, benchmark="sp500")


def test_matches_bt_reference(prices: pd.DataFrame) -> None:
    pytest.importorskip("bt")
    signal = (prices.rolling(20).mean() > prices.rolling(100).mean()).astype(float) * 0.5
    signal = signal.where(prices.rolling(100).mean().notna())
    for cost, tol in ((0.0, 1e-10), (5.0, 1e-5)):
        cfg = ExecutionConfig(cost_bps=cost)
        ours = run_backtest(prices, signal, cfg).returns
        ref = run_with_bt(prices, signal, cfg)
        assert float((ours - ref).abs().max()) < tol


def test_warmup_starts_at_first_decision_even_if_in_cash() -> None:
    # Regresión: el calentamiento terminaba en la primera fecha invertida, no en la primera
    # decisión, y recortaba la ventana de evaluación de estrategias que empiezan en efectivo.
    px = series([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    w = pd.Series([np.nan, 0.0, 0.0, 1.0, 1.0, 1.0], index=px.index)
    res = run_backtest(px, w, ExecutionConfig(lag=1))
    assert res.warmup_end == px.index[3]  # decisión en 1, ejecución en 2, efecto desde 3
    assert run_backtest(px, w, ExecutionConfig(lag=0)).warmup_end == px.index[2]
    assert run_backtest(px, w * np.nan, ExecutionConfig()).warmup_end is None
