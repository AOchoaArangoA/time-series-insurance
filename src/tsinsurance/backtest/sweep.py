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

    @property
    def active_returns(self) -> pd.Series:
        """Retorno activo frente a comprar y mantener del mismo activo."""
        return (
            self.excess_returns - self.benchmark_excess.reindex(self.excess_returns.index)
        ).rename(self.label)


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
        cols = [
            "best",
            "sharpe",
            "info_ratio",
            "n_trials",
            "n_effective",
            "dsr",
            "spa_p",
            "significant",
        ]
        return "\n".join(
            [
                f"Barrido: {len(self.table)} configuraciones; registro acumulado "
                f"{self.registry.n_trials} pruebas ({self.config.describe()})",
                "Mejor configuración por activo (por ratio de información frente a comprar y "
                "mantener). Nula común: sin habilidad de timing. DSR = P[IR verdadero > máximo "
                "esperado por azar con n_trials pruebas del activo]; SPA = valor p de Hansen "
                "sobre retornos activos medios (sin ajuste por riesgo):",
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
    registry: TrialRegistry | None = None,
    name: str = "idea",
) -> SweepResult:
    """Evalúa ``signal_fn`` con cada combinación de ``grid`` sobre cada activo.

    Todas las configuraciones de un activo se comparan en la misma ventana (desde el
    calentamiento más largo). ``signal_fn(prices_frame, **params)`` debe devolver pesos
    objetivo causales.

    La significancia se mide sobre el **retorno activo** frente a comprar y mantener
    (``r_estrategia − r_benchmark``), así ambas pruebas tienen la misma nula ("no hay
    habilidad de *timing*"):

    - DSR del ratio de información del mejor, deflactado con **todas** las pruebas del
      activo registradas en ``registry`` (comparta el registro entre barridos para que
      cuenten todas las ideas probadas);
    - SPA de Hansen sobre los retornos activos de todas esas pruebas (valor p consistente;
      compara retornos medios, sin ajuste por riesgo).
    """
    cfg = config or ExecutionConfig()
    combos = _grid(grid)
    registry = registry if registry is not None else TrialRegistry()
    rows: list[dict[str, Any]] = []
    selection: list[dict[str, Any]] = []
    for asset in prices.columns:
        px = prices[asset].dropna()
        runs, start = _run_asset(px, signal_fn, combos, cfg, risk_free)
        current: list[Trial] = []
        for params, res in runs:
            ex = res.excess_returns.loc[start:]
            bex = res.benchmark_excess_returns
            assert bex is not None
            trial = Trial(str(asset), {"idea": name, **params}, ex, bex.loc[start:])
            registry.add(trial)
            current.append(trial)
            m = performance_metrics(ex, res.periods_per_year, turnover=res.turnover.loc[start:])
            rows.append({"asset": asset, "idea": name, **params, **m.to_dict()})
        ppy = runs[0][1].periods_per_year
        all_trials = registry.for_asset(str(asset))
        active_all = pd.concat({t.label: t.active_returns for t in all_trials}, axis=1)
        irs_all = [sharpe_per_period(t.active_returns) for t in all_trials]
        irs_now = [sharpe_per_period(t.active_returns) for t in current]
        # Retorno activo idéntico a 0 (estrategia = benchmark): IR indefinido ⇒ 0.
        irs_all = [0.0 if np.isnan(v) else v for v in irs_all]
        irs_now = [0.0 if np.isnan(v) else v for v in irs_now]
        best_i = int(np.argmax(irs_now))
        best = current[best_i]
        var_ir = float(np.var(irs_all, ddof=1)) if len(irs_all) > 1 else 0.0
        common = active_all.dropna()
        if float(best.active_returns.std()) > 0:
            # N bruto para decidir: el N efectivo por autovalores subestima las pruebas
            # independientes cuando comparten un factor común e infla el tamaño (SC-003).
            dsr_value = deflated_sharpe(best.active_returns, len(all_trials), var_ir).dsr
        else:
            dsr_value = float("nan")
        if float(common.std().max()) > 0:
            spa_p = spa_test(
                np.zeros(len(common)), common, reps=reps, seed=seed, relative=False
            ).pvalue_consistent
        else:
            spa_p = 1.0
        selection.append(
            {
                "asset": asset,
                "best": best.label,
                "sharpe": sharpe_per_period(best.excess_returns) * np.sqrt(ppy),
                "info_ratio": irs_now[best_i] * np.sqrt(ppy),
                "n_trials": len(all_trials),
                "n_effective": effective_number_of_trials(active_all),
                "dsr": dsr_value,
                "spa_p": spa_p,
                "significant": bool(dsr_value > 1 - alpha and spa_p < alpha),
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
