"""Diferencias en diferencias y estudio de evento (spec 006, US4).

Referencia: Facure, cap. 13 (Difference-in-Differences). El ATET se identifica con el
supuesto de **tendencias paralelas**: sin tratamiento, los tratados habrían seguido la
misma tendencia que los controles.

- **Estimador**: efectos fijos de unidad y de tiempo con D_it = tratado_i × post_t. Con
  2 × 2 equivale a la regresión con interacción del libro.
- **Estudio de evento**: coeficientes por periodo relativo al evento (el periodo −1 es la
  referencia) y una prueba conjunta de que los *leads* son cero. **No rechazar no prueba**
  tendencias paralelas: puede ser falta de potencia, y condicionar el análisis al
  resultado de esta prueba sesga la inferencia (Roth 2022).
- **Supuesto de no anticipación**: la fecha del evento debe ser la del anuncio.
- **Una sola unidad tratada**: los errores agrupados no son válidos (Conley y Taber 2011).
  Se usa inferencia por permutación, con placebos sobre las unidades de control.
- **Adopción escalonada**: el TWFE clásico está sesgado con efectos heterogéneos
  (Goodman-Bacon 2021). Se advierte; los estimadores robustos quedan fuera de alcance.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin

__all__ = ["DiDResult", "diff_in_diff"]


@dataclass(frozen=True, slots=True)
class DiDResult(ResultMixin):
    """ATET, estudio de evento y prueba de tendencias previas."""

    atet: float
    se: float | None
    pvalue: float
    inference: str
    n_treated: int
    n_control: int
    event_study: dict[int, dict[str, float]]
    pretrend_stat: float | None
    pretrend_pvalue: float | None
    warnings: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Resumen legible."""
        se = f"ee={self.se:.4f}" if self.se is not None else "ee n/d"
        lines = [
            f"DiD (TWFE): ATET={self.atet:+.4f} {se} p={self.pvalue:.4f} ({self.inference}); "
            f"tratados={self.n_treated}, controles={self.n_control}",
        ]
        if self.pretrend_pvalue is not None:
            lines.append(
                f"  Tendencias previas (leads = 0): Wald={self.pretrend_stat:.3f} "
                f"p={self.pretrend_pvalue:.4f} (no rechazar NO prueba tendencias paralelas)"
            )
        lines += [f"  Advertencia: {w}" for w in self.warnings]
        return "\n".join(lines)


def _pre_sd(df: pd.DataFrame, y: str, pos: Mapping[Any, int], ev_pos: int) -> dict[Any, float]:
    """Desviación estándar de los residuos de dos vías de cada unidad antes del evento."""
    pre = df[[y]][[pos[t] < ev_pos for t in df.index.get_level_values(1)]]
    dm = pre[y] - pre[y].groupby(level=0).transform("mean")
    dm = dm - dm.groupby(level=1).transform("mean")
    return {u: float(v) for u, v in dm.groupby(level=0).std(ddof=1).items()}


def _twfe(df: pd.DataFrame, y: str, cols: list[str], cluster: bool) -> Any:
    from linearmodels.panel import PanelOLS

    model = PanelOLS(df[y], df[cols], entity_effects=True, time_effects=True)
    if cluster:
        return model.fit(cov_type="clustered", cluster_entity=True)
    return model.fit(cov_type="unadjusted")


def diff_in_diff(
    frame: pd.DataFrame,
    y: str,
    treated: Mapping[str, Any],
    *,
    leads: int = 4,
    lags: int = 4,
    alpha: float = 0.05,
) -> DiDResult:
    """DiD con efectos fijos de dos vías.

    Parameters
    ----------
    frame : DataFrame
        Panel con índice (unidad, periodo).
    y : str
        Variable dependiente.
    treated : Mapping[str, fecha]
        Unidades tratadas y su fecha de evento (la del anuncio: no anticipación).
    leads, lags : int
        Periodos antes y después del evento en el estudio de evento.
    """
    df = frame[[y]].dropna().copy()
    units = df.index.get_level_values(0)
    times = pd.Index(sorted(df.index.get_level_values(1).unique()))
    if not treated:
        raise DataValidationError("Declare al menos una unidad tratada.")
    unknown = set(treated) - set(units)
    if unknown:
        raise DataValidationError(f"Unidades tratadas no presentes: {sorted(unknown)}")
    warnings: list[str] = []
    event_dates = {pd.Timestamp(v) if not isinstance(v, int) else v for v in treated.values()}
    if len(event_dates) > 1:
        warnings.append(
            "Adopción escalonada: el TWFE clásico está sesgado con efectos heterogéneos en el "
            "tiempo (Goodman-Bacon 2021); use estimadores robustos (fuera de alcance)."
        )
    pos = {t: i for i, t in enumerate(times)}
    rel = np.full(len(df), np.nan)
    post = np.zeros(len(df))
    for k, (u, t) in enumerate(df.index):
        if u in treated:
            ev = treated[u]
            ev = pd.Timestamp(ev) if not isinstance(ev, int) else ev
            ev_pos = int(times.searchsorted(ev))
            rel[k] = pos[t] - ev_pos
            post[k] = float(pos[t] >= ev_pos)
    df["did"] = post
    n_treated = len(treated)
    n_control = int(pd.Index(units).nunique()) - n_treated
    if n_control < 1:
        raise DataValidationError("DiD necesita al menos una unidad de control.")
    cluster = n_treated >= 2
    res = _twfe(df, y, ["did"], cluster=cluster)
    atet = float(res.params["did"])
    if cluster:
        se: float | None = float(res.std_errors["did"])
        pvalue = float(res.pvalues["did"])
        inference = "errores agrupados por unidad"
        if n_treated + n_control < 30:
            warnings.append(
                f"Sólo {n_treated + n_control} unidades: los errores agrupados pueden "
                "subestimar la incertidumbre."
            )
    else:
        # Permutación: cada control recibe un tratamiento placebo con la misma fecha. Los
        # efectos se ESTUDENTIZAN por la desviación estándar previa al evento de los
        # residuos de cada unidad (Ferman y Pinto 2019: con varianzas heterogéneas los
        # placebos crudos no son intercambiables).
        ev = next(iter(treated.values()))
        ev_pos = int(times.searchsorted(pd.Timestamp(ev) if not isinstance(ev, int) else ev))
        tr_unit = next(iter(treated))
        pre_sd = _pre_sd(df, y, pos, ev_pos)
        stat_obs = atet / pre_sd[tr_unit] if pre_sd[tr_unit] > 0 else float("nan")
        placebos = []
        for u in sorted(set(units) - set(treated)):
            alt = df.drop(columns="did").copy()
            alt["did"] = [float(uu == u and pos[t] >= ev_pos) for uu, t in alt.index]
            alt = alt[alt.index.get_level_values(0) != tr_unit]
            est = float(_twfe(alt, y, ["did"], cluster=False).params["did"])
            placebos.append(est / pre_sd[u] if pre_sd[u] > 0 else float("nan"))
        arr = np.abs(np.asarray(placebos))
        arr = arr[np.isfinite(arr)]
        pvalue = float((1 + np.sum(arr >= abs(stat_obs))) / (1 + len(arr)))
        p_min = 1.0 / (1 + len(arr))
        se = None
        inference = (
            f"permutación estudentizada ({len(arr)} placebos; una sola unidad tratada; "
            f"p mínimo alcanzable {p_min:.3f})"
        )
        warnings.append(
            "Una sola unidad tratada: los errores agrupados no son válidos (Conley y Taber "
            "2011); se usa inferencia por permutación estudentizada."
        )
        if p_min > alpha:
            warnings.append(
                f"Con {len(arr)} controles el p mínimo alcanzable es {p_min:.3f} > α = {alpha}: "
                "la prueba NO puede rechazar; resultado no concluyente."
            )
    # Estudio de evento: dummies de periodo relativo (−1 de referencia), extremos agrupados.
    es_cols = []
    for k in range(-leads, lags + 1):
        if k == -1:
            continue
        col = f"rel_{k}".replace("-", "m")
        if k == -leads:
            ind = rel <= k
        elif k == lags:
            ind = rel >= k
        else:
            ind = rel == k
        df[col] = np.where(np.isnan(rel), 0.0, ind.astype(float))
        if df[col].abs().sum() > 0:
            es_cols.append((k, col))
    event: dict[int, dict[str, float]] = {}
    pre_stat = pre_p = None
    if es_cols:
        res_es = _twfe(df, y, [c for _, c in es_cols], cluster=cluster)
        for k, c in es_cols:
            event[k] = {
                "coef": float(res_es.params[c]),
                "se": float(res_es.std_errors[c]),
            }
        lead_cols = [c for k, c in es_cols if k < -1]
        if lead_cols:
            names = [c for _, c in es_cols]
            pre_stat, pre_p = _pretrend(
                df, y, res_es, names, lead_cols, cluster, n_treated + n_control
            )
            if not cluster:
                # Una tratada: Wald sin agrupar comparado con los placebos (permutación).
                tr_unit = next(iter(treated))
                ref = []
                for u in sorted(set(units) - set(treated)):
                    alt = df[df.index.get_level_values(0) != tr_unit].copy()
                    alt[[c for _, c in es_cols]] = 0.0
                    mask = alt.index.get_level_values(0) == u
                    for _k, c in es_cols:
                        src = df.loc[df.index.get_level_values(0) == tr_unit, c].to_numpy()
                        if mask.sum() == src.size:
                            alt.loc[mask, c] = src
                    cols_alt = [c for _, c in es_cols if alt[c].abs().sum() > 0]
                    leads_alt = [c for c in lead_cols if c in cols_alt]
                    if not leads_alt:
                        continue
                    r_alt = _twfe(alt, y, cols_alt, cluster=False)
                    ref.append(_pretrend(alt, y, r_alt, cols_alt, leads_alt, False, 0)[0])
                ref_arr = np.asarray([v for v in ref if np.isfinite(v)])
                if ref_arr.size:
                    pre_p = float((1 + np.sum(ref_arr >= pre_stat)) / (1 + ref_arr.size))
            if pre_p < alpha:
                warnings.append(
                    "Los coeficientes previos al evento no son cero: el supuesto de tendencias "
                    "paralelas no se sostiene; el ATET está sesgado."
                )
    assumptions = [
        "Tendencias paralelas: sin tratamiento, tratados y controles habrían seguido la misma "
        "tendencia (Facure, cap. 13).",
        "No anticipación: la fecha del evento es la del anuncio.",
        "No rechazar la prueba de tendencias previas NO prueba tendencias paralelas y "
        "condicionar a ella sesga la inferencia (Roth 2022).",
    ]
    return DiDResult(
        atet=atet,
        se=se,
        pvalue=pvalue,
        inference=inference,
        n_treated=n_treated,
        n_control=n_control,
        event_study=event,
        pretrend_stat=pre_stat,
        pretrend_pvalue=pre_p,
        warnings=warnings,
        assumptions=assumptions,
    )


def _pretrend(
    df: pd.DataFrame,
    y: str,
    res: Any,
    names: list[str],
    lead_cols: list[str],
    cluster: bool,
    n_groups: int,
) -> tuple[float, float]:
    """Wald conjunto de los *leads* = 0; con errores agrupados y G < 30, F(q, G−1)."""
    from scipy import stats

    restriction = np.zeros((len(lead_cols), len(names)))
    for i, c in enumerate(lead_cols):
        restriction[i, names.index(c)] = 1.0
    wt = res.wald_test(restriction, np.zeros(len(lead_cols)))
    stat = float(wt.stat)
    q = len(lead_cols)
    if cluster and n_groups < 30:
        return stat, float(stats.f.sf(stat / q, q, max(n_groups - 1, 1)))
    return stat, float(wt.pval)
