"""Estadísticos descriptivos, autocorrelación y pruebas de normalidad y efectos ARCH.

References
----------
.. [1] Jarque, C. M. & Bera, A. K. (1980). Efficient tests for normality,
   homoscedasticity and serial independence of regression residuals. Economics
   Letters, 6(3), 255-259.
.. [2] Ljung, G. M. & Box, G. E. P. (1978). On a measure of lack of fit in time series
   models. Biometrika, 65(2), 297-303.
.. [3] Engle, R. F. (1982). Autoregressive conditional heteroscedasticity with
   estimates of the variance of United Kingdom inflation. Econometrica, 50(4), 987-1007.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from statsmodels.tsa.ar_model import AutoReg, ar_select_order
from statsmodels.tsa.stattools import acf, pacf

from tsinsurance.diagnostics.stationarity import MIN_OBS, _clean
from tsinsurance.errors import DataValidationError
from tsinsurance.results import HypothesisTestResult, ResultMixin

__all__ = ["DescriptiveReport", "arch_lm", "describe", "jarque_bera", "ljung_box"]


def _finite(x: pd.Series | np.ndarray, procedure: str) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    if not np.isfinite(arr).all():
        raise DataValidationError(f"{procedure}: la serie tiene faltantes o infinitos.")
    return arr


def jarque_bera(x: pd.Series | np.ndarray) -> HypothesisTestResult:
    """Prueba de normalidad de Jarque-Bera (H0: asimetría 0 y curtosis 3)."""
    arr = _finite(x, "Jarque-Bera")
    res = stats.jarque_bera(arr)
    return HypothesisTestResult(
        name="Jarque-Bera",
        statistic=float(res.statistic),
        p_value=float(res.pvalue),
        null_hypothesis="Los datos provienen de una distribución normal.",
        specification={"nobs": int(arr.size), "df": 2},
        reference="Jarque & Bera (1980)",
    )


def ljung_box(
    x: pd.Series | np.ndarray, *, lags: int = 10, model_df: int = 0, name: str = "Ljung-Box"
) -> HypothesisTestResult:
    """Prueba de Ljung-Box (H0: sin autocorrelación hasta ``lags``).

    ``model_df`` resta grados de libertad por parámetros ARMA estimados.
    """
    arr = _finite(x, name)
    if lags <= model_df:
        raise ValueError("lags debe ser mayor que model_df.")
    table = acorr_ljungbox(arr, lags=[lags], model_df=model_df, return_df=True)
    return HypothesisTestResult(
        name=name,
        statistic=float(table["lb_stat"].iloc[0]),
        p_value=float(table["lb_pvalue"].iloc[0]),
        null_hypothesis=f"No hay autocorrelación hasta el rezago {lags}.",
        specification={"lags": lags, "model_df": model_df, "df": lags - model_df},
        reference="Ljung & Box (1978)",
    )


def arch_lm(x: pd.Series | np.ndarray, *, lags: int = 5) -> HypothesisTestResult:
    """Prueba ARCH-LM de Engle (H0: sin heterocedasticidad condicional).

    Se aplica sobre la serie centrada: si la media no es cero, ``x²`` contendría el
    término ``2μe`` y la autocorrelación de la media aparecería como falso ARCH.
    Para residuos de un modelo de media, pase directamente los residuos.
    """
    arr = _finite(x, "ARCH-LM")
    res = het_arch(arr - arr.mean(), nlags=lags, result_object=True)
    lm, lm_p = res.lm, res.lmpval
    return HypothesisTestResult(
        name="ARCH-LM",
        statistic=float(lm),
        p_value=float(lm_p),
        null_hypothesis=f"No hay efectos ARCH hasta el rezago {lags}.",
        specification={"lags": lags, "df": lags, "centered": True},
        reference="Engle (1982)",
    )


@dataclass(frozen=True, slots=True, eq=False)
class DescriptiveReport(ResultMixin):
    """Estadísticos descriptivos y pruebas básicas de una serie.

    Attributes
    ----------
    series_id : str
    stats : pandas.Series
        n, media, desviación, asimetría, curtosis en exceso, mínimo, cuantiles, máximo.
    acf, pacf : pandas.Series
        Autocorrelaciones simple y parcial (rezagos 1..nlags).
    confidence_band : float
        Banda aproximada al 95 % (``1.96 / sqrt(n)``).
    jarque_bera, ljung_box : HypothesisTestResult
        Sobre la serie.
    ljung_box_squared, arch_lm : HypothesisTestResult
        Sobre los residuos de un AR(p) con p elegido por AIC (``mean_ar_order``), para
        no confundir la dinámica de la media con heterocedasticidad condicional
        (Engle 1982 formula la prueba sobre residuos).
    mean_ar_order : int
        Orden del AR usado para filtrar la media.
    """

    series_id: str
    stats: pd.Series
    acf: pd.Series
    pacf: pd.Series
    confidence_band: float
    jarque_bera: HypothesisTestResult
    ljung_box: HypothesisTestResult
    ljung_box_squared: HypothesisTestResult
    arch_lm: HypothesisTestResult
    mean_ar_order: int = 0

    def summary(self) -> str:
        """Resumen legible."""
        st = self.stats
        lines = [
            f"Estadísticos descriptivos — {self.series_id}",
            f"  n={int(st['n'])}  media={st['mean']:.6g}  desv.={st['std']:.6g}  "
            f"asimetría={st['skewness']:.4f}  curtosis exceso={st['excess_kurtosis']:.4f}",
            f"  mín={st['min']:.6g}  p1={st['p01']:.6g}  p50={st['p50']:.6g}  "
            f"p99={st['p99']:.6g}  máx={st['max']:.6g}",
            "  ACF  1-5: " + " ".join(f"{v:+.3f}" for v in self.acf.iloc[:5]),
            "  PACF 1-5: " + " ".join(f"{v:+.3f}" for v in self.pacf.iloc[:5]),
            f"  Banda 95 %: ±{self.confidence_band:.3f}",
        ]
        for t in (self.jarque_bera, self.ljung_box, self.ljung_box_squared, self.arch_lm):
            lines.append(f"  {t.name:<16} estad.={t.statistic:10.4f}  p={t.p_value:.4f}")
        return "\n".join(lines)


def describe(series: pd.Series, *, nlags: int = 20, arch_lags: int = 5) -> DescriptiveReport:
    """Estadísticos descriptivos, ACF/PACF, normalidad, autocorrelación y efectos ARCH."""
    s = _clean(series, "describe", MIN_OBS)
    x = s.to_numpy()
    n = len(x)
    nlags = min(nlags, n // 2 - 1)
    q = np.quantile(x, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    summary_stats = pd.Series(
        {
            "n": float(n),
            "mean": float(np.mean(x)),
            "std": float(np.std(x, ddof=1)),
            "skewness": float(stats.skew(x)),
            "excess_kurtosis": float(stats.kurtosis(x)),
            "min": float(np.min(x)),
            "p01": q[0],
            "p05": q[1],
            "p25": q[2],
            "p50": q[3],
            "p75": q[4],
            "p95": q[5],
            "p99": q[6],
            "max": float(np.max(x)),
        }
    )
    lags = pd.RangeIndex(1, nlags + 1, name="lag")
    sel = ar_select_order(x, maxlag=min(10, nlags), ic="aic", trend="c")
    order = max(sel.ar_lags) if sel.ar_lags else 0
    if order:
        resid = np.asarray(AutoReg(x, lags=order, trend="c").fit().resid, dtype=float)
    else:
        resid = x - x.mean()
    centered = resid - resid.mean()
    return DescriptiveReport(
        series_id=str(s.name) if s.name is not None else "serie",
        stats=summary_stats,
        acf=pd.Series(acf(x, nlags=nlags, fft=True)[1:], index=lags, name="acf"),
        pacf=pd.Series(pacf(x, nlags=nlags, method="ywadjusted")[1:], index=lags, name="pacf"),
        confidence_band=1.96 / float(np.sqrt(n)),
        jarque_bera=jarque_bera(x),
        ljung_box=ljung_box(x, lags=min(10, nlags)),
        ljung_box_squared=ljung_box(centered**2, lags=min(10, nlags), name="Ljung-Box (e²)"),
        arch_lm=arch_lm(resid, lags=arch_lags),
        mean_ar_order=order,
    )
