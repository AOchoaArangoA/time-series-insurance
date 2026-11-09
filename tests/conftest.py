"""Fixtures compartidas: generadores con semilla y procesos generadores de datos (DGP)."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest

SEED = 20261102


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(SEED)


def _index(n: int, freq: str = "B", start: str = "2000-01-03") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq=freq)


def simulate_random_walk(rng: np.random.Generator, n: int, sigma: float = 1.0) -> pd.Series:
    return pd.Series(np.cumsum(rng.normal(0, sigma, n)) + 100.0, index=_index(n), name="rw")


def simulate_ar1(rng: np.random.Generator, n: int, phi: float = 0.5, burn: int = 200) -> pd.Series:
    e = rng.normal(size=n + burn)
    y = np.zeros(n + burn)
    for t in range(1, n + burn):
        y[t] = phi * y[t - 1] + e[t]
    return pd.Series(y[burn:], index=_index(n), name="ar1")


def simulate_arma11(
    rng: np.random.Generator, n: int, phi: float = 0.6, theta: float = 0.3, burn: int = 200
) -> pd.Series:
    e = rng.normal(size=n + burn)
    y = np.zeros(n + burn)
    for t in range(1, n + burn):
        y[t] = phi * y[t - 1] + e[t] + theta * e[t - 1]
    return pd.Series(y[burn:], index=_index(n), name="arma11")


def simulate_arma_garch(
    rng: np.random.Generator,
    n: int,
    *,
    mu: float = 0.05,
    phi: float = 0.1,
    omega: float = 0.05,
    alpha: float = 0.08,
    beta: float = 0.9,
    nu: float = 8.0,
    burn: int = 500,
) -> pd.Series:
    """AR(1)-GARCH(1,1) con innovaciones t de Student estandarizadas."""
    total = n + burn
    z = rng.standard_t(nu, size=total) / np.sqrt(nu / (nu - 2.0))
    h = np.empty(total)
    eps = np.empty(total)
    y = np.empty(total)
    h[0] = omega / (1 - alpha - beta)
    eps[0] = np.sqrt(h[0]) * z[0]
    y[0] = mu / (1 - phi) + eps[0]
    for t in range(1, total):
        h[t] = omega + alpha * eps[t - 1] ** 2 + beta * h[t - 1]
        eps[t] = np.sqrt(h[t]) * z[t]
        y[t] = mu + phi * (y[t - 1]) + eps[t]
    return pd.Series(y[burn:], index=_index(n), name="arma_garch")


@pytest.fixture
def make_random_walk() -> Callable[..., pd.Series]:
    return simulate_random_walk


@pytest.fixture
def make_ar1() -> Callable[..., pd.Series]:
    return simulate_ar1


@pytest.fixture
def make_arma11() -> Callable[..., pd.Series]:
    return simulate_arma11


@pytest.fixture
def make_arma_garch() -> Callable[..., pd.Series]:
    return simulate_arma_garch
