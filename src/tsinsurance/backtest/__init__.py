"""Backtesting responsable de estrategias cuantitativas y modelos econométricos.

Ver ``specs/002-quant-backtesting`` y ``docs/methodology/backtesting.md``.
"""

from tsinsurance.backtest.config import ExecutionConfig, infer_periods_per_year
from tsinsurance.backtest.econometric import (
    EconometricBacktest,
    ModelValidation,
    PredictiveRegression,
    WalkForwardForecast,
    backtest_econometric,
    forecast_to_weights,
)
from tsinsurance.backtest.engine import BacktestResult, equal_weight_benchmark, run_backtest
from tsinsurance.backtest.inference import (
    DeflatedSharpe,
    ForecastEvaluation,
    SharpeDifference,
    SharpeInference,
    SPAResult,
    clark_west,
    deflated_sharpe,
    effective_number_of_trials,
    evaluate_forecasts,
    expected_max_sharpe,
    oos_r2,
    pesaran_timmermann,
    probabilistic_sharpe,
    psr_from_moments,
    sharpe_difference,
    sharpe_inference,
    spa_test,
)
from tsinsurance.backtest.lookahead import LookaheadReport, check_lookahead
from tsinsurance.backtest.metrics import PerformanceMetrics, performance_metrics
from tsinsurance.backtest.pit import (
    Exogenous,
    align_point_in_time,
    dtb3_to_daily,
    monthly_decision_dates,
    monthly_returns,
)
from tsinsurance.backtest.reference import run_with_bt
from tsinsurance.backtest.signals import (
    ewma_volatility,
    garch_volatility_forecast,
    sma_crossover,
    tsmom,
    vol_target,
)
from tsinsurance.backtest.sweep import (
    CalibrationResult,
    SweepResult,
    Trial,
    TrialRegistry,
    calibrate_validate,
    sweep,
)
from tsinsurance.backtest.verdict import Verdict

__all__ = [
    "BacktestResult",
    "CalibrationResult",
    "DeflatedSharpe",
    "EconometricBacktest",
    "ExecutionConfig",
    "Exogenous",
    "ForecastEvaluation",
    "LookaheadReport",
    "ModelValidation",
    "PerformanceMetrics",
    "PredictiveRegression",
    "SPAResult",
    "SharpeDifference",
    "SharpeInference",
    "SweepResult",
    "Trial",
    "TrialRegistry",
    "Verdict",
    "WalkForwardForecast",
    "align_point_in_time",
    "backtest_econometric",
    "calibrate_validate",
    "check_lookahead",
    "clark_west",
    "deflated_sharpe",
    "dtb3_to_daily",
    "effective_number_of_trials",
    "equal_weight_benchmark",
    "evaluate_forecasts",
    "ewma_volatility",
    "expected_max_sharpe",
    "forecast_to_weights",
    "garch_volatility_forecast",
    "infer_periods_per_year",
    "monthly_decision_dates",
    "monthly_returns",
    "oos_r2",
    "performance_metrics",
    "pesaran_timmermann",
    "probabilistic_sharpe",
    "psr_from_moments",
    "run_backtest",
    "run_with_bt",
    "sharpe_difference",
    "sharpe_inference",
    "sma_crossover",
    "spa_test",
    "sweep",
    "tsmom",
    "vol_target",
]
