import numpy as np
import pandas as pd
import pytest

from tsinsurance.backtest import (
    ExecutionConfig,
    PredictiveRegression,
    backtest_econometric,
    calibrate_validate,
    check_lookahead,
    forecast_to_weights,
    sma_crossover,
    sweep,
)
from tsinsurance.errors import DataValidationError


def predictive_dgp(seed: int, n_months: int = 240, beta: float = 0.5, persistent: bool = False):  # type: ignore[no-untyped-def]
    """Precios diarios cuyo retorno mensual depende de x_{t-1} (más dos regresores)."""
    rng = np.random.default_rng(seed)
    months = pd.date_range("2000-01-31", periods=n_months, freq="BME")
    x = np.zeros(n_months)
    for t in range(1, n_months):
        x[t] = (0.98 if persistent else 0.0) * x[t - 1] + rng.normal()
    eps = rng.normal(scale=1.0, size=n_months)
    y = np.empty(n_months)
    y[0] = 0.0
    y[1:] = 0.003 + 0.04 * (beta * x[:-1] + eps[1:]) / np.sqrt(1 + beta**2)
    days = pd.bdate_range(months[0], months[-1])
    month_of_day = days.to_period("M")
    daily = pd.Series(0.0, index=days)
    for i, m in enumerate(months[1:], start=1):
        sel = (month_of_day == m.to_period("M")) & (days > months[i - 1])
        k = int(sel.sum())
        daily[sel] = (1 + y[i]) ** (1 / k) - 1
    prices = (1 + daily).cumprod() * 100
    prices.name = "ETF"
    X = pd.DataFrame({"x": x, "noise": rng.normal(size=n_months)}, index=months)
    yr = pd.Series(y, index=months, name="ETF")
    return prices, yr.iloc[1:], X.iloc[1:]


def test_walk_forward_uses_only_observable_pairs() -> None:
    _, y, X = predictive_dgp(0)
    model = PredictiveRegression(min_train=60)
    wf = model.walk_forward(y, X)
    first = wf.forecasts.first_valid_index()
    assert y.index.get_loc(first) == 60  # 60 pares (s, s+1) con s+1 <= t
    # Invariancia al truncamiento (punto en el tiempo).
    cut = y.index[150]
    part = model.walk_forward(y.loc[:cut], X.loc[:cut])
    pd.testing.assert_series_equal(wf.forecasts.loc[:cut], part.forecasts)
    assert wf.n_refits == wf.forecasts.notna().sum()
    assert np.isnan(wf.realized.iloc[-1]) and (wf.forecast_se.dropna() > 0).all()
    rolling = PredictiveRegression(scheme="rolling", window=60, min_train=60, refit_every=12)
    assert rolling.walk_forward(y, X).n_refits < wf.n_refits
    with pytest.raises(DataValidationError):
        PredictiveRegression(scheme="rolling", window=10, min_train=60)


def test_econometric_lookahead_full_pipeline() -> None:
    prices, y, X = predictive_dgp(1)
    model = PredictiveRegression(min_train=60, refit_every=6)

    def pipeline(data):  # type: ignore[no-untyped-def]
        wf = model.walk_forward(data["y"], data["X"])
        return forecast_to_weights(wf.forecasts, data["y"], "long_cash").to_frame()

    assert not check_lookahead(pipeline, {"y": y, "X": X}, n_cuts=8).has_lookahead


def test_predictive_signal_detected_and_verdict() -> None:
    prices, y, X = predictive_dgp(2, n_months=300)
    res = backtest_econometric(
        prices,
        y,
        X[["x"]],
        PredictiveRegression(min_train=60),
        position="proportional",
        reps=300,
        seed=0,
    )
    assert res.forecast_evaluation.oos_r2 > 0
    assert res.forecast_evaluation.clark_west.rejects(0.05)
    assert res.verdict.statistical and res.verdict.statistical_test == "Clark-West"
    assert not res.verdict.inconclusive and not res.verdict.exploratory
    text = res.summary()
    assert "VALIDACIÓN ESTADÍSTICA" in text and "BACKTEST ECONÓMICO" in text


def test_irrelevant_regressor_and_flags() -> None:
    prices, y, X = predictive_dgp(3, n_months=300, beta=0.0)
    res = backtest_econometric(
        prices,
        y,
        X[["noise"]],
        PredictiveRegression(min_train=60),
        position="long_cash",
        n_specifications=4,
        point_in_time=False,
        reps=200,
    )
    assert not res.verdict.statistical
    assert res.verdict.exploratory
    assert "EXPLORATORIO" in res.verdict.summary()
    with pytest.raises(DataValidationError):
        backtest_econometric(prices, y, X, PredictiveRegression(), alpha=0.2)


def test_validation_flags_persistent_regressor() -> None:
    _, y, X = predictive_dgp(4, n_months=300, persistent=True)
    val = PredictiveRegression(min_train=60).validate(y, X[["x"]])
    assert val.persistence.loc["x", "rho"] > 0.9
    assert any("persistente" in w or "desbalanceada" in w for w in val.warnings)
    assert {t.name for t in val.residual_tests} >= {"Ljung-Box", "ARCH-LM", "CUSUM (OLS)"}
    assert "Persistencia" in val.summary()


def test_forecast_to_weights_rules() -> None:
    f = pd.Series([0.01, -0.02, np.nan, 0.03])
    hist = pd.Series(np.random.default_rng(0).normal(0, 0.04, 4))
    assert forecast_to_weights(f, hist, "long_cash").tolist()[:2] == [1.0, 0.0]
    assert forecast_to_weights(f, hist, "long_short").tolist()[:2] == [1.0, -1.0]
    prop = forecast_to_weights(f, hist, "proportional", min_history=2)
    assert prop.dropna().between(0, 1).all()
    with pytest.raises(DataValidationError):
        forecast_to_weights(f, hist, "kelly")  # type: ignore[arg-type]


def test_sweep_and_calibration(prices: pd.DataFrame) -> None:
    def signal(p, fast, slow):  # type: ignore[no-untyped-def]
        return sma_crossover(p, fast, slow)

    grid = {"fast": [10, 20], "slow": [100, 150]}
    res = sweep(prices, signal, grid, ExecutionConfig(), reps=200)
    assert res.registry.n_trials == 8 and len(res.table) == 8
    sel = res.selection
    assert set(sel.index) == {"A0", "A1"} and (sel["n_trials"] == 4).all()
    assert (sel["n_effective"] <= 4).all() and sel["dsr"].between(0, 1).all()
    assert "Barrido" in res.summary()
    cal = calibrate_validate(prices, signal, grid, prices.index[1000], reps=200)
    assert set(cal.table.columns) >= {"sharpe_in_sample", "sharpe_out_of_sample"}
    assert "una sola vez" in cal.summary()
