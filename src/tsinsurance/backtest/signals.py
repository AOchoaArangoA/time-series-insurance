"""Señales de tendencia y volatilidad (pesos objetivo decididos al cierre de ``t``).

Todas las señales son causales: el valor en ``t`` sólo usa datos hasta ``t``
(verificable con :func:`tsinsurance.backtest.check_lookahead`).

References
----------
.. [1] Brock, W., Lakonishok, J. & LeBaron, B. (1992). Simple technical trading rules
   and the stochastic properties of stock returns. Journal of Finance, 47(5).
.. [2] Moskowitz, T., Ooi, Y. H. & Pedersen, L. H. (2012). Time series momentum.
   Journal of Financial Economics, 104(2), 228-250.
.. [3] Moreira, A. & Muir, T. (2017). Volatility-managed portfolios. Journal of
   Finance, 72(4), 1611-1644.
.. [4] J.P. Morgan/Reuters (1996). RiskMetrics — Technical Document (EWMA, λ = 0,94).
.. [5] Bollerslev, T. (1986). Generalized autoregressive conditional
   heteroskedasticity. Journal of Econometrics, 31(3), 307-327.
"""

from __future__ import annotations

import warnings
from typing import Literal

import numpy as np
import pandas as pd
from arch import arch_model

from tsinsurance.errors import InsufficientDataError

Dist = Literal["normal", "t", "skewt"]

__all__ = [
    "ewma_volatility",
    "garch_volatility_forecast",
    "sma_crossover",
    "tsmom",
    "vol_target",
]


def _frame(x: pd.Series | pd.DataFrame) -> pd.DataFrame:
    return x.to_frame() if isinstance(x, pd.Series) else x


def _scale(sig: pd.DataFrame, normalize: bool) -> pd.DataFrame:
    return sig / sig.shape[1] if normalize else sig


def sma_crossover(
    prices: pd.Series | pd.DataFrame,
    fast: int = 50,
    slow: int = 200,
    *,
    short: bool = False,
    normalize: bool = True,
) -> pd.DataFrame:
    """Cruce de medias móviles: largo si la media rápida supera a la lenta.

    Fuera de la señal: efectivo (o corto si ``short``). ``NaN`` durante el
    calentamiento (``slow`` observaciones). Con ``normalize`` cada activo recibe
    ``1/N`` del capital.
    """
    if fast >= slow:
        raise ValueError("fast debe ser menor que slow.")
    px = _frame(prices)
    f = px.rolling(fast, min_periods=fast).mean()
    s = px.rolling(slow, min_periods=slow).mean()
    sig = pd.DataFrame(
        np.where(f > s, 1.0, -1.0 if short else 0.0), index=px.index, columns=px.columns
    )
    sig = sig.where(s.notna())
    return _scale(sig, normalize)


def tsmom(
    prices: pd.Series | pd.DataFrame,
    lookback: int = 252,
    skip: int = 0,
    *,
    short: bool = False,
    normalize: bool = True,
) -> pd.DataFrame:
    """Momentum de serie de tiempo: signo del retorno entre ``t-lookback`` y ``t-skip``."""
    if lookback <= skip:
        raise ValueError("lookback debe ser mayor que skip.")
    px = _frame(prices)
    past = px.shift(skip) / px.shift(lookback) - 1.0
    sig = pd.DataFrame(
        np.where(past > 0, 1.0, -1.0 if short else 0.0), index=px.index, columns=px.columns
    ).where(past.notna())
    return _scale(sig, normalize)


def ewma_volatility(
    returns: pd.Series | pd.DataFrame,
    lam: float = 0.94,
    periods_per_year: int = 252,
    *,
    min_periods: int = 20,
) -> pd.DataFrame:
    """Volatilidad EWMA (RiskMetrics) anualizada, conocida al cierre de ``t``."""
    if not 0 < lam < 1:
        raise ValueError("lam debe estar en (0, 1).")
    r = _frame(returns)
    var = (r**2).ewm(alpha=1.0 - lam, adjust=False, min_periods=min_periods).mean()
    out: pd.DataFrame = (var * periods_per_year) ** 0.5
    return out


def garch_volatility_forecast(
    returns: pd.Series | pd.DataFrame,
    *,
    refit_every: int = 21,
    min_train: int = 500,
    periods_per_year: int = 252,
    dist: Dist = "t",
) -> pd.DataFrame:
    """Pronóstico GARCH(1,1) a un paso, re-estimado *walk-forward*.

    En cada fecha de re-estimación ``t_k`` los parámetros se estiman con datos hasta
    ``t_k``; entre re-estimaciones se filtran los datos nuevos con parámetros fijos. El
    valor en ``t`` es la volatilidad anualizada pronosticada para ``t+1`` con información
    hasta ``t``.
    """
    r = _frame(returns)
    out = pd.DataFrame(np.nan, index=r.index, columns=r.columns)
    for col in r.columns:
        x = r[col].dropna() * 100.0
        n = len(x)
        if n <= min_train:
            raise InsufficientDataError("garch_volatility_forecast", min_train + 1, n)
        values = np.full(n, np.nan)
        for start in range(min_train - 1, n, refit_every):
            stop = min(start + refit_every, n)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fit = arch_model(x.iloc[: start + 1], vol="GARCH", p=1, q=1, dist=dist).fit(
                    disp="off"
                )
                fixed = arch_model(x.iloc[:stop], vol="GARCH", p=1, q=1, dist=dist).fix(fit.params)
                fc = fixed.forecast(horizon=1, start=start, reindex=False)
            values[start:stop] = np.sqrt(fc.variance.to_numpy()[:, 0])
        out.loc[x.index, col] = values / 100.0 * np.sqrt(periods_per_year)
    return out


def vol_target(
    base_weights: pd.Series | pd.DataFrame,
    volatility: pd.Series | pd.DataFrame,
    target: float = 0.10,
    *,
    max_leverage: float = 1.0,
) -> pd.DataFrame:
    """Escala los pesos para apuntar a una volatilidad anual ``target`` por activo.

    ``w = base × min(target / σ̂_t, max_leverage)``, con ``σ̂_t`` conocida en ``t``.
    """
    if target <= 0 or max_leverage <= 0:
        raise ValueError("target y max_leverage deben ser positivos.")
    base = _frame(base_weights)
    vol = _frame(volatility).reindex_like(base)
    scale = (target / vol).clip(upper=max_leverage)
    return base * scale
