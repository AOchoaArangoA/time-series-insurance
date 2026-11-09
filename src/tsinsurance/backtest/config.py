"""Configuración explícita de ejecución de un backtest (Principio VIII)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

import pandas as pd

from tsinsurance.errors import TSInsuranceError

__all__ = ["ExecutionConfig", "infer_periods_per_year"]

Rebalance = Literal["every_bar", "W", "M"]

_PPY = {"B": 252, "C": 252, "D": 252, "W": 52, "M": 12, "ME": 12, "MS": 12, "BME": 12}


def infer_periods_per_year(index: pd.DatetimeIndex) -> int:
    """Periodos por año a partir del espaciado mediano del índice (252, 52 o 12)."""
    if len(index) < 3:
        raise TSInsuranceError("Se requieren al menos 3 fechas para inferir la frecuencia.")
    days = float(pd.Series(index).diff().dt.days.median())
    if days <= 4:
        return 252
    if days <= 10:
        return 52
    return 12


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Supuestos de ejecución; ninguno queda implícito.

    Attributes
    ----------
    lag : int
        Barras entre la decisión (cierre de ``t``) y la ejecución (cierre de ``t + lag``).
        ``0`` supone órdenes al cierre de la misma barra (optimista).
    cost_bps : float or Mapping[str, float]
        Costo proporcional por unidad de rotación, en puntos básicos; por activo si es
        un ``Mapping`` (los activos ausentes usan ``default_cost_bps``).
    slippage_bps : float
        Deslizamiento adicional por unidad de rotación.
    rebalance : {"every_bar", "W", "M"}
        Frecuencia con la que se actualizan los pesos objetivo (último día del periodo).
    max_gross : float
        Exposición bruta máxima Σ|w|; los excesos se recortan proporcionalmente.
    allow_short : bool
        Si ``False``, un peso negativo es un error.
    financing_spread_bps : float
        Diferencial anual sobre la tasa libre de riesgo para efectivo negativo
        (apalancamiento) y préstamo de cortos.
    default_cost_bps : float
        Costo para activos no listados cuando ``cost_bps`` es un ``Mapping``.
    periods_per_year : int or None
        ``None`` ⇒ se infiere del índice de precios.
    """

    lag: int = 1
    cost_bps: float | Mapping[str, float] = 5.0
    slippage_bps: float = 0.0
    rebalance: Rebalance = "every_bar"
    max_gross: float = 1.0
    allow_short: bool = False
    financing_spread_bps: float = 0.0
    default_cost_bps: float = 5.0
    periods_per_year: int | None = None
    notes: tuple[str, ...] = field(default=(), compare=False)

    def __post_init__(self) -> None:
        if self.lag < 0:
            raise TSInsuranceError("lag debe ser >= 0.")
        costs = self.cost_bps.values() if isinstance(self.cost_bps, Mapping) else [self.cost_bps]
        if any(c < 0 for c in costs) or self.slippage_bps < 0 or self.default_cost_bps < 0:
            raise TSInsuranceError("Costos y deslizamiento deben ser >= 0.")
        if self.rebalance not in ("every_bar", "W", "M"):
            raise TSInsuranceError("rebalance debe ser 'every_bar', 'W' o 'M'.")
        if self.max_gross <= 0:
            raise TSInsuranceError("max_gross debe ser > 0.")
        if self.financing_spread_bps < 0:
            raise TSInsuranceError("financing_spread_bps debe ser >= 0.")
        if isinstance(self.cost_bps, Mapping):
            object.__setattr__(self, "cost_bps", MappingProxyType(dict(self.cost_bps)))
        notes = list(self.notes)
        if self.lag == 0:
            notes.append(
                "lag=0: ejecución al cierre de la barra de decisión (optimista; requiere "
                "órdenes al cierre)."
            )
        object.__setattr__(self, "notes", tuple(notes))

    def cost_rate(self, assets: list[str]) -> list[float]:
        """Costo total (costo + deslizamiento) por unidad de rotación, por activo, en decimal."""
        out = []
        for a in assets:
            if isinstance(self.cost_bps, Mapping):
                c = float(self.cost_bps.get(a, self.default_cost_bps))
            else:
                c = float(self.cost_bps)
            out.append((c + self.slippage_bps) / 1e4)
        return out

    def describe(self) -> str:
        """Supuestos en una línea."""
        cost = dict(self.cost_bps) if isinstance(self.cost_bps, Mapping) else f"{self.cost_bps} pb"
        return (
            f"retraso={self.lag} barra(s), costo={cost}, deslizamiento={self.slippage_bps} pb, "
            f"rebalanceo={self.rebalance}, bruto máx.={self.max_gross}, cortos="
            f"{'sí' if self.allow_short else 'no'}, financiación=rf+{self.financing_spread_bps} pb"
        )
