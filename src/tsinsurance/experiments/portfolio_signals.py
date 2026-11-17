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
    "register_portfolio_signal",
]

PortfolioSignalFn = Callable[..., pd.DataFrame]
_DAYS_PER_MONTH = 21


def equal_weight(prices: pd.DataFrame) -> pd.DataFrame:
    """Benchmark: 1/n entre los activos con precio en cada fecha (``NaN`` = no disponible)."""
    avail = prices.notna().astype(float)
    n = avail.sum(axis=1).replace(0.0, np.nan)
    return avail.div(n, axis=0).fillna(0.0)


def cross_sectional_momentum(
    prices: pd.DataFrame, lookback_m: int = 12, skip_m: int = 1, top_k: int = 3
) -> pd.DataFrame:
    """Momentum relativo: 1/top_k en los ``top_k`` activos con mayor retorno pasado.

    El retorno de cada activo es ``P(t − 21·skip_m) / P(t − 21·(skip_m + lookback_m)) − 1``
    (meses de 21 días hábiles; ``skip_m`` evita la reversión de corto plazo). Sólo
    compiten los activos con historia suficiente; si hay menos de ``top_k``, la cartera
    queda en efectivo. Los empates se resuelven por el orden de las columnas (el orden
    declarado del universo), de forma determinista.
    """
    if top_k < 1 or lookback_m < 1 or skip_m < 0:
        raise TSInsuranceError("cross_sectional_momentum: top_k, lookback_m ≥ 1 y skip_m ≥ 0.")
    near = prices.shift(_DAYS_PER_MONTH * skip_m)
    far = prices.shift(_DAYS_PER_MONTH * (skip_m + lookback_m))
    mom = near / far - 1
    # Ranking con desempate por posición de la columna (método "first").
    rank = mom.rank(axis=1, ascending=False, method="first")
    enough = mom.notna().sum(axis=1) >= top_k
    w = (rank <= top_k).astype(float) / top_k
    w = w.where(mom.notna(), 0.0)
    return w.where(enough, 0.0)


def inverse_volatility(prices: pd.DataFrame, lookback: int = 63) -> pd.DataFrame:
    """Pesos proporcionales a 1/σ de los retornos diarios de los ``lookback`` días previos.

    Normalizados a 1 entre los activos con historia suficiente; sin ninguno, efectivo.
    """
    if lookback < 5:
        raise TSInsuranceError("inverse_volatility: lookback ≥ 5.")
    vol = prices.pct_change(fill_method=None).rolling(lookback, min_periods=lookback).std()
    inv = (1.0 / vol).replace([np.inf, -np.inf], np.nan)
    total = inv.sum(axis=1).replace(0.0, np.nan)
    return inv.div(total, axis=0).fillna(0.0)


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
