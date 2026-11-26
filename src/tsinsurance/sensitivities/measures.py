"""Sensibilidades de tasa: PV, DV01, KRD, duración y convexidad (spec 007, US5; revisión I4).

Con una :class:`~tsinsurance.stochastics.NodeCurve` (lineal en ceros continuos) la tasa
cero en t es z(t) = Σ_i w_i(t)·z_i, con funciones triangulares w_i que suman 1 (planas en
los extremos). Entonces, para flujos c_k en t_k:

- **KRD analítica** (Ho 1992): KRD_i = Σ_k c_k·t_k·w_i(t_k)·e^{−z(t_k)t_k} / PV;
- **duración efectiva (Fisher-Weil)**: D = Σ_k c_k·t_k·e^{−z_k t_k} / PV = Σ_i KRD_i
  (choque paralelo de los ceros continuos; no es la duración modificada en rendimiento);
- **convexidad (Fisher-Weil)**: C = Σ_k c_k·t_k²·e^{−z_k t_k} / PV;
- **hessiana por nodos**: ∂²PV/∂z_i∂z_j = Σ_k c_k·t_k²·w_i w_j·e^{−z_k t_k};
- **DV01** = PV·D·1 pb (choque paralelo de 1 pb).

Las diferencias finitas centrales con 1 pb se usan sólo para verificar (mismo esquema en
ambos lados de la comparación).

References
----------
Ho, T. (1992). Key rate durations: measures of interest rate risks. *Journal of Fixed
Income*, 2(2), 29-44.
Fisher, L. y Weil, R. (1971). Coping with the risk of interest-rate fluctuations.
*Journal of Business*, 44(4), 408-431.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin
from tsinsurance.sensitivities.instruments import BondPortfolio, FixedBond
from tsinsurance.stochastics.curves import NodeCurve

__all__ = ["Sensitivities", "hat_weights", "measures", "node_hessian"]

BP = 1e-4


def hat_weights(tenors: tuple[float, ...] | np.ndarray, t: np.ndarray) -> np.ndarray:
    """Pesos w_i(t) de la interpolación lineal (len(t) × nodos); planos fuera de rango."""
    nodes = np.asarray(tenors, dtype=float)
    eye = np.eye(nodes.size)
    return np.column_stack([np.interp(t, nodes, eye[i]) for i in range(nodes.size)])


def _flows(instrument: FixedBond | BondPortfolio) -> tuple[np.ndarray, np.ndarray]:
    return instrument.cashflows()


@dataclass(frozen=True, slots=True)
class Sensitivities(ResultMixin):
    """Medidas de riesgo de tasa de un instrumento o cartera."""

    pv: float
    dv01: float
    krd: dict[str, float]
    duration_eff: float
    convexity: float
    dollar_krd: dict[str, float] = field(default_factory=dict)
    note: str = "Choques sobre ceros continuos de la NodeCurve; KRD triangulares (Ho 1992)."

    def summary(self) -> str:
        """Resumen legible."""
        krd = ", ".join(f"{k}: {v:.3f}" for k, v in self.krd.items())
        return (
            f"PV {self.pv:,.4f} · DV01 {self.dv01:,.4f} · duración efectiva (Fisher-Weil) "
            f"{self.duration_eff:.4f} · convexidad {self.convexity:.3f}\n  KRD: {krd}"
        )


def measures(instrument: FixedBond | BondPortfolio, curve: NodeCurve) -> Sensitivities:
    """PV, DV01, KRD analíticas, duración efectiva y convexidad."""
    t, c = _flows(instrument)
    if t.size == 0:
        raise DataValidationError("Instrumento sin flujos.")
    disc = curve.discount(t)
    pv = float(c @ disc)
    if pv == 0:
        raise DataValidationError("PV = 0: las medidas relativas no están definidas.")
    w = hat_weights(curve.tenors, t)
    dollar = (c * t * disc) @ w  # −∂PV/∂z_i
    krd = dollar / pv
    dur = float((c * t * disc).sum() / pv)
    conv = float((c * t**2 * disc).sum() / pv)
    names = [f"{x:g}" for x in curve.tenors]
    return Sensitivities(
        pv=pv,
        dv01=pv * dur * BP,
        krd=dict(zip(names, krd.tolist(), strict=True)),
        duration_eff=dur,
        convexity=conv,
        dollar_krd=dict(zip(names, dollar.tolist(), strict=True)),
    )


def node_hessian(instrument: FixedBond | BondPortfolio, curve: NodeCurve) -> np.ndarray:
    """∂²PV/∂z_i∂z_j analítica (nodos × nodos)."""
    t, c = _flows(instrument)
    w = hat_weights(curve.tenors, t)
    weight = c * t**2 * curve.discount(t)
    return np.asarray((w * weight[:, None]).T @ w, dtype=float)
