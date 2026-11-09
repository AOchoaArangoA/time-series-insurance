"""Métricas de desempeño de una serie de retornos por periodo."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tsinsurance.results import ResultMixin

__all__ = ["PerformanceMetrics", "performance_metrics", "sharpe_per_period"]


def sharpe_per_period(returns: pd.Series | np.ndarray) -> float:
    """Sharpe por periodo (media / desviación muestral).

    Una serie idénticamente 0 (p. ej. retornos en exceso de estar siempre en efectivo)
    tiene Sharpe 0; otra serie constante no nula es indefinida (``NaN``).
    """
    x = np.asarray(returns, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 2:
        return float("nan")
    sd = float(np.std(x, ddof=1))
    if sd > 0:
        return float(np.mean(x)) / sd
    return 0.0 if abs(float(np.mean(x))) < 1e-14 else float("nan")


@dataclass(frozen=True, slots=True)
class PerformanceMetrics(ResultMixin):
    """Métricas anualizadas de desempeño.

    ``sharpe`` y ``sortino`` se calculan sobre los retornos recibidos (pase retornos en
    exceso de la tasa libre de riesgo para un Sharpe en sentido estricto).
    """

    annual_return: float
    annual_volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    hit_rate: float
    avg_turnover: float
    n_periods: int
    periods_per_year: int

    def summary(self) -> str:
        """Resumen de una línea."""
        return (
            f"ret. anual={self.annual_return:+.2%}  vol={self.annual_volatility:.2%}  "
            f"Sharpe={self.sharpe:.2f}  Sortino={self.sortino:.2f}  "
            f"máx. caída={self.max_drawdown:.2%}  Calmar={self.calmar:.2f}  "
            f"aciertos={self.hit_rate:.1%}  rotación media={self.avg_turnover:.4f}  "
            f"n={self.n_periods}"
        )


def performance_metrics(
    returns: pd.Series,
    periods_per_year: int,
    *,
    turnover: pd.Series | None = None,
) -> PerformanceMetrics:
    """Calcula métricas de desempeño.

    Parameters
    ----------
    returns : pandas.Series
        Retornos simples por periodo (se ignoran faltantes).
    periods_per_year : int
        252 (diario), 52 (semanal) o 12 (mensual).
    turnover : pandas.Series, optional
        Rotación por periodo (Σ|Δw|).
    """
    r = returns.dropna().astype(float)
    n = len(r)
    if n == 0:
        nan = float("nan")
        return PerformanceMetrics(nan, nan, nan, nan, nan, nan, nan, nan, 0, periods_per_year)
    growth = float(np.prod(1.0 + r.to_numpy()))
    years = n / periods_per_year
    ann_ret = growth ** (1.0 / years) - 1.0 if growth > 0 else -1.0
    vol = float(r.std(ddof=1)) * np.sqrt(periods_per_year) if n > 1 else float("nan")
    sr = sharpe_per_period(r) * np.sqrt(periods_per_year)
    downside = r[r < 0]
    dd_dev = float(np.sqrt(np.mean(np.minimum(r.to_numpy(), 0.0) ** 2))) if len(downside) else 0.0
    sortino = float(r.mean()) / dd_dev * np.sqrt(periods_per_year) if dd_dev > 0 else float("nan")
    equity = np.cumprod(1.0 + r.to_numpy())
    peak = np.maximum.accumulate(np.concatenate([[1.0], equity]))[1:]
    max_dd = float(np.min(equity / peak - 1.0))
    calmar = ann_ret / abs(max_dd) if max_dd < 0 else float("nan")
    active = r[r != 0]
    hit = float((active > 0).mean()) if len(active) else float("nan")
    avg_to = float(turnover.mean()) if turnover is not None and len(turnover) else 0.0
    return PerformanceMetrics(
        annual_return=float(ann_ret),
        annual_volatility=vol,
        sharpe=float(sr),
        sortino=sortino,
        max_drawdown=max_dd,
        calmar=float(calmar),
        hit_rate=hit,
        avg_turnover=avg_to,
        n_periods=n,
        periods_per_year=periods_per_year,
    )
