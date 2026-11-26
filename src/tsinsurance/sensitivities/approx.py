"""Δ y Γ por factor, aproximaciones frente a revaluación completa y atribución de P&L.

(spec 007, US5; revisión M3.)

- **Por factor**: la curva se choca con las cargas del modelo de factores (en pb):
  Δ_f = ∂PV/∂f y Γ_fg por diferencias finitas centrales; el Γ cruzado usa el esquema de 4
  puntos [PV(+,+) − PV(+,−) − PV(−,+) + PV(−,−)] / (4h²).
- **Aproximaciones**: ΔPV ≈ g'Δz (Δ) y ΔPV ≈ g'Δz + ½Δz'HΔz (ΔΓ), con g y H analíticos por
  nodos; el error se mide frente a la **revaluación completa** en cada escenario.
- **Atribución**: el cambio de los nodos se proyecta en los factores (mínimos cuadrados con
  las cargas); P&L = Σ Δ_f·f + ½f'Γf + residuo, donde el residuo incluye lo que los
  factores no explican de la curva y los términos de orden superior.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin
from tsinsurance.sensitivities.instruments import BondPortfolio, FixedBond
from tsinsurance.sensitivities.measures import measures, node_hessian
from tsinsurance.simulation.factors import FactorModel
from tsinsurance.simulation.scenarios import Scenarios
from tsinsurance.stochastics.curves import NodeCurve

__all__ = [
    "ApproxReport",
    "FactorGreeks",
    "PnLAttribution",
    "approximate",
    "attribute_pnl",
    "factor_greeks",
    "full_revaluation",
]

Instrument = FixedBond | BondPortfolio


def _check(model: FactorModel, curve: NodeCurve) -> None:
    if not np.allclose(model.tenors, curve.tenors):
        raise DataValidationError("Los nodos del modelo de factores y de la curva no coinciden.")


def full_revaluation(
    instrument: Instrument, curve: NodeCurve, node_changes: np.ndarray
) -> np.ndarray:
    """ΔPV exacto para cada fila de cambios de los nodos (decimales)."""
    base = instrument.pv(curve)
    return np.array([instrument.pv(curve.shifted(dz)) - base for dz in np.atleast_2d(node_changes)])


@dataclass(frozen=True, slots=True)
class FactorGreeks(ResultMixin):
    """Δ (por pb de factor) y Γ (por pb²) de un instrumento."""

    labels: tuple[str, ...]
    delta: np.ndarray = field(repr=False)
    gamma: np.ndarray = field(repr=False)
    step_bp: float = 1.0

    def summary(self) -> str:
        """Resumen legible."""
        d = ", ".join(f"{lab}: {v:+.4f}" for lab, v in zip(self.labels, self.delta, strict=True))
        return f"Δ por factor (por pb): {d}; Γ diagonal: {np.diag(self.gamma).round(6).tolist()}"


def factor_greeks(
    instrument: Instrument, curve: NodeCurve, model: FactorModel, step_bp: float = 1.0
) -> FactorGreeks:
    """Δ y Γ por factor con diferencias finitas centrales (Γ cruzado de 4 puntos)."""
    _check(model, curve)
    k = model.loadings.shape[1]
    h = step_bp

    def pv(f: np.ndarray) -> float:
        return instrument.pv(curve.shifted(model.reconstruct(f)[0]))

    base = pv(np.zeros(k))
    delta = np.zeros(k)
    gamma = np.zeros((k, k))
    for i in range(k):
        e = np.zeros(k)
        e[i] = h
        up, dn = pv(e), pv(-e)
        delta[i] = (up - dn) / (2 * h)
        gamma[i, i] = (up - 2 * base + dn) / h**2
        for j in range(i + 1, k):
            ej = np.zeros(k)
            ej[j] = h
            val = (pv(e + ej) - pv(e - ej) - pv(-e + ej) + pv(-e - ej)) / (4 * h * h)
            gamma[i, j] = gamma[j, i] = val
    return FactorGreeks(tuple(model.labels), delta, gamma, step_bp)


@dataclass(frozen=True, slots=True)
class ApproxReport(ResultMixin):
    """ΔPV por escenario: revaluación completa, Δ y ΔΓ, con sus errores."""

    full: np.ndarray = field(repr=False)
    delta: np.ndarray = field(repr=False)
    delta_gamma: np.ndarray = field(repr=False)
    errors: dict[str, dict[str, float]] = field(default_factory=dict)

    def summary(self) -> str:
        """Resumen legible."""
        lines = ["Aproximaciones frente a la revaluación completa:"]
        for k, v in self.errors.items():
            lines.append(
                f"  {k}: error absoluto medio {v['mae']:.4f}, máximo {v['max']:.4f}, "
                f"relativo a |ΔPV| medio {v['relative']:.2%}"
            )
        return "\n".join(lines)


def approximate(
    instrument: Instrument, curve: NodeCurve, scenarios: Scenarios | np.ndarray
) -> ApproxReport:
    """Δ y ΔΓ por nodos frente a la revaluación completa en cada escenario."""
    dz = np.atleast_2d(scenarios.values if isinstance(scenarios, Scenarios) else scenarios)
    if isinstance(scenarios, Scenarios) and not np.allclose(scenarios.tenors, curve.tenors):
        raise DataValidationError("Los nodos de los escenarios y de la curva no coinciden.")
    s = measures(instrument, curve)
    g = -np.array(list(s.dollar_krd.values()))  # ∂PV/∂z_i
    hess = node_hessian(instrument, curve)
    full = full_revaluation(instrument, curve, dz)
    d1 = dz @ g
    d2 = d1 + 0.5 * np.einsum("ni,ij,nj->n", dz, hess, dz)
    scale = float(np.mean(np.abs(full))) or 1.0
    errors = {}
    for name, approx in (("delta", d1), ("delta_gamma", d2)):
        err = np.abs(approx - full)
        errors[name] = {
            "mae": float(err.mean()),
            "max": float(err.max()),
            "relative": float(err.mean() / scale),
        }
    return ApproxReport(full, d1, d2, errors)


@dataclass(frozen=True, slots=True)
class PnLAttribution(ResultMixin):
    """P&L = Σ Δ_f·f + ½f'Γf + residuo."""

    total: float
    by_factor: dict[str, float]
    quadratic: float
    residual: float
    factor_moves_bp: dict[str, float]

    def summary(self) -> str:
        """Resumen legible."""
        parts = ", ".join(f"{k}: {v:+.4f}" for k, v in self.by_factor.items())
        return (
            f"P&L {self.total:+.4f} = {parts} · cuadrático {self.quadratic:+.4f} · residuo "
            f"{self.residual:+.4f}"
        )


def attribute_pnl(
    instrument: Instrument,
    curve: NodeCurve,
    model: FactorModel,
    node_change: np.ndarray,
    greeks: FactorGreeks | None = None,
) -> PnLAttribution:
    """Atribuye el ΔPV de un cambio de los nodos (decimales) a los factores."""
    _check(model, curve)
    gk = greeks or factor_greeks(instrument, curve, model)
    dz_bp = np.asarray(node_change, dtype=float) * 1e4
    f, *_ = np.linalg.lstsq(model.loadings, dz_bp, rcond=None)
    total = float(full_revaluation(instrument, curve, node_change)[0])
    by = gk.delta * f
    quad = float(0.5 * f @ gk.gamma @ f)
    return PnLAttribution(
        total=total,
        by_factor=dict(zip(gk.labels, by.tolist(), strict=True)),
        quadratic=quad,
        residual=total - float(by.sum()) - quad,
        factor_moves_bp=dict(zip(gk.labels, f.tolist(), strict=True)),
    )
