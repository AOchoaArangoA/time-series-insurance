"""Inferencia para paneles con pocas unidades y dependencia transversal (spec 006).

Revisión B2:

- La inferencia **principal** de un panel financiero es Driscoll-Kraay: robusta a
  dependencia transversal y temporal. Con T moderado el estimador HAC está sesgado hacia
  abajo y el t(T−1) previsto en el diseño **sobre-rechaza** (Monte Carlo de SC-004: ~9 %
  unilateral al 5 % con T = 36 y N = 11). Por eso:

  - el error se corrige por los grados de libertad que absorben los efectos fijos,
    c = n / (n − N − (T − 1)·[efectos de tiempo] − k);
  - el valor p usa la distribución de referencia **fixed-b** (Kiefer y Vogelsang 2005;
    Vogelsang 2012 para paneles con efectos fijos), simulada con el mismo T y el mismo
    ancho de banda de Bartlett. Con T grande coincide con la normal.

  :func:`driscoll_kraay` conserva la convención de ``plm::vcovSCC`` (HC0) y se verifica
  contra R; la corrección se aplica en :func:`tsinsurance.panel.fit_panel`.
- El **wild cluster bootstrap restringido** (WCR; Cameron, Gelbach y Miller 2008;
  MacKinnon y Webb 2017) es sólo una **sensibilidad**: supone clústeres independientes,
  lo que no se cumple con un factor común.
- Con G ≤ 12 clústeres se enumeran todas las combinaciones Rademacher (2^G), lo que da un
  resultado determinista. En otro caso se usan B extracciones con pesos de Webb (G < 12)
  o Rademacher, con semilla explícita.
- G₁ (unidades "tratadas" de una interacción): con G₁ < 2, ni los errores agrupados ni el
  WCR son válidos (Conley y Taber 2011), y el coeficiente es **no concluyente**.

Pruebas FE frente a RE:

- **Mundlak / efectos aleatorios correlacionados** (Mundlak 1978; Wooldridge 2010 §10.7.3,
  2021): se agregan las medias por unidad de los regresores (y, con dos vías, las medias por
  periodo) a una regresión de efectos aleatorios o MCO agrupado. H0: sus coeficientes son
  cero ⇒ RE consistente. Wald con error agrupado y F(q, G−1) con pocos grupos.
- **Hausman clásico**: sólo válido con errores homocedásticos y RE eficiente.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin

__all__ = [
    "FETest",
    "driscoll_kraay",
    "WildBootstrapResult",
    "dk_dof_correction",
    "dk_pvalue",
    "fixed_b_reference",
    "hausman_test",
    "mundlak_test",
    "treated_clusters",
    "wild_cluster_bootstrap",
]

_WEBB = np.array([-math.sqrt(1.5), -1.0, -math.sqrt(0.5), math.sqrt(0.5), 1.0, math.sqrt(1.5)])


def driscoll_kraay(
    frame: pd.DataFrame, y: str, x: Sequence[str], *, time_effects: bool, maxlag: int
) -> dict[str, float]:
    """Errores Driscoll-Kraay (1998) sobre los datos con efectos fijos.

    Convención de ``plm::vcovSCC(type="HC0")``: S_t = Σ_i x̃_it·ẽ_it; pesos de Bartlett
    w_j = 1 − j/(L+1); sin corrección de muestra pequeña. Es robusto a dependencia
    transversal arbitraria y a autocorrelación de hasta L periodos. Se verifica contra plm.
    """
    df = frame[[y, *x]].dropna()
    dm = _demean(df, [y, *x], time_effects)
    xv = dm[list(x)].to_numpy()
    yv = dm[y].to_numpy()
    xtx_inv = np.linalg.pinv(xv.T @ xv)
    beta = xtx_inv @ xv.T @ yv
    e = yv - xv @ beta
    scores = pd.DataFrame(xv * e[:, None], index=dm.index).groupby(level=1).sum().sort_index()
    h = scores.to_numpy()
    omega = h.T @ h
    for j in range(1, maxlag + 1):
        w = 1 - j / (maxlag + 1)
        g = h[j:].T @ h[:-j]
        omega += w * (g + g.T)
    var = xtx_inv @ omega @ xtx_inv
    return {c: float(math.sqrt(max(var[i, i], 0.0))) for i, c in enumerate(x)}


def dk_dof_correction(
    nobs: int, n_entities: int, n_periods: int, k: int, time_effects: bool
) -> float:
    """Factor c de la varianza DK por los parámetros que absorben los efectos fijos."""
    absorbed = n_entities + (n_periods - 1 if time_effects else 0)
    dof = nobs - absorbed - k
    return float(nobs / dof) if dof > 0 else float("nan")


@lru_cache(maxsize=64)
def fixed_b_reference(
    n_periods: int, bandwidth: int, draws: int = 19_999, seed: int = 20051
) -> np.ndarray:
    """Distribución de referencia fixed-b del t de Driscoll-Kraay (ordenada).

    Simula el modelo de localización con T = ``n_periods`` innovaciones gaussianas iid y
    el mismo estimador de Bartlett con L = ``bandwidth`` rezagos que usa DK: el
    numerador es la suma de las innovaciones y la varianza se estima con las innovaciones
    centradas (los *scores* de MCO suman cero). Es la aproximación fixed-b de Kiefer y
    Vogelsang (2005) evaluada en el T observado. Semilla fija: resultado determinista.

    References
    ----------
    Kiefer, N. M. y Vogelsang, T. J. (2005). A new asymptotic theory for
    heteroskedasticity-autocorrelation robust tests. *Econometric Theory*, 21(6),
    1130-1164.
    Vogelsang, T. J. (2012). Heteroskedasticity, autocorrelation, and spatial correlation
    robust inference in linear panel models with fixed-effects. *Journal of
    Econometrics*, 166(2), 303-319.
    """
    rng = np.random.default_rng(seed)
    out = np.empty(draws)
    chunk = max(1, min(draws, 2_000_000 // max(n_periods, 1)))
    for start in range(0, draws, chunk):
        m = min(chunk, draws - start)
        v = rng.standard_normal((m, n_periods))
        u = v - v.mean(axis=1, keepdims=True)
        omega = (u * u).sum(axis=1)
        for j in range(1, bandwidth + 1):
            omega += 2 * (1 - j / (bandwidth + 1)) * (u[:, j:] * u[:, :-j]).sum(axis=1)
        out[start : start + m] = v.sum(axis=1) / np.sqrt(omega)
    out.sort()
    return out


def dk_pvalue(
    tstat: float,
    n_periods: int,
    alternative: Literal["two-sided", "greater", "less"] = "two-sided",
    bandwidth: int | None = None,
) -> float:
    """Valor p de un t de Driscoll-Kraay.

    Con ``bandwidth`` usa la referencia fixed-b (:func:`fixed_b_reference`); sin él, la
    t(T−1) (que sobre-rechaza con T moderado; sólo por compatibilidad).
    """
    if not np.isfinite(tstat):
        return float("nan")
    if bandwidth is not None:
        ref = fixed_b_reference(int(n_periods), int(bandwidth))
        n = len(ref)
        upper = (1 + n - np.searchsorted(ref, tstat, side="left")) / (1 + n)
        lower = (1 + np.searchsorted(ref, tstat, side="right")) / (1 + n)
        if alternative == "greater":
            return float(upper)
        if alternative == "less":
            return float(lower)
        return float(min(1.0, 2 * min(upper, lower)))
    df = max(n_periods - 1, 1)
    if alternative == "greater":
        return float(stats.t.sf(tstat, df))
    if alternative == "less":
        return float(stats.t.cdf(tstat, df))
    return float(2 * stats.t.sf(abs(tstat), df))


def treated_clusters(frame: pd.DataFrame, column: str, tol: float = 1e-12) -> int:
    """Unidades con algún valor no nulo del regresor (G₁ de una interacción x_t·D_i)."""
    s = frame[column].astype(float).abs()
    return int((s.groupby(level=0).max() > tol).sum())


def _demean(frame: pd.DataFrame, cols: Sequence[str], time_effects: bool) -> pd.DataFrame:
    df = frame[list(cols)].astype(float)
    out = df - df.groupby(level=0).transform("mean")
    if time_effects:
        # Desbalanceo: alternar el centrado por unidad y por periodo hasta converger.
        for _ in range(200):
            prev = out
            out = out - out.groupby(level=1).transform("mean")
            out = out - out.groupby(level=0).transform("mean")
            if float((out - prev).abs().to_numpy().max()) < 1e-12:
                break
    return out


def _ols_cr1(
    yv: np.ndarray, xv: np.ndarray, groups: np.ndarray, k: int
) -> tuple[np.ndarray, float]:
    xtx_inv = np.linalg.pinv(xv.T @ xv)
    beta = xtx_inv @ xv.T @ yv
    e = yv - xv @ beta
    meat = np.zeros((xv.shape[1], xv.shape[1]))
    for g in np.unique(groups):
        idx = groups == g
        s = xv[idx].T @ e[idx]
        meat += np.outer(s, s)
    n, p = xv.shape
    g_count = len(np.unique(groups))
    adj = g_count / (g_count - 1) * (n - 1) / (n - p)
    var = adj * xtx_inv @ meat @ xtx_inv
    return beta, float(beta[k] / math.sqrt(max(var[k, k], 1e-300)))


@dataclass(frozen=True, slots=True)
class WildBootstrapResult(ResultMixin):
    """Wild cluster bootstrap restringido para un coeficiente (H0: β = 0)."""

    coefficient: str
    tstat: float
    pvalue_two_sided: float
    pvalue_greater: float
    pvalue_less: float
    n_clusters: int
    weights: str
    draws: int
    enumerated: bool
    note: str = (
        "Sensibilidad: supone clústeres independientes; con un factor común use Driscoll-Kraay."
    )

    def summary(self) -> str:
        """Resumen legible."""
        return (
            f"WCR {self.coefficient}: t={self.tstat:+.3f} p(2c)={self.pvalue_two_sided:.4f} "
            f"p(>)={self.pvalue_greater:.4f} G={self.n_clusters} {self.weights} "
            f"{'enumeración completa' if self.enumerated else f'B={self.draws}'}"
        )


def wild_cluster_bootstrap(
    frame: pd.DataFrame,
    y: str,
    x: Sequence[str],
    coefficient: str,
    *,
    time_effects: bool = True,
    draws: int = 9999,
    seed: int = 0,
    weights: Literal["auto", "rademacher", "webb"] = "auto",
) -> WildBootstrapResult:
    """WCR con efectos de unidad (y de tiempo), agrupado por unidad."""
    if coefficient not in x:
        raise DataValidationError(f"'{coefficient}' no está entre los regresores.")
    df = frame[[y, *x]].dropna()
    dm = _demean(df, [y, *x], time_effects)
    groups = pd.factorize(df.index.get_level_values(0))[0]
    g_count = len(np.unique(groups))
    if g_count < 3:
        raise DataValidationError("El WCR necesita al menos 3 unidades.")
    xv = dm[list(x)].to_numpy()
    yv = dm[y].to_numpy()
    k = list(x).index(coefficient)
    _, t_obs = _ols_cr1(yv, xv, groups, k)
    keep = [j for j in range(len(x)) if j != k]
    xr = xv[:, keep]
    if xr.shape[1]:
        br = np.linalg.pinv(xr.T @ xr) @ xr.T @ yv
        fitted_r = xr @ br
    else:
        fitted_r = np.zeros_like(yv)
    resid_r = yv - fitted_r
    kind = weights
    if kind == "auto":
        kind = "rademacher" if g_count > 12 else "webb"
    enumerate_all = g_count <= 12 and kind == "rademacher" or (weights == "auto" and g_count <= 12)
    if enumerate_all:
        kind = "rademacher"
        combos = np.array(list(itertools.product([-1.0, 1.0], repeat=g_count)))
    else:
        rng = np.random.default_rng(seed)
        combos = (
            rng.choice(_WEBB, size=(draws, g_count))
            if kind == "webb"
            else rng.choice([-1.0, 1.0], size=(draws, g_count))
        )
    t_star = np.empty(len(combos))
    for b, w in enumerate(combos):
        y_star = fitted_r + resid_r * w[groups]
        _, t_star[b] = _ols_cr1(y_star, xv, groups, k)
    return WildBootstrapResult(
        coefficient=coefficient,
        tstat=t_obs,
        pvalue_two_sided=float(np.mean(np.abs(t_star) >= abs(t_obs))),
        pvalue_greater=float(np.mean(t_star >= t_obs)),
        pvalue_less=float(np.mean(t_star <= t_obs)),
        n_clusters=g_count,
        weights=kind,
        draws=len(combos),
        enumerated=enumerate_all,
    )


@dataclass(frozen=True, slots=True)
class FETest(ResultMixin):
    """Comparación de efectos fijos y aleatorios."""

    mundlak_stat: float
    mundlak_df: int
    mundlak_pvalue: float
    mundlak_distribution: str
    hausman_stat: float | None
    hausman_pvalue: float | None
    recommendation: str
    notes: list[str]

    def summary(self) -> str:
        """Resumen legible."""
        h = (
            f"Hausman clásico χ²={self.hausman_stat:.3f} p={self.hausman_pvalue:.4f}"
            if self.hausman_stat is not None and self.hausman_pvalue is not None
            else "Hausman clásico: no disponible"
        )
        return (
            f"Mundlak/CRE (robusta): {self.mundlak_distribution}={self.mundlak_stat:.3f} "
            f"p={self.mundlak_pvalue:.4f} · {h} · recomendación: {self.recommendation}"
        )


def mundlak_test(
    frame: pd.DataFrame,
    y: str,
    x: Sequence[str],
    *,
    time_effects: bool = False,
    alpha: float = 0.05,
) -> FETest:
    """Prueba Mundlak/CRE robusta (agrupada por unidad) de FE frente a RE."""
    import statsmodels.api as sm

    df = frame[[y, *x]].dropna().astype(float)
    means = df[list(x)].groupby(level=0).transform("mean").add_suffix("__mean_i")
    parts = [df[list(x)], means]
    if time_effects:
        tdum = pd.get_dummies(df.index.get_level_values(1), prefix="t", drop_first=True).astype(
            float
        )
        tdum.index = df.index
        parts.append(tdum)
        # Medias por unidad de las dummies de tiempo (desbalanceo; Wooldridge 2021).
        sizes = df.groupby(level=0).size()
        if bool((sizes != sizes.iloc[0]).any()):
            parts.append(tdum.groupby(level=0).transform("mean").add_suffix("__mean_i"))
    design = sm.add_constant(pd.concat(parts, axis=1))
    design = design.loc[:, design.std() > 0].assign(const=1.0)
    groups = pd.factorize(df.index.get_level_values(0))[0]
    fit = sm.OLS(df[y], design).fit(cov_type="cluster", cov_kwds={"groups": groups})
    test_cols = [c for c in means.columns if c in design.columns]
    r = np.zeros((len(test_cols), design.shape[1]))
    for i, c in enumerate(test_cols):
        r[i, list(design.columns).index(c)] = 1.0
    wald = fit.wald_test(r, use_f=False, scalar=True)
    stat = float(wald.statistic)
    q = len(test_cols)
    g = len(np.unique(groups))
    notes = []
    if g < 30:
        f_stat = stat / q
        pval = float(stats.f.sf(f_stat, q, max(g - 1, 1)))
        dist, shown = f"F({q},{g - 1})", f_stat
        notes.append(f"Pocos grupos (G={g}): Wald reportado como F(q, G−1).")
    else:
        pval = float(stats.chi2.sf(stat, q))
        dist, shown = f"χ²({q})", stat
    h_stat, h_p = _hausman(df, y, x)
    rec = (
        "efectos fijos (los efectos de unidad están correlacionados con los regresores)"
        if pval < alpha
        else "efectos aleatorios son admisibles (no se rechaza la nula de Mundlak)"
    )
    if g < 30:
        notes.append(
            "Con pocas unidades la varianza de los efectos de unidad es poco confiable; con T "
            "grande θ ≈ 1 y RE ≈ FE."
        )
    return FETest(shown, q, pval, dist, h_stat, h_p, rec, notes)


def _hausman(df: pd.DataFrame, y: str, x: Sequence[str]) -> tuple[float | None, float | None]:
    try:
        from linearmodels.panel import PanelOLS, RandomEffects
    except ImportError:  # pragma: no cover
        return None, None
    fe = PanelOLS(df[y], df[list(x)], entity_effects=True).fit(cov_type="unadjusted")
    re = RandomEffects(df[y], df[list(x)].assign(const=1.0)).fit(cov_type="unadjusted")
    b = (fe.params - re.params[list(x)]).to_numpy()
    # "sigmamore": ambas covarianzas con la varianza residual de FE, para que la diferencia
    # sea definida positiva en muestras finitas (convención de Stata/plm).
    scale = float(fe.s2) / float(re.s2) if float(re.s2) > 0 else 1.0
    v = fe.cov.to_numpy() - scale * re.cov.loc[list(x), list(x)].to_numpy()
    try:
        stat = float(b @ np.linalg.pinv(v) @ b)
    except np.linalg.LinAlgError:
        return None, None
    if stat < 0:
        return stat, None
    return stat, float(stats.chi2.sf(stat, len(x)))


def hausman_test(
    frame: pd.DataFrame, y: str, x: Sequence[str]
) -> tuple[float | None, float | None]:
    """Hausman clásico (sólo válido con errores homocedásticos y RE eficiente)."""
    return _hausman(frame[[y, *x]].dropna().astype(float), y, x)
