"""Paneles predictivos unidades × meses en experimentos (spec 006, US3).

Variable dependiente: ``y_{i,t+1}``, el exceso de retorno de la unidad i en el mes
calendario siguiente a la decisión t (la misma convención descriptiva de los regímenes:
sin rezago de ejecución ni costos, así que no es una estrategia). Los regresores son
series del paquete alineadas punto en el tiempo al cierre de cada mes (último valor
publicado ≤ t; las series diarias desactualizadas más de 5 días hábiles quedan
faltantes). ``x_t × D_i`` estima el efecto **diferencial** de las unidades con la
característica D (Facure, cap. 14: con efectos de tiempo el efecto común de x_t queda
absorbido).

Cada hipótesis pre-registrada (coeficiente, signo) se prueba unilateralmente:

- **principal** (FE o TWFE con Driscoll-Kraay): el t de DK con corrección por grados de
  libertad y valor p por *wild bootstrap* restringido por bloques de periodos, condicionado
  a los X observados (revisión de la implementación, I1; Monte Carlo R10). En otro caso,
  el tipo de error declarado;
- **estabilidad** de cada coeficiente: Nyblom-Hansen sobre los scores DK;
- **sensibilidad**: wild cluster bootstrap restringido por unidad (no válido con factor
  común; sólo se reporta);
- **G₁ < 2** en una interacción ⇒ no concluyente (Conley y Taber 2011).

References
----------
Facure, M. *Causal Inference for the Brave and True*, cap. 14 (Panel Data and Fixed
Effects).
Driscoll, J. y Kraay, A. (1998). Consistent covariance matrix estimation with spatially
dependent panel data. *Review of Economics and Statistics*, 80(4), 549-560.
Hjalmarsson, E. (2008). The Stambaugh bias in panel predictive regressions. *Finance
Research Letters*, 5(1), 47-58.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from tsinsurance.backtest import monthly_decision_dates
from tsinsurance.data.bundle import Bundle
from tsinsurance.errors import TSInsuranceError
from tsinsurance.experiments.spec import PanelSpec

__all__ = ["PanelHypothesisRow", "PanelRun", "analyze_panel", "build_panel", "mde"]

Y = "y_next"


def build_panel(
    bundle: Bundle,
    spec: PanelSpec,
    *,
    start: str | None = None,
    end: str | None = None,
    after: str | None = None,
) -> pd.DataFrame:
    """Panel (unidad, mes) con ``y_next``, los regresores y las interacciones.

    ``after`` (fecha de corte) conserva sólo las decisiones cuyo mes objetivo empieza
    después del corte (validación).
    """
    from tsinsurance.experiments.regimes import _level_at
    from tsinsurance.experiments.runner import _excess_monthly

    rf = bundle.risk_free()
    pieces = []
    for unit in spec.units:
        try:
            px = bundle.assets([unit])[unit].loc[start:end].dropna()
        except KeyError:  # sin datos hasta el corte (p. ej. un ETF lanzado después)
            continue
        if px.empty:
            continue
        dates = monthly_decision_dates(px)
        if len(dates) < 3:
            continue
        cols: dict[str, pd.Series] = {
            Y: _excess_monthly(px, rf).reindex(dates).shift(-1),
        }
        for var in spec.regressors:
            level = _level_at(bundle, var, dates)
            cols[var] = level.diff() if spec.transforms.get(var, "level") == "diff" else level
        for x, c in spec.interactions:
            cols[f"{x}:{c}"] = cols[x] * float(unit in spec.characteristics[c])
        frame = pd.DataFrame(cols)
        if after is not None:
            # Sólo decisiones cuyo mes OBJETIVO empieza después del corte (fin del mes de
            # la decisión ≥ corte); con un corte a mitad de mes se omite el mes partido.
            month_end = pd.DatetimeIndex(frame.index) + pd.offsets.MonthEnd(0)
            frame = frame[month_end >= pd.Timestamp(after)]
        # Etiqueta común por mes: el último día con precio puede diferir entre unidades.
        frame.index = pd.DatetimeIndex(frame.index).to_period("M").to_timestamp("M")
        frame.index.name = "time"
        pieces.append(frame.assign(entity=unit).set_index("entity", append=True))
    if not pieces:
        raise TSInsuranceError(f"Panel '{spec.name}': ninguna unidad con datos.")
    out = pd.concat(pieces).swaplevel(0, 1).sort_index()
    return out.dropna()


def mde(
    se_cal: float,
    t_cal: int,
    t_val: int,
    *,
    alpha: float = 0.05,
    m: int = 1,
    power: float = 0.80,
) -> float:
    """Efecto mínimo detectable ex ante de la prueba unilateral de la validación.

    MDE = (z_{1−α/m} + z_{power})·ee_cal·√(T_cal/T_val): nivel unilateral α/m (la primera
    etapa de Holm con m hipótesis en la familia) y el ee reescalado al T de la validación,
    suponiendo el mismo número de unidades y la misma varianza de los scores. Es una cota
    optimista con T_val corto (no incluye la cola más gruesa de la referencia del t).
    """
    if t_val <= 0 or not np.isfinite(se_cal) or m < 1 or not 0 < alpha < 1:
        return float("nan")
    factor = stats.norm.ppf(1 - alpha / m) + stats.norm.ppf(power)
    return float(factor * se_cal * np.sqrt(t_cal / t_val))


@dataclass(frozen=True, slots=True)
class PanelHypothesisRow:
    """Prueba unilateral de una hipótesis pre-registrada."""

    panel: str
    coef: str
    sign: str
    estimate: float
    se: float
    t: float
    p_one_sided: float
    p_distribution: str
    wcr_p_one_sided: float | None
    fixed_b_p_one_sided: float | None
    stability_pvalue: float | None
    treated_clusters: int | None
    inconclusive: bool
    reason: str
    n_periods: int
    n_entities: int
    eval_start: str
    eval_end: str

    @property
    def label(self) -> str:
        """Identificador legible."""
        return f"panel:{self.panel}:{self.coef}{self.sign}"


@dataclass(frozen=True, slots=True)
class PanelRun:
    """Estimación, diagnósticos e hipótesis de un panel."""

    rows: list[PanelHypothesisRow]
    params: dict[str, float]
    std_errors: dict[str, float]
    diagnostics_passed: bool
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    fe_vs_re: dict[str, Any] = field(default_factory=dict)
    bandwidth: int | None = None


def _one_sided(t: float, sign: str, n_periods: int, bandwidth: int | None) -> float:
    if not np.isfinite(t):
        return float("nan")
    if bandwidth is not None:
        from tsinsurance.panel.inference import dk_pvalue

        return dk_pvalue(t, n_periods, "greater" if sign == "+" else "less", bandwidth=bandwidth)
    return float(stats.norm.sf(t if sign == "+" else -t))


def analyze_panel(
    bundle: Bundle,
    spec: PanelSpec,
    *,
    start: str | None = None,
    end: str | None = None,
    after: str | None = None,
    seed: int = 0,
    alpha: float = 0.05,
    with_diagnostics: bool = True,
) -> PanelRun:
    """Estima el panel declarado y prueba sus hipótesis (calibración o validación)."""
    from tsinsurance.panel import fit_panel
    from tsinsurance.panel.diagnostics import panel_diagnostics
    from tsinsurance.panel.inference import (
        dk_wild_bootstrap,
        mundlak_test,
        score_stability,
        wild_cluster_bootstrap,
    )

    frame = build_panel(bundle, spec, start=start, end=end, after=after)
    cols = spec.columns
    n_periods = int(frame.index.get_level_values(1).nunique())
    n_entities = int(frame.index.get_level_values(0).nunique())
    eval_start = str(frame.index.get_level_values(1).min().date())
    # Fin del mes OBJETIVO del último resultado.
    eval_end = str((frame.index.get_level_values(1).max() + pd.offsets.MonthEnd(1)).date())
    warnings: list[str] = []
    missing = sorted(set(spec.units) - set(frame.index.get_level_values(0)))
    if missing:
        warnings.append(f"Unidades sin datos en esta ventana: {missing}")
    short = n_periods < spec.min_months
    if short:
        warnings.append(f"Sólo {n_periods} meses (< {spec.min_months}): no concluyente.")
    res = fit_panel(
        frame, Y, cols, estimator=spec.estimator, cov=spec.cov, bandwidth=spec.bandwidth
    )
    warnings += res.warnings
    dk = spec.cov == "driscoll_kraay" and spec.estimator in ("fe", "twfe")
    bw_used = int(res.diagnostics.get("bandwidth_driscoll_kraay", 0))
    rows = []
    for h in spec.hypotheses:
        reason = ""
        g1 = res.treated_clusters.get(h.coef)
        if h.coef in res.absorbed:
            reason = f"absorbido: {res.absorbed[h.coef]}"
        elif h.coef in res.inconclusive:
            reason = f"G₁ = {g1} < 2 unidades con la característica"
        elif short:
            reason = "muestra corta"
        if h.coef in res.params:
            est = float(res.params[h.coef])
            se = float(res.std_errors[h.coef])
            t = float(res.tstats[h.coef])
        else:
            est = se = t = float("nan")
        p1 = float("nan")
        p_fixed_b: float | None = None
        stab: float | None = None
        dist = res.pvalue_distribution if dk else "normal"
        keep = [c for c in cols if c not in res.absorbed]
        if not reason:
            p1 = _one_sided(t, h.sign, n_periods, bw_used if dk else None)
            if dk:
                p_fixed_b = p1
                bres = dk_wild_bootstrap(
                    frame,
                    Y,
                    keep,
                    h.coef,
                    time_effects=spec.estimator == "twfe",
                    maxlag=bw_used,
                    draws=spec.bootstrap_draws,
                    seed=seed,
                )
                p1 = bres.pvalue_greater if h.sign == "+" else bres.pvalue_less
                dist = f"wild bootstrap DK ({bres.weights}; B = {bres.draws})"
            if spec.estimator in ("fe", "twfe"):
                stab = score_stability(
                    frame,
                    Y,
                    keep,
                    h.coef,
                    time_effects=spec.estimator == "twfe",
                    maxlag=bw_used,
                )["pvalue"]
                if stab < alpha:
                    warnings.append(
                        f"Coeficiente {h.coef} inestable (Nyblom-Hansen p = {stab:.3f})."
                    )
        wcr: float | None = None
        if not reason and spec.estimator in ("fe", "twfe") and n_entities >= 3:
            if g1 is not None and g1 <= 2:
                warnings.append(
                    f"WCR de {h.coef} con G₁ = {g1}: poco confiable (MacKinnon y Webb 2017)."
                )
            try:
                wb = wild_cluster_bootstrap(
                    frame,
                    Y,
                    keep,
                    h.coef,
                    time_effects=spec.estimator == "twfe",
                    draws=spec.bootstrap_draws,
                    seed=seed,
                )
                wcr = wb.pvalue_greater if h.sign == "+" else wb.pvalue_less
            except TSInsuranceError as exc:
                warnings.append(f"WCR de {h.coef} no disponible: {exc}")
        rows.append(
            PanelHypothesisRow(
                panel=spec.name,
                coef=h.coef,
                sign=h.sign,
                estimate=est,
                se=se,
                t=t,
                p_one_sided=p1,
                p_distribution=dist,
                wcr_p_one_sided=wcr,
                fixed_b_p_one_sided=p_fixed_b,
                stability_pvalue=stab,
                treated_clusters=g1,
                inconclusive=bool(reason),
                reason=reason,
                n_periods=n_periods,
                n_entities=n_entities,
                eval_start=eval_start,
                eval_end=eval_end,
            )
        )
    diag: dict[str, Any] = {}
    passed = True
    fe_vs_re: dict[str, Any] = {}
    if with_diagnostics:
        keep = [c for c in cols if c not in res.absorbed]
        try:
            d = panel_diagnostics(
                frame, Y, keep, time_effects=spec.estimator == "twfe", alpha=alpha
            )
            diag = {
                "serial": d.serial,
                "cross_section": d.cross_section,
                "stationarity": d.stationarity,
                "persistence": d.persistence,
                "arch_units_rejecting": sum(p < alpha for p in d.arch.values()),
            }
            passed = d.passed
            warnings += d.warnings
        except TSInsuranceError as exc:
            warnings.append(f"Diagnósticos no disponibles: {exc}")
            passed = False
        if spec.estimator in ("fe", "re"):
            # Mundlak sólo tiene sentido con regresores que varían entre unidades: las
            # medias por unidad de un x_t común son (casi) constantes.
            varying = []
            for c in keep:
                spread = frame[c].groupby(level=1).std().fillna(0.0)
                if float(spread.max()) > 1e-8 * max(float(frame[c].abs().max()), 1e-300):
                    varying.append(c)
            if not varying:
                fe_vs_re = {"note": "sin regresores que varíen entre unidades: FE ≈ RE"}
            else:
                try:
                    m = mundlak_test(frame, Y, keep, alpha=alpha, test=varying)
                    fe_vs_re = {
                        "regressors": varying,
                        "mundlak_stat": m.mundlak_stat,
                        "mundlak_pvalue": m.mundlak_pvalue,
                        "distribution": m.mundlak_distribution,
                        "recommendation": m.recommendation,
                        "notes": m.notes,
                    }
                except (TSInsuranceError, np.linalg.LinAlgError) as exc:
                    fe_vs_re = {"error": str(exc)}
    return PanelRun(
        rows=rows,
        params=dict(res.params),
        std_errors=dict(res.std_errors),
        diagnostics_passed=passed,
        warnings=warnings,
        diagnostics=diag,
        fe_vs_re=fe_vs_re,
        bandwidth=int(res.diagnostics.get("bandwidth_driscoll_kraay", 0)) or None,
    )
