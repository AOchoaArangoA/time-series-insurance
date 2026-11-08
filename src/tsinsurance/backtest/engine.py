"""Motor de backtesting vectorizado con supuestos de ejecución explícitos.

Convención: ``target_weights`` en la fecha ``t`` es una decisión tomada con información
hasta el cierre de ``t``. Se ejecuta al cierre de ``t + lag``. Entre ejecuciones los
pesos derivan con los precios. La porción no invertida rinde la tasa libre de riesgo
(si se entrega); el efectivo negativo y los cortos pagan ``rf + financing_spread``.
El motor se valida contra la librería ``bt`` (``reference.run_with_bt``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tsinsurance.backtest.config import ExecutionConfig, infer_periods_per_year
from tsinsurance.backtest.metrics import PerformanceMetrics, performance_metrics
from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin

__all__ = ["BacktestResult", "equal_weight_benchmark", "run_backtest"]

SURVIVORSHIP_NOTE = (
    "Universo elegido ex post (activos vigentes hoy): posible sesgo de supervivencia y de "
    "selección."
)


@dataclass(frozen=True, slots=True, eq=False)
class BacktestResult(ResultMixin):
    """Resultado de un backtest.

    Attributes
    ----------
    returns : pandas.Series
        Retornos netos de costos por periodo.
    gross_returns : pandas.Series
        Retornos antes de costos de transacción.
    excess_returns : pandas.Series
        ``returns`` menos la tasa libre de riesgo del periodo (igual a ``returns`` si no
        se entrega ``risk_free``).
    weights : pandas.DataFrame
        Pesos mantenidos durante cada periodo (después de ejecutar al cierre anterior).
    turnover, costs : pandas.Series
        Rotación Σ|Δw| y costo cobrado en cada periodo.
    benchmark_returns, benchmark_excess_returns : pandas.Series or None
    metrics, benchmark_metrics : PerformanceMetrics
        Calculadas sobre retornos en exceso desde ``warmup_end``.
    warmup_end : pandas.Timestamp or None
        Primera fecha con posición (antes: efectivo por calentamiento de la señal).
    """

    name: str
    returns: pd.Series
    gross_returns: pd.Series
    excess_returns: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    costs: pd.Series
    benchmark_returns: pd.Series | None
    benchmark_excess_returns: pd.Series | None
    config: ExecutionConfig
    metrics: PerformanceMetrics
    benchmark_metrics: PerformanceMetrics | None
    periods_per_year: int
    warmup_end: pd.Timestamp | None
    notes: tuple[str, ...] = ()

    @property
    def equity(self) -> pd.Series:
        """Curva de capital (base 1)."""
        return (1.0 + self.returns).cumprod()

    def evaluation_window(self) -> pd.Series:
        """Retornos en exceso desde el fin del calentamiento."""
        if self.warmup_end is None:
            return self.excess_returns.iloc[0:0]
        return self.excess_returns.loc[self.warmup_end :]

    def summary(self) -> str:
        """Resumen legible para comité."""
        lines = [
            f"Backtest '{self.name}' — {len(self.returns)} periodos "
            f"({self.returns.index[0].date()} a {self.returns.index[-1].date()})",
            f"Supuestos: {self.config.describe()}",
            f"Fin del calentamiento: {self.warmup_end.date() if self.warmup_end else 'n/d'}",
            f"Estrategia : {self.metrics.summary()}",
        ]
        if self.benchmark_metrics is not None:
            lines.append(f"Benchmark  : {self.benchmark_metrics.summary()}")
        lines.extend(f"Nota: {n}" for n in self.notes)
        return "\n".join(lines)


def _as_frame(x: pd.Series | pd.DataFrame, name: str) -> pd.DataFrame:
    frame = x.to_frame() if isinstance(x, pd.Series) else x
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise DataValidationError(f"{name}: el índice debe ser DatetimeIndex.")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise DataValidationError(f"{name}: el índice debe ser creciente y sin duplicados.")
    return frame.astype(float)


def _rebalance_mask(index: pd.DatetimeIndex, rule: str) -> np.ndarray:
    if rule == "every_bar":
        return np.ones(len(index), dtype=bool)
    period = index.to_period("W" if rule == "W" else "M")
    last = pd.Series(np.arange(len(index))).groupby(np.asarray(period)).transform("max")
    return np.asarray(last.to_numpy() == np.arange(len(index)))


def equal_weight_benchmark(prices: pd.DataFrame) -> pd.Series:
    """Benchmark igual ponderado rebalanceado cada barra entre los activos con precio.

    Con un solo activo equivale a comprar y mantener. Sin costos.
    """
    rets = prices.pct_change()
    out = rets.mean(axis=1, skipna=True).fillna(0.0)
    out.name = "benchmark"
    return out


def run_backtest(
    prices: pd.Series | pd.DataFrame,
    target_weights: pd.Series | pd.DataFrame,
    config: ExecutionConfig | None = None,
    *,
    risk_free: pd.Series | None = None,
    benchmark: pd.Series | str | None = "buy_and_hold",
    name: str = "strategy",
    universe_note: bool = True,
) -> BacktestResult:
    """Ejecuta un backtest de pesos objetivo.

    Parameters
    ----------
    prices : pandas.Series or DataFrame
        Precios (retorno total) por activo con ``DatetimeIndex``; ``NaN`` antes del
        inicio de cada activo.
    target_weights : pandas.Series or DataFrame
        Pesos decididos en cada fecha con información hasta su cierre. Se alinean al
        índice de precios y se propagan hacia adelante; ``NaN`` inicial = efectivo.
    config : ExecutionConfig
        Supuestos de ejecución.
    risk_free : pandas.Series, optional
        Tasa libre de riesgo **por periodo** (decimal) indexada por la fecha en que se
        conoce. El retorno del periodo ``t`` usa la tasa conocida en ``t - 1``.
    benchmark : {"buy_and_hold"}, pandas.Series or None
        ``"buy_and_hold"`` = igual ponderado entre los activos (comprar y mantener si es
        uno solo); o una serie de retornos por periodo.
    name : str
        Nombre de la estrategia.
    universe_note : bool
        Agrega la nota de sesgo de supervivencia del universo.

    Returns
    -------
    BacktestResult
    """
    cfg = config or ExecutionConfig()
    px = _as_frame(prices, "prices")
    tw = _as_frame(target_weights, "target_weights")
    if px.shape[1] == 1 and tw.shape[1] == 1:
        tw.columns = px.columns  # un solo activo: se alinea por posición
    unknown = set(tw.columns) - set(px.columns)
    if unknown:
        raise DataValidationError(f"target_weights tiene activos sin precio: {sorted(unknown)}")
    assets = [str(c) for c in px.columns]
    tw = tw.reindex(columns=px.columns)
    notes: list[str] = list(cfg.notes)

    # Proyección de decisiones al índice de precios (asof hacia atrás: nunca adelanta).
    decided = tw.reindex(px.index.union(tw.index)).ffill().reindex(px.index)
    first_decision = decided.dropna(how="all").index.min()
    decided = decided.fillna(0.0)
    if not cfg.allow_short and (decided < -1e-12).to_numpy().any():
        raise DataValidationError("Hay pesos negativos y allow_short=False.")
    gross = decided.abs().sum(axis=1)
    over = gross > cfg.max_gross + 1e-12
    if over.any():
        decided.loc[over] = decided.loc[over].mul(cfg.max_gross / gross[over], axis=0)
        notes.append(
            f"{int(over.sum())} decisión(es) recortada(s) a exposición bruta {cfg.max_gross}."
        )

    rets = px.pct_change()
    no_price = px.isna().to_numpy()
    if (decided.to_numpy()[no_price] != 0).any():
        decided = decided.mask(px.isna(), 0.0)
        notes.append("Pesos en activos aún sin precio fijados en 0 (inicio por activo).")
    r = rets.fillna(0.0).to_numpy()

    rebal = _rebalance_mask(pd.DatetimeIndex(px.index), cfg.rebalance)
    targets = decided.to_numpy()
    n, k = targets.shape
    trade = np.zeros(n, dtype=bool)
    exec_target = np.zeros_like(targets)
    for t in range(n):
        src = t - cfg.lag
        if src >= 0 and rebal[src]:
            trade[t] = True
            exec_target[t] = targets[src]
    # Entre rebalanceos se mantiene el último objetivo ejecutado (con deriva).

    ppy = cfg.periods_per_year or infer_periods_per_year(pd.DatetimeIndex(px.index))
    if risk_free is not None:
        rf_known = risk_free.astype(float).reindex(px.index.union(risk_free.index)).ffill()
        rf = rf_known.reindex(px.index).shift(1).fillna(0.0).to_numpy()
    else:
        rf = np.zeros(n)
    spread = cfg.financing_spread_bps / 1e4 / ppy
    cost_rate = np.asarray(cfg.cost_rate(assets))

    w = np.zeros(k)
    held = np.zeros((n, k))
    out_net = np.zeros(n)
    out_gross = np.zeros(n)
    out_turn = np.zeros(n)
    out_cost = np.zeros(n)
    for t in range(n):
        held[t] = w
        cash = 1.0 - w.sum()
        short = -w[w < 0].sum()
        rp = float(w @ r[t]) + cash * rf[t]
        if cash < 0:
            rp += cash * spread
        rp -= short * spread
        if w.any():
            denom = 1.0 + rp
            w = w * (1.0 + r[t]) / denom if denom > 0 else np.zeros(k)
        cost = 0.0
        if trade[t]:
            delta = np.abs(exec_target[t] - w)
            out_turn[t] = float(delta.sum())
            cost = float(delta @ cost_rate)
            w = exec_target[t].copy()
        out_gross[t] = rp
        out_cost[t] = cost
        out_net[t] = (1.0 + rp) * (1.0 - cost) - 1.0

    idx = px.index
    net = pd.Series(out_net, index=idx, name=name)
    rf_series = pd.Series(rf, index=idx)
    excess = net - rf_series
    weights = pd.DataFrame(held, index=idx, columns=px.columns)
    turnover = pd.Series(out_turn, index=idx, name="turnover")
    # Primer periodo cuyo retorno refleja una decisión (aunque sea estar en efectivo):
    # decisión en t0, ejecución al cierre de t0 + lag, efecto desde t0 + lag + 1.
    warmup_end: pd.Timestamp | None = None
    if not pd.isna(first_decision):
        pos = int(idx.searchsorted(pd.Timestamp(first_decision))) + cfg.lag + 1
        if pos < n:
            warmup_end = pd.Timestamp(idx[pos])

    bench_ret: pd.Series | None
    if isinstance(benchmark, str):
        if benchmark != "buy_and_hold":
            raise DataValidationError("benchmark debe ser 'buy_and_hold', una serie o None.")
        bench_ret = equal_weight_benchmark(px)
    elif benchmark is None:
        bench_ret = None
    else:
        bench_ret = benchmark.astype(float).reindex(idx).fillna(0.0)
    bench_excess = None if bench_ret is None else bench_ret - rf_series

    in_window = np.asarray(idx >= warmup_end) if warmup_end is not None else np.zeros(n, dtype=bool)
    metrics = performance_metrics(excess[in_window], ppy, turnover=turnover[in_window])
    bmetrics = None if bench_excess is None else performance_metrics(bench_excess[in_window], ppy)
    if universe_note:
        notes.append(SURVIVORSHIP_NOTE)
    if risk_free is None:
        notes.append("Sin tasa libre de riesgo: métricas sobre retornos totales.")
    return BacktestResult(
        name=name,
        returns=net,
        gross_returns=pd.Series(out_gross, index=idx, name=name),
        excess_returns=excess.rename(name),
        weights=weights,
        turnover=turnover,
        costs=pd.Series(out_cost, index=idx, name="costs"),
        benchmark_returns=bench_ret,
        benchmark_excess_returns=bench_excess,
        config=cfg,
        metrics=metrics,
        benchmark_metrics=bmetrics,
        periods_per_year=ppy,
        warmup_end=warmup_end,
        notes=tuple(notes),
    )
