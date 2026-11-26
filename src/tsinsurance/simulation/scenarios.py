"""Motores de escenarios de la curva (spec 007, US4; revisión I5, I8).

Todos devuelven :class:`Scenarios`: cambios de las tasas cero de los nodos (decimales) en
el horizonte, con la medida con que se simuló el **estado** (``state_measure``), la medida
con que se **revalúa** (``pricing_measure``) y el mapeo explícito del estado a los nodos.

- ``historical``: cambios a h días observados en una ventana que termina en ``asof``
  (solapados si h > 1; el IC de las medidas de riesgo debe usar bootstrap por bloques).
- ``filtered_historical`` (Barone-Adesi et al. 1999): innovaciones estandarizadas por una
  volatilidad EWMA (λ = 0,94) o GARCH(1,1) estimada **sólo con datos hasta** ``asof``, y
  reescaladas a la volatilidad pronosticada para el día siguiente. Con h > 1 se simula la
  trayectoria (la volatilidad se actualiza con la recursión EWMA o GARCH en cada paso);
  el escalado por √h sólo con ``sqrt_h=True``, que supone innovaciones iid.
- ``factor_mc``: normal multivariada o t de Student con la covarianza de los factores.
- ``short_rate_mc``: estado r_T simulado bajo ℙ (o con regímenes) y nodos revaluados con la
  fórmula afín bajo ℚ (parámetros ℚ declarados, típicamente con λ calibrado).

References
----------
Barone-Adesi, G., Giannopoulos, K. y Vosper, L. (1999). VaR without correlations for
portfolios of derivative securities. *Journal of Futures Markets*, 19(5), 583-602.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin
from tsinsurance.simulation.factors import FactorModel

__all__ = ["Scenarios", "factor_mc", "filtered_historical", "historical", "short_rate_mc"]

EWMA_LAMBDA = 0.94


@dataclass(frozen=True, slots=True)
class Scenarios(ResultMixin):
    """Escenarios de cambios de los nodos (n_escenarios × nodos, decimales)."""

    values: np.ndarray = field(repr=False)
    tenors: tuple[float, ...]
    method: str
    state_measure: Literal["P", "Q", "historical"]
    pricing_measure: str
    horizon_days: int
    seed: int | None
    window: tuple[str, str] | None
    mapping: str
    notes: list[str] = field(default_factory=list)

    @property
    def n(self) -> int:
        """Número de escenarios."""
        return int(self.values.shape[0])

    def summary(self) -> str:
        """Resumen legible."""
        sd = self.values.std(axis=0) * 1e4
        lines = [
            f"{self.n} escenarios ({self.method}), horizonte {self.horizon_days} días; estado "
            f"bajo {self.state_measure}, revaluación {self.pricing_measure}",
            "  Desv. estándar por nodo (pb): "
            + ", ".join(f"{t:g}a {s:.1f}" for t, s in zip(self.tenors, sd, strict=True)),
            f"  Mapeo: {self.mapping}",
        ]
        lines += [f"  Nota: {n}" for n in self.notes]
        return "\n".join(lines)


def _window(levels: pd.DataFrame, asof: Any, window: int | None) -> pd.DataFrame:
    df = levels.dropna()
    if asof is not None:
        df = df.loc[: pd.Timestamp(asof)]
    if window is not None:
        df = df.iloc[-(window + 1) :]
    if len(df) < 30:
        raise DataValidationError("Ventana con menos de 30 observaciones completas.")
    return df


def _tenors(levels: pd.DataFrame, tenors: list[float] | None) -> tuple[float, ...]:
    return tuple(float(t) for t in (tenors if tenors is not None else levels.columns))


def historical(
    levels: pd.DataFrame,
    *,
    horizon: int = 1,
    window: int | None = 750,
    asof: Any = None,
    tenors: list[float] | None = None,
) -> Scenarios:
    """Cambios observados a ``horizon`` días (solapados) en la ventana hasta ``asof``."""
    df = _window(levels, asof, window)
    changes = (df.shift(-horizon) - df).dropna().to_numpy()
    notes = ["Cambios solapados: use bootstrap por bloques para el IC."] if horizon > 1 else []
    return Scenarios(
        values=changes,
        tenors=_tenors(df, tenors),
        method=f"histórica ({len(df)} días)",
        state_measure="historical",
        pricing_measure="revaluación completa con la curva desplazada",
        horizon_days=horizon,
        seed=None,
        window=(str(df.index[0])[:10], str(df.index[-1])[:10]),
        mapping="cambio observado de cada nodo",
        notes=notes,
    )


def _ewma(x: np.ndarray, lam: float, init: int = 30) -> tuple[np.ndarray, float]:
    """σ_t (con datos hasta t−1) y σ pronosticada para el día siguiente al último."""
    var = np.empty_like(x)
    v = float(np.mean(x[:init] ** 2)) if x.size >= init else float(np.mean(x**2))
    for t in range(x.size):
        var[t] = v
        v = lam * v + (1 - lam) * x[t] ** 2
    return np.sqrt(var), float(np.sqrt(v))


def filtered_historical(
    levels: pd.DataFrame,
    *,
    horizon: int = 1,
    n: int = 10_000,
    vol: Literal["ewma", "garch"] = "ewma",
    lam: float = EWMA_LAMBDA,
    window: int | None = 1000,
    asof: Any = None,
    sqrt_h: bool = False,
    seed: int = 0,
    tenors: list[float] | None = None,
) -> Scenarios:
    """Histórica filtrada: innovaciones estandarizadas reescaladas a la volatilidad actual."""
    df = _window(levels, asof, window)
    d = df.diff().dropna().to_numpy()
    k = d.shape[1]
    sig = np.empty_like(d)
    sig_next = np.empty(k)
    params: list[dict[str, float]] = []
    for j in range(k):
        if vol == "ewma":
            sig[:, j], sig_next[j] = _ewma(d[:, j], lam)
        else:
            from arch import arch_model

            scale = 1e4
            res = arch_model(d[:, j] * scale, mean="Zero", vol="GARCH", p=1, q=1).fit(disp="off")
            sig[:, j] = np.asarray(res.conditional_volatility) / scale
            fc = res.forecast(horizon=1, reindex=False)
            sig_next[j] = float(np.sqrt(fc.variance.to_numpy()[-1, 0])) / scale
            params.append({str(key): float(v) for key, v in res.params.items()})
    z = d / sig
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, z.shape[0], size=(n, horizon))
    if horizon == 1 or sqrt_h:
        out = z[idx[:, 0]] * sig_next * (np.sqrt(horizon) if sqrt_h else 1.0)
        notes = ["Escalado por √h: supone innovaciones iid."] if sqrt_h and horizon > 1 else []
    else:
        out = np.zeros((n, k))
        s = np.tile(sig_next, (n, 1))
        for h in range(horizon):
            step = z[idx[:, h]] * s
            out += step
            if vol == "ewma":
                s = np.sqrt(lam * s**2 + (1 - lam) * step**2)
            else:
                om = np.array([p["omega"] for p in params]) / 1e8
                al = np.array([p["alpha[1]"] for p in params])
                be = np.array([p["beta[1]"] for p in params])
                s = np.sqrt(om + al * step**2 + be * s**2)
        notes = ["Horizonte por simulación de la trayectoria con la recursión de volatilidad."]
    notes.append(
        f"Volatilidad {vol} estimada sólo con datos hasta {str(df.index[-1])[:10]} (sin fuga)."
    )
    return Scenarios(
        values=out,
        tenors=_tenors(df, tenors),
        method=f"histórica filtrada ({vol})",
        state_measure="historical",
        pricing_measure="revaluación completa con la curva desplazada",
        horizon_days=horizon,
        seed=seed,
        window=(str(df.index[0])[:10], str(df.index[-1])[:10]),
        mapping="innovación estandarizada × volatilidad pronosticada de cada nodo",
        notes=notes,
    )


def factor_mc(
    model: FactorModel,
    *,
    n: int = 10_000,
    horizon: int = 1,
    dist: Literal["normal", "t"] = "normal",
    df: float = 5.0,
    seed: int = 0,
    antithetic: bool = False,
) -> Scenarios:
    """Monte Carlo de los factores con su covarianza (por día) escalada a ``horizon``."""
    rng = np.random.default_rng(seed)
    k = model.cov.shape[0]
    chol = np.linalg.cholesky(model.cov * horizon + 1e-12 * np.eye(k))
    m = (n + 1) // 2 if antithetic else n
    z = rng.standard_normal((m, k))
    if dist == "t":
        w = rng.chisquare(df, size=(m, 1)) / df
        z = z / np.sqrt(w) * np.sqrt((df - 2) / df)  # varianza unitaria
    if antithetic:
        z = np.vstack([z, -z])[:n]
    shocks = z @ chol.T
    return Scenarios(
        values=model.reconstruct(shocks),
        tenors=model.tenors,
        method=f"Monte Carlo de factores ({model.method}, {dist})",
        state_measure="P",
        pricing_measure="revaluación completa con la curva desplazada",
        horizon_days=horizon,
        seed=seed,
        window=model.window,
        mapping="nodos = cargas × choques de factor (sin residuo por nodo)",
        notes=["Escalado de la covarianza por h: supone cambios iid de los factores."]
        if horizon > 1
        else [],
    )


def short_rate_mc(
    fit: Any,
    tenors: list[float],
    *,
    horizon: int = 1,
    n: int = 10_000,
    params_q: Mapping[str, float] | None = None,
    model: Literal["vasicek", "cir"] | None = None,
    seed: int = 0,
    antithetic: bool = False,
    r0: float | None = None,
) -> Scenarios:
    """Estado r_T bajo ℙ (``ShortRateFit`` o ``RegimeFit``) revaluado con la fórmula afín ℚ.

    ``params_q`` por defecto: los de ℙ (λ = 0), lo que se declara en ``pricing_measure``.
    Con ``RegimeFit`` se usa el modelo de Vasicek con los parámetros ℚ declarados (obligatorios).
    """
    from tsinsurance.stochastics.affine import zero_coupon
    from tsinsurance.stochastics.regimes import RegimeFit

    rng = np.random.default_rng(seed)
    tt = np.asarray(tenors, dtype=float)
    if isinstance(fit, RegimeFit):
        if params_q is None or r0 is None:
            raise DataValidationError("Con regímenes declare params_q y r0 para la revaluación.")
        mdl: Literal["vasicek", "cir"] = "vasicek"
        pq = dict(params_q)
        pricing = "ℚ (Vasicek) con parámetros declarados"
        start = float(r0)
        paths, _ = fit.simulate(start, horizon, n, rng)
        state = "P (regímenes de Markov)"
    else:
        mdl = model or fit.model
        pq = dict(params_q) if params_q is not None else fit.params
        pricing = "ℚ con λ calibrado" if params_q is not None else "ℚ = ℙ (λ = 0, declarado)"
        start = fit.r_last if r0 is None else float(r0)
        paths = fit.simulate(start, horizon, n, rng, antithetic=antithetic)
        state = "P"
    r_t = paths[:, -1]
    z0 = -np.log(zero_coupon(mdl, pq, start, tt)) / tt
    z_t = -np.log(zero_coupon(mdl, pq, r_t[:, None], tt[None, :])) / tt[None, :]
    return Scenarios(
        values=z_t - z0,
        tenors=tuple(float(v) for v in tt),
        method=f"Monte Carlo de la tasa corta ({mdl}; estado {state})",
        state_measure="P",
        pricing_measure=pricing,
        horizon_days=horizon,
        seed=seed,
        window=None,
        mapping="z(τ) = −ln P(r_T, τ)/τ con la fórmula afín cerrada",
        notes=["Un factor: la curva se mueve sólo con r_T (pendiente y curvatura rígidas)."],
    )
