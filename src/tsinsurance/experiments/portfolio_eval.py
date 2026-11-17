"""Evaluación de ideas de cartera (spec 005, US1).

Reglas de la revisión econométrica (research R6):

- **Rebalanceo mensual siempre** (B4): la ejecución se fuerza a ``rebalance = "M"``.
- **Benchmark** (B4): cartera igual ponderada de los activos **elegibles del bloque**
  (≥ ``min_history_m`` cierres de mes de historia), ejecutada con el mismo motor y costos.
  La estrategia usa la misma elegibilidad. La ventana común empieza en el fin de
  calentamiento más tardío de la malla y del benchmark.
- **Medida de habilidad**: retorno activo = estrategia − exposición × igual ponderado
  (``Trial`` con ``asset`` = identidad del universo).
"""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Callable, Mapping
from typing import Any

import numpy as np
import pandas as pd

from tsinsurance.backtest import ExecutionConfig, check_lookahead, run_backtest
from tsinsurance.backtest.engine import BacktestResult
from tsinsurance.backtest.sweep import Trial
from tsinsurance.experiments.portfolio_signals import get_portfolio_signal, month_end_mask
from tsinsurance.experiments.spec import PortfolioSpec

__all__ = ["PortfolioRun", "combos", "evaluate_portfolio", "portfolio_backtests"]


def combos(grid: Mapping[str, list[Any]]) -> list[dict[str, Any]]:
    """Todas las combinaciones de la malla (orden estable)."""
    keys = list(grid)
    return [dict(zip(keys, v, strict=True)) for v in itertools.product(*(grid[k] for k in keys))]


def _eligible(prices: pd.DataFrame, min_history_m: int) -> pd.DataFrame:
    """Activo elegible en t si tiene ≥ ``min_history_m`` cierres de mes con precio hasta t."""
    ends = pd.Series(month_end_mask(pd.DatetimeIndex(prices.index)), index=prices.index)
    counts = (prices.notna() & ends.to_numpy()[:, None]).cumsum()
    return (counts >= min_history_m) & prices.notna()


def _weights_fn(
    pspec: PortfolioSpec, params: Mapping[str, Any]
) -> Callable[[pd.DataFrame], pd.DataFrame]:
    fn = get_portfolio_signal(pspec.signal)

    def weights(p: pd.DataFrame) -> pd.DataFrame:
        w = fn(p, **params)
        elig = _eligible(p, pspec.min_history_m)
        decided = w.notna().any(axis=1)
        masked = w.where(elig, 0.0)
        return masked.where(decided, np.nan)

    return weights


def _equal_weight_fn(pspec: PortfolioSpec) -> Callable[[pd.DataFrame], pd.DataFrame]:
    def weights(p: pd.DataFrame) -> pd.DataFrame:
        elig = _eligible(p, pspec.min_history_m).astype(float)
        n = elig.sum(axis=1).replace(0.0, np.nan)
        w = elig.div(n, axis=0).fillna(0.0)
        ends = pd.Series(month_end_mask(pd.DatetimeIndex(p.index)), index=p.index)
        return w.where(ends, np.nan)

    return weights


def portfolio_backtests(
    prices: pd.DataFrame,
    pspec: PortfolioSpec,
    params: Mapping[str, Any],
    execution: ExecutionConfig,
    risk_free: pd.Series | None,
) -> tuple[BacktestResult, BacktestResult]:
    """Backtests de la estrategia y del benchmark igual ponderado (rebalanceo mensual)."""
    cfg = dataclasses.replace(execution, rebalance="M")
    strat = run_backtest(prices, _weights_fn(pspec, params)(prices), cfg, risk_free=risk_free)
    bench = run_backtest(prices, _equal_weight_fn(pspec)(prices), cfg, risk_free=risk_free)
    return strat, bench


@dataclasses.dataclass(frozen=True, slots=True)
class PortfolioRun:
    """Resultado de la calibración de un bloque de cartera."""

    universe_id: str
    trials: list[Trial]
    rejected: list[dict[str, Any]]
    window_start: pd.Timestamp | None
    configurations: list[dict[str, Any]]


def evaluate_portfolio(
    prices: pd.DataFrame,
    pspec: PortfolioSpec,
    execution: ExecutionConfig,
    risk_free: pd.Series | None,
    *,
    seed: int = 0,
) -> PortfolioRun:
    """Evalúa toda la malla con prueba de anticipación, benchmark y ventana común."""
    runs: list[tuple[dict[str, Any], BacktestResult, BacktestResult]] = []
    rejected = []
    for params in combos(pspec.grid):
        look = check_lookahead(_weights_fn(pspec, params), prices, seed=seed)
        if look.has_lookahead or not look.conclusive:
            rejected.append({"params": params, "summary": look.summary()})
            continue
        strat, bench = portfolio_backtests(prices, pspec, params, execution, risk_free)
        runs.append((params, strat, bench))
    if not runs:
        return PortfolioRun(pspec.universe_id, [], rejected, None, [])
    # Ventana común: desde la primera fecha en que TODAS las configuraciones y el benchmark
    # están invertidos (un peso cero no es una posición).
    firsts = []
    for res in [r for _, r, _ in runs] + [b for _, _, b in runs]:
        invested = res.weights.abs().sum(axis=1) > 0
        firsts.append(invested.idxmax() if bool(invested.any()) else None)
    known = [f for f in firsts if f is not None]
    start = max(known) if len(known) == len(firsts) else None
    trials, rows = [], []
    for params, strat, bench in runs:
        ex = strat.excess_returns.loc[start:] if start is not None else strat.excess_returns
        bex = bench.excess_returns.reindex(ex.index)
        exposure = float(strat.weights.abs().sum(axis=1).reindex(ex.index).mean())
        t = Trial(
            pspec.universe_id,
            {"idea": pspec.name, **params},
            ex,
            bex,
            exposure,
            strat.periods_per_year,
        )
        trials.append(t)
        rows.append(
            {
                "params": params,
                "exposure": exposure,
                "turnover_mean": float(strat.turnover.reindex(ex.index).mean()),
                "sharpe_ann": float(ex.mean() / ex.std() * np.sqrt(strat.periods_per_year))
                if float(ex.std()) > 0
                else float("nan"),
                "benchmark_sharpe_ann": float(
                    bex.mean() / bex.std() * np.sqrt(strat.periods_per_year)
                )
                if float(bex.std()) > 0
                else float("nan"),
            }
        )
    return PortfolioRun(pspec.universe_id, trials, rejected, start, rows)
