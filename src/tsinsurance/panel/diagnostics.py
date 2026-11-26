"""Diagnósticos de paneles (spec 006; Principio I y revisión B3, I2, I5).

- **Correlación serial** de Wooldridge (2010, §10.6.3): en primeras diferencias, los
  residuos de un modelo de efectos fijos con errores iid tienen corr(Δe_t, Δe_{t−1}) =
  −0,5. Se prueba H0: el coeficiente de Δe_{t−1} es −0,5, con error agrupado por unidad.
- **Dependencia transversal** CD de Pesaran (2004, 2015): para residuos SIN efectos de
  tiempo; con efectos de tiempo la CD clásica no es válida (Juodis y Reese 2022) y se
  advierte.
- **Estacionariedad** (ADF + KPSS con la regla jerárquica del paquete) de los regresores
  y de y por unidad.
- **ARCH-LM** por unidad sobre los residuos.
- **Estabilidad**: CUSUM de los residuos OLS (Ploberger y Krämer 1992) sobre la serie
  apilada por periodo (media transversal de los residuos *within*).
- **Persistencia** de los regresores: AR(1) y correlación de sus innovaciones con los
  residuos. Un regresor predeterminado y persistente con innovaciones correlacionadas
  sesga el estimador within en O(1/T): es un sesgo tipo Stambaugh en panel (Hjalmarsson
  2008).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from tsinsurance.diagnostics.descriptive import arch_lm
from tsinsurance.diagnostics.stationarity import stationarity
from tsinsurance.errors import TSInsuranceError
from tsinsurance.results import ResultMixin

__all__ = ["PanelDiagnostics", "panel_diagnostics", "pesaran_cd", "wooldridge_serial"]

PERSISTENCE_RHO = 0.9
PERSISTENCE_CORR = 0.3


def wooldridge_serial(frame: pd.DataFrame, y: str, x: Sequence[str]) -> dict[str, float]:
    """Prueba de Wooldridge de correlación serial en paneles (H0: sin AR(1) en e_it)."""
    df = frame[[y, *x]].dropna()
    d = df.groupby(level=0).diff().dropna()
    if len(d) < 10:
        raise TSInsuranceError("Panel demasiado corto para la prueba de Wooldridge.")
    # Como plm::pwfdtest(h0="fe"): FD con intercepto; residuos sobre su rezago con
    # intercepto; error agrupado por unidad sin corrección de muestra pequeña (HC0).
    fd = sm.OLS(d[y], sm.add_constant(d[list(x)])).fit()
    e = pd.Series(fd.resid, index=d.index)
    lag = e.groupby(level=0).shift(1)
    m = pd.concat({"e": e, "lag": lag}, axis=1).dropna()
    groups = m.index.get_level_values(0)
    fit = sm.OLS(m["e"], sm.add_constant(m[["lag"]])).fit(
        cov_type="cluster",
        cov_kwds={"groups": pd.factorize(groups)[0], "use_correction": False},
    )
    coef = float(fit.params["lag"])
    se = float(fit.bse["lag"])
    f = ((coef + 0.5) / se) ** 2
    g = int(pd.Series(groups).nunique())
    # Valor p con F(1, G−1): más conservador que plm (que usa los grados de libertad de las
    # observaciones) cuando hay pocas unidades.
    return {"coef": coef, "F": f, "pvalue": float(stats.f.sf(f, 1, max(g - 1, 1)))}


def pesaran_cd(residuals: pd.Series, min_overlap: int = 3) -> dict[str, float]:
    """CD de Pesaran sobre residuos con índice (unidad, periodo); admite desbalanceo."""
    wide = residuals.unstack(level=0)
    cols = list(wide.columns)
    total, pairs = 0.0, 0
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            both = wide[[cols[i], cols[j]]].dropna()
            t = len(both)
            if t < min_overlap:
                continue
            a, b = both.iloc[:, 0], both.iloc[:, 1]
            a, b = a - a.mean(), b - b.mean()
            denom = math.sqrt(float((a**2).sum() * (b**2).sum()))
            if denom == 0:
                continue
            rho = float((a * b).sum()) / denom
            total += math.sqrt(t) * rho
            pairs += 1
    if pairs == 0:
        raise TSInsuranceError("Sin pares de unidades con periodos comunes para la CD.")
    n = len(cols)
    cd = math.sqrt(2.0 / (n * (n - 1))) * total
    return {"CD": cd, "pvalue": float(2 * stats.norm.sf(abs(cd))), "pairs": float(pairs)}


@dataclass(frozen=True, slots=True)
class PanelDiagnostics(ResultMixin):
    """Diagnósticos del panel; ``passed`` resume el Principio I."""

    serial: dict[str, float]
    cross_section: dict[str, float]
    stationarity: dict[str, Any]
    arch: dict[str, float]
    persistence: dict[str, dict[str, float]]
    stability: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    passed: bool = True

    def summary(self) -> str:
        """Resumen legible."""
        lines = [
            f"Diagnósticos del panel: {'superados' if self.passed else 'NO superados'}",
            f"  Wooldridge (AR(1)): F={self.serial['F']:.2f} p={self.serial['pvalue']:.4f}",
            f"  CD de Pesaran: {self.cross_section['CD']:+.2f} "
            f"p={self.cross_section['pvalue']:.4f}",
        ]
        lines += [f"  Advertencia: {w}" for w in self.warnings]
        return "\n".join(lines)


def panel_diagnostics(
    frame: pd.DataFrame,
    y: str,
    x: Sequence[str],
    *,
    time_effects: bool = False,
    alpha: float = 0.05,
) -> PanelDiagnostics:
    """Diagnósticos del Principio I para un panel con efectos de unidad."""
    df = frame[[y, *x]].dropna()
    warnings: list[str] = []
    passed = True
    serial = wooldridge_serial(df, y, x)
    if serial["pvalue"] < alpha:
        warnings.append(
            "Correlación serial en los residuos (Wooldridge): use errores Driscoll-Kraay."
        )
    # Residuos within SIN efectos de tiempo para la CD (I5).
    dm = df - df.groupby(level=0).transform("mean")
    fit = sm.OLS(dm[y], dm[list(x)]).fit()
    resid = pd.Series(fit.resid, index=dm.index)
    cd = pesaran_cd(resid)
    if cd["pvalue"] < alpha:
        warnings.append(
            "Dependencia transversal fuerte (CD de Pesaran): los errores agrupados por "
            "unidad no son válidos; use Driscoll-Kraay o efectos de tiempo."
        )
    if time_effects:
        warnings.append(
            "Con efectos de tiempo, la CD clásica no es válida (Juodis y Reese 2022); se "
            "reporta la CD sin efectos de tiempo."
        )
    station: dict[str, Any] = {}
    for col in x:
        common = df[col].groupby(level=1).nunique().max() == 1
        series = df[col].groupby(level=1).first() if common else df[col].groupby(level=1).mean()
        try:
            rep = stationarity(series.dropna(), alpha=alpha, breaks=False)
            station[col] = rep.integration_order
            if rep.integration_order not in (0, None):
                passed = False
                warnings.append(
                    f"'{col}' es I({rep.integration_order}): regresión desbalanceada "
                    "(retorno estacionario sobre un regresor no estacionario)."
                )
        except TSInsuranceError as exc:
            station[col] = f"no evaluado: {exc}"
    arch_p: dict[str, float] = {}
    for unit, r in resid.groupby(level=0):
        if len(r) > 30:
            arch_p[str(unit)] = float(arch_lm(r.to_numpy()).p_value or 1.0)
    if arch_p and sum(p < alpha for p in arch_p.values()) > len(arch_p) / 2:
        warnings.append("ARCH en los residuos de la mayoría de las unidades.")
        passed = False
    stability: dict[str, float] = {}
    by_period = resid.groupby(level=1).mean()
    # Con efectos de tiempo la media por periodo de los residuos es el factor común que el
    # modelo absorbe: el CUSUM detectaría ciclos de mercado, no inestabilidad del modelo.
    if not time_effects and len(by_period) >= 20:
        from statsmodels.stats.diagnostic import breaks_cusumolsresid

        stat, pval, _ = breaks_cusumolsresid(by_period.to_numpy(), ddof=len(x))
        stability = {"cusum": float(stat), "pvalue": float(pval)}
        if pval < alpha:
            passed = False
            warnings.append(
                "Inestabilidad de los parámetros (CUSUM de los residuos apilados por periodo)."
            )
    persistence: dict[str, dict[str, float]] = {}
    for col in x:
        xs = df[col].groupby(level=1).mean()
        if len(xs) < 20:
            continue
        rho = float(np.corrcoef(xs.to_numpy()[1:], xs.to_numpy()[:-1])[0, 1])
        innov = xs - rho * xs.shift(1)
        r_t = resid.groupby(level=1).mean().reindex(innov.index)
        both = pd.concat([innov, r_t], axis=1).dropna()
        corr = (
            float(np.corrcoef(both.iloc[:, 0], both.iloc[:, 1])[0, 1])
            if len(both) > 10
            else float("nan")
        )
        persistence[col] = {"rho": rho, "innovation_corr": corr}
        if rho > PERSISTENCE_RHO and abs(corr) > PERSISTENCE_CORR:
            passed = False
            warnings.append(
                f"'{col}' es persistente (ρ={rho:.2f}) con innovaciones correlacionadas con "
                f"los residuos ({corr:+.2f}): sesgo tipo Stambaugh en panel (Hjalmarsson 2008)."
            )
    return PanelDiagnostics(
        serial=serial,
        cross_section=cd,
        stationarity=station,
        arch=arch_p,
        persistence=persistence,
        stability=stability,
        warnings=warnings,
        passed=passed,
    )
