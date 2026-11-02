"""Diagnóstico estadístico: estacionariedad, descriptivos y pruebas sobre residuos."""

from tsinsurance.diagnostics.descriptive import (
    DescriptiveReport,
    arch_lm,
    describe,
    jarque_bera,
    ljung_box,
)
from tsinsurance.diagnostics.stationarity import (
    StationarityReport,
    adf,
    kpss,
    pp,
    stationarity,
    zivot_andrews,
)

__all__ = [
    "DescriptiveReport",
    "StationarityReport",
    "adf",
    "arch_lm",
    "describe",
    "jarque_bera",
    "kpss",
    "ljung_box",
    "pp",
    "stationarity",
    "zivot_andrews",
]
