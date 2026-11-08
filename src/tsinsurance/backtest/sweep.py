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
    sharpe_difference,
    sharpe_inference,
    spa_test,
)
from tsinsurance.backtest.metrics import performance_metrics, sharpe_per_period
from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin

__all__ = [
    "CalibrationResult",
    "SweepResult",
    "Trial",
    "TrialRegistry",
    "calibrate_validate",
    "sweep",
]

SignalFn = Callable[..., pd.DataFrame]


@dataclass(frozen=True, slots=True, eq=False)
class Trial:
    """Una configuración probada sobre un activo."""

    asset: str
    params: Mapping[str, Any]
    excess_returns: pd.Series
    benchmark_excess: pd.Series

    @property
    def label(self) -> str:
        """Etiqueta legible de los parámetros."""
        return ", ".join(f"{k}={v}" for k, v in self.params.items())


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


@dataclass(frozen=True, slots=True, eq=False)
class SweepResult(ResultMixin):
    """Tabla de resultados y selección ajustada por pruebas múltiples."""

    table: pd.DataFrame
    selection: pd.DataFrame
    registry: TrialRegistry
    config: ExecutionConfig

    def summary(self) -> str:
        """Resumen legible."""
        cols = ["best", "sharpe", "n_trials", "n_effective", "dsr", "spa_p", "significant"]
        return "\n".join(
            [
                f"Barrido: {self.registry.n_trials} pruebas ({self.config.describe()})",
                "Mejor configuración por activo, ajustada por pruebas múltiples "
                "(DSR = P[SR verdadero > máximo esperado por azar]; SPA vs comprar y mantener):",
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
) -> SweepResult:
    """Evalúa ``signal_fn`` con cada combinación de ``grid`` sobre cada activo.

    Todas las configuraciones de un activo se comparan en la misma ventana (desde el
    calentamiento más largo). ``signal_fn(prices_frame, **params)`` debe devolver pesos
    objetivo causales.
    """
    cfg = config or ExecutionConfig()
    combos = _grid(grid)
    registry = TrialRegistry()
    rows: list[dict[str, Any]] = []
    selection: list[dict[str, Any]] = []
    for asset in prices.columns:
        px = prices[asset].dropna()
        runs, start = _run_asset(px, signal_fn, combos, cfg, risk_free)
        sharpes = []
        for params, res in runs:
            ex = res.excess_returns.loc[start:]
            bex = res.benchmark_excess_returns
            assert bex is not None
            trial = Trial(str(asset), params, ex, bex.loc[start:])
            registry.add(trial)
            m = performance_metrics(ex, res.periods_per_year, turnover=res.turnover.loc[start:])
            sharpes.append(sharpe_per_period(ex))
            rows.append({"asset": asset, **params, **m.to_dict()})
        trials = registry.for_asset(str(asset))
        best_i = int(np.nanargmax(sharpes))
        best = trials[best_i]
        frame = registry.returns_frame(str(asset))
        var_sr = float(np.nanvar(sharpes, ddof=1)) if len(sharpes) > 1 else 0.0
        n_eff = effective_number_of_trials(frame)
        # N bruto para decidir: el N efectivo por autovalores subestima las pruebas
        # independientes cuando comparten un factor común e infla el tamaño (SC-003).
        dsr = deflated_sharpe(best.excess_returns, len(trials), var_sr)
        spa = spa_test(best.benchmark_excess, frame, reps=reps, seed=seed)
        selection.append(
            {
                "asset": asset,
                "best": best.label,
                "sharpe": sharpes[best_i] * np.sqrt(runs[best_i][1].periods_per_year),
                "n_trials": len(trials),
                "n_effective": n_eff,
                "dsr": dsr.dsr,
                "spa_p": spa.pvalue_consistent,
                "significant": bool(dsr.dsr > 1 - alpha and spa.pvalue_consistent < alpha),
                "eval_start": start,
            }
        )
    return SweepResult(
        table=pd.DataFrame(rows),
        selection=pd.DataFrame(selection).set_index("asset"),
        registry=registry,
        config=cfg,
    )


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
