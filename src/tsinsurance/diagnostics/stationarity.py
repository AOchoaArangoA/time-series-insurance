"""Pruebas de raíz unitaria / estacionariedad y diagnóstico del orden de integración.

Implementa el análisis confirmatorio del Principio I: pruebas con hipótesis nulas
opuestas (ADF y Phillips-Perron con H0 de raíz unitaria; KPSS con H0 de
estacionariedad) y la prueba de Zivot-Andrews con quiebre estructural endógeno.

References
----------
.. [1] Dickey, D. A. & Fuller, W. A. (1979). Distribution of the estimators for
   autoregressive time series with a unit root. JASA, 74(366), 427-431.
.. [2] Phillips, P. C. B. & Perron, P. (1988). Testing for a unit root in time series
   regression. Biometrika, 75(2), 335-346.
.. [3] Kwiatkowski, D., Phillips, P. C. B., Schmidt, P. & Shin, Y. (1992). Testing the
   null hypothesis of stationarity against the alternative of a unit root. Journal of
   Econometrics, 54, 159-178.
.. [4] Zivot, E. & Andrews, D. W. K. (1992). Further evidence on the great crash, the
   oil-price shock, and the unit-root hypothesis. JBES, 10(3), 251-270.
.. [5] MacKinnon, J. G. (1996). Numerical distribution functions for unit root and
   cointegration tests. Journal of Applied Econometrics, 11(6), 601-618.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from arch.unitroot import PhillipsPerron
from statsmodels.tools.sm_exceptions import InterpolationWarning
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.stattools import kpss as sm_kpss
from statsmodels.tsa.stattools import zivot_andrews as sm_za

from tsinsurance._types import Trend
from tsinsurance.errors import DataValidationError, InsufficientDataError
from tsinsurance.results import HypothesisTestResult, ResultMixin

__all__ = [
    "MIN_OBS",
    "MIN_OBS_BREAK",
    "StationarityReport",
    "adf",
    "kpss",
    "pp",
    "stationarity",
    "zivot_andrews",
]

MIN_OBS = 25
"""Observaciones mínimas para ADF, PP y KPSS."""
ALPHAS: tuple[float, ...] = (0.01, 0.025, 0.05, 0.10)
"""Niveles de significancia admitidos por :func:`stationarity` (tabla de KPSS)."""
MIN_OBS_BREAK = 50
"""Observaciones mínimas para Zivot-Andrews (recorte del 15 % en cada extremo)."""

_H0_UNIT_ROOT = "La serie tiene raíz unitaria (no estacionaria)."
_H0_STATIONARY = "La serie es estacionaria (alrededor de constante/tendencia)."
_H0_ZA = "Raíz unitaria sin quiebre estructural."
_TREND_LABEL = {"c": "constante", "ct": "constante y tendencia"}

Conclusion = Literal["I(0)", "I(1)", "I(2)", "inconclusive"]


def _clean(series: pd.Series | np.ndarray, procedure: str, minimum: int) -> pd.Series:
    s = pd.Series(series, dtype=float) if not isinstance(series, pd.Series) else series
    s = s.astype(float)
    if s.isna().any():
        raise DataValidationError(
            f"{procedure}: la serie tiene faltantes; trátelos antes con tsinsurance.data.prepare."
        )
    if not np.isfinite(s.to_numpy()).all():
        raise DataValidationError(f"{procedure}: la serie tiene valores infinitos.")
    if len(s) < minimum:
        raise InsufficientDataError(procedure, required=minimum, actual=len(s))
    if float(s.std()) == 0.0:
        raise DataValidationError(f"{procedure}: la serie es constante.")
    return s


def _check_trend(trend: str) -> None:
    if trend not in _TREND_LABEL:
        raise ValueError("trend debe ser 'c' (constante) o 'ct' (constante y tendencia).")


def adf(
    series: pd.Series,
    *,
    trend: Trend = "c",
    autolag: Literal["AIC", "BIC", "t-stat"] | None = "AIC",
    maxlag: int | None = None,
) -> HypothesisTestResult:
    """Prueba aumentada de Dickey-Fuller (H0: raíz unitaria).

    Rezagos seleccionados por ``autolag`` hasta ``maxlag`` (por defecto
    ``12 * (n/100)^{1/4}``, Schwert 1989). Valores p de MacKinnon (1996, 2010).
    """
    _check_trend(trend)
    s = _clean(series, "ADF", MIN_OBS)
    res = adfuller(
        s.to_numpy(), regression=trend, autolag=autolag, maxlag=maxlag, result_object=True
    )
    return HypothesisTestResult(
        name="ADF",
        statistic=float(res.statistic),
        p_value=float(res.pvalue),
        null_hypothesis=_H0_UNIT_ROOT,
        critical_values={k: float(v) for k, v in res.critical_values.items()},
        specification={
            "deterministic": _TREND_LABEL[trend],
            "lags": int(res.lags),
            "lag_selection": autolag or "fixed",
            "nobs": int(res.nobs),
        },
        reference="Dickey & Fuller (1979); MacKinnon (1996)",
    )


def pp(series: pd.Series, *, trend: Trend = "c", lags: int | None = None) -> HypothesisTestResult:
    """Prueba de Phillips-Perron (H0: raíz unitaria), estadístico Z-tau.

    Corrección no paramétrica de la autocorrelación con kernel de Bartlett
    (Newey-West); ``lags`` por defecto ``12 * (n/100)^{1/4}``.
    """
    _check_trend(trend)
    s = _clean(series, "Phillips-Perron", MIN_OBS)
    res = PhillipsPerron(s.to_numpy(), trend=trend, lags=lags, test_type="tau")
    return HypothesisTestResult(
        name="PP",
        statistic=float(res.stat),
        p_value=float(res.pvalue),
        null_hypothesis=_H0_UNIT_ROOT,
        critical_values={k: float(v) for k, v in res.critical_values.items()},
        specification={
            "deterministic": _TREND_LABEL[trend],
            "lags": int(res.lags),
            "kernel": "Bartlett",
            "nobs": int(res.nobs),
        },
        reference="Phillips & Perron (1988)",
    )


def kpss(
    series: pd.Series, *, trend: Trend = "c", nlags: Literal["auto", "legacy"] | int = "auto"
) -> HypothesisTestResult:
    """Prueba KPSS (H0: estacionariedad).

    El valor p se interpola en la tabla de KPSS (1992) y queda acotado a
    [0.01, 0.10]; cuando cae fuera se registra ``p_value_bound`` y la decisión a
    niveles fuera de ese rango se toma con los valores críticos (10 %, 5 %, 2,5 %, 1 %).
    """
    _check_trend(trend)
    s = _clean(series, "KPSS", MIN_OBS)
    notes: list[str] = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", InterpolationWarning)
        res = sm_kpss(s.to_numpy(), regression=trend, nlags=nlags, result_object=True)
    stat, pvalue, lags, crit = res.statistic, res.pvalue, res.lags, res.critical_values
    bound: Literal["below", "above"] | None = None
    if any(issubclass(w.category, InterpolationWarning) for w in caught):
        bound = "below" if pvalue <= 0.01 else "above"
        word = "menor" if bound == "below" else "mayor"
        notes.append(f"Valor p fuera de la tabla: el verdadero es {word} que el reportado.")
    crit_levels = {k: float(v) for k, v in crit.items()}
    return HypothesisTestResult(
        name="KPSS",
        statistic=float(stat),
        p_value=float(pvalue),
        null_hypothesis=_H0_STATIONARY,
        critical_values=crit_levels,
        specification={
            "deterministic": _TREND_LABEL[trend],
            "lags": int(lags),
            "nobs": len(s),
            "lower_tail": False,
        },
        reference="Kwiatkowski, Phillips, Schmidt & Shin (1992)",
        notes=tuple(notes),
        p_value_bound=bound,
    )


def zivot_andrews(
    series: pd.Series,
    *,
    trend: Literal["c", "t", "ct"] = "c",
    trim: float = 0.15,
    maxlag: int | None = None,
    autolag: Literal["AIC", "BIC", "t-stat"] | None = "AIC",
) -> tuple[HypothesisTestResult, pd.Timestamp | int]:
    """Prueba de Zivot-Andrews (H0: raíz unitaria sin quiebre).

    Busca endógenamente un quiebre en el intercepto (``"c"``), la tendencia
    (``"t"``) o ambos (``"ct"``).

    Returns
    -------
    result : HypothesisTestResult
    break_point : pandas.Timestamp or int
        Fecha del quiebre (o posición si la serie no tiene índice de fechas).
    """
    s = _clean(series, "Zivot-Andrews", MIN_OBS_BREAK)
    if maxlag is None:
        maxlag = int(np.ceil(12.0 * (len(s) / 100.0) ** 0.25))
    stat, pvalue, crit, baselag, bpidx = sm_za(
        s.to_numpy(), trim=trim, maxlag=maxlag, regression=trend, autolag=autolag
    )
    idx = int(bpidx)
    brk: pd.Timestamp | int = s.index[idx] if isinstance(s.index, pd.DatetimeIndex) else idx
    result = HypothesisTestResult(
        name="ZA",
        statistic=float(stat),
        p_value=float(pvalue),
        null_hypothesis=_H0_ZA,
        critical_values={k: float(v) for k, v in crit.items()},
        specification={
            "break_in": {"c": "intercepto", "t": "tendencia", "ct": "intercepto y tendencia"}[
                trend
            ],
            "lags": int(baselag),
            "trim": trim,
            "break_point": str(brk.date()) if isinstance(brk, pd.Timestamp) else brk,
            "nobs": len(s),
        },
        reference="Zivot & Andrews (1992)",
    )
    return result, brk


@dataclass(frozen=True, slots=True, eq=False)
class StationarityReport(ResultMixin):
    """Diagnóstico del orden de integración de una serie.

    Attributes
    ----------
    series_id : str
        Nombre de la serie.
    tests : tuple[HypothesisTestResult, ...]
        Todas las pruebas ejecutadas; ``specification["difference"]`` indica sobre
        qué diferencia se aplicó cada una.
    integration_order : int or None
        Orden de integración concluido (``None`` si es inconcluso).
    conclusion : {"I(0)", "I(1)", "I(2)", "inconclusive"}
    decision_rule : str
        Regla de decisión aplicada (texto auditable).
    alpha : float
        Nivel de significancia.
    break_date : pandas.Timestamp or None
        Fecha que minimiza el estadístico de Zivot-Andrews (convención: última
        observación antes del quiebre). Sólo es interpretable como quiebre si
        ``break_significant``; bajo la nula el argmin no estima el quiebre de forma
        consistente.
    break_significant : bool
        ``True`` si Zivot-Andrews rechaza al nivel ``alpha``.
    notes : tuple[str, ...]
        Observaciones (contradicciones, quiebres, límites de tablas).
    """

    series_id: str
    tests: tuple[HypothesisTestResult, ...]
    integration_order: int | None
    conclusion: Conclusion
    decision_rule: str
    alpha: float
    break_date: pd.Timestamp | None = None
    notes: tuple[str, ...] = ()
    break_significant: bool = False

    def tests_at(self, difference: int) -> list[HypothesisTestResult]:
        """Pruebas aplicadas sobre la ``difference``-ésima diferencia."""
        return [t for t in self.tests if t.specification.get("difference") == difference]

    def summary(self) -> str:
        """Reporte legible para comité o auditoría."""
        lines = [
            f"Diagnóstico de estacionariedad — {self.series_id}",
            f"Conclusión: {self.conclusion}  (alpha = {self.alpha:.0%})",
            f"Regla: {self.decision_rule}",
        ]
        if self.break_date is not None:
            status = (
                "significativo" if self.break_significant else "no significativo, solo indicativo"
            )
            lines.append(
                f"Fecha que minimiza el estadístico ZA: {self.break_date.date()} ({status})"
            )
        diffs = sorted({int(t.specification.get("difference", 0)) for t in self.tests})
        for d in diffs:
            lines.append(f"-- Diferencia d={d} --")
            for t in self.tests_at(d):
                decision = "rechaza H0" if t.rejects(self.alpha) else "no rechaza H0"
                p = t.p_value_label
                lines.append(
                    f"  {t.name:<4} estad.={t.statistic:9.4f}  p={p:<7} {decision}"
                    f"  [{t.specification.get('deterministic', t.specification.get('break_in'))},"
                    f" rezagos={t.specification.get('lags')}]"
                )
        lines.extend(f"Nota: {n}" for n in self.notes)
        return "\n".join(lines)


def _with_difference(result: HypothesisTestResult, d: int) -> HypothesisTestResult:
    spec = dict(result.specification)
    spec["difference"] = d
    return HypothesisTestResult(
        name=result.name,
        statistic=result.statistic,
        p_value=result.p_value,
        null_hypothesis=result.null_hypothesis,
        critical_values=result.critical_values,
        specification=spec,
        reference=result.reference,
        notes=result.notes,
        p_value_bound=result.p_value_bound,
    )


DECISION_RULE = (
    "Regla confirmatoria jerárquica en cada diferencia d: (1) si ADF y PP (H0: raíz unitaria) "
    "rechazan, la serie es estacionaria en d; si además KPSS (H0: estacionariedad) rechaza se "
    "registra la discrepancia. (2) Si ADF y PP no rechazan y KPSS rechaza, hay raíz unitaria: "
    "se diferencia y se repite. (3) Si ADF y PP no rechazan y KPSS tampoco, los datos no son "
    "informativos (inconcluso). (4) Si ADF y PP discrepan, inconcluso. Deterministas de la "
    "serie original en d=0 y solo constante en las diferencias."
)


def stationarity(
    series: pd.Series,
    *,
    trend: Trend = "c",
    alpha: float = 0.05,
    max_d: int = 2,
    breaks: bool = True,
) -> StationarityReport:
    """Determina el orden de integración con la regla confirmatoria.

    Parameters
    ----------
    series : pandas.Series
        Serie sin faltantes (ver :func:`tsinsurance.data.prepare`).
    trend : {"c", "ct"}
        Componentes determinísticos para el nivel de la serie.
    alpha : float
        Nivel de significancia de todas las pruebas.
    max_d : int
        Máximo orden de diferenciación a evaluar (1 o 2).
    breaks : bool
        Si ``True`` y hay al menos ``MIN_OBS_BREAK`` observaciones, ejecuta
        Zivot-Andrews sobre el nivel y reporta la fecha candidata de quiebre.

    Returns
    -------
    StationarityReport
    """
    if alpha not in ALPHAS:
        raise ValueError(
            f"alpha debe ser uno de {ALPHAS}: los valores p de KPSS están acotados a "
            "[0,01; 0,10] y la decisión usa valores críticos tabulados."
        )
    if max_d not in (1, 2):
        raise ValueError("max_d debe ser 1 o 2.")
    s = _clean(series, "stationarity", MIN_OBS + max_d)
    name = str(s.name) if s.name is not None else "serie"
    tests: list[HypothesisTestResult] = []
    notes: list[str] = []
    order: int | None = None
    conclusion: Conclusion = "inconclusive"

    current = s
    for d in range(max_d + 1):
        det: Trend = trend if d == 0 else "c"
        level_tests = [adf(current, trend=det), pp(current, trend=det), kpss(current, trend=det)]
        tests.extend(_with_difference(t, d) for t in level_tests)
        a, p, k = (t.rejects(alpha) for t in level_tests)
        if a and p:
            order = d
            conclusion = ("I(0)", "I(1)", "I(2)")[d]
            if k:
                notes.append(
                    f"En d={d} ADF y PP rechazan la raíz unitaria pero KPSS rechaza "
                    "estacionariedad: posible memoria larga o quiebre; revise con cautela."
                )
            break
        if not a and not p and k:
            if d == max_d:
                notes.append(f"La serie no es estacionaria ni tras {max_d} diferencias.")
                break
            current = current.diff().dropna()
            continue
        if not a and not p:
            notes.append(
                f"En d={d} ninguna prueba rechaza: los datos no permiten distinguir entre raíz "
                "unitaria y estacionariedad (baja potencia)."
            )
        else:
            notes.append(
                f"Resultados contradictorios en d={d}: ADF {'rechaza' if a else 'no rechaza'}, "
                f"PP {'rechaza' if p else 'no rechaza'}."
            )
        break

    break_date: pd.Timestamp | None = None
    break_significant = False
    if breaks:
        if len(s) >= MIN_OBS_BREAK:
            za, brk = zivot_andrews(s, trend="c" if trend == "c" else "ct")
            tests.append(_with_difference(za, 0))
            break_date = brk if isinstance(brk, pd.Timestamp) else None
            break_significant = za.rejects(alpha)
            if za.rejects(alpha) and order != 0:
                notes.append(
                    "Zivot-Andrews rechaza la raíz unitaria al permitir un quiebre en "
                    f"{za.specification['break_point']}: la no estacionariedad aparente "
                    "podría deberse a un cambio estructural."
                )
        else:
            notes.append(
                f"Zivot-Andrews omitida: requiere {MIN_OBS_BREAK} observaciones ({len(s)})."
            )
    return StationarityReport(
        series_id=name,
        tests=tuple(tests),
        integration_order=order,
        conclusion=conclusion,
        decision_rule=DECISION_RULE,
        alpha=alpha,
        break_date=break_date,
        notes=tuple(notes),
        break_significant=break_significant,
    )
