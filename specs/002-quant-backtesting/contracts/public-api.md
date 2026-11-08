# Contrato: API pública de `tsinsurance.backtest` v0.1

```python
from tsinsurance.backtest import (
    ExecutionConfig, run_backtest, run_with_bt,
    sma_crossover, tsmom, ewma_volatility, garch_volatility_forecast, vol_target,
    Exogenous, align_point_in_time, PredictiveRegression, backtest_econometric,
    check_lookahead, sweep, calibrate_validate, TrialRegistry,
    performance_metrics, sharpe_inference, probabilistic_sharpe, deflated_sharpe,
    spa_test, pesaran_timmermann, clark_west, oos_r2, evaluate_forecasts, Verdict,
)
from tsinsurance.validation import diebold_mariano
```

## Motor

```python
run_backtest(prices: DataFrame | Series, target_weights: DataFrame | Series,
             config: ExecutionConfig = ExecutionConfig(), *,
             risk_free: Series | None = None,       # tasa por periodo, decimal
             benchmark: Series | DataFrame | Literal["buy_and_hold"] | None = "buy_and_hold",
             name: str = "strategy") -> BacktestResult
run_with_bt(prices, target_weights, config) -> Series   # retornos netos según bt (extra [backtest])
```

`target_weights` en la fecha `t` = decisión con información hasta el cierre de `t`.

## Señales (devuelven pesos objetivo decididos en `t`)

```python
sma_crossover(prices, fast=50, slow=200, *, short=False) -> DataFrame
tsmom(prices, lookback=252, skip=0, *, short=False) -> DataFrame
ewma_volatility(returns, lam=0.94, periods_per_year=252) -> DataFrame  # anualizada
garch_volatility_forecast(returns, *, refit_every=21, min_train=500, periods_per_year=252, dist="t") -> DataFrame
vol_target(base_weights, volatility, target=0.10, *, max_leverage=1.0) -> DataFrame
```

## Punto en el tiempo y modelos econométricos

```python
Exogenous(name, series, frequency, release_lag: str | DateOffset, transform="level")
align_point_in_time(exogs: Sequence[Exogenous], decision_dates: DatetimeIndex) -> DataFrame
PredictiveRegression(ar_lags=0, scheme="expanding", window=None, min_train=60, refit_every=1)
    .walk_forward(y: Series, X: DataFrame) -> WalkForwardForecast
    .validate(y, X) -> ModelValidation              # muestra completa, HAC, diagnósticos
backtest_econometric(prices, y, X, model: PredictiveRegression, *,
    position: Literal["long_cash", "long_short", "proportional"] = "long_cash",
    config=ExecutionConfig(), risk_free=None, alpha=0.05, seed=0) -> EconometricBacktest
```

## Validación

```python
check_lookahead(signal_fn: Callable[[DataFrame], DataFrame | Series], data, *,
                n_cuts=10, seed=0, tol=1e-10) -> LookaheadReport
performance_metrics(returns, periods_per_year) -> PerformanceMetrics
sharpe_inference(returns, periods_per_year, *, reps=1000, seed=0) -> SharpeInference
probabilistic_sharpe(returns, sr_benchmark=0.0) -> float          # SR no anualizado
deflated_sharpe(returns, n_trials, trials_sharpe_variance) -> DeflatedSharpe
spa_test(benchmark_returns, strategy_returns: DataFrame, *, reps=1000, seed=0) -> SPAResult
pesaran_timmermann(forecast, realized) -> HypothesisTestResult
clark_west(realized, f_restricted, f_unrestricted, *, h=1) -> HypothesisTestResult
oos_r2(realized, f_restricted, f_unrestricted) -> float
evaluate_forecasts(realized, f_restricted, f_unrestricted) -> ForecastEvaluation
diebold_mariano(e1, e2, *, h=1, loss="mse") -> HypothesisTestResult
```

## Escalado

```python
sweep(prices: DataFrame, signal_fn: Callable[..., DataFrame], grid: Mapping[str, Sequence],
      config=ExecutionConfig(), *, per_asset=True, risk_free=None, seed=0) -> SweepResult
calibrate_validate(prices, signal_fn, grid, train_end, config=ExecutionConfig(), ...) -> CalibrationResult
```

## Errores

Reutiliza `DataValidationError` (índices, pesos negativos sin `allow_short`, columnas
desalineadas), `InsufficientDataError` (ventanas de entrenamiento) y
`LookaheadBiasError(TSInsuranceError)` (nuevo) al usar una señal marcada con fuga.
