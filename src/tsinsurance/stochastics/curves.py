"""Interfaz de curva y una curva de nodos mínima (spec 007, frontera estricta).

El ajuste paramétrico de curvas (Nelson-Siegel-Svensson, *splines*) y el *bootstrapping*
pertenecen al paquete hermano de curvas. Aquí sólo se define el contrato ``Curve`` que
consumen los modelos y una ``NodeCurve`` **mínima, no apta para producción**: lineal en
tasas cero continuas y plana fuera del rango de nodos. Su forward instantáneo es
discontinuo en los nodos; se define continuo por la derecha.

Conversiones de convención de los datos:

- **descuento act/360** (letras del Tesoro, ^IRX): precio = 1 − d·n/360 y tasa continua
  r = −ln(precio)·365/n;
- **par semestral** (^FVX, ^TNX, ^TYX): rendimiento del bono que cotiza a la par;
- **cero continuo**: z con P(t) = e^{−z·t}.

References
----------
Hull, J. (2018). *Options, Futures, and Other Derivatives*, 10.ª ed., cap. 4 y 6.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin

__all__ = [
    "Curve",
    "NodeCurve",
    "continuous_from_discount",
    "continuous_from_periodic",
    "discount_from_price",
    "par_yield",
    "periodic_from_continuous",
]

ArrayLike = float | npt.ArrayLike
RateType = Literal["zero", "par", "discount"]


@runtime_checkable
class Curve(Protocol):
    """Contrato de curva: plazos en años, tasas en decimales, capitalización continua."""

    def discount(self, t: ArrayLike) -> np.ndarray:
        """Factor de descuento P(0, t)."""
        ...

    def zero_rate(self, t: ArrayLike) -> np.ndarray:
        """Tasa cero continua z(t), con P(0, t) = exp(−z·t)."""
        ...

    def forward(self, t: ArrayLike) -> np.ndarray:
        """Forward instantáneo f(0, t) = −∂ ln P(0, t)/∂t."""
        ...


@dataclass(frozen=True, slots=True)
class NodeCurve(ResultMixin):
    """Curva mínima: lineal en ceros continuos, plana fuera de rango (no producción)."""

    tenors: tuple[float, ...]
    zero_rates: tuple[float, ...]
    note: str = field(
        default="NodeCurve mínima: lineal en ceros continuos; no apta para producción "
        "(forward discontinuo en los nodos)."
    )

    def __post_init__(self) -> None:
        t = np.asarray(self.tenors, dtype=float)
        z = np.asarray(self.zero_rates, dtype=float)
        if t.ndim != 1 or t.shape != z.shape or t.size < 1:
            raise DataValidationError("tenors y zero_rates deben ser vectores del mismo largo.")
        if np.any(t <= 0) or np.any(np.diff(t) <= 0):
            raise DataValidationError("Los plazos deben ser positivos y estrictamente crecientes.")
        if not np.all(np.isfinite(z)):
            raise DataValidationError("Las tasas cero deben ser finitas.")

    @classmethod
    def from_arrays(cls, tenors: npt.ArrayLike, zero_rates: npt.ArrayLike) -> NodeCurve:
        """Construye la curva desde arreglos."""
        return cls(
            tuple(float(v) for v in np.asarray(tenors, dtype=float)),
            tuple(float(v) for v in np.asarray(zero_rates, dtype=float)),
        )

    def zero_rate(self, t: ArrayLike) -> np.ndarray:
        """Interpolación lineal en z; plana fuera de rango."""
        tt = np.asarray(t, dtype=float)
        return np.asarray(np.interp(tt, self.tenors, self.zero_rates), dtype=float)

    def discount(self, t: ArrayLike) -> np.ndarray:
        """P(0, t) = exp(−z(t)·t)."""
        tt = np.asarray(t, dtype=float)
        return np.asarray(np.exp(-self.zero_rate(tt) * tt), dtype=float)

    def forward(self, t: ArrayLike) -> np.ndarray:
        """f(t) = z(t) + t·z'(t), con la pendiente del tramo a la derecha de t."""
        tt = np.asarray(t, dtype=float)
        nodes = np.asarray(self.tenors)
        z = np.asarray(self.zero_rates)
        slopes = np.diff(z) / np.diff(nodes) if nodes.size > 1 else np.zeros(0)
        idx = np.searchsorted(nodes, tt, side="right") - 1  # tramo [t_i, t_{i+1})
        inside = (idx >= 0) & (idx < nodes.size - 1)
        if slopes.size == 0:
            slope = np.zeros_like(tt)
        else:
            slope = np.where(inside, slopes[np.clip(idx, 0, slopes.size - 1)], 0.0)
        return np.asarray(self.zero_rate(tt) + tt * slope, dtype=float)

    def shifted(self, bumps: npt.ArrayLike) -> NodeCurve:
        """Curva con los ceros de los nodos desplazados (en decimales)."""
        b = np.broadcast_to(np.asarray(bumps, dtype=float), (len(self.tenors),))
        return NodeCurve.from_arrays(self.tenors, np.asarray(self.zero_rates) + b)

    def summary(self) -> str:
        """Resumen legible."""
        pairs = ", ".join(
            f"{t:g}a: {z:.4%}" for t, z in zip(self.tenors, self.zero_rates, strict=True)
        )
        return f"NodeCurve ({pairs}). {self.note}"


def discount_from_price(price: ArrayLike, days: int = 91) -> np.ndarray:
    """Tasa de descuento act/360 a partir del precio de una letra con ``days`` días."""
    return (1.0 - np.asarray(price, dtype=float)) * 360.0 / days


def continuous_from_discount(d: ArrayLike, days: int = 91) -> np.ndarray:
    """Tasa continua (act/365) de una letra cotizada con tasa de descuento ``d`` (decimal)."""
    price = 1.0 - np.asarray(d, dtype=float) * days / 360.0
    if np.any(price <= 0):
        raise DataValidationError("Tasa de descuento demasiado alta: precio ≤ 0.")
    return -np.log(price) * 365.0 / days


def continuous_from_periodic(y: ArrayLike, freq: int = 2) -> np.ndarray:
    """Tasa continua equivalente a una tasa con capitalización ``freq`` veces al año."""
    return freq * np.log1p(np.asarray(y, dtype=float) / freq)


def periodic_from_continuous(z: ArrayLike, freq: int = 2) -> np.ndarray:
    """Inversa de :func:`continuous_from_periodic`."""
    return freq * np.expm1(np.asarray(z, dtype=float) / freq)


def par_yield(
    discount: Callable[[np.ndarray], np.ndarray], maturity: float, freq: int = 2
) -> float:
    """Rendimiento par: y = freq·(1 − P(T)) / Σ P(t_i), con t_i = i/freq ≤ T.

    El primer cupón puede ser corto si T no es múltiplo de 1/freq (se usa la grilla hacia
    atrás desde T).
    """
    n = max(int(round(maturity * freq)), 1)
    times = maturity - np.arange(n)[::-1] / freq
    times = times[times > 0]
    p = discount(times)
    return float(freq * (1.0 - p[-1]) / p.sum())
