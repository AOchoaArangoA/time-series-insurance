"""Reducción de varianza en Monte Carlo (spec 007, US4; revisión B1).

- **Antitéticas**: pares Z y −Z. Sólo en motores gaussianos o t simétricos; en CIR no se
  ofrecen (la transición no es simétrica).
- **Variable de control**: con un control Y de media conocida E[Y], el estimador
  θ̂_cv = mean(X − β(Y − E[Y])) con β = cov(X, Y)/var(Y) estimada en una **muestra piloto
  independiente** (así β no correlaciona con la muestra principal y no hay sesgo).
- En Vasicek, (r_T, ∫₀ᵀ r) es conjuntamente gaussiano: se simula **exactamente** y el
  factor de descuento exp(−∫r) usa como control Y = ∫r, con
  E[Y] = θT + (r₀ − θ)(1 − e^{−κT})/κ. (Un precio cerrado es una constante y no sirve de
  control.)

El factor de reducción es var(MC simple)/var(MC reducido) con igual número de
evaluaciones.

References
----------
Glasserman, P. (2003). *Monte Carlo Methods in Financial Engineering*, cap. 4.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin
from tsinsurance.stochastics.affine import ou_joint_moments

__all__ = ["VRResult", "control_variate", "simulate_rate_integral", "vasicek_discount_mc"]


@dataclass(frozen=True, slots=True)
class VRResult(ResultMixin):
    """Estimación de Monte Carlo con su error y el factor de reducción de varianza."""

    estimate: float
    se: float
    plain_estimate: float
    plain_se: float
    reduction_factor: float
    beta: float | None
    n: int
    method: str

    def summary(self) -> str:
        """Resumen legible."""
        return (
            f"{self.method}: {self.estimate:.6f} (ee {self.se:.2e}) frente a MC simple "
            f"{self.plain_estimate:.6f} (ee {self.plain_se:.2e}); reducción de varianza "
            f"{self.reduction_factor:.1f}× con n = {self.n}"
        )


def control_variate(
    estimand: np.ndarray,
    control: np.ndarray,
    control_mean: float,
    pilot: tuple[np.ndarray, np.ndarray],
) -> VRResult:
    """Variable de control con β de una muestra piloto independiente ``(X_p, Y_p)``."""
    x = np.asarray(estimand, dtype=float)
    y = np.asarray(control, dtype=float)
    xp, yp = (np.asarray(v, dtype=float) for v in pilot)
    if x.shape != y.shape or xp.shape != yp.shape or xp.size < 10:
        raise DataValidationError("Muestras incompatibles o piloto demasiado pequeño (< 10).")
    vy = float(np.var(yp, ddof=1))
    beta = float(np.cov(xp, yp, ddof=1)[0, 1] / vy) if vy > 0 else 0.0
    adj = x - beta * (y - control_mean)
    n = x.size
    plain_se = float(x.std(ddof=1) / math.sqrt(n))
    se = float(adj.std(ddof=1) / math.sqrt(n))
    return VRResult(
        estimate=float(adj.mean()),
        se=se,
        plain_estimate=float(x.mean()),
        plain_se=plain_se,
        reduction_factor=float((plain_se / se) ** 2) if se > 0 else float("inf"),
        beta=beta,
        n=n,
        method="variable de control (β piloto)",
    )


def simulate_rate_integral(
    r0: float,
    kappa: float,
    theta: float,
    sigma: float,
    horizon: float,
    n: int,
    rng: np.random.Generator | int | None = None,
    *,
    antithetic: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """(r_T, ∫₀ᵀ r dt) exactos de Vasicek (conjuntamente gaussianos)."""
    gen = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
    mean, cov = ou_joint_moments(r0 - theta, kappa, sigma, horizon)
    chol = np.linalg.cholesky(cov)
    if antithetic:
        z = gen.standard_normal(((n + 1) // 2, 2))
        z = np.vstack([z, -z])[:n]
    else:
        z = gen.standard_normal((n, 2))
    draws = mean + z @ chol.T
    return theta + draws[:, 0], theta * horizon + draws[:, 1]


def vasicek_discount_mc(
    r0: float,
    kappa: float,
    theta: float,
    sigma: float,
    horizon: float,
    n: int,
    rng: np.random.Generator | int | None = None,
    *,
    method: str = "control",
    pilot: int = 2000,
) -> VRResult:
    """P(0, T) de Vasicek por Monte Carlo exacto: ``plain``, ``antithetic`` o ``control``."""
    gen = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
    _, y = simulate_rate_integral(r0, kappa, theta, sigma, horizon, n, gen)
    x = np.exp(-y)
    plain_se = float(x.std(ddof=1) / math.sqrt(n))
    if method == "plain":
        return VRResult(
            float(x.mean()), plain_se, float(x.mean()), plain_se, 1.0, None, n, "MC simple"
        )
    if method == "antithetic":
        _, ya = simulate_rate_integral(r0, kappa, theta, sigma, horizon, n, gen, antithetic=True)
        xa = np.exp(-ya)
        half = n // 2
        pairs = 0.5 * (xa[:half] + xa[half : 2 * half])
        se = float(pairs.std(ddof=1) / math.sqrt(half))
        return VRResult(
            float(pairs.mean()),
            se,
            float(x.mean()),
            plain_se,
            float((plain_se / se) ** 2) if se > 0 else float("inf"),
            None,
            n,
            "antitéticas",
        )
    if method != "control":
        raise DataValidationError("method debe ser plain, antithetic o control.")
    ey = theta * horizon + (r0 - theta) * (1 - math.exp(-kappa * horizon)) / kappa
    _, yp = simulate_rate_integral(r0, kappa, theta, sigma, horizon, pilot, gen)
    return control_variate(x, y, ey, (np.exp(-yp), yp))
