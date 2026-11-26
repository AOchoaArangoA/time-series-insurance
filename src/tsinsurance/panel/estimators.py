"""Estimación de paneles con diagnóstico y supuestos causales explícitos (spec 006, US1).

Referencia principal: Facure, *Causal Inference for the Brave and True*, cap. 14 (Panel
Data and Fixed Effects). Los efectos fijos de unidad eliminan el sesgo de confusores
**constantes en el tiempo** mediante la transformación *within* (restar la media de cada
unidad). **No** eliminan confusores que cambian en el tiempo ni la causalidad inversa, y
suponen un efecto **homogéneo** entre unidades. Los regresores constantes por unidad se
anulan. Efectos aleatorios: Wooldridge (2010, cap. 10); el libro no los trata.

Motor: :mod:`linearmodels` (K. Sheppard). Driscoll-Kraay es ``cov_type="kernel"`` de
``PanelOLS`` (Bartlett, ancho de banda declarado).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin

__all__ = [
    "ASSUMPTIONS",
    "Cov",
    "Estimator",
    "PanelResult",
    "absorbed_regressors",
    "fit_panel",
    "to_panel",
]

Estimator = Literal["pooled", "fe", "twfe", "fd", "re"]
Cov = Literal[
    "unadjusted",
    "robust",
    "clustered_entity",
    "clustered_time",
    "clustered_twoway",
    "driscoll_kraay",
]

FEW_CLUSTERS = 30
LOW_WITHIN_RATIO = 0.1

ASSUMPTIONS: dict[str, list[str]] = {
    "pooled": [
        "Supone que no hay confusores no observados correlacionados con los regresores "
        "(ni constantes por unidad ni comunes en el tiempo): en general, sesgado.",
    ],
    "fe": [
        "Controla confusores no observados CONSTANTES EN EL TIEMPO de cada unidad "
        "(transformación within; Facure, cap. 14).",
        "NO controla confusores que cambian en el tiempo.",
        "NO controla la causalidad inversa ni la retroalimentación de y hacia x.",
        "Supone un efecto homogéneo entre unidades (una pendiente común).",
        "Los regresores constantes por unidad se anulan y no se pueden estimar.",
    ],
    "twfe": [
        "Controla confusores constantes por unidad Y los comunes a todas las unidades en "
        "cada periodo (efectos de tiempo: mercado, inflación, política monetaria).",
        "NO controla confusores que cambian en el tiempo de forma distinta entre unidades.",
        "NO controla la causalidad inversa.",
        "Un regresor común a todas las unidades queda absorbido por los efectos de tiempo: "
        "sólo su interacción con una característica de la unidad (efecto diferencial) es "
        "estimable.",
        "Supone un efecto homogéneo entre unidades.",
    ],
    "fd": [
        "Primeras diferencias: elimina lo constante por unidad, como los efectos fijos; más "
        "eficiente que within si los errores son un paseo aleatorio.",
        "NO controla confusores que cambian en el tiempo ni la causalidad inversa.",
    ],
    "re": [
        "Efectos aleatorios: más eficiente que FE, pero SÓLO consistente si los efectos de "
        "unidad no están correlacionados con los regresores. Verifíquelo con la prueba de "
        "Mundlak (robusta) antes de usarlo (Wooldridge 2010).",
    ],
}


@dataclass(frozen=True, slots=True)
class PanelResult(ResultMixin):
    """Resultado de una estimación de panel."""

    estimator: str
    cov_type: str
    params: dict[str, float]
    std_errors: dict[str, float]
    tstats: dict[str, float]
    pvalues: dict[str, float]
    nobs: int
    n_entities: int
    n_periods: int
    balanced: bool
    absorbed: dict[str, str]
    low_within: list[str]
    assumptions: list[str]
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    re_components: dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        """Resumen legible."""
        lines = [
            f"Panel {self.estimator.upper()} · errores {self.cov_type} · n={self.nobs} "
            f"({self.n_entities} unidades × {self.n_periods} periodos, "
            f"{'balanceado' if self.balanced else 'desbalanceado'})",
        ]
        for k, v in self.params.items():
            lines.append(
                f"  {k:<24} {v:+.5f}  ee={self.std_errors[k]:.5f}  t={self.tstats[k]:+.2f}  "
                f"p={self.pvalues[k]:.4f}"
            )
        for k, why in self.absorbed.items():
            lines.append(f"  [absorbido] {k}: {why}")
        lines += [f"  Supuesto: {a}" for a in self.assumptions]
        lines += [f"  Advertencia: {w}" for w in self.warnings]
        return "\n".join(lines)


def to_panel(frame: pd.DataFrame, entity: str = "entity", time: str = "time") -> pd.DataFrame:
    """Índice (unidad, periodo) ordenado; valida duplicados y fechas."""
    df = frame.set_index([entity, time]) if entity in frame.columns else frame.copy()
    if not isinstance(df.index, pd.MultiIndex) or df.index.nlevels != 2:
        raise DataValidationError("El panel necesita un índice (unidad, periodo).")
    if df.index.has_duplicates:
        raise DataValidationError("El panel tiene pares (unidad, periodo) duplicados.")
    lvl = df.index.levels[1]
    if not isinstance(lvl, pd.DatetimeIndex) and not pd.api.types.is_integer_dtype(lvl):
        raise DataValidationError("El periodo debe ser fecha o entero.")
    return df.sort_index()


def absorbed_regressors(
    df: pd.DataFrame, x: Sequence[str], *, entity_effects: bool, time_effects: bool
) -> tuple[dict[str, str], list[str]]:
    """Regresores absorbidos por los efectos y regresores con poca variación within."""
    absorbed: dict[str, str] = {}
    low: list[str] = []
    for col in x:
        s = df[col].astype(float)
        scale = float(s.std()) or 1.0
        if entity_effects:
            within_sd = float(s.groupby(level=0).transform(lambda v: v - v.mean()).std())
            if within_sd <= 1e-10 * scale:
                absorbed[col] = "constante dentro de cada unidad: lo absorben los efectos de unidad"
                continue
            if within_sd < LOW_WITHIN_RATIO * scale:
                low.append(col)
        if time_effects:
            across = float(s.groupby(level=1).transform(lambda v: v - v.mean()).std())
            if across <= 1e-10 * scale:
                absorbed[col] = (
                    "común a todas las unidades en cada periodo: lo absorben los efectos de "
                    "tiempo (use su interacción con una característica de la unidad)"
                )
    return absorbed, low


def _bandwidth(n_periods: int) -> int:
    return max(1, math.floor(4 * (n_periods / 100) ** (2 / 9)))


def fit_panel(
    frame: pd.DataFrame,
    y: str,
    x: Sequence[str],
    *,
    estimator: Estimator = "fe",
    cov: Cov = "driscoll_kraay",
    bandwidth: int | None = None,
) -> PanelResult:
    """Estima un panel con el estimador y los errores declarados.

    Con ``cov="clustered_entity"`` y menos de 30 unidades agrega una advertencia (los
    errores agrupados con pocos grupos no son confiables; Cameron, Gelbach y Miller 2008)
    y reporta en ``diagnostics`` los errores Driscoll-Kraay como alternativa. El wild
    cluster bootstrap está en :func:`tsinsurance.panel.inference.wild_cluster_bootstrap`.
    """
    from linearmodels.panel import FirstDifferenceOLS, PanelOLS, PooledOLS, RandomEffects

    df = to_panel(frame)[[y, *x]].dropna()
    entity_fx = estimator in ("fe", "twfe")
    time_fx = estimator == "twfe"
    absorbed, low = absorbed_regressors(df, x, entity_effects=entity_fx, time_effects=time_fx)
    if estimator == "fd":
        absorbed.update(
            {
                c: "constante dentro de cada unidad: se anula en primeras diferencias"
                for c in absorbed_regressors(df, x, entity_effects=True, time_effects=False)[0]
            }
        )
    keep = [c for c in x if c not in absorbed]
    if not keep:
        raise DataValidationError(f"Todos los regresores quedan absorbidos: {absorbed}")
    n_entities = int(df.index.get_level_values(0).nunique())
    n_periods = int(df.index.get_level_values(1).nunique())
    balanced = len(df) == n_entities * n_periods
    exog = df[keep].astype(float)
    if estimator in ("pooled", "re"):
        exog = exog.assign(const=1.0)
    bw = bandwidth if bandwidth is not None else _bandwidth(n_periods)
    fit_kw: dict[str, Any]
    if cov == "unadjusted":
        fit_kw = {"cov_type": "unadjusted"}
    elif cov == "robust":
        fit_kw = {"cov_type": "robust"}
    elif cov == "clustered_entity":
        fit_kw = {"cov_type": "clustered", "cluster_entity": True}
    elif cov == "clustered_time":
        fit_kw = {"cov_type": "clustered", "cluster_time": True}
    elif cov == "clustered_twoway":
        fit_kw = {"cov_type": "clustered", "cluster_entity": True, "cluster_time": True}
    else:
        fit_kw = {"cov_type": "kernel", "kernel": "bartlett", "bandwidth": bw}
    yy = df[y].astype(float)
    if estimator == "pooled":
        model: Any = PooledOLS(yy, exog)
    elif estimator == "re":
        model = RandomEffects(yy, exog)
    elif estimator == "fd":
        model = FirstDifferenceOLS(yy, exog)
    else:
        model = PanelOLS(yy, exog, entity_effects=entity_fx, time_effects=time_fx)
    res = model.fit(**fit_kw)
    warnings: list[str] = []
    diagnostics: dict[str, Any] = {"bandwidth_driscoll_kraay": bw}
    if cov in ("clustered_entity", "clustered_twoway") and n_entities < FEW_CLUSTERS:
        warnings.append(
            f"Sólo {n_entities} unidades: los errores agrupados por unidad no son confiables "
            "(tamaño mayor al nominal). Use Driscoll-Kraay o el wild cluster bootstrap."
        )
        if estimator not in ("fd", "re"):
            alt = model.fit(cov_type="kernel", kernel="bartlett", bandwidth=bw)
            diagnostics["driscoll_kraay_std_errors"] = {
                k: float(v) for k, v in alt.std_errors.items()
            }
    if low:
        warnings.append(
            f"Poca variación within (< {LOW_WITHIN_RATIO:.0%} de la total) en {low}: "
            "coeficientes imprecisos."
        )
    if absorbed:
        warnings.append(f"Regresores absorbidos y excluidos: {sorted(absorbed)}")
    re_comp: dict[str, float] = {}
    if estimator == "re":
        vd = res.variance_decomposition
        re_comp = {
            "sigma2_entity": float(vd["Effects"]),
            "sigma2_idiosyncratic": float(vd["Residual"]),
            "theta_mean": float(np.asarray(res.theta).mean()),
        }
        if re_comp["sigma2_entity"] <= 0:
            warnings.append("Varianza de unidad ≤ 0: efectos aleatorios equivale a MCO agrupado.")
    try:
        cd = res.pesaran_cd if hasattr(res, "pesaran_cd") else None
        if cd is not None:
            diagnostics["pesaran_cd"] = {"stat": float(cd.stat), "pvalue": float(cd.pval)}
    except Exception:  # noqa: BLE001 - diagnóstico opcional de linearmodels
        pass
    return PanelResult(
        estimator=estimator,
        cov_type=cov,
        params={k: float(v) for k, v in res.params.items()},
        std_errors={k: float(v) for k, v in res.std_errors.items()},
        tstats={k: float(v) for k, v in res.tstats.items()},
        pvalues={k: float(v) for k, v in res.pvalues.items()},
        nobs=int(res.nobs),
        n_entities=n_entities,
        n_periods=n_periods,
        balanced=balanced,
        absorbed=absorbed,
        low_within=low,
        assumptions=list(ASSUMPTIONS[estimator]),
        warnings=warnings,
        diagnostics=diagnostics,
        re_components=re_comp,
    )
