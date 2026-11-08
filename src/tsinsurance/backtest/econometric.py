"""Señales econométricas: regresión predictiva *walk-forward* con variables macro.

Validación doble (Principio VIII): (a) estadística —estacionariedad y persistencia de
regresores, coeficientes HAC, diagnósticos de residuos, R² fuera de muestra con
Clark-West y precisión direccional con Pesaran-Timmermann— y (b) económica —backtest
neto de costos frente a la misma regla de posición aplicada a la media histórica—.

References
----------
.. [1] Welch, I. & Goyal, A. (2008). A comprehensive look at the empirical performance
   of equity premium prediction. Review of Financial Studies, 21(4), 1455-1508.
.. [2] Campbell, J. & Thompson, S. (2008). Predicting excess stock returns out of
   sample. Review of Financial Studies, 21(4), 1509-1531.
.. [3] Stambaugh, R. (1999). Predictive regressions. JFE, 54(3), 375-421.
.. [4] Newey, W. & West, K. (1987). A simple, positive semi-definite,
   heteroskedasticity and autocorrelation consistent covariance matrix. Econometrica.
.. [5] Brown, R., Durbin, J. & Evans, J. (1975). Techniques for testing the constancy
   of regression relationships over time. JRSS B, 37(2), 149-192.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import breaks_cusumolsresid

from tsinsurance.backtest.config import ExecutionConfig
from tsinsurance.backtest.engine import BacktestResult, run_backtest
from tsinsurance.backtest.inference import (
    ForecastEvaluation,
    SharpeDifference,
    evaluate_forecasts,
    sharpe_difference,
)
from tsinsurance.backtest.verdict import Verdict, make_verdict
from tsinsurance.diagnostics import StationarityReport, arch_lm, jarque_bera, ljung_box
from tsinsurance.diagnostics import stationarity as stationarity_report
from tsinsurance.diagnostics.stationarity import ALPHAS
from tsinsurance.errors import DataValidationError, InsufficientDataError
from tsinsurance.results import HypothesisTestResult, ResultMixin

__all__ = [
    "EconometricBacktest",
    "ModelValidation",
    "PredictiveRegression",
    "WalkForwardForecast",
    "backtest_econometric",
    "forecast_to_weights",
]

PositionRule = Literal["long_cash", "long_short", "proportional"]
PERSISTENCE_WARNING = 0.95


def _design(y: pd.Series, X: pd.DataFrame, ar_lags: int) -> pd.DataFrame:
    """Matriz de regresores en ``t`` (para pronosticar ``y_{t+1}``)."""
    feats = X.copy()
    for k in range(ar_lags):
        feats[f"{y.name or 'y'}_lag{k}"] = y.shift(k)
    feats.insert(0, "const", 1.0)
    return feats


@dataclass(frozen=True, slots=True, eq=False)
class WalkForwardForecast(ResultMixin):
    """Pronósticos fuera de muestra decididos en ``t`` para ``t+1``."""

    forecasts: pd.Series
    forecast_se: pd.Series
    benchmark_forecasts: pd.Series
    realized: pd.Series
    coefficient_path: pd.DataFrame
    n_refits: int
    scheme: str
    min_train: int
    refit_every: int

    def summary(self) -> str:
        """Resumen de una línea."""
        valid = self.forecasts.dropna()
        return (
            f"Walk-forward {self.scheme}: {len(valid)} pronósticos "
            f"({valid.index[0].date()} a {valid.index[-1].date()}), {self.n_refits} "
            f"re-estimaciones, min_train={self.min_train}, refit_every={self.refit_every}"
        )


@dataclass(frozen=True, slots=True, eq=False)
class ModelValidation(ResultMixin):
    """Validación estadística de muestra completa (descriptiva ex post).

    No debe usarse para elegir la especificación: hacerlo introduce información futura.
    """

    coefficients: pd.DataFrame
    r2: float
    adj_r2: float
    hac_lags: int
    regressor_stationarity: dict[str, StationarityReport]
    persistence: pd.DataFrame
    residual_tests: tuple[HypothesisTestResult, ...]
    diagnostics_passed: bool
    warnings: tuple[str, ...]
    nobs: int

    def summary(self) -> str:
        """Reporte legible."""
        lines = [
            f"Validación del modelo (muestra completa, n={self.nobs}, descriptiva ex post): "
            f"R²={self.r2:.3f}  R² ajustado={self.adj_r2:.3f}  HAC rezagos={self.hac_lags}",
            self.coefficients.to_string(float_format=lambda v: f"{v: .4f}"),
            "Estacionariedad de regresores: "
            + ", ".join(f"{k}={v.conclusion}" for k, v in self.regressor_stationarity.items()),
            "Persistencia (ρ AR(1), δ = corr. de innovaciones, sesgo de Stambaugh aprox.):",
            self.persistence.to_string(float_format=lambda v: f"{v: .4f}"),
            "Diagnósticos de residuos:",
        ]
        for t in self.residual_tests:
            lines.append(f"  {t.name:<16} estad.={t.statistic:9.4f}  p={t.p_value_label}")
        lines.append(f"Diagnósticos superados: {'sí' if self.diagnostics_passed else 'no'}")
        lines.extend(f"Advertencia: {w}" for w in self.warnings)
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class PredictiveRegression:
    """Regresión predictiva ``y_{t+1} = a + b'X_t + Σ c_k y_{t-k} + e``.

    Parameters
    ----------
    ar_lags : int
        Rezagos autorregresivos de ``y`` incluidos como regresores.
    scheme : {"expanding", "rolling"}
    window : int, optional
        Tamaño de ventana para ``rolling``.
    min_train : int
        Pares (X_s, y_{s+1}) mínimos antes del primer pronóstico.
    refit_every : int
        Re-estimar cada ``refit_every`` fechas de decisión.
    """

    ar_lags: int = 0
    scheme: Literal["expanding", "rolling"] = "expanding"
    window: int | None = None
    min_train: int = 60
    refit_every: int = 1

    def __post_init__(self) -> None:
        if self.scheme == "rolling" and (self.window is None or self.window < self.min_train):
            raise DataValidationError("scheme='rolling' requiere window >= min_train.")
        if self.min_train < 10 or self.refit_every < 1 or self.ar_lags < 0:
            raise DataValidationError("min_train >= 10, refit_every >= 1 y ar_lags >= 0.")

    def walk_forward(self, y: pd.Series, X: pd.DataFrame) -> WalkForwardForecast:
        """Pronósticos fuera de muestra usando sólo pares observables en cada ``t``.

        ``y_t`` es el retorno del periodo que termina en ``t``; ``X_t`` lo conocido en
        ``t`` (ver :func:`tsinsurance.backtest.align_point_in_time`).
        """
        y = y.astype(float)
        feats = _design(y, X.reindex(y.index), self.ar_lags)
        target = y.shift(-1)  # y_{t+1} alineado en t
        dates = y.index
        n = len(dates)
        f = np.full(n, np.nan)
        se = np.full(n, np.nan)
        fb = np.full(n, np.nan)
        coefs: dict[pd.Timestamp, np.ndarray] = {}
        beta: np.ndarray | None = None
        cov: np.ndarray | None = None
        bench_mean = np.nan
        since_refit = self.refit_every
        F = feats.to_numpy(dtype=float)
        T = target.to_numpy(dtype=float)
        valid_pair = np.isfinite(F).all(axis=1) & np.isfinite(T)
        for i in range(n):
            # Pares (s, s+1) con s+1 <= i  ⇒  s <= i-1.
            train = np.where(valid_pair[:i])[0]
            if self.scheme == "rolling" and self.window is not None:
                train = train[-self.window :]
            if len(train) < self.min_train or not np.isfinite(F[i]).all():
                continue
            if since_refit >= self.refit_every or beta is None:
                A, b = F[train], T[train]
                beta, *_ = np.linalg.lstsq(A, b, rcond=None)
                resid = b - A @ beta
                dof = max(len(b) - A.shape[1], 1)
                sigma2 = float(resid @ resid) / dof
                cov = sigma2 * np.linalg.pinv(A.T @ A)
                bench_mean = float(np.mean(b))
                coefs[pd.Timestamp(dates[i])] = beta
                since_refit = 0
            since_refit += 1
            assert cov is not None
            f[i] = float(F[i] @ beta)
            se[i] = float(np.sqrt(max(F[i] @ cov @ F[i], 0.0)))
            fb[i] = bench_mean
        path = pd.DataFrame.from_dict(coefs, orient="index", columns=list(feats.columns))
        return WalkForwardForecast(
            forecasts=pd.Series(f, index=dates, name="forecast"),
            forecast_se=pd.Series(se, index=dates, name="forecast_se"),
            benchmark_forecasts=pd.Series(fb, index=dates, name="historical_mean"),
            realized=target.rename("realized"),
            coefficient_path=path,
            n_refits=len(coefs),
            scheme=self.scheme,
            min_train=self.min_train,
            refit_every=self.refit_every,
        )

    def validate(self, y: pd.Series, X: pd.DataFrame, *, alpha: float = 0.05) -> ModelValidation:
        """Validación de muestra completa: HAC, estacionariedad, persistencia y residuos."""
        if alpha not in ALPHAS:
            raise DataValidationError(f"alpha debe ser uno de {ALPHAS}.")
        feats = _design(y.astype(float), X.reindex(y.index), self.ar_lags)
        data = pd.concat([feats, y.shift(-1).rename("__y")], axis=1).dropna()
        n = len(data)
        if n < self.min_train:
            raise InsufficientDataError("PredictiveRegression.validate", self.min_train, n)
        A, b = data.drop(columns="__y"), data["__y"]
        lags = int(np.floor(4 * (n / 100) ** (2 / 9)))
        fit = sm.OLS(b, A).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
        coef = pd.DataFrame(
            {"coef": fit.params, "se_hac": fit.bse, "t": fit.tvalues, "p": fit.pvalues}
        )
        resid = np.asarray(fit.resid, dtype=float)
        warn: list[str] = []
        station: dict[str, StationarityReport] = {}
        unbalanced = False
        rows = []
        for col in X.columns:
            x = X[col].reindex(y.index).dropna()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                rep = stationarity_report(x.rename(col), alpha=alpha, breaks=False)
            station[col] = rep
            if rep.conclusion in ("I(1)", "I(2)"):
                unbalanced = True
                warn.append(
                    f"'{col}' es {rep.conclusion}: regresión desbalanceada (retorno I(0) sobre "
                    "regresor no estacionario); inferencia HAC no válida."
                )
            # Persistencia y sesgo de Stambaugh.
            xa = x.to_numpy()
            rho = float(np.polyfit(xa[:-1], xa[1:], 1)[0])
            v = pd.Series(xa[1:] - rho * xa[:-1], index=x.index[1:])
            u = pd.Series(resid, index=data.index).shift(1)  # u_{t+1} alineado con v_{t+1}
            pair = pd.concat([u, v], axis=1).dropna()
            pu, pv = pair.iloc[:, 0].to_numpy(), pair.iloc[:, 1].to_numpy()
            ok = len(pair) > 3
            delta = float(np.corrcoef(pu, pv)[0, 1]) if ok else float("nan")
            s_uv = float(np.cov(pu, pv)[0, 1]) if ok else float("nan")
            s_vv = float(np.var(pv, ddof=1)) if ok else float("nan")
            bias = -(s_uv / s_vv) * (1 + 3 * rho) / n if s_vv > 0 else float("nan")
            rows.append({"regresor": col, "rho": rho, "delta": delta, "sesgo_stambaugh": bias})
            if rho > PERSISTENCE_WARNING:
                warn.append(
                    f"'{col}' es muy persistente (ρ={rho:.3f}, δ={delta:.2f}): sesgo de Stambaugh "
                    f"≈ {bias:+.4f} en su coeficiente y t-estadísticos HAC sobredimensionados "
                    "(IVX pendiente)."
                )
        lb_lags = max(min(10, n // 5), self.ar_lags + 1)
        cusum_stat, cusum_p, _ = breaks_cusumolsresid(resid, ddof=A.shape[1])
        cusum = HypothesisTestResult(
            name="CUSUM (OLS)",
            statistic=float(cusum_stat),
            p_value=float(cusum_p),
            null_hypothesis="Parámetros estables en la muestra.",
            specification={"ddof": A.shape[1]},
            reference="Ploberger & Krämer (1992); Brown, Durbin & Evans (1975)",
        )
        tests = (
            ljung_box(resid, lags=lb_lags, model_df=self.ar_lags),
            arch_lm(resid, lags=min(5, n // 10)),
            jarque_bera(resid),
            cusum,
        )
        failed = [t.name for t in (tests[0], tests[1], tests[3]) if t.rejects(alpha)]
        if failed:
            warn.append("Diagnósticos rechazados: " + ", ".join(failed) + ".")
        return ModelValidation(
            coefficients=coef,
            r2=float(fit.rsquared),
            adj_r2=float(fit.rsquared_adj),
            hac_lags=lags,
            regressor_stationarity=station,
            persistence=pd.DataFrame(rows).set_index("regresor"),
            residual_tests=tests,
            diagnostics_passed=not failed and not unbalanced,
            warnings=tuple(warn),
            nobs=n,
        )


def forecast_to_weights(
    forecasts: pd.Series,
    realized_history: pd.Series,
    rule: PositionRule,
    *,
    gamma: float = 3.0,
    max_weight: float = 1.0,
    min_history: int = 12,
) -> pd.Series:
    """Convierte pronósticos (decididos en ``t``) en pesos objetivo.

    ``long_cash``: 1 si el pronóstico es positivo, 0 si no; ``long_short``: signo;
    ``proportional``: peso media-varianza ``f / (γ σ̂²_t)`` recortado a
    ``[0, max_weight]``, con ``σ̂²_t`` la varianza de los retornos conocidos hasta ``t``.
    """
    f = forecasts.astype(float)
    if rule == "long_cash":
        w = (f > 0).astype(float)
    elif rule == "long_short":
        w = pd.Series(np.sign(f.to_numpy()), index=f.index)
    elif rule == "proportional":
        var = realized_history.astype(float).expanding(min_periods=min_history).var()
        w = (f / (gamma * var.reindex(f.index))).clip(0.0, max_weight)
    else:
        raise DataValidationError(f"Regla de posición desconocida: '{rule}'.")
    out: pd.Series = w.where(f.notna())
    return out


@dataclass(frozen=True, slots=True, eq=False)
class EconometricBacktest(ResultMixin):
    """Resultado completo de la validación doble de una señal econométrica."""

    forecast: WalkForwardForecast
    validation: ModelValidation
    forecast_evaluation: ForecastEvaluation
    backtest: BacktestResult
    benchmark_backtest: BacktestResult
    economic_test: SharpeDifference
    verdict: Verdict
    position_rule: str
    point_in_time: bool
    notes: tuple[str, ...] = field(default=())

    def summary(self) -> str:
        """Reporte completo para comité."""
        sep = "-" * 88
        return "\n".join(
            [
                sep,
                self.verdict.summary(),
                sep,
                "(a) VALIDACIÓN ESTADÍSTICA",
                self.forecast.summary(),
                self.forecast_evaluation.summary(),
                self.validation.summary(),
                sep,
                f"(b) BACKTEST ECONÓMICO (regla '{self.position_rule}')",
                self.backtest.summary(),
                "Benchmark de la regla (media histórica): "
                + self.benchmark_backtest.metrics.summary(),
                self.economic_test.summary(),
                *[f"Nota: {n}" for n in self.notes],
                sep,
            ]
        )


def backtest_econometric(
    prices: pd.Series,
    y: pd.Series,
    X: pd.DataFrame,
    model: PredictiveRegression,
    *,
    position: PositionRule = "long_cash",
    config: ExecutionConfig | None = None,
    risk_free: pd.Series | None = None,
    alpha: float = 0.05,
    n_specifications: int = 1,
    point_in_time: bool = True,
    reps: int = 1000,
    seed: int = 0,
) -> EconometricBacktest:
    """Validación doble de una señal econométrica sobre un activo.

    Parameters
    ----------
    prices : pandas.Series
        Precios diarios (retorno total) del activo.
    y : pandas.Series
        Retornos (en exceso) por periodo de decisión, fechados al cierre de la fecha de
        decisión (p. ej. :func:`tsinsurance.backtest.monthly_returns`).
    X : pandas.DataFrame
        Regresores punto-en-el-tiempo en las fechas de decisión.
    model : PredictiveRegression
    position : {"long_cash", "long_short", "proportional"}
    config : ExecutionConfig
        Retraso 1 por defecto: la decisión del cierre de ``t`` se ejecuta al cierre
        siguiente y se mantiene hasta la próxima decisión.
    risk_free : pandas.Series, optional
        Tasa diaria por periodo (ver :func:`tsinsurance.backtest.dtb3_to_daily`).
    alpha : float
        Uno de ``ALPHAS``.
    n_specifications : int
        Especificaciones probadas para llegar a esta (> 1 ⇒ veredicto exploratorio).
    point_in_time : bool
        ``False`` si alguna variable es revisable y se usa su versión actual.
    """
    if alpha not in ALPHAS:
        raise DataValidationError(f"alpha debe ser uno de {ALPHAS}.")
    cfg = config or ExecutionConfig()
    wf = model.walk_forward(y, X)
    validation = model.validate(y, X, alpha=alpha)
    mask = wf.forecasts.notna() & wf.realized.notna()
    evaluation = evaluate_forecasts(
        wf.realized[mask], wf.benchmark_forecasts[mask], wf.forecasts[mask]
    )
    w_model = forecast_to_weights(wf.forecasts, y, position, max_weight=cfg.max_gross)
    w_bench = forecast_to_weights(wf.benchmark_forecasts, y, position, max_weight=cfg.max_gross)
    first = wf.forecasts.first_valid_index()
    if first is None:
        raise InsufficientDataError("backtest_econometric", model.min_train + 1, len(y))
    name = str(prices.name or "activo")
    bt_model = run_backtest(
        prices, w_model.rename(name).dropna(), cfg, risk_free=risk_free, name="modelo"
    )
    bt_bench = run_backtest(
        prices, w_bench.rename(name).dropna(), cfg, risk_free=risk_free, name="media_historica"
    )
    start = max(t for t in (bt_model.warmup_end, bt_bench.warmup_end) if t is not None)
    a = bt_model.excess_returns.loc[start:]
    b = bt_bench.excess_returns.loc[start:]
    econ = sharpe_difference(a, b, periods_per_year=bt_model.periods_per_year, reps=reps, seed=seed)
    if position == "proportional":
        stat_test = evaluation.clark_west
    else:
        stat_test = evaluation.pesaran_timmermann
        if stat_test.p_value is None:
            stat_test = evaluation.clark_west
    statistical = stat_test.p_value is not None and stat_test.rejects(alpha)
    notes = []
    if position != "proportional" and stat_test is evaluation.clark_west:
        notes.append("Pesaran-Timmermann no aplicable (un solo signo); se usa Clark-West.")
    verdict = make_verdict(
        statistical=statistical,
        economic=econ.p_value < alpha,
        diagnostics_passed=validation.diagnostics_passed,
        n_specifications=n_specifications,
        point_in_time=point_in_time,
        n_forecasts=evaluation.n_forecasts,
        alpha=alpha,
        statistical_test=stat_test.name,
    )
    notes.append(
        "La decisión de fin de mes se ejecuta al cierre siguiente (retraso 1): el periodo "
        "mantenido está desplazado un día respecto del retorno pronosticado."
    )
    return EconometricBacktest(
        forecast=wf,
        validation=validation,
        forecast_evaluation=evaluation,
        backtest=bt_model,
        benchmark_backtest=bt_bench,
        economic_test=econ,
        verdict=verdict,
        position_rule=position,
        point_in_time=point_in_time,
        notes=tuple(notes),
    )
