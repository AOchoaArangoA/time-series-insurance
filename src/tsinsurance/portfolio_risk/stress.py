"""Estrés y cobertura (spec 007, US6; revisión M5).

- **Estrés**: choques en puntos básicos sobre los nodos (paralelo, empinamiento y
  aplanamiento con un pivote declarado, curvatura) o en desviaciones estándar de los
  factores; revaluación completa. **Condicionado a régimen**: los cambios observados en
  los días cuya probabilidad **filtrada** (punto en el tiempo, re-estimada *walk-forward*)
  del régimen supera un umbral (0,8 por defecto).
- **Inmunización / cobertura**: mínimos cuadrados con cotas (``scipy.optimize.lsq_linear``)
  sobre la matriz de exposiciones (KRD en dólares) de los instrumentos de cobertura. Si las
  restricciones son factibles se exige exposición residual ≈ 0 (1e-8); si no, se reporta
  la exposición residual mínima.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import optimize

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin
from tsinsurance.sensitivities.approx import full_revaluation
from tsinsurance.sensitivities.instruments import BondPortfolio, FixedBond
from tsinsurance.sensitivities.measures import measures
from tsinsurance.simulation.factors import FactorModel
from tsinsurance.simulation.scenarios import Scenarios
from tsinsurance.stochastics.curves import NodeCurve

__all__ = [
    "HedgeResult",
    "StressReport",
    "immunize",
    "regime_conditional_scenarios",
    "standard_shocks",
    "stress",
]

Instrument = FixedBond | BondPortfolio


def standard_shocks(
    tenors: Sequence[float], *, size_bp: float = 100.0, pivot: float = 5.0
) -> dict[str, np.ndarray]:
    """Choques estándar en decimales: paralelo ±, empinamiento, aplanamiento y curvatura."""
    t = np.asarray(tenors, dtype=float)
    span = max(t.max() - t.min(), 1e-12)
    tilt = (t - pivot) / span  # 0 en el pivote
    hump = 1 - np.abs(2 * (t - t.min()) / span - 1)  # 1 al medio, 0 en los extremos
    s = size_bp * 1e-4
    return {
        "paralelo +": np.full(t.size, s),
        "paralelo −": np.full(t.size, -s),
        "empinamiento": s * tilt,
        "aplanamiento": -s * tilt,
        "curvatura +": s * hump,
    }


@dataclass(frozen=True, slots=True)
class StressReport(ResultMixin):
    """ΔPV por escenario de estrés (revaluación completa)."""

    pv: float
    results: dict[str, float]
    shocks_bp: dict[str, list[float]]
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Resumen legible."""
        lines = [f"Estrés (PV base {self.pv:,.4f})"]
        lines += [f"  {k}: ΔPV {v:+,.4f}" for k, v in self.results.items()]
        lines += [f"  Nota: {n}" for n in self.notes]
        return "\n".join(lines)


def stress(
    instrument: Instrument,
    curve: NodeCurve,
    shocks: Mapping[str, np.ndarray] | None = None,
    *,
    factor_model: FactorModel | None = None,
    factor_sd: float = 3.0,
) -> StressReport:
    """Revaluación completa ante choques de nodos y, opcionalmente, de ±k σ de cada factor."""
    all_shocks = dict(shocks or standard_shocks(curve.tenors))
    notes = []
    if factor_model is not None:
        sd = np.sqrt(np.diag(factor_model.cov))
        for j, lab in enumerate(factor_model.labels):
            e = np.zeros(sd.size)
            e[j] = factor_sd * sd[j]
            all_shocks[f"{lab} +{factor_sd:g}σ"] = factor_model.reconstruct(e)[0]
            all_shocks[f"{lab} −{factor_sd:g}σ"] = factor_model.reconstruct(-e)[0]
        notes.append(f"σ de los factores de la ventana {factor_model.window} (cambios diarios).")
    names = list(all_shocks)
    mat = np.vstack([np.asarray(all_shocks[n], dtype=float) for n in names])
    dpv = full_revaluation(instrument, curve, mat)
    return StressReport(
        pv=instrument.pv(curve),
        results=dict(zip(names, dpv.tolist(), strict=True)),
        shocks_bp={n: (mat[i] * 1e4).round(4).tolist() for i, n in enumerate(names)},
        notes=notes,
    )


def regime_conditional_scenarios(
    node_changes: pd.DataFrame,
    filtered_prob: pd.Series,
    *,
    threshold: float = 0.8,
    tenors: Sequence[float] | None = None,
) -> Scenarios:
    """Cambios observados en los días con probabilidad filtrada del régimen > umbral.

    ``filtered_prob`` debe ser punto en el tiempo (filtro con parámetros estimados hasta
    cada fecha, p. ej. re-estimación mensual): las probabilidades suavizadas o
    pseudo-filtradas introducen información futura.
    """
    prob = filtered_prob.reindex(node_changes.index)
    sel = node_changes[prob > threshold].dropna()
    if len(sel) < 30:
        raise DataValidationError(f"Sólo {len(sel)} días con probabilidad > {threshold}.")
    return Scenarios(
        values=sel.to_numpy(),
        tenors=tuple(float(t) for t in (tenors if tenors is not None else node_changes.columns)),
        method=f"condicionada a régimen (P filtrada > {threshold})",
        state_measure="historical",
        pricing_measure="revaluación completa con la curva desplazada",
        horizon_days=1,
        seed=None,
        window=(str(sel.index[0])[:10], str(sel.index[-1])[:10]),
        mapping="cambios observados en los días del régimen",
        notes=[
            "Requiere probabilidades filtradas punto en el tiempo (re-estimación walk-forward)."
        ],
    )


@dataclass(frozen=True, slots=True)
class HedgeResult(ResultMixin):
    """Cantidades de cobertura y exposición residual (KRD en dólares)."""

    quantities: list[float]
    residual_exposure: dict[str, float]
    feasible: bool
    target: dict[str, float]

    def summary(self) -> str:
        """Resumen legible."""
        res = ", ".join(f"{k}: {v:+.3e}" for k, v in self.residual_exposure.items())
        return (
            f"Cobertura {'factible' if self.feasible else 'NO factible (residual mínimo)'}: "
            f"cantidades {np.round(self.quantities, 6).tolist()}; exposición residual {res}"
        )


def immunize(
    portfolio: Instrument,
    hedges: Sequence[FixedBond],
    curve: NodeCurve,
    *,
    target: Mapping[str, float] | None = None,
    bounds: tuple[float, float] | Sequence[tuple[float, float]] = (-np.inf, np.inf),
    tol: float = 1e-8,
) -> HedgeResult:
    """Cantidades que llevan la KRD en dólares de cartera + coberturas al objetivo (0)."""
    base = measures(portfolio, curve).dollar_krd
    names = list(base)
    goal = np.array([float((target or {}).get(k, 0.0)) for k in names])
    a = np.column_stack([np.array(list(measures(h, curve).dollar_krd.values())) for h in hedges])
    b = goal - np.array([base[k] for k in names])
    if isinstance(bounds, tuple) and len(bounds) == 2 and np.isscalar(bounds[0]):
        lb = np.full(len(hedges), float(bounds[0]))
        ub = np.full(len(hedges), float(bounds[1]))
    else:
        lb = np.array([float(x[0]) for x in bounds])
        ub = np.array([float(x[1]) for x in bounds])
    sol = optimize.lsq_linear(a, b, bounds=(lb, ub), lsmr_tol="auto")
    resid = a @ sol.x - b
    scale = max(float(np.abs(b).max()), 1.0)
    return HedgeResult(
        quantities=sol.x.tolist(),
        residual_exposure=dict(zip(names, resid.tolist(), strict=True)),
        feasible=bool(np.abs(resid).max() <= tol * scale),
        target=dict(zip(names, goal.tolist(), strict=True)),
    )
