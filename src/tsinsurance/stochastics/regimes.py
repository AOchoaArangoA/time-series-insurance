"""Tasa corta con cambio de régimen de Markov (spec 007, US2; revisión B4 e I1).

Modelo: r_t = c_s + φ_s·r_{t−1} + σ_s·ε_t, con s_t una cadena de Markov de k estados. Es la
discretización **exacta** de un Vasicek por régimen con paso Δ: θ_s = c_s/(1 − φ_s) y
κ_s = −ln(φ_s)/Δ. Se estima con ``statsmodels`` (``MarkovRegression`` con r_{t−1} como
regresor, ``switching_exog`` y ``switching_variance``) y se simula con **la misma
recursión**.

- **Identificación:** varias inicializaciones (``search_reps``). Los regímenes se ordenan
  por σ_s (0 = el de menor volatilidad) para que las etiquetas no se permuten entre
  estimaciones *walk-forward*.
- **Número de regímenes:** AIC y BIC frente al modelo de un régimen (Vasicek).
- **Sin fuga (I1):** todo resultado declara ``params_estimation_end``. Las probabilidades
  filtradas en t sólo usan datos hasta t, pero con parámetros estimados con datos
  posteriores son **pseudo-filtradas (descriptivas)**. :meth:`RegimeFit.filter` aplica el
  filtro de Hamilton con los parámetros fijos a datos nuevos.

References
----------
Hamilton, J. (1989). A new approach to the economic analysis of nonstationary time series
and the business cycle. *Econometrica*, 57(2), 357-384.
Ang, A. y Bekaert, G. (2002). Short rate nonlinearities and regime switches. *Journal of
Economic Dynamics and Control*, 26(7-8), 1243-1274.
"""

from __future__ import annotations

import math
import warnings as _warnings
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from tsinsurance.errors import InsufficientDataError
from tsinsurance.results import ResultMixin

__all__ = ["MarkovShortRate", "RegimeFit", "hamilton_filter"]


def hamilton_filter(
    r: np.ndarray,
    c: np.ndarray,
    phi: np.ndarray,
    sigma: np.ndarray,
    transition: np.ndarray,
    p0: np.ndarray | None = None,
) -> np.ndarray:
    """Probabilidades filtradas P(s_t = j | r_1..r_t) para t = 1..n−1.

    ``transition[i, j]`` = P(s_t = j | s_{t−1} = i). ``p0`` por defecto: la ergódica.
    """
    k = c.size
    if p0 is None:
        a = np.vstack([transition.T - np.eye(k), np.ones(k)])
        b = np.r_[np.zeros(k), 1.0]
        p0 = np.linalg.lstsq(a, b, rcond=None)[0]
    prob = np.asarray(p0, dtype=float)
    out = np.empty((r.size - 1, k))
    for t in range(1, r.size):
        pred = prob @ transition
        mu = c + phi * r[t - 1]
        dens = np.exp(-0.5 * ((r[t] - mu) / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi))
        joint = pred * dens
        total = joint.sum()
        prob = joint / total if total > 0 else pred
        out[t - 1] = prob
    return out


@dataclass(frozen=True, slots=True)
class RegimeFit(ResultMixin):
    """Ajuste de la tasa corta con regímenes (ordenados por σ)."""

    k_regimes: int
    dt: float
    c: tuple[float, ...]
    phi: tuple[float, ...]
    sigma: tuple[float, ...]
    transition: tuple[tuple[float, ...], ...]
    theta: tuple[float, ...]
    kappa: tuple[float, ...]
    expected_duration: tuple[float, ...]
    aic: float
    bic: float
    aic_one_regime: float
    bic_one_regime: float
    params_estimation_end: str
    filtered_probabilities: pd.DataFrame = field(repr=False)
    smoothed_probabilities: pd.DataFrame = field(repr=False)
    warnings: list[str] = field(default_factory=list)
    note: str = (
        "Probabilidades filtradas con parámetros estimados hasta params_estimation_end: "
        "antes de esa fecha son pseudo-filtradas (descriptivas), no punto en el tiempo."
    )

    @property
    def prefers_regimes(self) -> dict[str, bool]:
        """¿AIC y BIC prefieren k regímenes sobre uno?"""
        return {"aic": self.aic < self.aic_one_regime, "bic": self.bic < self.bic_one_regime}

    def summary(self) -> str:
        """Resumen legible."""
        lines = [
            f"Tasa corta con {self.k_regimes} regímenes (estimación hasta "
            f"{self.params_estimation_end})"
        ]
        for j in range(self.k_regimes):
            lines.append(
                f"  Régimen {j}: θ = {self.theta[j]:.4%}, κ = {self.kappa[j]:.3f}, "
                f"σ_Δ = {self.sigma[j]:.5f}, duración esperada {self.expected_duration[j]:.1f} "
                "pasos"
            )
        lines.append(
            f"  AIC {self.aic:.1f} vs {self.aic_one_regime:.1f} (1 régimen); BIC {self.bic:.1f} "
            f"vs {self.bic_one_regime:.1f}"
        )
        lines += [f"  Advertencia: {w}" for w in self.warnings]
        lines.append(f"  Nota: {self.note}")
        return "\n".join(lines)

    def filter(self, r: pd.Series | np.ndarray) -> np.ndarray:
        """Filtro de Hamilton con los parámetros FIJOS de este ajuste (punto en el tiempo).

        Devuelve P(s_t | r_1..r_t) para t = 1..n−1: la fila t no depende de datos
        posteriores a t.
        """
        x = np.asarray(r, dtype=float)
        return hamilton_filter(
            x,
            np.asarray(self.c),
            np.asarray(self.phi),
            np.asarray(self.sigma),
            np.asarray(self.transition),
        )

    def simulate(
        self,
        r0: float,
        horizon: int,
        n_paths: int,
        rng: np.random.Generator | int | None = None,
        *,
        state0: int | np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Trayectorias (tasas, estados) con la MISMA recursión estimada (B4).

        ``state0``: régimen inicial (entero) o probabilidades; por defecto la última
        probabilidad filtrada.
        """
        gen = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
        k = self.k_regimes
        trans = np.asarray(self.transition)
        if state0 is None:
            p_init = self.filtered_probabilities.iloc[-1].to_numpy()
        elif isinstance(state0, (int, np.integer)):
            p_init = np.eye(k)[int(state0)]
        else:
            p_init = np.asarray(state0, dtype=float)
        states = np.empty((n_paths, horizon + 1), dtype=int)
        states[:, 0] = gen.choice(k, size=n_paths, p=p_init / p_init.sum())
        rates = np.empty((n_paths, horizon + 1))
        rates[:, 0] = r0
        cum = np.cumsum(trans, axis=1)
        c, phi, sig = np.asarray(self.c), np.asarray(self.phi), np.asarray(self.sigma)
        for t in range(horizon):
            u = gen.random(n_paths)
            nxt = (u[:, None] > cum[states[:, t]]).sum(axis=1)
            states[:, t + 1] = np.minimum(nxt, k - 1)
            s = states[:, t + 1]
            rates[:, t + 1] = c[s] + phi[s] * rates[:, t] + sig[s] * gen.standard_normal(n_paths)
        return rates, states


class MarkovShortRate:
    """``MarkovShortRate.fit(r, k_regimes=2, dt=1/252, search_reps=20)``."""

    @staticmethod
    def fit(
        r: pd.Series,
        k_regimes: int = 2,
        dt: float = 1 / 252,
        *,
        search_reps: int = 20,
        seed: int = 0,
    ) -> RegimeFit:
        """Estima el modelo por MV (EM + BFGS de statsmodels) y ordena los regímenes por σ."""
        from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

        from tsinsurance.stochastics.short_rate import _vasicek_mle

        series = pd.Series(r).dropna().astype(float)
        if series.size < 200:
            raise InsufficientDataError("regímenes de Markov", 200, int(series.size))
        y = series.iloc[1:]
        x = series.shift(1).iloc[1:].rename("r_lag")
        model = MarkovRegression(
            y.to_numpy(),
            k_regimes=k_regimes,
            exog=x.to_numpy()[:, None],
            switching_exog=True,
            switching_variance=True,
        )
        np.random.seed(seed)  # statsmodels usa el generador global en search_reps
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            res = model.fit(search_reps=search_reps, disp=False)
        names = list(model.param_names)
        p = np.asarray(res.params)
        get = dict(zip(names, p, strict=True))
        c = np.array([get[f"const[{j}]"] for j in range(k_regimes)])
        phi = np.array([get[f"x1[{j}]"] for j in range(k_regimes)])
        sig = np.sqrt(np.array([get[f"sigma2[{j}]"] for j in range(k_regimes)]))
        trans = np.asarray(res.regime_transition)[:, :, 0].T  # [i, j] = P(j | i)
        order = np.argsort(sig)
        c, phi, sig = c[order], phi[order], sig[order]
        trans = trans[np.ix_(order, order)]
        warnings: list[str] = []
        theta = np.where(phi < 1, c / (1 - phi), np.nan)
        kappa = np.where((phi > 0) & (phi < 1), -np.log(np.clip(phi, 1e-12, None)) / dt, np.nan)
        if np.any(~np.isfinite(kappa)):
            warnings.append(
                "Algún régimen sin reversión a la media (φ_s ≥ 1): θ_s y κ_s no definidos."
            )
        dur = 1 / np.clip(1 - np.diag(trans), 1e-12, None)
        idx = y.index
        filt = pd.DataFrame(np.asarray(res.filtered_marginal_probabilities)[:, order], index=idx)
        smooth = pd.DataFrame(np.asarray(res.smoothed_marginal_probabilities)[:, order], index=idx)
        one = _vasicek_mle(series.to_numpy(), dt)
        n = y.size
        ll1 = -0.5 * n * (math.log(2 * math.pi * one["s2"]) + 1)
        aic1, bic1 = -2 * ll1 + 2 * 3, -2 * ll1 + 3 * math.log(n)
        if not (res.aic < aic1 and res.bic < bic1):
            warnings.append("AIC y BIC no prefieren ambos el modelo con regímenes.")
        end = idx[-1]
        return RegimeFit(
            k_regimes=k_regimes,
            dt=dt,
            c=tuple(float(v) for v in c),
            phi=tuple(float(v) for v in phi),
            sigma=tuple(float(v) for v in sig),
            transition=tuple(tuple(float(v) for v in row) for row in trans),
            theta=tuple(float(v) for v in theta),
            kappa=tuple(float(v) for v in kappa),
            expected_duration=tuple(float(v) for v in dur),
            aic=float(res.aic),
            bic=float(res.bic),
            aic_one_regime=float(aic1),
            bic_one_regime=float(bic1),
            params_estimation_end=str(end.date()) if isinstance(end, pd.Timestamp) else str(end),
            filtered_probabilities=filt,
            smoothed_probabilities=smooth,
            warnings=warnings,
        )
