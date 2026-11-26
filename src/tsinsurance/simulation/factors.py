"""Factores de la curva para simular y medir riesgo (spec 007, US4; frontera estricta).

- **PCA sobre cambios** (no niveles) de las tasas de los nodos, en puntos básicos, con la
  covarianza de la ventana. Los componentes se rotulan por su patrón de signos (nivel:
  un signo; pendiente: un cambio de signo; curvatura: dos) y se normalizan para que el
  nivel sea positivo, la pendiente suba con el plazo y la curvatura sea positiva al
  medio.
- **Diebold-Li con λ fija** (0,0609 con plazos en meses; Diebold y Li 2006): MCO de cada
  fecha sobre las cargas de Nelson-Siegel. λ **no** se optimiza (eso es ajuste de curva,
  del paquete hermano). Con 4 nodos y 3 factores queda 1 grado de libertad: se reporta el
  residuo por nodo y se advierte.

References
----------
Litterman, R. y Scheinkman, J. (1991). Common factors affecting bond returns. *Journal of
Fixed Income*, 1(1), 54-61.
Diebold, F. y Li, C. (2006). Forecasting the term structure of government bond yields.
*Journal of Econometrics*, 130(2), 337-364.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin

__all__ = ["DIEBOLD_LI_LAMBDA", "FactorModel", "fit_factors", "nelson_siegel_loadings"]

DIEBOLD_LI_LAMBDA = 0.0609  # plazos en meses


def nelson_siegel_loadings(tenors_years: np.ndarray, lam: float = DIEBOLD_LI_LAMBDA) -> np.ndarray:
    """Cargas de Nelson-Siegel (nivel, pendiente, curvatura) con λ en meses⁻¹."""
    tau = np.asarray(tenors_years, dtype=float) * 12.0
    x = lam * tau
    slope = (1 - np.exp(-x)) / x
    return np.column_stack([np.ones_like(tau), slope, slope - np.exp(-x)])


def _label(v: np.ndarray) -> str:
    signs = np.sign(v[np.abs(v) > 0.05 * np.abs(v).max()])
    changes = int(np.sum(signs[1:] != signs[:-1]))
    return {0: "nivel", 1: "pendiente", 2: "curvatura"}.get(changes, f"componente ({changes})")


@dataclass(frozen=True, slots=True)
class FactorModel(ResultMixin):
    """Factores de cambios de la curva: cargas (nodos × k) y series de factores."""

    method: Literal["pca", "diebold_li"]
    tenors: tuple[float, ...]
    loadings: np.ndarray = field(repr=False)
    factors: pd.DataFrame = field(repr=False)
    labels: tuple[str, ...]
    explained: tuple[float, ...]
    cov: np.ndarray = field(repr=False)
    residual_sd_bp: dict[str, float]
    window: tuple[str, str]
    units: str = "puntos básicos"
    warnings: list[str] = field(default_factory=list)

    def reconstruct(self, shocks: np.ndarray) -> np.ndarray:
        """Cambios de los nodos (decimales) para choques de factor (n × k, en pb)."""
        return np.asarray(np.atleast_2d(shocks) @ self.loadings.T / 1e4, dtype=float)

    def summary(self) -> str:
        """Resumen legible."""
        lines = [
            f"Factores ({self.method}) de cambios de la curva, {self.window[0]} a {self.window[1]}"
        ]
        for j, lab in enumerate(self.labels):
            load = ", ".join(f"{v:+.2f}" for v in self.loadings[:, j])
            lines.append(f"  {lab}: cargas [{load}] · varianza explicada {self.explained[j]:.1%}")
        lines += [f"  Advertencia: {w}" for w in self.warnings]
        return "\n".join(lines)


def fit_factors(
    node_changes: pd.DataFrame,
    method: Literal["pca", "diebold_li"] = "pca",
    k: int = 3,
    *,
    tenors: list[float] | None = None,
    lam: float = DIEBOLD_LI_LAMBDA,
) -> FactorModel:
    """Factores de los cambios de tasas de los nodos (decimales; columnas = nodos).

    ``tenors``: plazos en años de las columnas (por defecto, las columnas convertidas a
    número).
    """
    df = node_changes.dropna()
    if len(df) < 30:
        raise DataValidationError("Se requieren al menos 30 cambios sin faltantes.")
    tt = np.asarray(tenors if tenors is not None else [float(c) for c in df.columns])
    if tt.size != df.shape[1] or np.any(np.diff(tt) <= 0):
        raise DataValidationError("Los plazos deben coincidir con las columnas y ser crecientes.")
    x = df.to_numpy() * 1e4  # pb
    warnings: list[str] = []
    window = (str(df.index[0])[:10], str(df.index[-1])[:10])
    if method == "pca":
        if k > df.shape[1]:
            raise DataValidationError("k no puede superar el número de nodos.")
        cov = np.cov(x, rowvar=False)
        vals, vecs = np.linalg.eigh(cov)
        order = np.argsort(vals)[::-1][:k]
        vals, vecs = vals[order], vecs[:, order]
        for j in range(k):  # normalización de signos
            v = vecs[:, j]
            lab = _label(v)
            if (
                (lab == "nivel" and v.sum() < 0)
                or (lab == "pendiente" and v[-1] - v[0] < 0)
                or (lab == "curvatura" and v[len(v) // 2] < 0)
            ):
                vecs[:, j] = -v
        load = vecs
        centered = x - x.mean(axis=0)
        f = centered @ load
        explained = tuple(float(v) for v in vals / np.trace(cov))
        labels = tuple(_label(load[:, j]) for j in range(k))
        resid = centered - f @ load.T
    else:
        load = nelson_siegel_loadings(tt, lam)[:, :k]
        dof = tt.size - k
        if dof <= 1:
            warnings.append(
                f"Diebold-Li con {tt.size} nodos y {k} factores: {dof} grado(s) de libertad; "
                "el ajuste por fecha es casi exacto y el residuo por nodo es poco informativo."
            )
        coef, *_ = np.linalg.lstsq(load, x.T, rcond=None)
        f = coef.T
        resid = x - f @ load.T
        total = float(np.var(x, axis=0).sum())
        explained = tuple(
            float(np.var(np.outer(f[:, j], load[:, j]), axis=0).sum() / total) for j in range(k)
        )
        labels = ("nivel", "pendiente", "curvatura")[:k]
        fitted = f @ load.T
        r2 = 1 - float(np.var(x - fitted, axis=0).sum()) / total
        warnings.append(
            f"Las cargas de Nelson-Siegel no son ortogonales: las varianzas por factor no son "
            f"aditivas (su suma puede superar 100 %). R² conjunto = {r2:.1%}."
        )
        warnings.append(
            f"λ fija = {lam} (meses⁻¹): no se optimiza (frontera con el paquete de curvas)."
        )
    factors = pd.DataFrame(f, index=df.index, columns=list(labels))
    return FactorModel(
        method=method,
        tenors=tuple(float(v) for v in tt),
        loadings=load,
        factors=factors,
        labels=labels,
        explained=explained,
        cov=np.cov(f, rowvar=False).reshape(k, k),
        residual_sd_bp={
            str(c): float(s) for c, s in zip(df.columns, resid.std(axis=0), strict=True)
        },
        window=window,
        warnings=warnings,
    )
