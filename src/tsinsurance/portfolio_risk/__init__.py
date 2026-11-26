"""Riesgo de cartera de tasas (spec 007): VaR/ES, backtesting, estrés y cobertura."""

from tsinsurance.portfolio_risk.backtest import (
    VaRBacktest,
    backtest_var,
    christoffersen,
    duration_test,
    kupiec,
)
from tsinsurance.portfolio_risk.stress import (
    HedgeResult,
    StressReport,
    immunize,
    regime_conditional_scenarios,
    standard_shocks,
    stress,
)
from tsinsurance.portfolio_risk.var_es import (
    RiskMeasure,
    expected_shortfall,
    value_at_risk,
    var_es,
)

__all__ = [
    "HedgeResult",
    "RiskMeasure",
    "StressReport",
    "VaRBacktest",
    "backtest_var",
    "christoffersen",
    "duration_test",
    "expected_shortfall",
    "immunize",
    "kupiec",
    "regime_conditional_scenarios",
    "standard_shocks",
    "stress",
    "value_at_risk",
    "var_es",
]
