"""Demostración de la spec 007 con el Tesoro de EE. UU. (Yahoo; 4 nodos).

Mide el riesgo de tasa de una cartera de bonos típica de una aseguradora. NO toma
decisiones de asignación: cualquier regla que use estas salidas es una idea y debe pasar
por el flujo de experimentos (FR-017).

    uv run python experiments/tesoro_riesgo/demo.py [--asof 2026-10-30]

Escribe ``results/<asof>/report.md`` y ``result.json``.
"""

from __future__ import annotations

import argparse
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from tsinsurance import __version__
from tsinsurance.data.bundle import Bundle
from tsinsurance.portfolio_risk import backtest_var, immunize, stress, var_es
from tsinsurance.results import to_jsonable
from tsinsurance.sensitivities import BondPortfolio, FixedBond, measures, node_hessian
from tsinsurance.simulation import factor_mc, filtered_historical, fit_factors, historical
from tsinsurance.simulation import short_rate_mc
from tsinsurance.stochastics import NodeCurve, RateQuote, VasicekP, calibrate_q, q_params
from tsinsurance.stochastics.curves import continuous_from_discount, continuous_from_periodic
from tsinsurance.stochastics.regimes import MarkovShortRate

HERE = Path(__file__).parent
TENORS = [0.25, 5.0, 10.0, 30.0]
IDS = ["^IRX", "^FVX", "^TNX", "^TYX"]
CONV = {
    "^IRX": RateQuote(0.25, "discount"),
    "^FVX": RateQuote(5.0, "par"),
    "^TNX": RateQuote(10.0, "par"),
    "^TYX": RateQuote(30.0, "par"),
}


def load(asof: str) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """Cotizaciones (decimales), nodos cero aproximados y tasa corta continua, hasta asof."""
    b = Bundle.load(HERE / "data").as_of(asof)
    quotes = pd.concat({i: b.variable(i).available_series() for i in IDS}, axis=1).sort_index()
    quotes = quotes.dropna() / 100.0
    notes = []
    gap = quotes.loc["2002-02-18":"2006-02-09", "^TYX"]
    if len(gap):
        notes.append(
            f"^TYX entre 2002-02 y 2006-02 ({len(gap)} días): el bono a 30 años no se emitió; "
            "el dato es el publicado por el CBOE y se usa tal cual (M2)."
        )
    return quotes, b.as_of_sha256 or "", notes


def zero_nodes(quotes: pd.DataFrame) -> pd.DataFrame:
    """Nodos cero continuos APROXIMADOS: ^IRX exacto; par semestral ≈ cero (declarado)."""
    z = pd.DataFrame(index=quotes.index)
    z[0.25] = continuous_from_discount(quotes["^IRX"].to_numpy(), 91)
    for col, t in (("^FVX", 5.0), ("^TNX", 10.0), ("^TYX", 30.0)):
        z[t] = continuous_from_periodic(quotes[col].to_numpy(), 2)
    return z


def main() -> None:  # noqa: C901, PLR0915 - guion lineal de demostración
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default="2026-10-30")
    args = ap.parse_args()
    t0 = time.time()
    warnings.filterwarnings("ignore")
    quotes, as_of_sha, notes = load(args.asof)
    z = zero_nodes(quotes)
    r = pd.Series(z[0.25].to_numpy(), index=z.index, name="r")
    out: dict = {
        "asof": args.asof,
        "package_version": __version__,
        "bundle_as_of_sha256": as_of_sha,
    }
    rep = [f"# Riesgo de tasa con el Tesoro de EE. UU. — {args.asof}", ""]
    rep += [
        "Demostración de la spec 007 (procesos estocásticos, simulación y sensibilidades). "
        "Mide riesgo; no recomienda asignaciones (FR-017).",
        "",
        f"- Datos: {len(quotes)} días ({quotes.index[0].date()} a {quotes.index[-1].date()}), "
        "Yahoo/CBOE, truncados en la fecha de análisis.",
        "- Nodos cero: ^IRX exacto (descuento act/360 → continuo); 5, 10 y 30 años como par "
        "semestral ≈ cero (aproximación sesgada en plazos largos con pendiente; declarada). "
        "La calibración ℚ sí valora el bono par.",
        *[f"- {n}" for n in notes],
        "",
    ]

    # 1. Tasa corta bajo ℙ. Desde 2009 (tasas de 0 % a 5 %) φ̂ ≥ 1: κ no identificado; se
    # usa la muestra completa y se reporta la debilidad de la identificación.
    since_2009 = VasicekP.fit(r.loc["2009-01-01":], 1 / 252, bootstrap=0)
    fit = VasicekP.fit(r, 1 / 252, bootstrap=199, seed=1, jackknife=True)
    diag = fit.diagnostics()
    out["vasicek_p"] = {
        **fit.params,
        "ci": fit.ci,
        "kappa_jackknife": fit.bias_corrected_kappa,
        "warnings": fit.warnings,
        "identified_since_2009": since_2009.identified,
    }
    out["vasicek_diagnostics"] = {
        "passed": diag.passed,
        "warnings": diag.warnings,
        "walk_forward": diag.walk_forward,
    }
    neg = int((r <= 0).sum())
    rep += [
        "## 1. Tasa corta bajo ℙ (Vasicek, 1998-2026)",
        "",
        "```",
        fit.summary(),
        "",
        diag.summary(),
        "```",
        "",
        f"- Desde 2009 φ̂ = {since_2009.warnings[0].split('=')[1].split('≥')[0].strip() if not since_2009.identified else 'n/d'}"
        " ≥ 1: en esa muestra la tasa corta se comporta como un paseo aleatorio (κ no "
        "identificado). Con toda la muestra κ es pequeño y su IC es muy ancho: la reversión "
        "a la media es un supuesto del modelo más que un hecho de los datos.",
        f"- CIR no aplica: {neg} días con tasa ≤ 0 (2009-2015 y 2020-2021).",
        "",
    ]

    # 2. Regímenes (mensual para la velocidad; parámetros hasta asof ⇒ pseudo-filtradas).
    r_m = r.resample("ME").last().dropna()
    reg = MarkovShortRate.fit(r_m, k_regimes=2, dt=1 / 12, search_reps=10, seed=3)
    out["regimes"] = {
        "sigma": reg.sigma,
        "theta": reg.theta,
        "kappa": reg.kappa,
        "transition": reg.transition,
        "prefers": reg.prefers_regimes,
        "last_filtered": reg.filtered_probabilities.iloc[-1].tolist(),
    }
    rep += [
        "## 2. Regímenes de Markov (mensual)",
        "",
        "```",
        reg.summary(),
        "```",
        "",
        f"- Probabilidad filtrada del régimen volátil al cierre: "
        f"{reg.filtered_probabilities.iloc[-1, 1]:.1%} (pseudo-filtrada: parámetros "
        "estimados con toda la muestra).",
        "",
    ]

    # 3. Calibración ℚ en los últimos 12 meses: λ con σ_ℚ = σ_ℙ.
    win = (str((quotes.index[-1] - pd.DateOffset(months=12)).date()), args.asof)
    cal = calibrate_q("vasicek", quotes, CONV, r, fit, window=win)
    free = calibrate_q("vasicek", quotes, CONV, r, fit, window=win, mode="free")
    out["q_calibration"] = {
        "lambda": cal.lam,
        "lambda_se": cal.lam_se,
        "rmse_bp": cal.rmse_bp,
        "free": {"params_q": free.params_q, "rmse_bp": free.rmse_bp},
    }
    rep += [
        "## 3. Medida ℚ (Vasicek, 12 meses)",
        "",
        "```",
        cal.summary(),
        "",
        free.summary(),
        "```",
        "",
        "- Un factor no reproduce bien la curva entera: el RMSE por nodo mide cuánto. Para "
        "valorar se usa la curva observada (revaluación completa), no el modelo.",
        "",
    ]

    # 4. Factores (PCA de cambios diarios, 3 años).
    dz = z.diff().dropna()
    fm = fit_factors(dz.iloc[-756:], "pca", 3, tenors=TENORS)
    dl = fit_factors(dz.iloc[-756:], "diebold_li", 3, tenors=TENORS)
    out["factors"] = {
        "labels": fm.labels,
        "explained": fm.explained,
        "loadings": fm.loadings.tolist(),
        "diebold_li_residual_bp": dl.residual_sd_bp,
    }
    rep += [
        "## 4. Factores de la curva (3 años de cambios diarios)",
        "",
        "```",
        fm.summary(),
        "",
        dl.summary(),
        "```",
        "",
    ]

    # 5. Cartera y sensibilidades.
    curve = NodeCurve.from_arrays(TENORS, z.iloc[-1].to_numpy())
    port = BondPortfolio.of(
        [
            (FixedBond(2.0, 0.04), 2000),
            (FixedBond(5.0, 0.042), 3000),
            (FixedBond(10.0, 0.045), 3000),
            (FixedBond(25.0, 0.047), 1500),
        ]
    )
    sens = measures(port, curve)
    out["sensitivities"] = to_jsonable(sens)
    rep += [
        "## 5. Cartera y sensibilidades",
        "",
        f"- {port.summary()}",
        "",
        "```",
        sens.summary(),
        "```",
        "",
    ]

    # 6. Escenarios a 10 días y VaR/ES (pérdida = −ΔPV), con revaluación completa.
    h = 10
    scen = {
        "histórica (3 años)": historical(z, horizon=h, window=756, tenors=TENORS),
        "histórica filtrada EWMA": filtered_historical(z, horizon=h, n=5000, seed=4, tenors=TENORS),
        "MC de factores t₅": factor_mc(fm, n=5000, horizon=h, dist="t", seed=5),
        "MC de la tasa corta (ℙ→ℚ λ)": short_rate_mc(
            fit,
            TENORS,
            horizon=h,
            n=5000,
            seed=6,
            params_q=q_params("vasicek", fit, cal.lam or 0.0),
        ),
    }
    out["var_es"] = {}
    rep += [
        f"## 6. VaR y ES a {h} días (revaluación completa)",
        "",
        "| Motor | VaR 99 % | ES 97,5 % | IC 95 % del ES |",
        "|---|---|---|---|",
    ]
    base_pv = port.pv(curve)
    for name, sc in scen.items():
        losses = -np.array([port.pv(curve.shifted(v)) - base_pv for v in sc.values])
        rm = var_es(
            losses,
            (0.99, 0.975),
            ci="block" if "histórica (" in name else "bootstrap",
            reps=300,
            monte_carlo="MC" in name,
        )
        out["var_es"][name] = to_jsonable(rm)
        lo, hi = rm.es_ci["0.975"]
        rep.append(
            f"| {name} | {rm.var['0.99']:,.0f} | {rm.es['0.975']:,.0f} | [{lo:,.0f}; {hi:,.0f}] |"
        )
    rep += [
        "",
        "- El MC de un factor mueve toda la curva con r_T: subestima el riesgo de "
        "pendiente. Los IC de Monte Carlo miden sólo el error de simulación.",
        "",
    ]

    # 7. Backtesting del VaR a 1 día (FHS EWMA punto en el tiempo, sensibilidades mensuales).
    lam = 0.94
    d = dz.loc["2006-01-01":].to_numpy()
    dates = dz.loc["2006-01-01":].index
    var_ = np.zeros_like(d)
    v = d[:250].var(axis=0)
    for t in range(d.shape[0]):
        var_[t] = v
        v = lam * v + (1 - lam) * d[t] ** 2
    sig = np.sqrt(var_)
    zstd = d / sig
    realized, forecast, es_fc, kept = [], [], [], []
    start = 1000
    g = hess = None
    month = None
    for t in range(start, d.shape[0]):
        if dates[t].month != month:  # re-estimación mensual (I9) con la curva de t−1
            month = dates[t].month
            c_t = NodeCurve.from_arrays(TENORS, z.loc[: dates[t - 1]].iloc[-1].to_numpy())
            s_t = measures(port, c_t)
            g = -np.array(list(s_t.dollar_krd.values()))
            hess = node_hessian(port, c_t)
        sims = zstd[t - 750 : t] * sig[t]  # innovaciones hasta t−1, σ pronosticada para t
        loss_s = -(sims @ g + 0.5 * np.einsum("ni,ij,nj->n", sims, hess, sims))
        realized.append(-(d[t] @ g + 0.5 * d[t] @ hess @ d[t]))
        q = np.quantile(loss_s, 0.99)
        forecast.append(q)
        es_fc.append(loss_s[loss_s >= np.quantile(loss_s, 0.975)].mean())
        kept.append(loss_s)
    bt = backtest_var(np.array(realized), np.array(forecast), 0.99)
    out["backtest"] = to_jsonable(bt)
    rep += [
        f"## 7. Backtesting del VaR 99 % a 1 día (FHS EWMA, {len(realized)} días)",
        "",
        "```",
        bt.summary(),
        "```",
        "",
        "- Pérdidas realizadas y pronosticadas con la aproximación ΔΓ (sensibilidades "
        "re-estimadas cada mes con la curva del día previo): mide el modelo de escenarios, "
        "no el error de la aproximación.",
        "",
    ]

    # 8. Estrés e inmunización.
    st = stress(port, curve, factor_model=fm, factor_sd=3.0)
    hedges = [FixedBond(5.0, 0.0, 1), FixedBond(10.0, 0.0, 1), FixedBond(30.0, 0.0, 1)]
    hd = immunize(port, hedges, curve)
    out["stress"] = st.results
    out["hedge"] = to_jsonable(hd)
    rep += [
        "## 8. Estrés e inmunización",
        "",
        "```",
        st.summary(),
        "",
        hd.summary(),
        "```",
        "",
        "- Con 3 coberturas cupón cero para 4 nodos no se anula la exposición del nodo de 13 "
        "semanas: se reporta el residual mínimo (M5).",
        "",
    ]
    out["elapsed_s"] = round(time.time() - t0, 1)
    rep += [f"_Tiempo de ejecución: {out['elapsed_s']} s · tsinsurance {__version__}_", ""]
    dest = HERE / "results" / args.asof
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "report.md").write_text("\n".join(rep), encoding="utf-8")
    (dest / "result.json").write_text(
        json.dumps(to_jsonable(out), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("\n".join(rep))


if __name__ == "__main__":
    main()
