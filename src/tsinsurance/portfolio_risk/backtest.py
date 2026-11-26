"""Backtesting del VaR y del ES (spec 007, US6; revisión I6, M6).

Pronósticos rodantes a 1 día con información hasta t−1. Excepción: pérdida_t > VaR_t.

- **Kupiec (1995)** POF: razón de verosimilitud de la frecuencia de excepciones, χ²(1).
- **Christoffersen (1998)**: independencia (cadena de Markov de las excepciones, χ²(1)) y
  cobertura condicional (POF + independencia, χ²(2)).
- **Duraciones** (Christoffersen y Pelletier 2004): bajo H0 las duraciones entre
  excepciones son geométricas (exponenciales en continuo); se prueba b = 1 en una Weibull
  con censura en los extremos, LR χ²(1). Más potente con pocas excepciones.
- **Z2 de Acerbi y Székely (2014)** para el ES: Z2 = Σ L_t·I_t / (T·(1−α)·ES_t) − 1. El
  valor p se simula bajo la distribución predictiva **guardada** de cada día (los
  escenarios), unilateral (H1: el ES subestima). Ignora el error de estimación.

Con menos de 250 observaciones el resultado es **no concluyente**.

References
----------
Kupiec, P. (1995). Techniques for verifying the accuracy of risk measurement models.
*Journal of Derivatives*, 3(2), 73-84.
Christoffersen, P. (1998). Evaluating interval forecasts. *International Economic Review*,
39(4), 841-862.
Christoffersen, P. y Pelletier, D. (2004). Backtesting value-at-risk: a duration-based
approach. *Journal of Financial Econometrics*, 2(1), 84-108.
Acerbi, C. y Székely, B. (2014). Backtesting expected shortfall. *Risk*, diciembre.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from scipy import optimize, stats

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin

__all__ = ["MIN_OBS", "VaRBacktest", "backtest_var", "christoffersen", "duration_test", "kupiec"]

MIN_OBS = 250


def _xlogy(x: float, y: float) -> float:
    return 0.0 if x == 0 else x * math.log(y)


def kupiec(hits: np.ndarray, p: float) -> dict[str, float]:
    """POF de Kupiec: H0 frecuencia de excepciones = p."""
    n, x = hits.size, int(hits.sum())
    pi = x / n
    ll0 = _xlogy(n - x, 1 - p) + _xlogy(x, p)
    ll1 = _xlogy(n - x, 1 - pi) + _xlogy(x, pi) if 0 < x < n else 0.0
    lr = -2 * (ll0 - ll1)
    return {"exceptions": float(x), "rate": pi, "lr": lr, "pvalue": float(stats.chi2.sf(lr, 1))}


def christoffersen(hits: np.ndarray, p: float) -> dict[str, float]:
    """Independencia y cobertura condicional de Christoffersen."""
    h = hits.astype(int)
    a, b = h[:-1], h[1:]
    n00 = int(np.sum((a == 0) & (b == 0)))
    n01 = int(np.sum((a == 0) & (b == 1)))
    n10 = int(np.sum((a == 1) & (b == 0)))
    n11 = int(np.sum((a == 1) & (b == 1)))
    p01 = n01 / (n00 + n01) if n00 + n01 else 0.0
    p11 = n11 / (n10 + n11) if n10 + n11 else 0.0
    p1 = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)
    ll_ind = (
        _xlogy(n00, 1 - p01) + _xlogy(n01, p01) + _xlogy(n10, 1 - p11) + _xlogy(n11, p11)
        if 0 < p01 < 1 or 0 < p11 < 1
        else 0.0
    )
    ll_null = _xlogy(n00 + n10, 1 - p1) + _xlogy(n01 + n11, p1)
    lr_ind = max(-2 * (ll_null - ll_ind), 0.0)
    lr_cc = kupiec(hits, p)["lr"] + lr_ind
    return {
        "lr_ind": lr_ind,
        "pvalue_ind": float(stats.chi2.sf(lr_ind, 1)),
        "lr_cc": lr_cc,
        "pvalue_cc": float(stats.chi2.sf(lr_cc, 2)),
    }


def duration_test(hits: np.ndarray) -> dict[str, float]:
    """Christoffersen-Pelletier: Weibull (b libre) frente a exponencial (b = 1), con censura."""
    idx = np.flatnonzero(hits)
    if idx.size < 2:
        return {"lr": float("nan"), "pvalue": float("nan"), "b": float("nan"), "n_durations": 0.0}
    d = np.diff(idx).astype(float)
    first = float(idx[0] + 1)  # censurada a la izquierda
    last = float(hits.size - idx[-1])  # censurada a la derecha
    durations = np.r_[first, d, last]
    censored = np.r_[1, np.zeros(d.size), 1].astype(bool)

    def ll(params: np.ndarray) -> float:
        a, b = math.exp(params[0]), math.exp(params[1])
        x = durations
        log_f = math.log(b) + b * np.log(a) + (b - 1) * np.log(x) - (a * x) ** b
        log_s = -((a * x) ** b)
        return float(np.sum(np.where(censored, log_s, log_f)))

    res1 = optimize.minimize(
        lambda p: -ll(p), np.array([math.log(1 / d.mean()), 0.0]), method="Nelder-Mead"
    )
    res0 = optimize.minimize_scalar(
        lambda la: -ll(np.array([la, 0.0])), bounds=(-12, 2), method="bounded"
    )
    lr = max(2 * (-res1.fun + res0.fun), 0.0)
    return {
        "lr": float(lr),
        "pvalue": float(stats.chi2.sf(lr, 1)),
        "b": float(math.exp(res1.x[1])),
        "n_durations": float(d.size),
    }


def _z2(losses: np.ndarray, var: np.ndarray, es: np.ndarray, alpha_tail: float) -> float:
    hits = losses > var
    return float(np.sum(losses * hits / es) / (losses.size * alpha_tail) - 1)


@dataclass(frozen=True, slots=True)
class VaRBacktest(ResultMixin):
    """Resultados del backtesting de VaR/ES."""

    level: float
    n: int
    kupiec: dict[str, float]
    christoffersen: dict[str, float]
    duration: dict[str, float]
    z2: dict[str, float]
    inconclusive: bool
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Resumen legible."""
        k = self.kupiec
        lines = [
            f"Backtesting VaR {self.level:.3g} (n = {self.n}"
            + ("; NO CONCLUYENTE: < 250 observaciones" if self.inconclusive else "")
            + ")",
            f"  Excepciones {int(k['exceptions'])} ({k['rate']:.2%} vs {1 - self.level:.2%}); "
            f"Kupiec p = {k['pvalue']:.3f}",
            f"  Christoffersen: independencia p = {self.christoffersen['pvalue_ind']:.3f}, "
            f"cobertura condicional p = {self.christoffersen['pvalue_cc']:.3f}",
            f"  Duraciones (Christoffersen-Pelletier) p = {self.duration['pvalue']}",
        ]
        if self.z2:
            lines.append(f"  Z2 (ES) = {self.z2['statistic']:+.3f}, p = {self.z2['pvalue']:.3f}")
        lines += [f"  Nota: {n}" for n in self.notes]
        return "\n".join(lines)


def backtest_var(
    realized_losses: np.ndarray,
    var_forecasts: np.ndarray,
    level: float = 0.99,
    *,
    es_forecasts: np.ndarray | None = None,
    predictive: Sequence[np.ndarray] | None = None,
    reps: int = 2000,
    seed: int = 0,
) -> VaRBacktest:
    """Backtesting con pronósticos punto en el tiempo (VaR_t con datos hasta t−1).

    ``predictive``: para Z2, los escenarios de pérdidas pronosticados de cada día (la
    distribución predictiva guardada). El valor p se simula muestreando L_t* de ella.
    """
    loss = np.asarray(realized_losses, dtype=float)
    var = np.asarray(var_forecasts, dtype=float)
    if loss.shape != var.shape:
        raise DataValidationError("Pérdidas y pronósticos de VaR deben tener el mismo largo.")
    p = 1 - level
    hits = (loss > var).astype(int)
    notes = ["El valor p de Z2 ignora el error de estimación del modelo."] if predictive else []
    z2: dict[str, float] = {}
    if es_forecasts is not None and predictive is not None:
        es = np.asarray(es_forecasts, dtype=float)
        stat = _z2(loss, var, es, p)
        rng = np.random.default_rng(seed)
        sims = np.empty(reps)
        for r in range(reps):
            draw = np.array([rng.choice(np.asarray(sc)) for sc in predictive])
            sims[r] = _z2(draw, var, es, p)
        z2 = {"statistic": stat, "pvalue": float((1 + np.sum(sims >= stat)) / (1 + reps))}
    return VaRBacktest(
        level=level,
        n=int(loss.size),
        kupiec=kupiec(hits, p),
        christoffersen=christoffersen(hits, p),
        duration=duration_test(hits),
        z2=z2,
        inconclusive=loss.size < MIN_OBS,
        notes=notes,
    )
