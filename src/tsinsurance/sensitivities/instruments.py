"""Instrumentos de flujos fijos para medir sensibilidades (spec 007, US5).

Un bono de cupón fijo con vencimiento en años, cupón anual (decimal) pagado ``freq`` veces
al año y nominal 100. Las fechas de pago se cuentan hacia atrás desde el vencimiento (el
primer cupón puede ser corto). Valoración con cualquier :class:`~tsinsurance.stochastics.Curve`:
PV = Σ c_k·P(0, t_k). No hay devengo, convenciones de calendario ni opcionalidad: es el
mínimo para medir riesgo de tasa; los instrumentos de producción vienen del sistema de
valoración.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin
from tsinsurance.stochastics.curves import Curve

__all__ = ["BondPortfolio", "FixedBond"]


@dataclass(frozen=True, slots=True)
class FixedBond(ResultMixin):
    """Bono de cupón fijo (nominal 100)."""

    maturity: float
    coupon: float
    freq: int = 2
    notional: float = 100.0

    def __post_init__(self) -> None:
        if self.maturity <= 0 or self.freq < 1 or self.coupon < 0:
            raise DataValidationError("Vencimiento > 0, frecuencia ≥ 1 y cupón ≥ 0.")

    def cashflows(self) -> tuple[np.ndarray, np.ndarray]:
        """(tiempos en años, flujos)."""
        n = max(int(np.ceil(self.maturity * self.freq - 1e-9)), 1)
        times = self.maturity - np.arange(n)[::-1] / self.freq
        times = times[times > 1e-12]
        flows = np.full(times.size, self.notional * self.coupon / self.freq)
        flows[-1] += self.notional
        return times, flows

    def pv(self, curve: Curve) -> float:
        """Valor presente con la curva."""
        t, c = self.cashflows()
        return float(c @ curve.discount(t))

    def summary(self) -> str:
        """Resumen legible."""
        return f"Bono {self.maturity:g}a, cupón {self.coupon:.3%} ({self.freq}/año)"


@dataclass(frozen=True, slots=True)
class BondPortfolio(ResultMixin):
    """Cartera de bonos con cantidades (número de bonos de nominal 100)."""

    positions: tuple[tuple[FixedBond, float], ...] = field(default_factory=tuple)

    @classmethod
    def of(cls, positions: Iterable[tuple[FixedBond, float]]) -> BondPortfolio:
        """Construye la cartera."""
        return cls(tuple((b, float(q)) for b, q in positions))

    def cashflows(self) -> tuple[np.ndarray, np.ndarray]:
        """Flujos agregados por fecha (tiempos ordenados)."""
        if not self.positions:
            return np.zeros(0), np.zeros(0)
        ts, cs = [], []
        for bond, qty in self.positions:
            t, c = bond.cashflows()
            ts.append(t)
            cs.append(c * qty)
        t_all = np.concatenate(ts)
        c_all = np.concatenate(cs)
        uniq, inv = np.unique(np.round(t_all, 12), return_inverse=True)
        return uniq, np.bincount(inv, weights=c_all)

    def pv(self, curve: Curve) -> float:
        """Valor presente con la curva."""
        t, c = self.cashflows()
        return float(c @ curve.discount(t)) if t.size else 0.0

    def summary(self) -> str:
        """Resumen legible."""
        return "Cartera: " + "; ".join(f"{q:g} × {b.summary()}" for b, q in self.positions)
