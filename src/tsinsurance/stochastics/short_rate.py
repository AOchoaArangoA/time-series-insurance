"""Modelos de tasa corta bajo la medida física ℙ: Vasicek y CIR (spec 007, US1).

- **Vasicek**: dr = κ(θ − r)dt + σ dW. La transición es gaussiana:
  r_{t+Δ} | r_t ~ N(θ + (r_t − θ)φ, σ²(1 − φ²)/(2κ)), con φ = e^{−κΔ}. La máxima
  verosimilitud exacta (condicional al primer dato) es el MCO del AR(1).
- **CIR**: dr = κ(θ − r)dt + σ√r dW. La transición es una χ² no central escalada:
  2c·r_{t+Δ} | r_t ~ χ²'(4κθ/σ², 2c·r_t·φ), con c = 2κ/(σ²(1 − φ)). MV exacta con
  ``scipy.stats.ncx2``; inicio con el MCO de la discretización de Euler.

Las dos simulaciones son **exactas** (sin sesgo de discretización ni tasas negativas en
CIR).

**Incertidumbre.** El MV de κ tiene un sesgo de orden ≈ 4/T_años hacia arriba (Tang y
Chen 2009; Phillips y Yu 2009) y su distribución es asimétrica con T moderado. Los IC de
κ, θ y σ se calculan con un **bootstrap paramétrico**; se ofrece la corrección de sesgo
por *jackknife* de Phillips y Yu (2009). Con φ̂ ≥ 1 (sin reversión a la media) κ no está
identificado: se advierte y se sugiere el paseo aleatorio.

References
----------
Vasicek, O. (1977). An equilibrium characterization of the term structure. *Journal of
Financial Economics*, 5(2), 177-188.
Cox, J., Ingersoll, J. y Ross, S. (1985). A theory of the term structure of interest
rates. *Econometrica*, 53(2), 385-407.
Phillips, P. C. B. y Yu, J. (2009). Simulation-based estimation of contingent-claims
prices. *Review of Financial Studies*, 22(9), 3669-3705.
Tang, C. Y. y Chen, S. X. (2009). Parameter estimation and bias correction for diffusion
processes. *Journal of Econometrics*, 149(1), 65-81.
Glasserman, P. (2003). *Monte Carlo Methods in Financial Engineering*, §3.3-3.4.
"""

from __future__ import annotations

import math
import warnings as _warnings
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import optimize, stats

from tsinsurance.errors import DataValidationError, InsufficientDataError, TSInsuranceError
from tsinsurance.results import HypothesisTestResult, ResultMixin

__all__ = [
    "CIRP",
    "ShortRateDiagnostics",
    "ShortRateFit",
    "VasicekP",
    "conditional_mean",
    "conditional_variance",
]

Model = Literal["vasicek", "cir"]
MIN_OBS = 100


def conditional_mean(r: np.ndarray | float, kappa: float, theta: float, h: float) -> np.ndarray:
    """E[r_{t+h} | r_t] = θ + (r_t − θ)e^{−κh} (igual en Vasicek y CIR)."""
    return theta + (np.asarray(r, dtype=float) - theta) * math.exp(-kappa * h)


def conditional_variance(
    model: Model, r: np.ndarray | float, kappa: float, theta: float, sigma: float, h: float
) -> np.ndarray:
    """Var[r_{t+h} | r_t] exacta."""
    e = math.exp(-kappa * h)
    rr = np.asarray(r, dtype=float)
    if model == "vasicek":
        return np.full_like(rr, sigma**2 * (1 - e**2) / (2 * kappa), dtype=float)
    return rr * sigma**2 * (e - e**2) / kappa + theta * sigma**2 * (1 - e) ** 2 / (2 * kappa)


def _clean(r: pd.Series | np.ndarray) -> np.ndarray:
    x = np.asarray(r, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < MIN_OBS:
        raise InsufficientDataError("modelo de tasa corta", MIN_OBS, int(x.size))
    return x


# --------------------------------------------------------------------------- Vasicek


def _vasicek_mle(x: np.ndarray, dt: float) -> dict[str, Any]:
    y, z = x[1:], x[:-1]
    n = y.size
    zbar, ybar = z.mean(), y.mean()
    sxx = float(((z - zbar) ** 2).sum())
    phi = float(((z - zbar) * (y - ybar)).sum() / sxx)
    c = float(ybar - phi * zbar)
    resid = y - c - phi * z
    s2 = float(resid @ resid / n)  # MV: SSR/n
    out: dict[str, Any] = {"phi": phi, "c": c, "s2": s2, "n": n, "resid": resid}
    if phi >= 1 or phi <= 0:
        out.update(kappa=float("nan"), theta=float("nan"), sigma=float("nan"), identified=False)
        return out
    kappa = -math.log(phi) / dt
    theta = c / (1 - phi)
    sigma = math.sqrt(s2 * 2 * kappa / (1 - phi**2))
    loglik = -0.5 * n * (math.log(2 * math.pi * s2) + 1)
    # Método delta desde (c, φ, s²) con la covarianza de MCO y var(s²) = 2s⁴/n.
    cov_cphi = s2 * np.linalg.inv(np.array([[n, z.sum()], [z.sum(), float(z @ z)]]))
    jac = np.zeros((3, 3))  # filas: κ, θ, σ; columnas: c, φ, s²
    jac[0, 1] = -1 / (phi * dt)
    jac[1, 0] = 1 / (1 - phi)
    jac[1, 1] = c / (1 - phi) ** 2
    dk_dphi = jac[0, 1]
    # σ² = s²·2κ/(1 − φ²)
    g = 2 * kappa / (1 - phi**2)
    dg_dphi = 2 * dk_dphi / (1 - phi**2) + 2 * kappa * 2 * phi / (1 - phi**2) ** 2
    jac[2, 1] = 0.5 / sigma * s2 * dg_dphi
    jac[2, 2] = 0.5 / sigma * g
    full = np.zeros((3, 3))
    full[:2, :2] = cov_cphi
    full[2, 2] = 2 * s2**2 / n
    cov = jac @ full @ jac.T
    out.update(
        kappa=kappa,
        theta=theta,
        sigma=sigma,
        loglik=loglik,
        identified=True,
        se=dict(zip(("kappa", "theta", "sigma"), np.sqrt(np.diag(cov)).tolist(), strict=True)),
    )
    return out


def _vasicek_rows(paths: np.ndarray, dt: float) -> list[tuple[float, float, float]]:
    """(κ, θ, σ) de MV para cada fila de ``paths`` (sólo las identificadas)."""
    z, y = paths[:, :-1], paths[:, 1:]
    n = y.shape[1]
    zc = z - z.mean(axis=1, keepdims=True)
    yc = y - y.mean(axis=1, keepdims=True)
    phi = (zc * yc).sum(axis=1) / (zc * zc).sum(axis=1)
    c = y.mean(axis=1) - phi * z.mean(axis=1)
    resid = y - c[:, None] - phi[:, None] * z
    s2 = (resid**2).sum(axis=1) / n
    ok = (phi > 0) & (phi < 1)
    kappa = -np.log(phi[ok]) / dt
    theta = c[ok] / (1 - phi[ok])
    sigma = np.sqrt(s2[ok] * 2 * kappa / (1 - phi[ok] ** 2))
    return list(zip(kappa.tolist(), theta.tolist(), sigma.tolist(), strict=True))


# --------------------------------------------------------------------------- CIR


def _cir_loglik(params: np.ndarray, x: np.ndarray, dt: float) -> float:
    kappa, theta, sigma = params
    if kappa <= 0 or theta <= 0 or sigma <= 0:
        return -np.inf
    e = math.exp(-kappa * dt)
    c = 2 * kappa / (sigma**2 * (1 - e))
    df = 4 * kappa * theta / sigma**2
    nc = 2 * c * x[:-1] * e
    val = np.log(2 * c) + stats.ncx2.logpdf(2 * c * x[1:], df, nc)
    total = float(np.sum(val))
    return total if np.isfinite(total) else -np.inf


def _cir_start(x: np.ndarray, dt: float) -> np.ndarray:
    # Euler: (r_{t+1} − r_t)/√r_t = κθΔ/√r_t − κΔ√r_t + σ√Δ ε
    sq = np.sqrt(x[:-1])
    yy = (x[1:] - x[:-1]) / sq
    xx = np.column_stack([dt / sq, -dt * sq])
    beta, *_ = np.linalg.lstsq(xx, yy, rcond=None)
    kth, kappa = float(beta[0]), float(beta[1])
    kappa = max(kappa, 0.05)
    theta = max(kth / kappa, float(np.mean(x)) * 0.5, 1e-4)
    resid = yy - xx @ beta
    sigma = max(float(resid.std() / math.sqrt(dt)), 1e-4)
    return np.array([kappa, theta, sigma])


def _cir_mle(x: np.ndarray, dt: float, start: np.ndarray | None = None) -> dict[str, Any]:
    x0 = _cir_start(x, dt) if start is None else start

    def neg(logp: np.ndarray) -> float:
        v = _cir_loglik(np.exp(logp), x, dt)
        return -v if np.isfinite(v) else 1e300

    with np.errstate(all="ignore"), _warnings.catch_warnings():
        _warnings.simplefilter("ignore")
        res = optimize.minimize(
            neg,
            np.log(x0),
            method="Nelder-Mead",
            options={"xatol": 1e-8, "fatol": 1e-8, "maxiter": 4000},
        )
        res = optimize.minimize(neg, res.x, method="BFGS")
    kappa, theta, sigma = (float(v) for v in np.exp(res.x))
    loglik = -float(res.fun)
    se = _hessian_se(lambda p: _cir_loglik(p, x, dt), np.array([kappa, theta, sigma]))
    e = math.exp(-kappa * dt)
    m = theta + (x[:-1] - theta) * e
    v = conditional_variance("cir", x[:-1], kappa, theta, sigma, dt)
    return {
        "kappa": kappa,
        "theta": theta,
        "sigma": sigma,
        "loglik": loglik,
        "identified": bool(res.success or np.isfinite(loglik)),
        "se": se,
        "std_resid": (x[1:] - m) / np.sqrt(v),
        "phi": e,
    }


def _hessian_se(f: Any, p: np.ndarray) -> dict[str, float]:
    """EE por la hessiana numérica (diferencias centrales relativas) del log-verosímil."""
    k = p.size
    h = 1e-4 * np.maximum(np.abs(p), 1e-6)
    hess = np.zeros((k, k))
    f0 = f(p)
    for i in range(k):
        for j in range(i, k):
            ei, ej = np.zeros(k), np.zeros(k)
            ei[i], ej[j] = h[i], h[j]
            if i == j:
                val = (f(p + ei) - 2 * f0 + f(p - ei)) / h[i] ** 2
            else:
                val = (f(p + ei + ej) - f(p + ei - ej) - f(p - ei + ej) + f(p - ei - ej)) / (
                    4 * h[i] * h[j]
                )
            hess[i, j] = hess[j, i] = val
    try:
        cov = np.linalg.inv(-hess)
        se = np.sqrt(np.where(np.diag(cov) > 0, np.diag(cov), np.nan))
    except np.linalg.LinAlgError:
        se = np.full(k, np.nan)
    return dict(zip(("kappa", "theta", "sigma"), se.tolist(), strict=True))


# --------------------------------------------------------------------------- simulación


def _simulate(
    model: Model,
    kappa: float,
    theta: float,
    sigma: float,
    dt: float,
    r0: float,
    steps: int,
    n_paths: int,
    rng: np.random.Generator,
    antithetic: bool = False,
) -> np.ndarray:
    out = np.empty((n_paths, steps + 1))
    out[:, 0] = r0
    e = math.exp(-kappa * dt)
    if model == "vasicek":
        sd = math.sqrt(sigma**2 * (1 - e**2) / (2 * kappa))
        if antithetic:
            half = (n_paths + 1) // 2
            z = rng.standard_normal((half, steps))
            z = np.vstack([z, -z])[:n_paths]
        else:
            z = rng.standard_normal((n_paths, steps))
        for t in range(steps):
            out[:, t + 1] = theta + (out[:, t] - theta) * e + sd * z[:, t]
        return out
    if antithetic:
        raise TSInsuranceError(
            "Las antitéticas no se ofrecen en CIR: la transición χ² no central no es "
            "simétrica (revisión B1)."
        )
    c = 2 * kappa / (sigma**2 * (1 - e))
    df = 4 * kappa * theta / sigma**2
    for t in range(steps):
        nc = 2 * c * out[:, t] * e
        # Mezcla exacta de Poisson y gamma (Glasserman 2003, §3.4): χ²'(df, nc) =
        # χ²(df + 2N), N ~ Poisson(nc/2). Vale también con df < 1.
        n = rng.poisson(nc / 2)
        out[:, t + 1] = rng.chisquare(df + 2 * n) / (2 * c)
    return out


# --------------------------------------------------------------------------- resultados


@dataclass(frozen=True, slots=True)
class ShortRateDiagnostics(ResultMixin):
    """Diagnósticos FR-001b: estacionariedad, residuos y pronóstico fuera de muestra."""

    integration_order: int | None
    stationarity_conclusion: str
    zivot_andrews_break: str | None
    residual_tests: dict[str, HypothesisTestResult]
    cusum_pvalue: float | None
    walk_forward: dict[str, Any]
    passed: bool
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Resumen legible."""
        lines = [
            f"Diagnósticos de la tasa corta: {'superados' if self.passed else 'NO superados'}",
            f"  Estacionariedad de r_t: {self.stationarity_conclusion}"
            + (
                f" (quiebre candidato {self.zivot_andrews_break})"
                if self.zivot_andrews_break
                else ""
            ),
        ]
        for name, t in self.residual_tests.items():
            lines.append(f"  {name}: estadístico {t.statistic:.3f}, p = {t.p_value}")
        if self.walk_forward:
            wf = self.walk_forward
            lines.append(
                f"  Pronóstico a {wf['horizon']} pasos frente al paseo aleatorio: ECM modelo "
                f"{wf['mse_model']:.3e} vs {wf['mse_random_walk']:.3e}, DM p = {wf['dm_pvalue']}"
            )
        lines += [f"  Advertencia: {w}" for w in self.warnings]
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ShortRateFit(ResultMixin):
    """Ajuste de un modelo de tasa corta bajo ℙ.

    ``ci`` contiene los IC al 95 % del bootstrap paramétrico: en Vasicek, intervalos
    **básicos** (Hall 1992) y, para θ, re-simulados con κ corregido por sesgo; en CIR,
    percentiles. ``se`` son los errores asintóticos (método delta o hessiana), que con T
    moderado subestiman la incertidumbre de κ.
    """

    model: Model
    kappa: float
    theta: float
    sigma: float
    dt: float
    n_obs: int
    loglik: float
    identified: bool
    se: dict[str, float]
    ci: dict[str, tuple[float, float]]
    bias_corrected_kappa: float | None
    feller: dict[str, Any]
    warnings: list[str]
    r_last: float
    data: pd.Series = field(repr=False)
    measure: str = "P"

    @property
    def params(self) -> dict[str, float]:
        """Parámetros (κ, θ, σ)."""
        return {"kappa": self.kappa, "theta": self.theta, "sigma": self.sigma}

    def summary(self) -> str:
        """Resumen legible."""
        name = "Vasicek" if self.model == "vasicek" else "CIR"
        lines = [f"{name} bajo ℙ (n = {self.n_obs}, Δ = {self.dt:.5f})"]
        if not self.identified:
            lines.append("  κ NO identificado (φ̂ ≥ 1): sin reversión a la media en la muestra.")
        for k, v in self.params.items():
            lo, hi = self.ci.get(k, (float("nan"), float("nan")))
            lines.append(
                f"  {k} = {v:.5f} (ee asint. {self.se.get(k, float('nan')):.5f}; "
                f"IC 95 % bootstrap [{lo:.5f}; {hi:.5f}])"
            )
        if self.bias_corrected_kappa is not None:
            lines.append(f"  κ corregido por jackknife: {self.bias_corrected_kappa:.5f}")
        if self.feller:
            lines.append(
                f"  Feller 2κθ/σ² = {self.feller['ratio']:.3f} "
                f"(IC {self.feller.get('ci', ('n/d', 'n/d'))})"
            )
        lines += [f"  Advertencia: {w}" for w in self.warnings]
        return "\n".join(lines)

    def mean(self, h: float) -> float:
        """E[r_{t+h} | r_último]."""
        return float(conditional_mean(self.r_last, self.kappa, self.theta, h))

    def simulate(
        self,
        r0: float | None = None,
        horizon: int = 252,
        n_paths: int = 1000,
        rng: np.random.Generator | int | None = None,
        antithetic: bool = False,
    ) -> np.ndarray:
        """Trayectorias exactas (``n_paths`` × ``horizon + 1``) con paso ``dt``."""
        if not self.identified:
            raise TSInsuranceError("κ no identificado: no se simula un proceso sin reversión.")
        gen = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
        start = self.r_last if r0 is None else float(r0)
        return _simulate(
            self.model,
            self.kappa,
            self.theta,
            self.sigma,
            self.dt,
            start,
            horizon,
            n_paths,
            gen,
            antithetic,
        )

    def diagnostics(
        self, *, alpha: float = 0.05, horizon: int = 21, min_train: int = 750, step: int = 21
    ) -> ShortRateDiagnostics:
        """Diagnósticos FR-001b (B3) sobre los datos del ajuste."""
        if not self.identified:
            raise TSInsuranceError(
                "κ no identificado (φ̂ ≥ 1): no hay residuos del modelo que diagnosticar; "
                "la serie se comporta como un paseo aleatorio en la muestra."
            )
        return _diagnostics(self, alpha=alpha, horizon=horizon, min_train=min_train, step=step)


def _fit(
    model: Model,
    r: pd.Series | np.ndarray,
    dt: float,
    bootstrap: int,
    jackknife: bool,
    seed: int,
    floor: float | None,
) -> ShortRateFit:
    series = pd.Series(r).dropna() if isinstance(r, pd.Series) else pd.Series(np.asarray(r))
    x = _clean(series)
    warnings: list[str] = []
    if model == "cir":
        if np.any(x <= 0):
            if floor is None:
                raise DataValidationError(
                    "CIR no admite tasas ≤ 0 (p. ej. ^IRX en 2020-2021): use Vasicek o "
                    "declare un piso con floor=... (CIR desplazado no está en el MVP)."
                )
            n_floor = int(np.sum(x < floor))
            x = np.maximum(x, floor)
            warnings.append(f"Piso numérico {floor} aplicado a {n_floor} observaciones.")
        est = _cir_mle(x, dt)
    else:
        est = _vasicek_mle(x, dt)
    identified = bool(est["identified"])
    if not identified:
        warnings.append(
            f"φ̂ = {est['phi']:.5f} ≥ 1 (o ≤ 0): κ no identificado; use un paseo aleatorio."
        )
        return ShortRateFit(
            model,
            float("nan"),
            float("nan"),
            float("nan"),
            dt,
            x.size,
            float("nan"),
            False,
            {},
            {},
            None,
            {},
            warnings,
            float(x[-1]),
            series,
        )
    kappa, theta, sigma = est["kappa"], est["theta"], est["sigma"]
    years = x.size * dt
    if kappa * years < 50:
        warnings.append(
            f"κ·T = {kappa * years:.1f} < 50: el MV de κ está sesgado hacia arriba "
            f"(≈ 4/T_años = {4 / years:.3f}) y sus IC asintóticos no son confiables; use los "
            "IC del bootstrap paramétrico."
        )
    ci: dict[str, tuple[float, float]] = {}
    feller: dict[str, Any] = {}
    boot = np.empty((0, 3))
    if bootstrap > 0:
        rng = np.random.default_rng(seed)
        draws = []
        if model == "vasicek":
            # Vectorizado: todas las trayectorias a la vez y MCO por fila.
            paths = _simulate(
                model, kappa, theta, sigma, dt, float(x[0]), x.size - 1, bootstrap, rng
            )
            draws = _vasicek_rows(paths, dt)
        for _ in range(bootstrap if model == "cir" else 0):
            path = _simulate(model, kappa, theta, sigma, dt, float(x[0]), x.size - 1, 1, rng)[0]
            try:
                b = (
                    _vasicek_mle(path, dt)
                    if model == "vasicek"
                    else _cir_mle(path, dt, start=np.array([kappa, theta, sigma]))
                )
            except (ValueError, np.linalg.LinAlgError):
                continue
            if b["identified"] and np.isfinite(b["kappa"]):
                draws.append((b["kappa"], b["theta"], b["sigma"]))
        boot = np.asarray(draws)
        if len(boot) < 0.9 * bootstrap:
            warnings.append(
                f"{bootstrap - len(boot)} réplicas del bootstrap sin reversión identificada."
            )
        est_vec = np.array([kappa, theta, sigma])
        if model == "vasicek" and len(boot):
            # Intervalo BÁSICO (Hall 1992): [2θ̂ − q₀,₉₇₅; 2θ̂ − q₀,₀₂₅]. Corrige el sesgo de
            # κ̂ que el percentil hereda (Monte Carlo de SC-001: cobertura de κ 49 % → 93 %).
            for i, k in enumerate(("kappa", "theta", "sigma")):
                lo, hi = np.quantile(boot[:, i], [0.025, 0.975])
                ci[k] = (float(2 * est_vec[i] - hi), float(2 * est_vec[i] - lo))
            # La dispersión de θ̂ depende de κ (var ∝ σ²/(κ²T)): se re-simula con κ corregido
            # por el sesgo del bootstrap, κ̃ = 2κ̂ − media(κ*) (cobertura de θ 77 % → 90 %).
            k_tilde = max(2 * kappa - float(boot[:, 0].mean()), 0.2 * kappa)
            paths2 = _simulate(
                model, k_tilde, theta, sigma, dt, float(x[0]), x.size - 1, bootstrap, rng
            )
            th2 = np.array([b[1] for b in _vasicek_rows(paths2, dt)])
            if th2.size:
                lo, hi = np.quantile(th2 - theta, [0.025, 0.975])
                ci["theta"] = (float(theta - hi), float(theta - lo))
        else:
            for i, k in enumerate(("kappa", "theta", "sigma")):
                if len(boot):
                    lo, hi = np.quantile(boot[:, i], [0.025, 0.975])
                    ci[k] = (float(lo), float(hi))
    if model == "cir":
        ratio = 2 * kappa * theta / sigma**2
        feller = {"ratio": float(ratio), "satisfied": bool(ratio >= 1)}
        if len(boot):
            fr = 2 * boot[:, 0] * boot[:, 1] / boot[:, 2] ** 2
            lo, hi = np.quantile(fr, [0.025, 0.975])
            feller["ci"] = (float(lo), float(hi))
        if ratio < 1:
            warnings.append(
                "No se cumple la condición de Feller (2κθ < σ²): el proceso toca cero; la "
                "simulación exacta lo maneja, pero el ajuste es frágil."
            )
    bc: float | None = None
    if jackknife:
        # Phillips y Yu (2009), m = 2 subbloques: κ_J = 2κ̂ − (κ̂₁ + κ̂₂)/2.
        half = x.size // 2
        parts = []
        for seg in (x[:half], x[half:]):
            p = _vasicek_mle(seg, dt) if model == "vasicek" else _cir_mle(seg, dt)
            parts.append(p["kappa"])
        if all(np.isfinite(parts)):
            bc = float(2 * kappa - 0.5 * (parts[0] + parts[1]))
    return ShortRateFit(
        model=model,
        kappa=float(kappa),
        theta=float(theta),
        sigma=float(sigma),
        dt=dt,
        n_obs=int(x.size),
        loglik=float(est["loglik"]),
        identified=True,
        se={k: float(v) for k, v in est["se"].items()},
        ci=ci,
        bias_corrected_kappa=bc,
        feller=feller,
        warnings=warnings,
        r_last=float(x[-1]),
        data=pd.Series(x, index=series.index[-x.size :])
        if isinstance(r, pd.Series)
        else pd.Series(x),
    )


class VasicekP:
    """Vasicek bajo ℙ: ``VasicekP.fit(r, dt)``."""

    @staticmethod
    def fit(
        r: pd.Series | np.ndarray,
        dt: float = 1 / 252,
        *,
        bootstrap: int = 499,
        jackknife: bool = False,
        seed: int = 0,
    ) -> ShortRateFit:
        """MV exacta (AR(1) gaussiano) con IC por bootstrap paramétrico.

        ``r`` en decimales (0,04 = 4 %), con paso ``dt`` en años.
        """
        return _fit("vasicek", r, dt, bootstrap, jackknife, seed, None)


class CIRP:
    """CIR bajo ℙ: ``CIRP.fit(r, dt)``."""

    @staticmethod
    def fit(
        r: pd.Series | np.ndarray,
        dt: float = 1 / 252,
        *,
        bootstrap: int = 199,
        jackknife: bool = False,
        seed: int = 0,
        floor: float | None = None,
    ) -> ShortRateFit:
        """MV exacta con la χ² no central; Feller con IC por bootstrap paramétrico.

        Las tasas ≤ 0 producen un error, salvo que se declare un piso numérico ``floor``.
        """
        return _fit("cir", r, dt, bootstrap, jackknife, seed, floor)


# --------------------------------------------------------------------------- diagnósticos


def _std_resid(fit: ShortRateFit, x: np.ndarray) -> np.ndarray:
    m = conditional_mean(x[:-1], fit.kappa, fit.theta, fit.dt)
    v = conditional_variance(fit.model, x[:-1], fit.kappa, fit.theta, fit.sigma, fit.dt)
    return np.asarray((x[1:] - m) / np.sqrt(v))


def _diagnostics(
    fit: ShortRateFit, *, alpha: float, horizon: int, min_train: int, step: int
) -> ShortRateDiagnostics:
    from statsmodels.stats.diagnostic import breaks_cusumolsresid

    from tsinsurance.diagnostics.descriptive import arch_lm, jarque_bera, ljung_box
    from tsinsurance.diagnostics.stationarity import stationarity
    from tsinsurance.validation.comparison import diebold_mariano

    warnings: list[str] = []
    passed = True
    x = fit.data.to_numpy()
    series = (
        fit.data
        if isinstance(fit.data.index, pd.DatetimeIndex)
        else pd.Series(x, index=pd.RangeIndex(x.size))
    )
    order: int | None = None
    conclusion = "no evaluado"
    brk: str | None = None
    try:
        rep = stationarity(series, alpha=alpha, breaks=True)
        order, conclusion = rep.integration_order, rep.conclusion
        if rep.break_significant and rep.break_date is not None:
            brk = (
                str(pd.Timestamp(rep.break_date).date())
                if isinstance(rep.break_date, pd.Timestamp)
                else str(rep.break_date)
            )
        if order != 0:
            passed = False
            warnings.append(
                f"r_t no es I(0) según ADF/PP+KPSS ({conclusion}): la reversión a la media del "
                "modelo no está respaldada por los datos."
            )
    except TSInsuranceError as exc:
        warnings.append(f"Estacionariedad no evaluada: {exc}")
    z = _std_resid(fit, x)
    tests = {
        "Ljung-Box": ljung_box(z, lags=10),
        "ARCH-LM": arch_lm(z),
        "Jarque-Bera": jarque_bera(z),
    }
    for name, t in tests.items():
        if t.p_value is not None and t.p_value < alpha:
            passed = False
            warnings.append(
                f"{name} rechaza en los residuos estandarizados (p = {t.p_value:.3g})"
                + (
                    ": σ constante no captura la volatilidad (esperado)."
                    if name == "ARCH-LM"
                    else "."
                )
            )
    stat, cusum_p, _ = breaks_cusumolsresid(z, ddof=3)
    if cusum_p < alpha:
        passed = False
        warnings.append("CUSUM: inestabilidad de los parámetros.")
    wf: dict[str, Any] = {}
    if x.size >= min_train + horizon + 10 * step:
        fe_m, fe_rw = [], []
        for end in range(min_train, x.size - horizon, step):
            sub = x[:end]
            est = _vasicek_mle(sub, fit.dt) if fit.model == "vasicek" else _cir_mle(sub, fit.dt)
            target = x[end - 1 + horizon]
            if est["identified"] and np.isfinite(est["kappa"]):
                pred = float(
                    conditional_mean(sub[-1], est["kappa"], est["theta"], horizon * fit.dt)
                )
            else:
                pred = float(sub[-1])
            fe_m.append(target - pred)
            fe_rw.append(target - sub[-1])
        a, b = np.asarray(fe_m), np.asarray(fe_rw)
        dm = diebold_mariano(b, a, h=max(1, horizon // step))
        wf = {
            "horizon": horizon,
            "step": step,
            "n_forecasts": int(a.size),
            "mse_model": float(np.mean(a**2)),
            "mse_random_walk": float(np.mean(b**2)),
            "dm_statistic": dm.statistic,
            "dm_pvalue": dm.p_value,
            "note": "re-estimación expansiva cada `step` observaciones; DM con HLN",
        }
        if np.mean(a**2) >= np.mean(b**2):
            warnings.append(
                "El pronóstico del modelo no supera al paseo aleatorio fuera de muestra."
            )
    return ShortRateDiagnostics(
        integration_order=order,
        stationarity_conclusion=conclusion,
        zivot_andrews_break=brk,
        residual_tests=tests,
        cusum_pvalue=float(cusum_p),
        walk_forward=wf,
        passed=passed,
        warnings=warnings,
    )
