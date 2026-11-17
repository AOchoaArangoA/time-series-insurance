"""Señales de cartera: pesos objetivo **entre** los activos de un universo (spec 005).

Una señal de cartera es una función causal ``(precios: DataFrame, **parámetros) ->
pesos`` con las mismas columnas que los precios: el peso de la fecha t sólo puede usar
precios hasta t. El paquete verifica la causalidad con la prueba de anticipación sobre el
universo completo antes de evaluar.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from tsinsurance.errors import TSInsuranceError

__all__ = [
    "PortfolioSignalFn",
    "available_portfolio_signals",
    "cross_sectional_momentum",
    "equal_weight",
    "get_portfolio_signal",
    "inverse_volatility",
    "month_end_mask",
    "register_portfolio_signal",
]

PortfolioSignalFn = Callable[..., pd.DataFrame]
_DAYS_PER_MONTH = 21


def equal_weight(prices: pd.DataFrame) -> pd.DataFrame:
    """Benchmark: 1/n entre los activos con precio en cada fecha (``NaN`` = no disponible)."""
    avail = prices.notna().astype(float)
    n = avail.sum(axis=1).replace(0.0, np.nan)
    return avail.div(n, axis=0).fillna(0.0)


def month_end_mask(index: pd.DatetimeIndex) -> np.ndarray:
    """``True`` en el último día hábil de calendario de cada mes.

    Se decide con el calendario (el día hábil siguiente cae en otro mes), no con los datos
    disponibles: así un corte a mitad de mes no convierte su último dato en una fecha de
    decisión (causalidad verificable por la prueba de anticipación).
    """
    idx = pd.DatetimeIndex(index)
    nxt = idx + pd.offsets.BDay(1)
    return np.asarray(nxt.month != idx.month)


def _sorted_rank(values: pd.DataFrame) -> pd.DataFrame:
    """Ranking descendente con empates resueltos por id ordenado (coherente con la identidad)."""
    cols = sorted(values.columns)
    return values[cols].rank(axis=1, ascending=False, method="first")[list(values.columns)]


def cross_sectional_momentum(
    prices: pd.DataFrame, lookback_m: int = 12, skip_m: int = 1, top_k: int = 3
) -> pd.DataFrame:
    """Momentum relativo: 1/top_k en los ``top_k`` activos con mayor retorno pasado.

    Sólo decide en los cierres de mes (calendario). El retorno de cada activo es
    ``C(m − skip_m) / C(m − skip_m − lookback_m) − 1`` con ``C`` el cierre de cada mes;
    ``skip_m`` evita la reversión de corto plazo. Compiten sólo los activos con historia
    suficiente; si hay menos de ``top_k``, la cartera queda en efectivo (el ejecutor de
    experimentos evalúa sólo la ventana donde hay suficientes elegibles). Los empates se
    resuelven por id ordenado. Entre cierres de mes devuelve ``NaN`` (se mantiene la
    decisión anterior).
    """
    if top_k < 1 or lookback_m < 1 or skip_m < 0:
        raise TSInsuranceError("cross_sectional_momentum: top_k, lookback_m ≥ 1 y skip_m ≥ 0.")
    if top_k >= prices.shape[1]:
        raise TSInsuranceError(
            f"cross_sectional_momentum: top_k={top_k} debe ser menor que el universo "
            f"({prices.shape[1]} activos); si no, es la cartera igual ponderada."
        )
    ends = month_end_mask(pd.DatetimeIndex(prices.index))
    closes = prices[ends]
    mom = closes.shift(skip_m) / closes.shift(skip_m + lookback_m) - 1
    rank = _sorted_rank(mom)
    enough = mom.notna().sum(axis=1) >= top_k
    w = ((rank <= top_k) & mom.notna()).astype(float) / top_k
    w = w.where(enough, 0.0)
    return w.reindex(prices.index)


def inverse_volatility(prices: pd.DataFrame, lookback: int = 63) -> pd.DataFrame:
    """Pesos proporcionales a 1/σ de los retornos diarios de los ``lookback`` días hasta t.

    Sólo decide en los cierres de mes; exige ``lookback`` retornos; piso de σ de 1e-4
    diario. Normalizados a 1 entre los activos con historia suficiente; sin ninguno,
    efectivo. Entre cierres de mes devuelve ``NaN`` (se mantiene la decisión anterior).
    """
    if lookback < 5:
        raise TSInsuranceError("inverse_volatility: lookback ≥ 5.")
    rets = prices.pct_change(fill_method=None)
    vol = rets.rolling(lookback, min_periods=lookback).std().clip(lower=1e-4)
    inv = 1.0 / vol
    total = inv.sum(axis=1).replace(0.0, np.nan)
    w = inv.div(total, axis=0).fillna(0.0)
    ends = month_end_mask(pd.DatetimeIndex(prices.index))
    return w.where(pd.Series(ends, index=prices.index), np.nan)


_REGISTRY: dict[str, PortfolioSignalFn] = {
    "cross_sectional_momentum": cross_sectional_momentum,
    "inverse_volatility": inverse_volatility,
}


def register_portfolio_signal(name: str, fn: PortfolioSignalFn) -> None:
    """Registra una señal de cartera propia bajo ``name``."""
    _REGISTRY[name] = fn


def available_portfolio_signals() -> dict[str, str]:
    """Señales de cartera registradas con la primera línea de su descripción."""
    return {k: (v.__doc__ or "").strip().splitlines()[0] for k, v in sorted(_REGISTRY.items())}


def get_portfolio_signal(name: str) -> PortfolioSignalFn:
    """Señal de cartera registrada por nombre."""
    if name not in _REGISTRY:
        raise TSInsuranceError(
            f"Señal de cartera '{name}' desconocida. Disponibles: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]
