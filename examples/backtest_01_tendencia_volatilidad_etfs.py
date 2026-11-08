"""Ejercicio backtest 01 — Tendencia y volatilidad sobre ETFs (foco en TLT).

Datos reales replicables (instantáneas en ``examples/data``):
- Yahoo Finance: TLT, IEF, SHY, TIP, LQD, HYG, AGG, SPY (precio ajustado = retorno total).
- FRED: DTB3 (letra a 3 meses) como tasa libre de riesgo, rezagada un día hábil.

Supuestos explícitos: decisión al cierre, ejecución al cierre siguiente, costo 5 pb por
unidad de rotación (2 pb para SHY e IEF, 10 pb para HYG), sin cortos.

    uv run python examples/backtest_01_tendencia_volatilidad_etfs.py [--report r.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from tsinsurance.backtest import (
    ExecutionConfig,
    Trial,
    TrialRegistry,
    calibrate_validate,
    check_lookahead,
    dtb3_to_daily,
    ewma_volatility,
    run_backtest,
    sharpe_difference,
    sharpe_inference,
    sma_crossover,
    sweep,
    tsmom,
    vol_target,
)
from tsinsurance.data import Snapshot, to_wide

DATA = Path(__file__).parent / "data"
CONFIG = ExecutionConfig(cost_bps={"SHY": 2.0, "IEF": 2.0, "HYG": 10.0}, default_cost_bps=5.0)


def load() -> tuple[pd.DataFrame, pd.Series]:
    """Precios de ETFs y tasa libre de riesgo diaria (por fecha de disponibilidad)."""
    etfs = to_wide(Snapshot.load(DATA / "yahoo_etfs").data)
    fred = to_wide(Snapshot.load(DATA / "fred_daily").data)
    rf = dtb3_to_daily(fred["DTB3"])
    return etfs, rf


def trend(p: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.DataFrame:
    """Cruce de medias por activo (cada activo se evalúa por separado)."""
    return sma_crossover(p, fast, slow, normalize=False)


def momentum(p: pd.DataFrame, lookback: int = 252, skip: int = 21) -> pd.DataFrame:
    """Momentum de serie de tiempo 12-1."""
    return tsmom(p, lookback, skip, normalize=False)


def trend_vol(p: pd.DataFrame, target: float = 0.08) -> pd.DataFrame:
    """Momentum con objetivo de volatilidad EWMA (sin apalancamiento)."""
    vol = ewma_volatility(p.pct_change())
    return vol_target(momentum(p), vol, target=target, max_leverage=1.0)


def main() -> None:
    """Ejecuta el ejercicio completo."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Guarda un JSON con las métricas.")
    args = parser.parse_args()
    etfs, rf = load()
    tlt = etfs[["TLT"]].dropna()
    report: dict[str, object] = {}
    # Registro único: cada idea y configuración probada cuenta para el ajuste por pruebas
    # múltiples de los pasos siguientes.
    registry = TrialRegistry()

    print("=" * 88)
    print("1) Prueba de anticipación de las señales (sobre TLT)")
    for name, fn in {"tendencia": trend, "momentum": momentum, "momentum+vol": trend_vol}.items():
        rep = check_lookahead(fn, tlt, n_cuts=10)
        rep.raise_if_biased()
        print(f"   {name:<14} {rep.summary()}")

    print("=" * 88)
    print("2) TLT: tres ideas frente a comprar y mantener (retornos en exceso de rf)")
    print("   EXPLORATORIO: valores p sin ajuste; las 3 ideas quedan en el registro y se")
    print("   descuentan en el Sharpe deflactado del barrido (paso 3).")
    for name, fn in {"tendencia": trend, "momentum": momentum, "momentum+vol": trend_vol}.items():
        res = run_backtest(tlt, fn(tlt), CONFIG, risk_free=rf, name=f"TLT {name}")
        window = res.evaluation_window()
        assert res.benchmark_excess_returns is not None
        bench = res.benchmark_excess_returns.loc[window.index]
        inf = sharpe_inference(window, res.periods_per_year, reps=500, seed=0)
        diff = sharpe_difference(window, bench, reps=500, seed=0)
        registry.add(Trial("TLT", {"idea": name}, window, bench))
        print(res.summary())
        print(f"   Inferencia: {inf.summary()}")
        print(f"   vs comprar y mantener: {diff.summary()}\n")
        report[f"TLT_{name}"] = {
            "sharpe": round(inf.sharpe, 10),
            "ci": [round(inf.ci_low, 10), round(inf.ci_high, 10)],
            "diff_p": round(diff.p_value, 10),
            "max_drawdown": round(res.metrics.max_drawdown, 10),
        }

    print("=" * 88)
    print("3) Barrido sobre 8 ETFs con ajuste por pruebas múltiples")
    grid_trend = {"fast": [20, 50, 100], "slow": [150, 200, 250]}
    sw = sweep(
        etfs,
        trend,
        grid_trend,
        CONFIG,
        risk_free=rf,
        reps=500,
        seed=0,
        registry=registry,
        name="tendencia",
    )
    print(sw.summary())
    grid_mom = {"lookback": [63, 126, 252], "skip": [0, 21]}
    sw2 = sweep(
        etfs,
        momentum,
        grid_mom,
        CONFIG,
        risk_free=rf,
        reps=500,
        seed=0,
        registry=registry,
        name="momentum",
    )
    print(sw2.summary())
    cols = ["best", "sharpe", "info_ratio", "n_trials", "dsr", "spa_p"]
    report["sweep_trend"] = sw.selection[cols].round(10).to_dict()
    report["sweep_momentum"] = sw2.selection[cols].round(10).to_dict()

    print("=" * 88)
    print("4) Calibración 2003-2016 y validación única 2017-2025 (tendencia)")
    cal = calibrate_validate(
        etfs[["TLT", "IEF", "LQD", "SPY"]],
        trend,
        grid_trend,
        "2016-12-30",
        CONFIG,
        risk_free=rf,
        reps=500,
        registry=registry,
    )
    print(f"Registro total de pruebas: {registry.n_trials}")
    print(cal.summary())
    report["calibration"] = cal.table.round(10).to_dict()

    if args.report:
        text = json.dumps(report, sort_keys=True, default=str, indent=2)
        args.report.write_text(text, encoding="utf-8")
        print(f"\nReporte: {args.report} sha256={hashlib.sha256(text.encode()).hexdigest()[:16]}")


if __name__ == "__main__":
    main()
