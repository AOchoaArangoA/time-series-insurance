"""Pruebas de regresión de la revisión econométrica de la implementación (2026-11-08)."""

import numpy as np
import pandas as pd
import pytest

from tests.backtest.conftest import make_prices
from tests.backtest.test_econometric_sweep import predictive_dgp
from tsinsurance.backtest import (
    ExecutionConfig,
    Exogenous,
    PredictiveRegression,
    TrialRegistry,
    align_point_in_time,
    backtest_econometric,
    check_lookahead,
    dtb3_to_daily,
    ewma_volatility,
    monthly_decision_dates,
    run_backtest,
    sharpe_difference,
    sharpe_inference,
    sma_crossover,
    sweep,
    vol_target,
)
from tsinsurance.errors import DataValidationError, LookaheadBiasError


def test_lookahead_inconclusive_when_cuts_fail() -> None:
    """Bloqueante #1: no certificar ausencia de fuga si todos los cortes fallan."""
    prices = make_prices()

    def fragile(p):  # type: ignore[no-untyped-def]
        if len(p) < len(prices):
            raise ValueError("necesita toda la historia")
        return sma_crossover(p, 20, 100).shift(-1)

    rep = check_lookahead(fragile, prices)
    assert not rep.conclusive and rep.valid_cuts == 0
    assert "NO CONCLUYENTE" in rep.summary()
    with pytest.raises(LookaheadBiasError):
        rep.raise_if_biased()


def test_lookahead_detects_leak_only_at_first_valid_value() -> None:
    """Importante #2: fuga sólo en el primer peso válido (corte en el fin del calentamiento)."""
    prices = make_prices()

    def leaky(p):  # type: ignore[no-untyped-def]
        w = vol_target(p.notna().astype(float), ewma_volatility(p.pct_change()))
        first = w.dropna(how="all").index[0]
        pos = p.index.get_loc(first)
        if pos + 1 < len(p):
            w.loc[first] = w.loc[first] * (p.iloc[pos + 1] / p.iloc[pos])
        return w

    detected = [check_lookahead(leaky, prices, seed=s).has_lookahead for s in range(10)]
    assert all(detected)


def test_yoy_by_date_with_gap() -> None:
    """Importante #3: con un mes faltante la variación anual no compara contra otro mes."""
    months = pd.date_range("2023-01-01", "2024-12-01", freq="MS")
    cpi = pd.Series(np.arange(len(months), dtype=float) + 100.0, index=months)
    cpi = cpi.drop(pd.Timestamp("2024-10-01"))
    yoy = Exogenous("cpi", cpi, "M", transform="yoy").transformed()
    assert pd.Timestamp("2024-10-01") not in yoy.index
    assert yoy.loc["2024-11-01"] == pytest.approx(122.0 / 110.0 - 1)
    assert yoy.loc["2024-12-01"] == pytest.approx(123.0 / 111.0 - 1)


def test_internal_price_gap_keeps_return_and_no_spurious_trades() -> None:
    """Importante #4."""
    px = pd.Series(
        [100, 101, np.nan, 110, 111, 112.0], index=pd.bdate_range("2024-01-01", periods=6)
    )
    res = run_backtest(px, px * 0 + 1.0, ExecutionConfig(cost_bps=0))
    assert (1 + res.returns).prod() - 1 == pytest.approx(112 / 101 - 1)
    assert res.turnover.sum() == pytest.approx(1.0)
    assert any("rellenado" in n for n in res.notes)


def test_econometric_defaults_monthly_rebalance_and_checks_dates() -> None:
    """Importantes #5 y #14."""
    prices, y, X = predictive_dgp(5, n_months=200)
    model = PredictiveRegression(min_train=60)
    res = backtest_econometric(prices, y, X[["x"]], model, position="proportional", reps=100)
    assert res.backtest.config.rebalance == "M"
    every = backtest_econometric(
        prices, y, X[["x"]], model, position="proportional", config=ExecutionConfig(), reps=100
    )
    assert any("every_bar" in n for n in every.notes)
    assert every.backtest.turnover.sum() > res.backtest.turnover.sum()
    shifted = y.copy()
    shifted.index = shifted.index - pd.Timedelta(days=1)
    with pytest.raises(DataValidationError, match="fechas de decisión"):
        backtest_econometric(prices, shifted, X.set_axis(shifted.index), PredictiveRegression())


def test_point_in_time_flag_propagates_to_verdict() -> None:
    """Importante #6."""
    prices, y, X = predictive_dgp(6, n_months=200)
    ex = Exogenous("x", X["x"], "M", release_lag="0D", point_in_time=False)
    aligned = align_point_in_time([ex], y.index)
    assert aligned.attrs["point_in_time"] is False
    res = backtest_econometric(prices, y, aligned, PredictiveRegression(min_train=60), reps=100)
    assert res.verdict.exploratory and not res.point_in_time


def test_shared_registry_accumulates_trials() -> None:
    """Importante #7: el DSR cuenta todas las ideas probadas sobre el activo."""
    prices = make_prices(assets=1)
    reg = TrialRegistry()
    first = sweep(
        prices,
        lambda p, f: sma_crossover(p, f, 150),
        {"f": [20, 50]},
        reps=100,
        registry=reg,
        name="a",
    )
    second = sweep(
        prices,
        lambda p, f: sma_crossover(p, f, 200),
        {"f": [20, 50, 100]},
        reps=100,
        registry=reg,
        name="b",
    )
    assert first.selection["n_trials"].iloc[0] == 2
    assert second.selection["n_trials"].iloc[0] == 5 and reg.n_trials == 5
    assert "info_ratio" in second.selection and "Nula común" in second.summary()


def test_dtb3_effective_annual_rate() -> None:
    """Menor #11: rendimiento efectivo anual (no BEY)."""
    daily = dtb3_to_daily(pd.Series([5.0], index=pd.to_datetime(["2024-01-02"])))
    effective = (1 + daily.iloc[0]) ** 252 - 1
    assert effective == pytest.approx(0.0523, abs=2e-4)


def test_incomplete_last_month_dropped() -> None:
    """Menor #13."""
    idx = pd.bdate_range("2024-01-01", "2024-03-15")
    px = pd.Series(1.0, index=idx)
    assert monthly_decision_dates(px)[-1] == pd.Timestamp("2024-02-29")
    assert monthly_decision_dates(px, complete_only=False)[-1] == pd.Timestamp("2024-03-15")


def test_sharpe_difference_null_size_is_controlled() -> None:
    """Menor #12: tamaño con dos series independientes de igual Sharpe (no idénticas)."""
    rng = np.random.default_rng(11)
    rejections = [
        sharpe_difference(
            rng.normal(3e-4, 0.01, 1000), rng.normal(3e-4, 0.01, 1000), reps=200, seed=i
        ).p_value
        < 0.05
        for i in range(60)
    ]
    assert np.mean(rejections) <= 0.15


def test_hac_se_closer_than_iid_under_autocorrelation() -> None:
    """Menor #12: con AR(1) φ = 0,3 el EE HAC se acerca más a la dispersión real."""
    rng = np.random.default_rng(3)
    sharpes, hac, iid = [], [], []
    for _ in range(150):
        e = rng.normal(0, 0.01, 1500)
        x = np.empty(1500)
        x[0] = e[0]
        for t in range(1, 1500):
            x[t] = 0.3 * x[t - 1] + e[t]
        inf = sharpe_inference(x + 3e-4, 252, reps=50, seed=0)
        sharpes.append(inf.sharpe)
        hac.append(inf.se_hac)
        iid.append(inf.se_iid)
    sd = float(np.std(sharpes, ddof=1))
    assert abs(np.mean(hac) - sd) < abs(np.mean(iid) - sd)


def test_sweep_strategy_identical_to_benchmark() -> None:
    """Caso límite: retorno activo idénticamente 0 (sin diferencia ⇒ sin habilidad)."""
    prices = make_prices(assets=1)
    res = sweep(prices, lambda p, k: p.notna().astype(float) * k, {"k": [1.0, 2.0]}, reps=50)
    row = res.selection.iloc[0]
    assert row["info_ratio"] == 0.0 and row["spa_p"] == 1.0 and not row["significant"]
