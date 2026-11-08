"""Ejercicio backtest 02 — Modelo econométrico macro para TLT con validación doble.

Pregunta: ¿las variables macro-financieras pronostican el retorno mensual en exceso de
TLT y esas señales "se cumplen" en un backtest responsable?

Variables explicativas (FRED, punto en el tiempo, con rezago de publicación declarado):
- ``term_spread``  : T10Y2Y (10 años − 2 años), nivel; rezago 1 día hábil.
- ``d_yield10``    : cambio mensual de DGS10; rezago 1 día hábil.
- ``credit_spread``: BAA10Y (Baa − Tesoro 10 años), nivel; rezago 1 día hábil.
- ``inflation``    : IPC sin desestacionalizar (CPIAUCNS), variación anual; rezago de
  20 días tras el fin de mes (BLS publica hacia el día 10-15; conservador). Se usa la
  serie sin desestacionalizar porque la ajustada se revisa hacia atrás.

Flujo: decisión el último día hábil de cada mes; regresión predictiva re-estimada cada
mes con ventana expansiva (mínimo 60 meses); ejecución al cierre siguiente y posición
mantenida hasta la próxima decisión; costo 5 pb.

    uv run python examples/backtest_02_macro_tlt.py [--report r.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from tsinsurance.backtest import (
    ExecutionConfig,
    Exogenous,
    PredictiveRegression,
    align_point_in_time,
    backtest_econometric,
    check_lookahead,
    dtb3_to_daily,
    forecast_to_weights,
    monthly_decision_dates,
    monthly_returns,
)
from tsinsurance.data import Snapshot, to_wide

DATA = Path(__file__).parent / "data"
MODEL = PredictiveRegression(min_train=60, scheme="expanding", refit_every=1)
CONFIG = ExecutionConfig(cost_bps=5.0, rebalance="M")  # mantener hasta la próxima decisión


def load() -> tuple[pd.Series, pd.Series, list[Exogenous]]:
    """Precios de TLT, tasa libre de riesgo diaria y variables exógenas."""
    tlt = to_wide(Snapshot.load(DATA / "yahoo_etfs").data)["TLT"].dropna()
    daily = to_wide(Snapshot.load(DATA / "fred_daily").data)
    monthly = to_wide(Snapshot.load(DATA / "fred_monthly").data)
    rf = dtb3_to_daily(daily["DTB3"])
    exogs = [
        Exogenous("term_spread", daily["T10Y2Y"].dropna(), "B", release_lag="1B"),
        Exogenous("yield10", daily["DGS10"].dropna(), "B", release_lag="1B"),
        Exogenous("credit_spread", daily["BAA10Y"].dropna(), "B", release_lag="1B"),
        Exogenous(
            "inflation", monthly["CPIAUCNS"].dropna(), "M", release_lag="20D", transform="yoy"
        ),
    ]
    return tlt.rename("TLT"), rf, exogs


def build_inputs(
    prices: pd.Series, rf: pd.Series, exogs: list[Exogenous]
) -> tuple[pd.Series, pd.DataFrame]:
    """Retorno mensual en exceso de TLT y regresores conocidos en cada fecha de decisión."""
    dates = monthly_decision_dates(prices)
    x = align_point_in_time(exogs, dates)
    x["d_yield10"] = x["yield10"].diff()  # cambio entre fechas de decisión: ambos conocidos
    x = x.drop(columns="yield10")
    r = monthly_returns(prices)
    rf_daily = rf.reindex(prices.index.union(rf.index)).ffill().reindex(prices.index).shift(1)
    rf_month = (1 + rf_daily.fillna(0.0)).groupby(prices.index.to_period("M")).prod() - 1
    rf_month = rf_month.loc[[d.to_period("M") for d in dates]]
    rf_month.index = dates
    y = (r - rf_month.reindex(r.index)).rename("TLT_excess")
    out = x.loc[y.index].dropna()
    out.attrs = dict(x.attrs)  # indicadores punto-en-el-tiempo de las variables
    return y, out


def pipeline(data: dict[str, object]) -> pd.DataFrame:
    """Datos crudos → pesos (para la prueba de anticipación de todo el flujo)."""
    prices = data["prices"]
    rf = data["rf"]
    exogs = data["exogs"]
    assert isinstance(prices, pd.Series) and isinstance(rf, pd.Series)
    assert isinstance(exogs, list)
    y, x = build_inputs(prices, rf, exogs)
    wf = MODEL.walk_forward(y.loc[x.index], x)
    return forecast_to_weights(wf.forecasts, y, "long_cash").to_frame("TLT")


def main() -> None:
    """Ejecuta el ejercicio completo."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Guarda un JSON con los resultados.")
    args = parser.parse_args()
    tlt, rf, exogs = load()
    y, x = build_inputs(tlt, rf, exogs)
    y = y.loc[x.index]
    print(f"Muestra: {len(y)} meses ({y.index[0].date()} a {y.index[-1].date()})")

    print("=" * 88)
    print("1) Prueba de anticipación del flujo completo (datos crudos → pesos)")
    rep = check_lookahead(pipeline, {"prices": tlt, "rf": rf, "exogs": exogs}, n_cuts=6)
    rep.raise_if_biased()
    print("   " + rep.summary())

    report: dict[str, object] = {}
    # Se prueban dos reglas de posición: se declara n_specifications=2 (veredicto exploratorio).
    for rule in ("long_cash", "proportional"):
        print("=" * 88)
        print(f"2) Validación doble — regla '{rule}'")
        res = backtest_econometric(
            tlt,
            y,
            x,
            MODEL,
            position=rule,
            config=CONFIG,
            risk_free=rf,
            n_specifications=2,
            reps=1000,
            seed=0,
        )
        print(res.summary())
        ev = res.forecast_evaluation
        report[rule] = {
            "quadrant": res.verdict.quadrant,
            "exploratory": res.verdict.exploratory,
            "oos_r2": round(ev.oos_r2, 10),
            "clark_west_p": round(ev.clark_west.p_value or float("nan"), 10),
            "sharpe_model": round(res.economic_test.sharpe_a, 10),
            "sharpe_benchmark_rule": round(res.economic_test.sharpe_b, 10),
            "economic_p": round(res.economic_test.p_value, 10),
            "diagnostics_passed": res.validation.diagnostics_passed,
        }

    if args.report:
        text = json.dumps(report, sort_keys=True, default=str, indent=2)
        args.report.write_text(text, encoding="utf-8")
        print(f"\nReporte: {args.report} sha256={hashlib.sha256(text.encode()).hexdigest()[:16]}")


if __name__ == "__main__":
    main()
