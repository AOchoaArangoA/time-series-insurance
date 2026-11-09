"""Registro de señales por nombre para experimentos declarativos.

Una señal es una función ``(precios: DataFrame, **parámetros) -> pesos objetivo`` causal.
Agregue las suyas con :func:`register_signal`.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from tsinsurance.backtest.signals import ewma_volatility, sma_crossover, tsmom, vol_target
from tsinsurance.errors import TSInsuranceError

__all__ = ["SignalFn", "available_signals", "get_signal", "register_signal"]

SignalFn = Callable[..., pd.DataFrame]


def _sma(p: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.DataFrame:
    """Cruce de medias: largo si la media rápida supera a la lenta; si no, efectivo."""
    return sma_crossover(p, fast, slow, normalize=False)


def _tsmom(p: pd.DataFrame, lookback: int = 252, skip: int = 21) -> pd.DataFrame:
    """Momentum de serie de tiempo: largo si el retorno pasado es positivo."""
    return tsmom(p, lookback, skip, normalize=False)


def _ewma_target(p: pd.DataFrame, target: float = 0.10, lam: float = 0.94) -> pd.DataFrame:
    """Siempre invertido, escalado a una volatilidad objetivo (EWMA)."""
    vol = ewma_volatility(p.pct_change(), lam=lam)
    return vol_target(p.notna().astype(float), vol, target=target, max_leverage=1.0)


def _tsmom_vol(
    p: pd.DataFrame, lookback: int = 252, skip: int = 21, target: float = 0.10
) -> pd.DataFrame:
    """Momentum con objetivo de volatilidad (sin apalancamiento)."""
    vol = ewma_volatility(p.pct_change())
    return vol_target(_tsmom(p, lookback, skip), vol, target=target, max_leverage=1.0)


_REGISTRY: dict[str, SignalFn] = {
    "sma_crossover": _sma,
    "tsmom": _tsmom,
    "ewma_vol_target": _ewma_target,
    "tsmom_vol_target": _tsmom_vol,
}


def register_signal(name: str, fn: SignalFn) -> None:
    """Registra una señal propia bajo ``name``."""
    _REGISTRY[name] = fn


def available_signals() -> dict[str, str]:
    """Señales registradas con su descripción."""
    return {
        k: ((v.__doc__ or "").strip().splitlines() or ["(sin descripción)"])[0]
        for k, v in sorted(_REGISTRY.items())
    }


def get_signal(name: str) -> SignalFn:
    """Devuelve la señal registrada ``name``."""
    if name not in _REGISTRY:
        raise TSInsuranceError(f"Señal '{name}' desconocida. Disponibles: {sorted(_REGISTRY)}")
    return _REGISTRY[name]
