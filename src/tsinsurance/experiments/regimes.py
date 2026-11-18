"""Análisis por regímenes del ciclo (spec 005, US2).

Un **estado** es una serie booleana mensual construida al cierre de cada mes sólo con
información publicada hasta ese cierre:

- ``threshold``: una variable (exógena o tasa libre de riesgo) frente a un umbral;
- ``spread``: la diferencia entre dos variables frente a un umbral. Si la última
  observación diaria de alguna tiene más de 5 días hábiles de antigüedad, el estado es
  faltante;
- ``trend``: el cierre de mes de un activo bajo su media de los ``months`` cierres de mes
  previos (incluido el actual).

Para cada activo se estima ``y_{t+1} = a + b·S_t + e``, con ``y_{t+1}`` el exceso de
retorno del mes calendario siguiente al cierre t. Es una **convención descriptiva**: sin
rezago de ejecución ni costos, así que no es una estrategia. Se usan errores HC3, porque la
volatilidad cambia con el régimen y los meses en el estado pueden ser pocos. Las variantes
(umbrales) de una malla son hipótesis distintas, y el Holm suma las variantes previas con
la misma clave de memoria (revisión B1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from tsinsurance.backtest import align_point_in_time, monthly_decision_dates
from tsinsurance.data.bundle import Bundle
from tsinsurance.experiments.spec import RegimeSpec

__all__ = ["MAX_STALENESS_BDAYS", "RegimeRow", "analyze_regime", "holm_extended", "regime_state"]

MAX_STALENESS_BDAYS = 5


@dataclass(frozen=True, slots=True)
class RegimeRow:
    """Resultado de una hipótesis (régimen, variante, activo)."""

    regime: str
    variant: dict[str, Any]
    asset: str
    months_on: int
    months_off: int
    ann_on: float
    ann_off: float
    diff_ann: float
    t: float
    p: float
    inconclusive: bool
    eval_start: str
    eval_end: str

    @property
    def label(self) -> str:
        """Identificador legible de la hipótesis."""
        v = ",".join(f"{k}={val}" for k, val in self.variant.items())
        return f"regimen:{self.regime}[{v}]:{self.asset}"


def holm_extended(pvalues: list[float], extra_m: int = 0) -> list[float]:
    """Holm con ``m = len(pvalues) + extra_m`` (variantes previas ya probadas; B1)."""
    p = np.asarray(pvalues, dtype=float)
    m = len(p) + max(int(extra_m), 0)
    order = np.argsort(p)
    adj = np.empty(len(p))
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return adj.tolist()


def _level_at(bundle: Bundle, var: str, dates: pd.DatetimeIndex) -> pd.Series:
    """Último valor publicado ≤ d; faltante si una serie diaria está desactualizada."""
    ex = bundle.variable(var)
    aligned: pd.Series = align_point_in_time([ex], dates)[var]
    if ex.frequency in ("B", "D"):
        avail = ex.available_series()
        last = (
            pd.Series(avail.index, index=avail.index)
            .reindex(avail.index.union(dates))
            .ffill()
            .reindex(dates)
        )
        age = pd.Series(
            [
                np.busday_count(a.date(), d.date()) if pd.notna(a) else np.inf
                for a, d in zip(last, dates, strict=True)
            ],
            index=dates,
        )
        aligned = aligned.where(age <= MAX_STALENESS_BDAYS)
    return aligned


def regime_state(
    bundle: Bundle, spec: RegimeSpec, variant: dict[str, Any], dates: pd.DatetimeIndex
) -> pd.Series:
    """Estado (1.0 activo, 0.0 inactivo, NaN faltante) en las fechas de decisión ``dates``."""
    if spec.type == "trend":
        assert spec.asset is not None
        px = bundle.assets([spec.asset])[spec.asset].dropna()
        closes = px.reindex(px.index.union(dates)).ffill().reindex(dates)
        sma = closes.rolling(int(variant["months"]), min_periods=int(variant["months"])).mean()
        state = (closes < sma).astype(float).where(sma.notna())
        return state
    values = [_level_at(bundle, v, dates) for v in spec.variables]
    x = values[0] if spec.type == "threshold" else values[0] - values[1]
    threshold = float(variant["value"])
    on = x > threshold if variant["op"] == ">" else x < threshold
    result: pd.Series = on.astype(float).where(x.notna())
    return result


def _excess_monthly(prices: pd.Series, rf: pd.Series | None) -> pd.Series:
    from tsinsurance.experiments.runner import _excess_monthly as em

    return em(prices, rf)


def analyze_regime(
    bundle: Bundle,
    spec: RegimeSpec,
    *,
    start: str | None = None,
    end: str | None = None,
    after: str | None = None,
) -> list[RegimeRow]:
    """Exceso de retorno del mes siguiente por estado, para cada variante y activo.

    ``after`` (fecha de corte) restringe a los meses objetivo posteriores al corte: las
    decisiones desde la última fecha de decisión ≤ corte (validación única).
    """
    rf = bundle.risk_free()
    rows: list[RegimeRow] = []
    for asset in spec.assets:
        px = bundle.assets([asset])[asset].loc[start:end].dropna()
        if px.empty:
            continue
        dates = monthly_decision_dates(px)
        y_next = _excess_monthly(px, rf).reindex(dates).shift(-1)
        if after is not None:
            decided = dates[dates <= pd.Timestamp(after)]
            first = decided.max() if len(decided) else dates.min()
            keep = dates >= first
            dates, y_next = dates[keep], y_next[keep]
        for variant in spec.variants():
            s = regime_state(bundle, spec, variant, dates)
            d = pd.concat({"y": y_next, "s": s}, axis=1, sort=True).dropna()
            on, off = int(d["s"].sum()), int((1 - d["s"]).sum())
            inconclusive = min(on, off) < spec.min_months
            if inconclusive:
                t = p = diff = float("nan")
            else:
                fit = sm.OLS(d["y"], sm.add_constant(d["s"])).fit(cov_type="HC3")
                diff = float(fit.params["s"] * 12)
                t = float(fit.tvalues["s"])
                p = float(fit.pvalues["s"])
            rows.append(
                RegimeRow(
                    regime=spec.name,
                    variant=variant,
                    asset=asset,
                    months_on=on,
                    months_off=off,
                    ann_on=float(d.loc[d["s"] == 1, "y"].mean() * 12) if on else float("nan"),
                    ann_off=float(d.loc[d["s"] == 0, "y"].mean() * 12) if off else float("nan"),
                    diff_ann=diff,
                    t=t,
                    p=p,
                    inconclusive=inconclusive,
                    eval_start=str(d.index.min().date()) if len(d) else "",
                    # Fin del mes OBJETIVO del último resultado (revisión M2).
                    eval_end=str((d.index.max() + pd.offsets.MonthEnd(1)).date()) if len(d) else "",
                )
            )
    return rows


def one_sided_p(t: float, sign: float) -> float:
    """Valor p unilateral en el signo calibrado (validación de una hipótesis seleccionada)."""
    if not np.isfinite(t):
        return float("nan")
    return float(1 - stats.norm.cdf(np.sign(sign) * t))
