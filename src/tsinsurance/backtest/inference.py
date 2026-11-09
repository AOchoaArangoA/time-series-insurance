"""Inferencia sobre el desempeño de estrategias y la precisión de pronósticos.

References
----------
.. [1] Mertens, E. (2002). Comments on variance of the IID estimator in Lo (2002).
.. [2] Lo, A. (2002). The statistics of Sharpe ratios. FAJ, 58(4), 36-52.
.. [3] Bailey, D. & López de Prado, M. (2012). The Sharpe ratio efficient frontier.
   Journal of Risk, 15(2).
.. [4] Bailey, D. & López de Prado, M. (2014). The deflated Sharpe ratio. Journal of
   Portfolio Management, 40(5), 94-107.
.. [5] Hansen, P. R. (2005). A test for superior predictive ability. JBES, 23(4).
.. [6] Ledoit, O. & Wolf, M. (2008). Robust performance hypothesis testing with the
   Sharpe ratio. Journal of Empirical Finance, 15(5), 850-859.
.. [7] Politis, D. & Romano, J. (1994). The stationary bootstrap. JASA, 89(428).
.. [8] Pesaran, M. H. & Timmermann, A. (1992). A simple nonparametric test of
   predictive performance. JBES, 10(4), 461-465.
.. [9] Clark, T. & West, K. (2007). Approximately normal tests for equal predictive
   accuracy in nested models. Journal of Econometrics, 138(1), 291-311.
.. [10] Campbell, J. & Thompson, S. (2008). Predicting excess stock returns out of
   sample. Review of Financial Studies, 21(4), 1509-1531.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from arch.bootstrap import SPA, StationaryBootstrap, optimal_block_length
from scipy import stats

from tsinsurance.errors import DataValidationError, InsufficientDataError
from tsinsurance.results import HypothesisTestResult, ResultMixin
from tsinsurance.validation import diebold_mariano

__all__ = [
    "DeflatedSharpe",
    "ForecastEvaluation",
    "SPAResult",
    "SharpeDifference",
    "SharpeInference",
    "clark_west",
    "deflated_sharpe",
    "effective_number_of_trials",
    "evaluate_forecasts",
    "expected_max_sharpe",
    "oos_r2",
    "pesaran_timmermann",
    "probabilistic_sharpe",
    "psr_from_moments",
    "sharpe_difference",
    "sharpe_inference",
    "spa_test",
]

EULER_GAMMA = 0.5772156649015329


def _clean(x: pd.Series | np.ndarray, name: str, minimum: int = 10) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < minimum:
        raise InsufficientDataError(name, minimum, int(arr.size))
    return arr


def _sr(x: np.ndarray) -> float:
    from tsinsurance.backtest.metrics import sharpe_per_period

    return sharpe_per_period(x)


def _block(x: np.ndarray) -> int:
    """Bloque óptimo de Politis-White para el bootstrap estacionario (1 si es degenerado)."""
    if float(np.std(x)) == 0.0:
        return 1
    with np.errstate(invalid="ignore", divide="ignore"):
        value = float(optimal_block_length(x)["stationary"].iloc[0])
    return max(1, int(np.ceil(value))) if np.isfinite(value) else 1


# --- Sharpe ---------------------------------------------------------------------------


def psr_from_moments(
    sharpe: float, n: int, skew: float, kurtosis: float, sharpe_benchmark: float = 0.0
) -> float:
    """Sharpe probabilístico a partir de momentos (SR por periodo, curtosis no-exceso)."""
    denom = 1.0 - skew * sharpe + (kurtosis - 1.0) / 4.0 * sharpe**2
    if denom <= 0 or n < 2:
        return float("nan")
    z = (sharpe - sharpe_benchmark) * math.sqrt(n - 1) / math.sqrt(denom)
    return float(stats.norm.cdf(z))


def probabilistic_sharpe(returns: pd.Series | np.ndarray, sr_benchmark: float = 0.0) -> float:
    """Probabilidad de que el Sharpe verdadero (por periodo) supere ``sr_benchmark``."""
    x = _clean(returns, "probabilistic_sharpe")
    return psr_from_moments(
        _sr(x), x.size, float(stats.skew(x)), float(stats.kurtosis(x, fisher=False)), sr_benchmark
    )


def expected_max_sharpe(trials_sharpe_variance: float, n_trials: float) -> float:
    """Máximo esperado del Sharpe (por periodo) entre ``n_trials`` pruebas sin habilidad."""
    if n_trials <= 1:
        return 0.0
    g = EULER_GAMMA
    z1 = float(stats.norm.ppf(1 - 1 / n_trials))
    z2 = float(stats.norm.ppf(1 - 1 / (n_trials * math.e)))
    return math.sqrt(trials_sharpe_variance) * ((1 - g) * z1 + g * z2)


def effective_number_of_trials(trial_returns: pd.DataFrame) -> float:
    """Número efectivo de pruebas ``(Σλ)²/Σλ²`` de la matriz de correlación."""
    clean = trial_returns.dropna()
    if clean.shape[1] < 2:
        return float(clean.shape[1])
    corr = np.nan_to_num(np.corrcoef(clean.to_numpy(), rowvar=False), nan=0.0)
    lam = np.clip(np.linalg.eigvalsh(corr), 0.0, None)
    return float(lam.sum() ** 2 / (lam**2).sum())


@dataclass(frozen=True, slots=True)
class SharpeInference(ResultMixin):
    """Inferencia sobre el Sharpe anualizado."""

    sharpe: float
    se_iid: float
    se_hac: float
    ci_low: float
    ci_high: float
    psr: float
    block_length: int
    reps: int
    seed: int
    n: int

    def summary(self) -> str:
        """Resumen de una línea."""
        return (
            f"Sharpe anual={self.sharpe:.3f}  EE iid={self.se_iid:.3f}  EE HAC={self.se_hac:.3f}  "
            f"IC95 bootstrap=[{self.ci_low:.3f}, {self.ci_high:.3f}]  PSR(>0)={self.psr:.3f}  "
            f"(bloque={self.block_length}, n={self.n})"
        )


def sharpe_inference(
    returns: pd.Series | np.ndarray,
    periods_per_year: int,
    *,
    reps: int = 1000,
    seed: int = 0,
) -> SharpeInference:
    """Sharpe anualizado con EE iid (Mertens), EE HAC (delta) e IC por bootstrap estacionario."""
    x = _clean(returns, "sharpe_inference", 30)
    n = x.size
    sr = _sr(x)
    skew = float(stats.skew(x))
    kurt = float(stats.kurtosis(x, fisher=False))
    ann = math.sqrt(periods_per_year)
    se_iid = math.sqrt(max(1 - skew * sr + (kurt - 1) / 4 * sr**2, 0.0) / n)
    # Método delta con covarianza HAC (Newey-West) de (r, r²).
    m1, m2 = x.mean(), (x**2).mean()
    sigma = math.sqrt(m2 - m1**2)
    grad = np.array([m2 / sigma**3, -m1 / (2 * sigma**3)])
    z = np.column_stack([x - m1, x**2 - m2])
    lags = int(np.floor(4 * (n / 100) ** (2 / 9)))
    cov = z.T @ z / n
    for k in range(1, lags + 1):
        g = z[k:].T @ z[:-k] / n
        cov += (1 - k / (lags + 1)) * (g + g.T)
    se_hac = math.sqrt(max(float(grad @ cov @ grad), 0.0) / n)
    block = _block(x)
    bs = StationaryBootstrap(block, x, seed=seed)
    ci = bs.conf_int(lambda y: np.array([_sr(y) * ann]), reps=reps, method="percentile")
    return SharpeInference(
        sharpe=sr * ann,
        se_iid=se_iid * ann,
        se_hac=se_hac * ann,
        ci_low=float(ci[0, 0]),
        ci_high=float(ci[1, 0]),
        psr=psr_from_moments(sr, n, skew, kurt),
        block_length=block,
        reps=reps,
        seed=seed,
        n=n,
    )


@dataclass(frozen=True, slots=True)
class DeflatedSharpe(ResultMixin):
    """Sharpe deflactado (todo por periodo)."""

    sharpe: float
    n_trials: int
    n_effective: float
    trials_sharpe_variance: float
    sr0: float
    dsr: float

    def summary(self) -> str:
        """Resumen de una línea."""
        return (
            f"DSR={self.dsr:.3f} (SR/periodo={self.sharpe:.4f}, umbral SR0={self.sr0:.4f}, "
            f"pruebas={self.n_trials}, efectivas={self.n_effective:.1f})"
        )


def deflated_sharpe(
    returns: pd.Series | np.ndarray,
    n_trials: int,
    trials_sharpe_variance: float,
    *,
    n_effective: float | None = None,
) -> DeflatedSharpe:
    """Sharpe deflactado de Bailey y López de Prado (2014).

    ``trials_sharpe_variance`` es la varianza **por periodo** de los Sharpe de todas las
    pruebas; ``n_effective`` (si se da) reemplaza a ``n_trials`` en el umbral.

    Advertencia: el N efectivo por autovalores (:func:`effective_number_of_trials`) no es
    consistente con una varianza calculada sobre todas las pruebas; con pruebas que
    comparten un factor común produce N ≈ 4 de 100 y un tamaño ≈ 22 % (medido). Use
    ``n_effective`` sólo con representantes de clústeres y su varianza propia.
    """
    x = _clean(returns, "deflated_sharpe")
    n_eff = float(n_effective) if n_effective is not None else float(n_trials)
    sr0 = expected_max_sharpe(trials_sharpe_variance, max(n_eff, 1.0))
    dsr = psr_from_moments(
        _sr(x), x.size, float(stats.skew(x)), float(stats.kurtosis(x, fisher=False)), sr0
    )
    return DeflatedSharpe(_sr(x), n_trials, n_eff, trials_sharpe_variance, sr0, dsr)


@dataclass(frozen=True, slots=True)
class SharpeDifference(ResultMixin):
    """Comparación de Sharpe y equivalente cierto de dos estrategias (a − b)."""

    sharpe_a: float
    sharpe_b: float
    difference: float
    p_value: float
    cer_gain: float
    gamma: float
    block_length: int
    reps: int

    def summary(self) -> str:
        """Resumen de una línea."""
        return (
            f"Sharpe {self.sharpe_a:.3f} vs {self.sharpe_b:.3f} (dif. {self.difference:+.3f}, "
            f"p unilateral={self.p_value:.3f}); ganancia CER(γ={self.gamma:g})="
            f"{self.cer_gain:+.2%} anual"
        )


def sharpe_difference(
    a: pd.Series | np.ndarray,
    b: pd.Series | np.ndarray,
    *,
    periods_per_year: int = 252,
    reps: int = 1000,
    seed: int = 0,
    gamma: float = 3.0,
) -> SharpeDifference:
    """Prueba unilateral H0: Sharpe(a) ≤ Sharpe(b) por bootstrap estacionario pareado.

    Versión no estudentizada del enfoque de Ledoit y Wolf (2008): valor p
    ``P*(Δ* − Δ̂ ≥ Δ̂)``. Incluye la ganancia de equivalente cierto media-varianza
    (Campbell y Thompson 2008) ``CER = μ − γσ²/2`` anualizada.
    """
    xa = np.asarray(a, dtype=float)
    xb = np.asarray(b, dtype=float)
    mask = np.isfinite(xa) & np.isfinite(xb)
    xa, xb = xa[mask], xb[mask]
    if xa.size < 30:
        raise InsufficientDataError("sharpe_difference", 30, int(xa.size))
    ann = math.sqrt(periods_per_year)
    diff = (_sr(xa) - _sr(xb)) * ann
    block = _block(xa - xb)
    bs = StationaryBootstrap(block, xa, xb, seed=seed)
    draws = np.array(
        [(_sr(np.asarray(p[0])) - _sr(np.asarray(p[1]))) * ann for p, _ in bs.bootstrap(reps)]
    )
    draws = draws[np.isfinite(draws)]
    p = float(np.mean(draws - diff >= diff))

    def cer(x: np.ndarray) -> float:
        return float(np.mean(x) - gamma / 2 * np.var(x, ddof=1)) * periods_per_year

    return SharpeDifference(
        sharpe_a=_sr(xa) * ann,
        sharpe_b=_sr(xb) * ann,
        difference=diff,
        p_value=p,
        cer_gain=cer(xa) - cer(xb),
        gamma=gamma,
        block_length=block,
        reps=reps,
    )


@dataclass(frozen=True, slots=True)
class SPAResult(ResultMixin):
    """Prueba SPA de Hansen (H0: ningún modelo supera al benchmark)."""

    pvalue_consistent: float
    pvalue_lower: float
    pvalue_upper: float
    n_models: int
    block_size: int
    reps: int
    seed: int

    def summary(self) -> str:
        """Resumen de una línea."""
        return (
            f"SPA (Hansen): p consistente={self.pvalue_consistent:.3f} "
            f"[inferior {self.pvalue_lower:.3f}, superior {self.pvalue_upper:.3f}], "
            f"{self.n_models} modelo(s)"
        )


def spa_test(
    benchmark_returns: pd.Series | np.ndarray,
    strategy_returns: pd.DataFrame | pd.Series,
    *,
    reps: int = 1000,
    seed: int = 0,
    relative: bool = True,
) -> SPAResult:
    """SPA de Hansen sobre pérdidas = −retornos.

    Con ``relative=True`` (por defecto) las pérdidas de cada modelo son
    ``−(r_estrategia − r_benchmark)`` frente a un benchmark de pérdida 0, lo que permite
    un benchmark distinto por columna si se entregan ya en diferencias. Decide el valor
    p *consistente*.
    """
    strat = (
        strategy_returns.to_frame() if isinstance(strategy_returns, pd.Series) else strategy_returns
    )
    bench = np.asarray(benchmark_returns, dtype=float)
    models = strat.to_numpy(dtype=float)
    if models.shape[0] != bench.shape[0]:
        raise DataValidationError("benchmark y estrategias deben tener la misma longitud.")
    mask = np.isfinite(bench) & np.isfinite(models).all(axis=1)
    bench, models = bench[mask], models[mask]
    if bench.size < 30:
        raise InsufficientDataError("spa_test", 30, int(bench.size))
    if relative:
        losses_m = -(models - bench[:, None])
        losses_b = np.zeros_like(bench)
    else:
        losses_m, losses_b = -models, -bench
    block = _block(losses_m.mean(axis=1) - losses_b)
    spa = SPA(losses_b, losses_m, block_size=block, reps=reps, bootstrap="stationary", seed=seed)
    spa.compute()
    pv = spa.pvalues
    return SPAResult(
        pvalue_consistent=float(pv["consistent"]),
        pvalue_lower=float(pv["lower"]),
        pvalue_upper=float(pv["upper"]),
        n_models=models.shape[1],
        block_size=block,
        reps=reps,
        seed=seed,
    )


# --- Pronósticos ------------------------------------------------------------------------


def _aligned(*arrays: pd.Series | np.ndarray) -> list[np.ndarray]:
    arrs = [np.asarray(a, dtype=float) for a in arrays]
    if len({a.shape for a in arrs}) != 1:
        raise DataValidationError("Las series de pronóstico deben tener la misma longitud.")
    mask = np.ones(arrs[0].shape, dtype=bool)
    for a in arrs:
        mask &= np.isfinite(a)
    return [a[mask] for a in arrs]


def pesaran_timmermann(
    forecast: pd.Series | np.ndarray, realized: pd.Series | np.ndarray
) -> HypothesisTestResult:
    """Prueba de Pesaran-Timmermann de precisión direccional (unilateral).

    Dirección = signo estrictamente positivo. Si los pronósticos o los realizados tienen
    un solo signo la prueba no es aplicable (``p_value=None``).
    """
    f, y = _aligned(forecast, realized)
    n = f.size
    if n < 10:
        raise InsufficientDataError("Pesaran-Timmermann", 10, n)
    x_up, y_up = f > 0, y > 0
    p_hat = float(np.mean(x_up == y_up))
    px, py = float(x_up.mean()), float(y_up.mean())
    spec = {"nobs": n, "hit_rate": p_hat, "share_forecast_up": px, "share_realized_up": py}
    if px in (0.0, 1.0) or py in (0.0, 1.0):
        return HypothesisTestResult(
            name="Pesaran-Timmermann",
            statistic=float("nan"),
            p_value=None,
            null_hypothesis="Los signos pronosticados son independientes de los realizados.",
            specification=spec,
            reference="Pesaran & Timmermann (1992)",
            notes=("No aplicable: pronósticos o realizados con un solo signo.",),
        )
    p_star = py * px + (1 - py) * (1 - px)
    v_p = p_star * (1 - p_star) / n
    v_star = (
        (2 * py - 1) ** 2 * px * (1 - px) / n
        + (2 * px - 1) ** 2 * py * (1 - py) / n
        + 4 * py * px * (1 - py) * (1 - px) / n**2
    )
    stat = (p_hat - p_star) / math.sqrt(v_p - v_star)
    return HypothesisTestResult(
        name="Pesaran-Timmermann",
        statistic=float(stat),
        p_value=float(stats.norm.sf(stat)),
        null_hypothesis="Los signos pronosticados son independientes de los realizados.",
        specification={**spec, "one_sided": True},
        reference="Pesaran & Timmermann (1992)",
    )


def clark_west(
    realized: pd.Series | np.ndarray,
    f_restricted: pd.Series | np.ndarray,
    f_unrestricted: pd.Series | np.ndarray,
) -> HypothesisTestResult:
    """Prueba de Clark-West (2007) para modelos anidados, h = 1, unilateral.

    H0: el modelo restringido (p. ej. media histórica) es al menos tan preciso.
    """
    y, f1, f2 = _aligned(realized, f_restricted, f_unrestricted)
    n = y.size
    if n < 10:
        raise InsufficientDataError("Clark-West", 10, n)
    adj = (y - f1) ** 2 - ((y - f2) ** 2 - (f1 - f2) ** 2)
    sd = float(np.std(adj, ddof=1))
    stat = float(np.mean(adj) / (sd / math.sqrt(n))) if sd > 0 else float("nan")
    return HypothesisTestResult(
        name="Clark-West",
        statistic=stat,
        p_value=float(stats.norm.sf(stat)) if math.isfinite(stat) else None,
        null_hypothesis="El modelo restringido (anidado) es al menos tan preciso.",
        specification={"h": 1, "nobs": n, "one_sided": True},
        reference="Clark & West (2007)",
    )


def oos_r2(
    realized: pd.Series | np.ndarray,
    f_restricted: pd.Series | np.ndarray,
    f_unrestricted: pd.Series | np.ndarray,
) -> float:
    """R² fuera de muestra de Campbell y Thompson (2008)."""
    y, f1, f2 = _aligned(realized, f_restricted, f_unrestricted)
    denom = float(np.sum((y - f1) ** 2))
    return 1.0 - float(np.sum((y - f2) ** 2)) / denom if denom > 0 else float("nan")


@dataclass(frozen=True, slots=True)
class ForecastEvaluation(ResultMixin):
    """Evaluación fuera de muestra de un pronóstico frente a la media histórica."""

    oos_r2: float
    clark_west: HypothesisTestResult
    diebold_mariano: HypothesisTestResult
    pesaran_timmermann: HypothesisTestResult
    hit_rate: float
    n_forecasts: int

    def summary(self) -> str:
        """Resumen legible."""
        lines = [
            f"Evaluación fuera de muestra ({self.n_forecasts} pronósticos): "
            f"R²_OS={self.oos_r2:+.2%}  aciertos de signo={self.hit_rate:.1%}"
        ]
        for t in (self.clark_west, self.pesaran_timmermann, self.diebold_mariano):
            lines.append(f"  {t.name:<22} estad.={t.statistic:8.3f}  p={t.p_value_label}")
            lines.extend(f"    Nota: {n}" for n in t.notes)
        return "\n".join(lines)


def evaluate_forecasts(
    realized: pd.Series | np.ndarray,
    f_restricted: pd.Series | np.ndarray,
    f_unrestricted: pd.Series | np.ndarray,
) -> ForecastEvaluation:
    """R²_OS, Clark-West, Diebold-Mariano (con nota de anidamiento) y Pesaran-Timmermann."""
    y, f1, f2 = _aligned(realized, f_restricted, f_unrestricted)
    dm = diebold_mariano(y - f1, y - f2)
    dm = HypothesisTestResult(
        name=dm.name,
        statistic=dm.statistic,
        p_value=dm.p_value,
        null_hypothesis=dm.null_hypothesis,
        specification=dm.specification,
        reference=dm.reference,
        notes=(
            "No válida para modelos anidados (subdimensionada); la prueba principal es Clark-West.",
        ),
    )
    return ForecastEvaluation(
        oos_r2=oos_r2(y, f1, f2),
        clark_west=clark_west(y, f1, f2),
        diebold_mariano=dm,
        pesaran_timmermann=pesaran_timmermann(f2, y),
        hit_rate=float(np.mean((f2 > 0) == (y > 0))),
        n_forecasts=int(y.size),
    )
