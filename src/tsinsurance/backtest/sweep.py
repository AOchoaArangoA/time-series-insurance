"""Barridos de parámetros con registro de pruebas y ajuste por pruebas múltiples.

Cada configuración probada queda registrada (:class:`TrialRegistry`); el mejor
resultado por activo se reporta con su Sharpe deflactado (número bruto y efectivo de
pruebas) y la prueba SPA de Hansen frente a comprar y mantener (Principio VIII).
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from tsinsurance.backtest.config import ExecutionConfig
from tsinsurance.backtest.engine import run_backtest
from tsinsurance.backtest.inference import (
    SharpeDifference,
    SharpeInference,
    deflated_sharpe,
    effective_number_of_trials,
    probabilistic_sharpe,
    sharpe_difference,
    sharpe_inference,
    spa_test,
)
from tsinsurance.backtest.metrics import performance_metrics, sharpe_per_period
from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin

__all__ = [
    "CalibrationResult",
    "evaluate_grid",
    "holm",
    "select",
    "SweepResult",
    "Trial",
    "TrialRegistry",
    "calibrate_validate",
    "sweep",
]

SignalFn = Callable[..., pd.DataFrame]


@dataclass(frozen=True, slots=True, eq=False)
class Trial:
    """Una configuración probada sobre un activo.

    ``exposure`` es la exposición bruta media de la estrategia en la ventana evaluada.
    El benchmark de *timing* es mantener esa exposición constante en el activo
    (comprar y mantener escalado): así un activo con deriva negativa no hace parecer
    hábil a una regla que sólo está menos invertida.
    """

    asset: str
    params: Mapping[str, Any]
    excess_returns: pd.Series
    benchmark_excess: pd.Series
    exposure: float = 1.0
    periods_per_year: int = 252

    @property
    def label(self) -> str:
        """Etiqueta legible de los parámetros."""
        return ", ".join(f"{k}={v}" for k, v in self.params.items())

    @property
    def active_returns(self) -> pd.Series:
        """Retorno de *timing*: estrategia − exposición media × comprar y mantener."""
        bench = self.benchmark_excess.reindex(self.excess_returns.index)
        return (self.excess_returns - self.exposure * bench).rename(self.label)

    @property
    def active_vs_buy_hold(self) -> pd.Series:
        """Retorno activo frente a comprar y mantener sin escalar (descriptivo)."""
        bench = self.benchmark_excess.reindex(self.excess_returns.index)
        return (self.excess_returns - bench).rename(self.label)


@dataclass(eq=False)
class TrialRegistry:
    """Registro de todas las configuraciones probadas."""

    trials: list[Trial] = field(default_factory=list)

    def add(self, trial: Trial) -> None:
        """Registra una prueba."""
        self.trials.append(trial)

    @property
    def n_trials(self) -> int:
        """Número total de pruebas registradas."""
        return len(self.trials)

    def for_asset(self, asset: str) -> list[Trial]:
        """Pruebas de un activo."""
        return [t for t in self.trials if t.asset == asset]

    def returns_frame(self, asset: str) -> pd.DataFrame:
        """Retornos en exceso de las pruebas de un activo (columnas = configuraciones)."""
        trials = self.for_asset(asset)
        return pd.concat({t.label: t.excess_returns for t in trials}, axis=1)


SELECTION_NOTE = (
    "Nula común: sin habilidad de timing. Retorno de timing = estrategia − (exposición media "
    "× comprar y mantener). DSR = P[ratio de timing verdadero > máximo esperado por azar con "
    "n_trials pruebas del activo, incluida la bitácora]; SPA = valor p de Hansen sobre los "
    "retornos de timing medios; spa_p_holm ajusta además por el número de activos (Holm). "
    "sharpe = Sharpe propio en exceso de rf (vs efectivo); ir_vs_bh es descriptivo."
)


@dataclass(frozen=True, slots=True, eq=False)
class SweepResult(ResultMixin):
    """Tabla de resultados y selección ajustada por pruebas múltiples."""

    table: pd.DataFrame
    selection: pd.DataFrame
    registry: TrialRegistry
    config: ExecutionConfig

    def summary(self) -> str:
        """Resumen legible."""
        cols = [
            "best",
            "sharpe",
            "psr",
            "ir_vs_bh",
            "exposure",
            "timing_ir",
            "n_trials",
            "dsr",
            "spa_p",
            "spa_p_holm",
            "significant",
        ]
        return "\n".join(
            [
                f"Barrido: {len(self.table)} configuraciones; registro acumulado "
                f"{self.registry.n_trials} pruebas ({self.config.describe()})",
                SELECTION_NOTE,
                self.selection[cols].to_string(float_format=lambda v: f"{v:.3f}"),
            ]
        )


def _grid(grid: Mapping[str, Sequence[Any]]) -> list[dict[str, Any]]:
    keys = list(grid)
    return [dict(zip(keys, combo, strict=True)) for combo in itertools.product(*grid.values())]


def _run_asset(
    prices: pd.Series,
    signal_fn: SignalFn,
    combos: list[dict[str, Any]],
    cfg: ExecutionConfig,
    risk_free: pd.Series | None,
) -> tuple[list[tuple[dict[str, Any], Any]], pd.Timestamp]:
    runs = []
    starts = []
    for params in combos:
        weights = signal_fn(prices.to_frame(), **params)
        res = run_backtest(prices, weights, cfg, risk_free=risk_free, name=str(prices.name))
        runs.append((params, res))
        if res.warmup_end is not None:
            starts.append(res.warmup_end)
    if not starts:
        raise DataValidationError(f"Ninguna configuración genera posiciones para {prices.name}.")
    return runs, max(starts)


def _ir(x: pd.Series) -> float:
    v = sharpe_per_period(x)
    return 0.0 if np.isnan(v) else v


def holm(pvalues: Sequence[float]) -> list[float]:
    """Valores p ajustados de Holm-Bonferroni (en el orden original)."""
    p = np.asarray(pvalues, dtype=float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return adj.tolist()


def select(
    registry: TrialRegistry,
    current: Mapping[str, Sequence[Trial]],
    *,
    alpha: float = 0.05,
    reps: int = 500,
    seed: int = 0,
    prior_information_ratios: Mapping[str, Sequence[float]] | None = None,
) -> pd.DataFrame:
    """Mejor configuración de ``current`` por activo, deflactada con TODO el registro.

    Llamar después de evaluar todas las ideas: el número de pruebas no depende del
    orden en que se evaluaron.
    """
    rows = []
    for asset, trials in current.items():
        all_trials = registry.for_asset(asset)
        active_all = pd.concat({t.label: t.active_returns for t in all_trials}, axis=1)
        irs_all = [_ir(t.active_returns) for t in all_trials]
        irs_all += [float(v) for v in (prior_information_ratios or {}).get(asset, [])]
        irs_now = [_ir(t.active_returns) for t in trials]
        best_i = int(np.argmax(irs_now))
        best = trials[best_i]
        ppy = best.periods_per_year
        var_ir = float(np.var(irs_all, ddof=1)) if len(irs_all) > 1 else 0.0
        if float(best.active_returns.std()) > 0:
            # N bruto: el N efectivo por autovalores sub-deflacta con un factor común (SC-003).
            dsr_value = deflated_sharpe(best.active_returns, len(irs_all), var_ir).dsr
        else:
            dsr_value = float("nan")
        common = active_all.dropna()
        if float(common.std().max()) > 0:
            spa_p = spa_test(
                np.zeros(len(common)), common, reps=reps, seed=seed, relative=False
            ).pvalue_consistent
        else:
            spa_p = 1.0
        rows.append(
            {
                "asset": asset,
                "best": best.label,
                "sharpe": sharpe_per_period(best.excess_returns) * np.sqrt(ppy),
                "psr": probabilistic_sharpe(best.excess_returns)
                if float(best.excess_returns.std()) > 0
                else float("nan"),
                "ir_vs_bh": _ir(best.active_vs_buy_hold) * np.sqrt(ppy),
                "exposure": best.exposure,
                "timing_ir": irs_now[best_i] * np.sqrt(ppy),
                "n_trials": len(irs_all),
                "n_effective": effective_number_of_trials(active_all),
                "dsr": dsr_value,
                "spa_p": spa_p,
                "eval_start": best.excess_returns.index[0],
                "eval_end": best.excess_returns.index[-1],
            }
        )
    out = pd.DataFrame(rows).set_index("asset")
    out["spa_p_holm"] = holm(out["spa_p"].tolist()) if len(out) else []
    out["significant"] = (out["dsr"] > 1 - alpha) & (out["spa_p_holm"] < alpha)
    return out


def evaluate_grid(
    prices: pd.DataFrame,
    signal_fn: SignalFn,
    grid: Mapping[str, Sequence[Any]],
    config: ExecutionConfig,
    *,
    risk_free: pd.Series | None,
    registry: TrialRegistry,
    name: str,
    end: str | pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict[str, list[Trial]]]:
    """Evalúa la malla sobre cada activo, registra las pruebas y devuelve la tabla.

    Con ``end`` la evaluación termina en esa fecha (p. ej. fin de la calibración).
    """
    combos = _grid(grid)
    rows: list[dict[str, Any]] = []
    current: dict[str, list[Trial]] = {}
    for asset in prices.columns:
        px = prices[asset].dropna()
        runs, start = _run_asset(px, signal_fn, combos, config, risk_free)
        for params, res in runs:
            ex = res.excess_returns.loc[start:end]
            bex = res.benchmark_excess_returns
            assert bex is not None
            exposure = float(res.weights.abs().sum(axis=1).loc[start:end].mean())
            trial = Trial(
                str(asset),
                {"idea": name, **params},
                ex,
                bex.loc[start:end],
                exposure,
                res.periods_per_year,
            )
            registry.add(trial)
            current.setdefault(str(asset), []).append(trial)
            turn = res.turnover.loc[start:end]
            m = performance_metrics(ex, res.periods_per_year, turnover=turn)
            rows.append(
                {"asset": asset, "idea": name, **params, "exposure": exposure, **m.to_dict()}
            )
    return pd.DataFrame(rows), current


def sweep(
    prices: pd.DataFrame,
    signal_fn: SignalFn,
    grid: Mapping[str, Sequence[Any]],
    config: ExecutionConfig | None = None,
    *,
    risk_free: pd.Series | None = None,
    alpha: float = 0.05,
    reps: int = 500,
    seed: int = 0,
    registry: TrialRegistry | None = None,
    name: str = "idea",
    prior_information_ratios: Mapping[str, Sequence[float]] | None = None,
    end: str | pd.Timestamp | None = None,
) -> SweepResult:
    """Evalúa ``signal_fn`` con cada combinación de ``grid`` sobre cada activo.

    Todas las configuraciones de un activo se comparan en la misma ventana. La
    significancia se mide sobre el retorno de **timing** (ver :class:`Trial`) con el DSR
    deflactado por todas las pruebas del activo en ``registry`` y en
    ``prior_information_ratios`` (bitácora, por periodo y de la misma frecuencia), la SPA
    de Hansen sobre esas pruebas y el ajuste de Holm entre activos. Para varios barridos,
    use :func:`evaluate_grid` + :func:`select` al final (independiente del orden).
    """
    cfg = config or ExecutionConfig()
    registry = registry if registry is not None else TrialRegistry()
    table, current = evaluate_grid(
        prices, signal_fn, grid, cfg, risk_free=risk_free, registry=registry, name=name, end=end
    )
    selection = select(
        registry,
        current,
        alpha=alpha,
        reps=reps,
        seed=seed,
        prior_information_ratios=prior_information_ratios,
    )
    return SweepResult(table=table, selection=selection, registry=registry, config=cfg)


@dataclass(frozen=True, slots=True, eq=False)
class CalibrationResult(ResultMixin):
    """Selección en calibración y evaluación única fuera de muestra."""

    train_end: pd.Timestamp
    table: pd.DataFrame
    out_of_sample: dict[str, SharpeInference]
    vs_benchmark: dict[str, SharpeDifference]
    n_trials: int

    def summary(self) -> str:
        """Resumen legible."""
        lines = [
            f"Calibración hasta {self.train_end.date()} ({self.n_trials} configuraciones por "
            "activo); validación evaluada una sola vez, sin re-optimizar:",
            self.table.to_string(float_format=lambda v: f"{v:.3f}"),
        ]
        for asset, inf in self.out_of_sample.items():
            lines.append(f"  {asset} fuera de muestra: {inf.summary()}")
            lines.append(f"  {asset} vs comprar y mantener: {self.vs_benchmark[asset].summary()}")
        return "\n".join(lines)


def calibrate_validate(
    prices: pd.DataFrame,
    signal_fn: SignalFn,
    grid: Mapping[str, Sequence[Any]],
    train_end: str | pd.Timestamp,
    config: ExecutionConfig | None = None,
    *,
    risk_free: pd.Series | None = None,
    reps: int = 500,
    seed: int = 0,
    registry: TrialRegistry | None = None,
) -> CalibrationResult:
    """Elige parámetros con datos hasta ``train_end`` y evalúa una vez después.

    Las señales se calculan con toda la historia (son causales); la selección sólo
    mira el periodo de calibración.
    """
    cfg = config or ExecutionConfig()
    cut = pd.Timestamp(train_end)
    combos = _grid(grid)
    rows = []
    oos: dict[str, SharpeInference] = {}
    vs: dict[str, SharpeDifference] = {}
    for asset in prices.columns:
        px = prices[asset].dropna()
        runs, start = _run_asset(px, signal_fn, combos, cfg, risk_free)
        in_sample = [sharpe_per_period(r.excess_returns.loc[start:cut]) for _, r in runs]
        best_i = int(np.nanargmax(in_sample))
        params, res = runs[best_i]
        if registry is not None:
            for p_, r_ in runs:
                bex_ = r_.benchmark_excess_returns
                assert bex_ is not None
                registry.add(
                    Trial(
                        str(asset),
                        {"idea": "calibracion", **p_},
                        r_.excess_returns.loc[start:cut],
                        bex_.loc[start:cut],
                    )
                )
        after = res.excess_returns.loc[cut:].iloc[1:]
        bench = res.benchmark_excess_returns
        assert bench is not None
        ppy = res.periods_per_year
        oos[str(asset)] = sharpe_inference(after, ppy, reps=reps, seed=seed)
        vs[str(asset)] = sharpe_difference(
            after, bench.loc[after.index], periods_per_year=ppy, reps=reps, seed=seed
        )
        rows.append(
            {
                "asset": asset,
                "best": ", ".join(f"{k}={v}" for k, v in params.items()),
                "sharpe_in_sample": in_sample[best_i] * np.sqrt(ppy),
                "sharpe_out_of_sample": oos[str(asset)].sharpe,
                "benchmark_out_of_sample": sharpe_per_period(bench.loc[after.index]) * np.sqrt(ppy),
            }
        )
    return CalibrationResult(
        train_end=cut,
        table=pd.DataFrame(rows).set_index("asset"),
        out_of_sample=oos,
        vs_benchmark=vs,
        n_trials=len(combos),
    )
