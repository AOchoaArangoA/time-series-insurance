"""Motor de simulación de la curva (spec 007): factores, escenarios y reducción de varianza."""

from tsinsurance.simulation.factors import FactorModel, fit_factors, nelson_siegel_loadings
from tsinsurance.simulation.scenarios import (
    Scenarios,
    factor_mc,
    filtered_historical,
    historical,
    short_rate_mc,
)
from tsinsurance.simulation.variance import (
    VRResult,
    control_variate,
    simulate_rate_integral,
    vasicek_discount_mc,
)

__all__ = [
    "FactorModel",
    "Scenarios",
    "VRResult",
    "control_variate",
    "factor_mc",
    "filtered_historical",
    "fit_factors",
    "historical",
    "nelson_siegel_loadings",
    "short_rate_mc",
    "simulate_rate_integral",
    "vasicek_discount_mc",
]
