"""Valoración afín bajo ℚ: Vasicek, CIR y Hull-White (spec 007, US3).

P(t, T) = A(τ)·exp(−B(τ)·r_t), τ = T − t.

- **Vasicek**: B = (1 − e^{−aτ})/a; ln A = (θ − σ²/(2a²))(B − τ) − σ²B²/(4a).
- **CIR**: γ = √(a² + 2σ²); B = 2(e^{γτ} − 1)/[(γ + a)(e^{γτ} − 1) + 2γ];
  A = [2γ·e^{(a+γ)τ/2} / ((γ + a)(e^{γτ} − 1) + 2γ)]^{2aθ/σ²}.
- **Hull-White** (Brigo y Mercurio 2006, §3.3): r(t) = x(t) + α(t), con
  dx = −a·x dt + σ dW, x(0) = 0 y α(t) = f^M(0, t) + σ²/(2a²)(1 − e^{−at})². No requiere
  ∂f/∂t. El modelo reproduce la curva inicial P^M(0, T).

**De ℙ a ℚ** (Girsanov con precio de mercado del riesgo λ constante; σ_ℚ = σ_ℙ):

- Vasicek: κ_ℚ = κ_ℙ y θ_ℚ = θ_ℙ − λσ/κ;
- CIR: κ_ℚ = κ_ℙ + λσ y θ_ℚ = κ_ℙθ_ℙ/κ_ℚ.

:func:`calibrate_q` estima λ (o κ_ℚ y θ_ℚ libres, como diagnóstico) **valorando cada dato
según su convención**: rendimientos par semestrales (^FVX, ^TNX, ^TYX) con el bono par del
modelo y tasas de descuento (^IRX) con el precio de la letra. Los parámetros son comunes en
la ventana y r_t de cada fecha es la tasa corta observada.

References
----------
Brigo, D. y Mercurio, F. (2006). *Interest Rate Models — Theory and Practice*, 2.ª ed.,
Springer, cap. 3.
Vasicek (1977); Cox, Ingersoll y Ross (1985); Hull y White (1990).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import optimize

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin
from tsinsurance.stochastics.curves import Curve
from tsinsurance.stochastics.short_rate import ShortRateFit

__all__ = [
    "HullWhite",
    "QCalibration",
    "RateQuote",
    "calibrate_q",
    "ou_joint_moments",
    "q_params",
    "zero_coupon",
]

Model = Literal["vasicek", "cir"]


def _vasicek_ab(
    a: float, theta: float, sigma: float, tau: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    b = (1 - np.exp(-a * tau)) / a
    ln_a = (theta - sigma**2 / (2 * a**2)) * (b - tau) - sigma**2 * b**2 / (4 * a)
    return ln_a, b


def _cir_ab(a: float, theta: float, sigma: float, tau: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    g = math.sqrt(a**2 + 2 * sigma**2)
    eg = np.expm1(g * tau)
    den = (g + a) * eg + 2 * g
    b = 2 * eg / den
    ln_a = (2 * a * theta / sigma**2) * (np.log(2 * g) + (a + g) * tau / 2 - np.log(den))
    return ln_a, b


def zero_coupon(
    model: Model, params_q: Mapping[str, float], r_t: float | np.ndarray, tau: float | np.ndarray
) -> np.ndarray:
    """Precio cerrado del cupón cero bajo ℚ.

    ``params_q`` = {"kappa", "theta", "sigma"} bajo ℚ; ``r_t`` y ``tau`` admiten
    *broadcasting* (p. ej. r_t de cada escenario × plazos).
    """
    a, th, s = float(params_q["kappa"]), float(params_q["theta"]), float(params_q["sigma"])
    if a <= 0 or s <= 0:
        raise DataValidationError("κ_ℚ y σ deben ser positivos.")
    tt = np.asarray(tau, dtype=float)
    ln_a, b = _vasicek_ab(a, th, s, tt) if model == "vasicek" else _cir_ab(a, th, s, tt)
    return np.asarray(np.exp(ln_a - b * np.asarray(r_t, dtype=float)))


def q_params(model: Model, fit: ShortRateFit, lam: float) -> dict[str, float]:
    """Parámetros ℚ desde los de ℙ y el precio de mercado del riesgo λ (σ_ℚ = σ_ℙ)."""
    k, th, s = fit.kappa, fit.theta, fit.sigma
    if model == "vasicek":
        return {"kappa": k, "theta": th - lam * s / k, "sigma": s}
    kq = k + lam * s
    if kq <= 0:
        raise DataValidationError(f"κ_ℚ = κ + λσ = {kq:.4f} ≤ 0: λ fuera de rango.")
    return {"kappa": kq, "theta": k * th / kq, "sigma": s}


def ou_joint_moments(
    x0: float, a: float, sigma: float, horizon: float
) -> tuple[np.ndarray, np.ndarray]:
    """Media y covarianza exactas de (x_T, ∫₀ᵀ x dt) para dx = −a·x dt + σ dW.

    Con Vasicek, r = θ + x con x₀ = r₀ − θ, y ∫r = θT + ∫x.
    """
    e1 = math.exp(-a * horizon)
    e2 = math.exp(-2 * a * horizon)
    b = (1 - e1) / a
    mean = np.array([x0 * e1, x0 * b])
    var_x = sigma**2 * (1 - e2) / (2 * a)
    var_i = sigma**2 / a**2 * (horizon - 2 * b + (1 - e2) / (2 * a))
    cov = sigma**2 / (2 * a**2) * (1 - e1) ** 2
    return mean, np.array([[var_x, cov], [cov, var_i]])


@dataclass(frozen=True, slots=True)
class HullWhite(ResultMixin):
    """Hull-White de un factor ajustado a una curva inicial (interfaz :class:`Curve`)."""

    a: float
    sigma: float
    curve: Curve = field(repr=False)

    def alpha(self, t: float | np.ndarray) -> np.ndarray:
        """α(t) = f^M(0, t) + σ²/(2a²)(1 − e^{−at})²."""
        tt = np.asarray(t, dtype=float)
        return np.asarray(
            self.curve.forward(tt)
            + self.sigma**2 / (2 * self.a**2) * (1 - np.exp(-self.a * tt)) ** 2
        )

    def zero_coupon(
        self, t: float, maturity: float | np.ndarray, r_t: float | np.ndarray
    ) -> np.ndarray:
        """P(t, T) cerrado dado r_t (Brigo y Mercurio 2006, ec. 3.39)."""
        tm = np.asarray(maturity, dtype=float)
        b = (1 - np.exp(-self.a * (tm - t))) / self.a
        p0t = float(self.curve.discount(np.array([t]))[0]) if t > 0 else 1.0
        f0t = float(self.curve.forward(np.array([t]))[0])
        ln_a = (
            np.log(self.curve.discount(tm) / p0t)
            + b * f0t
            - self.sigma**2 / (4 * self.a) * (1 - math.exp(-2 * self.a * t)) * b**2
        )
        return np.asarray(np.exp(ln_a - b * np.asarray(r_t, dtype=float)))

    def simulate(
        self, times: np.ndarray, n_paths: int, rng: np.random.Generator | int | None = None
    ) -> np.ndarray:
        """Trayectorias exactas de r en la grilla ``times`` (años, creciente, con 0)."""
        gen = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
        grid = np.asarray(times, dtype=float)
        x = np.zeros((n_paths, grid.size))
        for k in range(1, grid.size):
            dt = grid[k] - grid[k - 1]
            e = math.exp(-self.a * dt)
            sd = self.sigma * math.sqrt((1 - e**2) / (2 * self.a))
            x[:, k] = x[:, k - 1] * e + sd * gen.standard_normal(n_paths)
        return np.asarray(x + self.alpha(grid)[None, :], dtype=float)

    def simulate_discount(
        self,
        maturity: float,
        n_paths: int,
        rng: np.random.Generator | int | None = None,
        *,
        antithetic: bool = False,
    ) -> np.ndarray:
        """Factores de descuento exp(−∫₀ᵀ r) exactos (simulación conjunta de ∫x).

        E[exp(−∫r)] = P^M(0, T): sirve para verificar el ajuste a la curva (SC-005).
        """
        gen = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
        _, cov = ou_joint_moments(0.0, self.a, self.sigma, maturity)
        sd = math.sqrt(cov[1, 1])
        z = gen.standard_normal((n_paths + 1) // 2 if antithetic else n_paths)
        if antithetic:
            z = np.concatenate([z, -z])[:n_paths]
        int_alpha = -math.log(float(self.curve.discount(np.array([maturity]))[0])) + 0.5 * cov[1, 1]
        return np.asarray(np.exp(-(int_alpha + sd * z)), dtype=float)

    def summary(self) -> str:
        """Resumen legible."""
        return f"Hull-White (a = {self.a:.4f}, σ = {self.sigma:.4f}) sobre la curva inicial dada."


@dataclass(frozen=True, slots=True)
class RateQuote:
    """Convención de un dato de mercado: plazo en años y tipo de tasa."""

    tenor: float
    rate_type: Literal["par", "discount", "zero"]
    freq: int = 2
    days: int = 91


def _model_quote(model: Model, pq: Mapping[str, float], r: np.ndarray, q: RateQuote) -> np.ndarray:
    if q.rate_type == "discount":
        p = zero_coupon(model, pq, r, q.days / 365.0)
        return (1 - p) * 360.0 / q.days
    if q.rate_type == "zero":
        return -np.log(zero_coupon(model, pq, r, q.tenor)) / q.tenor
    n = max(int(round(q.tenor * q.freq)), 1)
    times = q.tenor - np.arange(n)[::-1] / q.freq
    p = zero_coupon(model, pq, r[:, None], times[None, :])
    return np.asarray(q.freq * (1 - p[:, -1]) / p.sum(axis=1), dtype=float)


@dataclass(frozen=True, slots=True)
class QCalibration(ResultMixin):
    """Calibración ℚ con parámetros comunes en una ventana."""

    model: Model
    mode: Literal["lambda", "free"]
    params_q: dict[str, float]
    lam: float | None
    lam_se: float | None
    params_p: dict[str, float]
    rmse_bp: dict[str, float]
    n_dates: int
    window: tuple[str, str]
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Resumen legible."""
        lines = [
            f"Calibración ℚ ({self.model}, {self.mode}) con {self.n_dates} fechas "
            f"({self.window[0]} a {self.window[1]})",
            f"  ℚ: κ = {self.params_q['kappa']:.4f}, θ = {self.params_q['theta']:.4%}, "
            f"σ = {self.params_q['sigma']:.4f}",
        ]
        if self.lam is not None:
            lines.append(
                f"  λ (precio de mercado del riesgo) = {self.lam:+.4f} (ee {self.lam_se:.4f})"
            )
        lines.append(
            "  RMSE por dato (pb): " + ", ".join(f"{k}: {v:.1f}" for k, v in self.rmse_bp.items())
        )
        lines += [f"  Nota: {n}" for n in self.notes]
        return "\n".join(lines)


def calibrate_q(
    model: Model,
    quotes: pd.DataFrame,
    conventions: Mapping[str, RateQuote],
    r_short: pd.Series,
    fit_p: ShortRateFit,
    *,
    window: tuple[str, str] | None = None,
    mode: Literal["lambda", "free"] = "lambda",
) -> QCalibration:
    """Calibra la medida ℚ a los datos de mercado (decimales) en una ventana común.

    ``mode="lambda"``: un solo parámetro, el precio de mercado del riesgo λ, con
    σ_ℚ = σ_ℙ y la relación de Girsanov del modelo. ``mode="free"``: κ_ℚ y θ_ℚ libres
    (σ_ℚ = σ_ℙ), como diagnóstico de cuánto se aleja ℚ de la restricción.
    """
    cols = [c for c in quotes.columns if c in conventions]
    if not cols:
        raise DataValidationError("Ninguna columna de quotes tiene convención declarada.")
    data = quotes[cols].join(r_short.rename("__r"), how="inner").dropna()
    if window is not None:
        data = data.loc[window[0] : window[1]]
    if len(data) < 5:
        raise DataValidationError("Muy pocas fechas con todos los datos en la ventana.")
    r = data["__r"].to_numpy()
    obs = data[cols].to_numpy()
    sigma = fit_p.sigma
    notes = [
        "σ_ℚ = σ_ℙ por construcción (Girsanov).",
        "r_t de cada fecha = tasa corta observada (no se filtra).",
    ]

    def pq_from(theta_vec: np.ndarray) -> dict[str, float]:
        if mode == "lambda":
            return q_params(model, fit_p, float(theta_vec[0]))
        return {"kappa": float(theta_vec[0]), "theta": float(theta_vec[1]), "sigma": sigma}

    def resid(theta_vec: np.ndarray) -> np.ndarray:
        try:
            pq = pq_from(theta_vec)
        except DataValidationError:
            return np.full(obs.size, 1.0)
        model_vals = np.column_stack([_model_quote(model, pq, r, conventions[c]) for c in cols])
        return np.asarray((model_vals - obs).ravel(), dtype=float)

    if mode == "lambda":
        x0 = np.array([0.0])
        bounds: tuple[Any, Any] = (-np.inf, np.inf)
    else:
        x0 = np.array([fit_p.kappa, fit_p.theta])
        bounds = ([1e-4, -0.5], [50.0, 0.5])
    sol = optimize.least_squares(resid, x0, bounds=bounds, x_scale="jac")
    pq = pq_from(sol.x)
    res = sol.fun.reshape(obs.shape)
    rmse = {c: float(np.sqrt(np.mean(res[:, j] ** 2)) * 1e4) for j, c in enumerate(cols)}
    lam = lam_se = None
    if mode == "lambda":
        lam = float(sol.x[0])
        dof = max(res.size - 1, 1)
        s2 = float(sol.fun @ sol.fun) / dof
        jtj = float(sol.jac[:, 0] @ sol.jac[:, 0])
        lam_se = float(math.sqrt(s2 / jtj)) if jtj > 0 else float("nan")
        notes.append(
            "ee de λ por el jacobiano con errores iid: subestima la incertidumbre con errores "
            "persistentes entre fechas."
        )
    return QCalibration(
        model=model,
        mode=mode,
        params_q=pq,
        lam=lam,
        lam_se=lam_se,
        params_p=fit_p.params,
        rmse_bp=rmse,
        n_dates=int(len(data)),
        window=(str(data.index[0])[:10], str(data.index[-1])[:10]),
        notes=notes,
    )
