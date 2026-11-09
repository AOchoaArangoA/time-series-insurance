"""Comparación de precisión de pronósticos.

References
----------
.. [1] Diebold, F. X. & Mariano, R. S. (1995). Comparing predictive accuracy. JBES,
   13(3), 253-263.
.. [2] Harvey, D., Leybourne, S. & Newbold, P. (1997). Testing the equality of
   prediction mean squared errors. International Journal of Forecasting, 13(2), 281-291.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

from tsinsurance.errors import DataValidationError, InsufficientDataError
from tsinsurance.results import HypothesisTestResult

__all__ = ["diebold_mariano"]


def diebold_mariano(
    e1: pd.Series | np.ndarray,
    e2: pd.Series | np.ndarray,
    *,
    h: int = 1,
    loss: Literal["mse", "mae"] = "mse",
) -> HypothesisTestResult:
    """Prueba de Diebold-Mariano con corrección de Harvey-Leybourne-Newbold.

    H0: igual precisión esperada. ``statistic > 0`` indica que el pronóstico 2 es más
    preciso. Valor p bilateral con distribución t de ``n - 1`` grados de libertad.
    No es válida para modelos anidados (use Clark-West).
    """
    a = np.asarray(e1, dtype=float)
    b = np.asarray(e2, dtype=float)
    if a.shape != b.shape:
        raise DataValidationError("e1 y e2 deben tener la misma longitud.")
    mask = np.isfinite(a) & np.isfinite(b)
    a, b = a[mask], b[mask]
    n = a.size
    if n < 10:
        raise InsufficientDataError("Diebold-Mariano", 10, n)
    d = (a**2 - b**2) if loss == "mse" else (np.abs(a) - np.abs(b))
    dbar = d.mean()
    dc = d - dbar
    gamma0 = float(dc @ dc) / n
    lrv = gamma0 + 2.0 * sum(float(dc[k:] @ dc[:-k]) / n for k in range(1, h))
    if lrv <= 0:
        raise DataValidationError("Varianza de largo plazo no positiva en Diebold-Mariano.")
    dm = dbar / np.sqrt(lrv / n)
    correction = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    stat = float(dm * correction)
    p = float(2.0 * stats.t.sf(abs(stat), df=n - 1))
    return HypothesisTestResult(
        name="Diebold-Mariano (HLN)",
        statistic=stat,
        p_value=p,
        null_hypothesis="Ambos pronósticos tienen igual precisión esperada.",
        specification={"h": h, "loss": loss, "nobs": n, "two_sided": True},
        reference="Diebold & Mariano (1995); Harvey, Leybourne & Newbold (1997)",
    )
