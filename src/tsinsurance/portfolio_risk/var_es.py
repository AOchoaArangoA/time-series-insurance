"""VaR y ES empíricos con intervalos de confianza (spec 007, US6; revisión I5).

Las pérdidas son positivas (L = −ΔPV). VaR_α es el cuantil α de L (interpolación lineal,
``numpy.quantile`` con ``method="linear"``) y ES_α es la media de las pérdidas ≥ VaR_α.

- **IC por bootstrap** iid de los escenarios (escenarios históricos no solapados o Monte
  Carlo); con escenarios de Monte Carlo el IC mide **sólo el error de simulación**, no la
  incertidumbre de los parámetros (se declara).
- **IC por bloques** (bootstrap por bloques móviles) para cambios solapados a h días.

References
----------
Acerbi, C. y Tasche, D. (2002). On the coherence of expected shortfall. *Journal of
Banking & Finance*, 26(7), 1487-1503.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin

__all__ = ["RiskMeasure", "expected_shortfall", "value_at_risk", "var_es"]


def value_at_risk(losses: np.ndarray, level: float) -> float:
    """Cuantil ``level`` de las pérdidas (interpolación lineal)."""
    return float(np.quantile(np.asarray(losses, dtype=float), level))


def expected_shortfall(losses: np.ndarray, level: float) -> float:
    """Media de las pérdidas en o por encima del VaR."""
    x = np.asarray(losses, dtype=float)
    v = value_at_risk(x, level)
    return float(x[x >= v].mean())


@dataclass(frozen=True, slots=True)
class RiskMeasure(ResultMixin):
    """VaR y ES por nivel, con IC al 95 %."""

    var: dict[str, float]
    es: dict[str, float]
    var_ci: dict[str, tuple[float, float]]
    es_ci: dict[str, tuple[float, float]]
    n: int
    ci_method: str
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Resumen legible."""
        lines = [f"VaR y ES ({self.n} escenarios; IC {self.ci_method})"]
        for k in self.var:
            lo, hi = self.var_ci[k]
            elo, ehi = self.es_ci[k]
            lines.append(
                f"  {k}: VaR {self.var[k]:,.4f} [{lo:,.4f}; {hi:,.4f}] · ES {self.es[k]:,.4f} "
                f"[{elo:,.4f}; {ehi:,.4f}]"
            )
        lines += [f"  Nota: {n}" for n in self.notes]
        return "\n".join(lines)


def var_es(
    losses: np.ndarray,
    levels: Sequence[float] = (0.99, 0.975),
    *,
    ci: Literal["bootstrap", "block"] = "bootstrap",
    reps: int = 999,
    block: int | None = None,
    seed: int = 0,
    monte_carlo: bool = False,
) -> RiskMeasure:
    """VaR y ES con IC por bootstrap iid o por bloques móviles."""
    x = np.asarray(losses, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 50:
        raise DataValidationError("Se requieren al menos 50 escenarios de pérdidas.")
    rng = np.random.default_rng(seed)
    if ci == "bootstrap":
        idx = rng.integers(0, x.size, size=(reps, x.size))
        boots = x[idx]
    else:
        b = block or max(1, int(round(x.size ** (1 / 3))))
        n_blocks = int(np.ceil(x.size / b))
        starts = rng.integers(0, x.size - b + 1, size=(reps, n_blocks))
        idx = (starts[:, :, None] + np.arange(b)[None, None, :]).reshape(reps, -1)[:, : x.size]
        boots = x[idx]
    var, es, var_ci, es_ci = {}, {}, {}, {}
    for lev in levels:
        key = f"{lev:.3g}"
        var[key] = value_at_risk(x, lev)
        es[key] = expected_shortfall(x, lev)
        bv = np.quantile(boots, lev, axis=1)
        be = np.array([row[row >= v].mean() for row, v in zip(boots, bv, strict=True)])
        var_ci[key] = (float(np.quantile(bv, 0.025)), float(np.quantile(bv, 0.975)))
        es_ci[key] = (float(np.quantile(be, 0.025)), float(np.quantile(be, 0.975)))
    notes = []
    if monte_carlo:
        notes.append("Escenarios de Monte Carlo: el IC mide sólo el error de simulación.")
    if ci == "block":
        notes.append("Bootstrap por bloques móviles (cambios solapados).")
    return RiskMeasure(var, es, var_ci, es_ci, int(x.size), ci, notes)
