"""Análisis EXPLORATORIO complementario del experimento ``sectores-gics-ciclo``.

No escribe en la bitácora (el ejecutor de experimentos evalúa activo por activo y todavía
no admite estrategias de cartera entre sectores). Usa las piezas del paquete: paquete de
insumos, datos punto-en-el-tiempo, prueba de anticipación, motor de backtesting e
inferencia. Todo lo que reporta es exploratorio.

1. Rotación sectorial por momentum relativo (cartera de los k sectores con mayor retorno
   pasado), calibración 1999-2014 y validación única 2015-2026, contra los 9 sectores
   igual ponderados.
2. Ciclo de mercado: exceso de retorno del mes siguiente de cada sector según tres
   estados conocidos al cierre de mes (pendiente de la curva, VIX, tendencia del S&P 500),
   con errores HAC y ajuste de Holm.
3. Recesiones NBER (fechadas ex post, sólo descriptivo).

Uso (desde la raíz del repositorio):
    uv run python experiments/sectores_gics/analisis_exploratorio.py SALIDA.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from tsinsurance.backtest import (
    ExecutionConfig,
    align_point_in_time,
    check_lookahead,
    deflated_sharpe,
    monthly_decision_dates,
    monthly_returns,
    run_backtest,
    sharpe_difference,
    sharpe_inference,
)
from tsinsurance.backtest.metrics import sharpe_per_period
from tsinsurance.backtest.sweep import holm
from tsinsurance.data.bundle import Bundle

HERE = Path(__file__).parent
ORIGINAL = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
ALL_SECTORS = [*ORIGINAL, "XLC", "XLRE"]
DEFENSIVE = ["XLP", "XLU", "XLV"]
CYCLICAL = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLY"]
TRAIN_END = "2014-12-31"
START, END = "1999-01-01", "2026-10-31"
CFG = ExecutionConfig(lag=1, cost_bps=3.0, slippage_bps=2.0, rebalance="M")
REPS, SEED = 500, 17
# Recesiones NBER (anunciadas con meses de rezago: NO son información punto-en-el-tiempo).
NBER = [("2001-03-01", "2001-11-30"), ("2007-12-01", "2009-06-30"), ("2020-02-01", "2020-04-30")]


def rotation_weights(prices: pd.DataFrame, lookback_m: int, k: int) -> pd.DataFrame:
    """Pesos 1/k en los k sectores con mayor retorno de ``lookback_m`` meses (salta 1 mes)."""
    skip = 21
    mom = prices.shift(skip) / prices.shift(skip + 21 * lookback_m) - 1
    rank = mom.rank(axis=1, ascending=False)
    w = (rank <= k).astype(float) / k
    return w.where(mom.notna().sum(axis=1) >= k, np.nan)


def ann(sr_per_period: float, ppy: int = 252) -> float:
    return float(sr_per_period * np.sqrt(ppy))


def rotation(bundle: Bundle, rf: pd.Series | None) -> dict[str, object]:
    px = bundle.assets(ORIGINAL).loc[START:END].dropna()
    grid = [(lb, k) for lb in (6, 12) for k in (3, 4)]
    calib, oos = {}, {}
    # Prueba de anticipación sobre la regla (antes de evaluar nada).
    look = {
        f"L{lb}_k{k}": check_lookahead(lambda p, lb=lb, k=k: rotation_weights(p, lb, k), px)
        for lb, k in grid
    }
    results = {}
    for lb, k in grid:
        res = run_backtest(px, rotation_weights(px, lb, k), CFG, risk_free=rf)
        results[(lb, k)] = res
        ex = res.evaluation_window()
        calib[f"L{lb}_k{k}"] = ann(sharpe_per_period(ex.loc[:TRAIN_END]))
    best = max(calib, key=lambda c: calib[c])
    lb, k = (int(best.split("_")[0][1:]), int(best.split("_")[1][1:]))
    res = results[(lb, k)]
    assert res.benchmark_excess_returns is not None

    # DSR del ratio de información frente a igual ponderado, con las 4 configuraciones.
    def active_calib(r: object) -> pd.Series:
        ew = r.evaluation_window().loc[:TRAIN_END]  # type: ignore[attr-defined]
        return ew - r.benchmark_excess_returns.loc[ew.index]  # type: ignore[attr-defined]

    ir_var = float(np.var([sharpe_per_period(active_calib(r)) for r in results.values()], ddof=1))
    dsr = deflated_sharpe(active_calib(res), len(grid), ir_var)
    after = res.excess_returns.loc[TRAIN_END:].iloc[1:]
    bench = res.benchmark_excess_returns.loc[after.index]
    inf = sharpe_inference(after, 252, reps=REPS, seed=SEED)
    inf_b = sharpe_inference(bench, 252, reps=REPS, seed=SEED)
    diff = sharpe_difference(after, bench, reps=REPS, seed=SEED)
    spy = bundle.assets(["SPY"])["SPY"].loc[after.index[0] : after.index[-1]]
    spy_res = run_backtest(spy, pd.Series(1.0, index=spy.index), CFG, risk_free=rf)
    eq = (1 + after).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    eqb = (1 + bench).cumprod()
    ddb = float((eqb / eqb.cummax() - 1).min())
    for name, r in results.items():
        a = r.excess_returns.loc[TRAIN_END:].iloc[1:]
        oos[f"L{name[0]}_k{name[1]}"] = ann(sharpe_per_period(a))  # sólo diagnóstico, no selección
    return {
        "grid": [f"L{lb}_k{k}" for lb, k in grid],
        "lookahead": {c: r.summary() for c, r in look.items()},
        "calibration_sharpe": calib,
        "chosen": best,
        "dsr_vs_equal_weight_calibration": dsr.dsr,
        "oos": {
            "sharpe": inf.sharpe,
            "ci95": [inf.ci_low, inf.ci_high],
            "se_hac": inf.se_hac,
            "max_drawdown": dd,
            "equal_weight_sharpe": inf_b.sharpe,
            "equal_weight_max_drawdown": ddb,
            "spy_sharpe": ann(sharpe_per_period(spy_res.excess_returns.iloc[1:])),
            "diff_vs_equal_weight": diff.difference,
            "p_one_sided": diff.p_value,
            "turnover_mean": float(res.turnover.loc[after.index].mean()),
            "months": int(len(monthly_returns(px.iloc[:, 0].loc[after.index]))),
        },
        "oos_all_configs_diagnostic_only": oos,
    }


def excess_monthly(prices: pd.Series, rf: pd.Series | None) -> pd.Series:
    r = monthly_returns(prices)
    if rf is None:
        return r
    daily = rf.reindex(prices.index.union(rf.index)).ffill().reindex(prices.index).shift(1)
    idx = pd.DatetimeIndex(prices.index)
    rf_m = (1 + daily.fillna(0.0)).groupby(idx.to_period("M")).prod() - 1
    rf_m.index = rf_m.index.to_timestamp("M")
    r.index = pd.DatetimeIndex(r.index).to_period("M").to_timestamp("M")
    return r - rf_m.reindex(r.index).fillna(0.0)


def cycles(bundle: Bundle, rf: pd.Series | None) -> dict[str, object]:
    spy = bundle.assets(["SPY"])["SPY"].loc[START:END].dropna()
    dates = monthly_decision_dates(spy)
    x = align_point_in_time(bundle.exogenous(["^TNX", "^VIX"]), dates)
    # ^IRX es la tasa libre de riesgo del paquete; su nivel en % se obtiene de los datos crudos.
    raw = bundle.data
    irx_s = raw[raw["series_id"] == "^IRX"].set_index("date")["value"].sort_index()
    irx_s.index = pd.DatetimeIndex(irx_s.index)
    irx_pit = irx_s.shift(1).reindex(irx_s.index.union(dates)).ffill().reindex(dates)  # rezago 1B
    spy_m = spy.reindex(spy.index.union(dates)).ffill().reindex(dates)
    sma10 = spy_m.rolling(10).mean()
    states = pd.DataFrame(
        {
            "curva_invertida": (x["^TNX"] - irx_pit) < 0,
            "vix_alto": x["^VIX"] > 25,
            "mercado_bajista": spy_m < sma10,
        },
        index=dates,
    ).iloc[10:]
    states.index = states.index.to_period("M").to_timestamp("M")
    out: dict[str, object] = {"state_months": {c: int(states[c].sum()) for c in states}}
    out["total_months"] = len(states)
    rows, pvals = [], []
    nxt = {}
    for s in [*ALL_SECTORS, "SPY"]:
        px = bundle.assets([s])[s].loc[START:END].dropna()
        nxt[s] = excess_monthly(px, rf).shift(-1)  # retorno del mes SIGUIENTE a la decisión
    for regime in states.columns:
        for s in ALL_SECTORS:
            d = pd.concat({"y": nxt[s], "on": states[regime].astype(float)}, axis=1).dropna()
            if d["on"].sum() < 6 or (1 - d["on"]).sum() < 6:
                continue
            fit = sm.OLS(d["y"], sm.add_constant(d["on"])).fit(
                cov_type="HAC", cov_kwds={"maxlags": 3}
            )
            rows.append(
                {
                    "regime": regime,
                    "sector": s,
                    "months_on": int(d["on"].sum()),
                    "months_off": int((1 - d["on"]).sum()),
                    "ann_excess_on": float(d.loc[d["on"] == 1, "y"].mean() * 12),
                    "ann_excess_off": float(d.loc[d["on"] == 0, "y"].mean() * 12),
                    "diff_ann": float(fit.params["on"] * 12),
                    "t_hac": float(fit.tvalues["on"]),
                    "p": float(fit.pvalues["on"]),
                }
            )
            pvals.append(float(fit.pvalues["on"]))
    for r, ph in zip(rows, holm(pvals), strict=True):
        r["p_holm"] = ph
    out["by_regime"] = rows
    # Defensivos menos cíclicos (9 originales), por estado.
    defn = pd.concat([nxt[s] for s in DEFENSIVE], axis=1).mean(axis=1)
    cyc = pd.concat([nxt[s] for s in CYCLICAL], axis=1).mean(axis=1)
    spread = (defn - cyc).rename("y")
    sp = []
    for regime in states.columns:
        d = pd.concat({"y": spread, "on": states[regime].astype(float)}, axis=1).dropna()
        fit = sm.OLS(d["y"], sm.add_constant(d["on"])).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
        sp.append(
            {
                "regime": regime,
                "def_minus_cyc_on": float(d.loc[d["on"] == 1, "y"].mean() * 12),
                "def_minus_cyc_off": float(d.loc[d["on"] == 0, "y"].mean() * 12),
                "p": float(fit.pvalues["on"]),
            }
        )
    out["defensive_minus_cyclical"] = sp
    # NBER (ex post): retorno anualizado en exceso CONTEMPORÁNEO por sector.
    rec = pd.Series(False, index=states.index)
    for a, b in NBER:
        rec.loc[a:b] = True
    nb = []
    for s in [*ORIGINAL, "SPY"]:
        px = bundle.assets([s])[s].loc[START:END].dropna()
        m = excess_monthly(px, rf).reindex(rec.index)
        nb.append(
            {
                "sector": s,
                "recession_ann": float(m[rec].mean() * 12),
                "expansion_ann": float(m[~rec].mean() * 12),
                "recession_months": int(rec.sum()),
            }
        )
    out["nber_ex_post"] = nb
    return out


def sector_overview(bundle: Bundle, rf: pd.Series | None) -> list[dict[str, object]]:
    rows = []
    for s in [*ALL_SECTORS, "SPY"]:
        px = bundle.assets([s])[s].loc[START:END].dropna()
        m = excess_monthly(px, rf)
        eq = px / px.iloc[0]
        rows.append(
            {
                "ticker": s,
                "start": str(px.index[0].date()),
                "ann_excess": float(m.mean() * 12),
                "ann_vol": float(m.std() * np.sqrt(12)),
                "sharpe": float(m.mean() / m.std() * np.sqrt(12)),
                "max_drawdown": float((eq / eq.cummax() - 1).min()),
            }
        )
    return rows


def main(out_path: str) -> None:
    bundle = Bundle.load(HERE / "data")
    rf = bundle.risk_free()
    result = {
        "bundle_sha256": bundle.sha256,
        "overview": sector_overview(bundle, rf),
        "rotation": rotation(bundle, rf),
        "cycles": cycles(bundle, rf),
    }
    Path(out_path).write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(f"Escrito {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "analisis_exploratorio.json")
