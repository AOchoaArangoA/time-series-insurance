"""Ejecución de experimentos declarativos con registro permanente.

Salvaguardas (Principio VIII):

1. **Pre-registro**: antes de ejecutar se agrega a la bitácora el hash de
   ``experiment.toml`` y del paquete de insumos.
2. **Anticipación**: cada combinación de cada idea pasa :func:`check_lookahead`.
3. **Calibración separada**: con ``train_end`` el barrido y la selección sólo miran el
   periodo de calibración; la validación se abre una vez por clave y queda registrada.
   Volver a abrir la misma validación marca el resultado como exploratorio.
4. **Pruebas múltiples**: todas las pruebas (señales y modelos econométricos) de todas
   las ejecuciones se cuentan por activo en el DSR (identidad completa: señal,
   parámetros, ejecución, ventana, huella del paquete); la selección se calcula al final
   (independiente del orden de las ideas) y la SPA se ajusta por activos (Holm).
5. **Marcas automáticas**: el resultado es exploratorio si git está sucio, la bitácora no
   es la declarada, no se registra, el paquete no está sellado, hay variables no
   punto-en-el-tiempo o se reabre una validación.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import itertools
import json
import os
import platform
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tsinsurance import __version__
from tsinsurance.backtest import (
    PredictiveRegression,
    TrialRegistry,
    align_point_in_time,
    backtest_econometric,
    check_lookahead,
    monthly_decision_dates,
    monthly_returns,
    sharpe_difference,
    sharpe_inference,
)
from tsinsurance.backtest.econometric import forecast_to_weights
from tsinsurance.backtest.metrics import sharpe_per_period
from tsinsurance.backtest.sweep import Trial, evaluate_grid, select
from tsinsurance.data.bundle import Bundle
from tsinsurance.errors import TSInsuranceError
from tsinsurance.experiments.registry import (
    append_trials,
    prior_information_ratios,
    prior_specifications,
    read_registry,
    trial_key,
    validation_seen,
    verify_registry,
)
from tsinsurance.experiments.signals import SignalFn, get_signal
from tsinsurance.experiments.spec import EconometricSpec, ExperimentSpec, load_experiment
from tsinsurance.results import to_jsonable

__all__ = ["ExperimentResult", "run_experiment"]

RESULT_VERSION = "1.1"


@dataclass(frozen=True, slots=True, eq=False)
class ExperimentResult:
    """Resultado de una ejecución."""

    run_id: str
    output_dir: Path
    result: dict[str, Any]
    report: str
    n_trials_registered: int

    @property
    def exploratory(self) -> bool:
        """``True`` si alguna salvaguarda no se cumplió."""
        return bool(self.result["status"]["exploratory_reasons"])

    def summary(self) -> str:
        """Resumen corto."""
        flag = " [EXPLORATORIO]" if self.exploratory else ""
        return (
            f"Experimento '{self.result['experiment']['id']}' ejecución {self.run_id}{flag}: "
            f"{self.n_trials_registered} línea(s) registradas; resultados en {self.output_dir}"
        )


def _git(start: Path) -> dict[str, Any]:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=start, capture_output=True, text=True, check=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=start,
            capture_output=True,
            text=True,
        ).stdout
        return {"commit": sha, "dirty": bool(status.strip())}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def _combos(grid: Mapping[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(grid)
    return [dict(zip(keys, c, strict=True)) for c in itertools.product(*grid.values())]


def _bind(fn: SignalFn, params: Mapping[str, Any]) -> Callable[[pd.DataFrame], pd.DataFrame]:
    def call(p: pd.DataFrame) -> pd.DataFrame:
        return fn(p, **params)

    return call


def _excess_monthly(prices: pd.Series, rf: pd.Series | None) -> pd.Series:
    r = monthly_returns(prices)
    if rf is None:
        return r
    daily = rf.reindex(prices.index.union(rf.index)).ffill().reindex(prices.index).shift(1)
    idx = pd.DatetimeIndex(prices.index)
    rf_m = (1 + daily.fillna(0.0)).groupby(idx.to_period("M")).prod() - 1
    rf_m = rf_m.reindex([d.to_period("M") for d in pd.DatetimeIndex(r.index)])
    out: pd.Series = r - rf_m.to_numpy()
    out.name = prices.name
    return out


def _econ_inputs(
    bundle: Bundle, prices: pd.Series, spec: EconometricSpec, rf: pd.Series | None
) -> tuple[pd.Series, pd.DataFrame]:
    needed = {*spec.regressors, *(d["from"] for d in spec.derived.values())}
    exogs = bundle.exogenous(sorted(needed - set(spec.derived)))
    x = align_point_in_time(exogs, monthly_decision_dates(prices))
    attrs = dict(x.attrs)
    for name, rule in spec.derived.items():
        if rule.get("op") != "diff":
            raise TSInsuranceError(f"Derivada '{name}': sólo se admite op='diff'.")
        x[name] = x[rule["from"]].diff()
    y = _excess_monthly(prices, rf)
    out = x.loc[y.index, list(spec.regressors)].dropna()
    out.attrs = attrs
    return y.loc[out.index], out


def _round(obj: Any, digits: int = 10) -> Any:
    if isinstance(obj, float):
        return round(obj, digits) if np.isfinite(obj) else None
    if isinstance(obj, Mapping):
        return {k: _round(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v, digits) for v in obj]
    return obj


def _execution_identity(cfg: Any) -> dict[str, Any]:
    out = {}
    for f in dataclasses.fields(cfg):
        if f.name == "notes":
            continue
        v = getattr(cfg, f.name)
        out[f.name] = dict(v) if isinstance(v, Mapping) else v
    return out


def run_experiment(
    path: str | os.PathLike[str] | ExperimentSpec,
    *,
    registry: str | os.PathLike[str] | None = None,
    output_root: str | os.PathLike[str] | None = None,
    record: bool = True,
) -> ExperimentResult:
    """Ejecuta un experimento con todas las salvaguardas.

    Parameters
    ----------
    path : str, PathLike o ExperimentSpec
        ``experiment.toml``.
    registry : PathLike, optional
        Bitácora alternativa (marca el resultado como exploratorio si no es la declarada).
    output_root : PathLike, optional
        Carpeta de resultados (por defecto ``results/`` junto al experimento).
    record : bool
        ``False`` no escribe en la bitácora (marca el resultado como exploratorio).
    """
    declared = load_experiment(path) if not isinstance(path, ExperimentSpec) else path
    spec = load_experiment(declared.path, registry=registry) if registry is not None else declared
    started = dt.datetime.now(dt.UTC).replace(microsecond=0)
    bundle = Bundle.load(spec.bundle)
    eval_end = spec.train_end or spec.end
    prices = bundle.assets(spec.assets).loc[spec.start : spec.end]
    rf = bundle.risk_free()
    exp_sha = hashlib.sha256(spec.path.read_bytes()).hexdigest()
    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "-" + exp_sha[:6]
    git = _git(spec.path.parent)

    reasons: list[str] = []
    if git["dirty"]:
        reasons.append("cambios sin confirmar en git (código o experimento no versionado)")
    if spec.registry != declared.registry:
        reasons.append(f"bitácora distinta de la declarada ({spec.registry})")
    if not record:
        reasons.append("ejecución sin registro en la bitácora")
    if not bundle.sealed:
        reasons.append("paquete de insumos sin sellar (sin huella)")
    not_pit = [s.id for s in bundle.series if s.role == "exogenous" and not s.point_in_time]
    if not_pit:
        reasons.append(f"variables no punto-en-el-tiempo: {not_pit}")
    integrity = verify_registry(spec.registry)
    if integrity:
        raise TSInsuranceError("La bitácora fue alterada: " + "; ".join(integrity[:3]))

    history = read_registry(spec.registry)
    base_identity = {
        "bundle": bundle.sha256,
        "execution": _execution_identity(spec.execution),
        "start": spec.start,
        "end": eval_end,
    }

    def signal_key(asset: str, signal: str, params: Mapping[str, Any]) -> str:
        return trial_key(
            kind="signal", asset=asset, signal=signal, params=dict(params), **base_identity
        )

    current_keys = [
        signal_key(a, idea.signal, c)
        for idea in spec.ideas
        for c in _combos(idea.grid)
        for a in spec.assets
    ]
    econ_keys = {
        es.name: trial_key(kind="econometric", **dataclasses.asdict(es), **base_identity)
        for es in spec.econometric
    }
    prior = prior_information_ratios(
        history, exclude_keys=[*current_keys, *econ_keys.values()], periods_per_year=252
    )
    lines: list[dict[str, Any]] = []
    common = {
        "experiment_id": spec.id,
        "run_id": run_id,
        "created_at": started.isoformat(),
        "bundle_sha256": bundle.sha256,
        "package_version": __version__,
        "git_commit": git["commit"],
        "seed": spec.seed,
    }
    if record:
        append_trials(
            spec.registry,
            [
                {
                    **common,
                    "kind": "preregistration",
                    "experiment_sha256": exp_sha,
                    "hypothesis": spec.hypothesis,
                    "train_end": spec.train_end,
                }
            ],
        )

    result: dict[str, Any] = {
        "result_version": RESULT_VERSION,
        "experiment": {
            "id": spec.id,
            "title": spec.title,
            "hypothesis": spec.hypothesis,
            "author": spec.author,
            "file": str(spec.path),
            "sha256": exp_sha,
        },
        "provenance": {
            "run_id": run_id,
            "started_at": started.isoformat(),
            "package_version": __version__,
            "python": platform.python_version(),
            "git": git,
            "bundle": {
                "name": bundle.name,
                "sha256": bundle.sha256,
                "path": str(spec.bundle),
                "quality_warnings": bundle.quality_warnings(),
            },
            "seed": spec.seed,
            "registry": str(spec.registry),
            "prior_trials_by_asset": {k: len(v) for k, v in prior.items()},
        },
        "assumptions": {
            "execution": spec.execution.describe(),
            "alpha": spec.alpha,
            "risk_free": bundle.ids("risk_free"),
            "window": [str(prices.index[0].date()), str(prices.index[-1].date())],
            "selection_window_end": eval_end,
            "train_end": spec.train_end,
            "asset_start": {a: str(prices[a].dropna().index[0].date()) for a in spec.assets},
        },
        "ideas": {},
        "calibration": {},
        "econometric": {},
    }
    report = [
        f"# Experimento {spec.id}",
        "",
        f"**Hipótesis (pre-registrada)**: {spec.hypothesis or 'n/d'}",
        "",
        f"- Ejecución `{run_id}` · experimento sha256 {exp_sha[:12]}… · paquete `{bundle.name}` "
        f"(sha256 {bundle.sha256[:12]}…) · tsinsurance {__version__} · semilla {spec.seed}",
        f"- Supuestos: {spec.execution.describe()}",
        f"- Selección y pruebas múltiples sobre datos hasta {eval_end or 'el final'}"
        + (f"; validación única desde {spec.train_end}" if spec.train_end else ""),
        "- Pruebas previas en la bitácora por activo: "
        + str(result["provenance"]["prior_trials_by_asset"]),
    ]
    for w in bundle.quality_warnings():
        report.append(f"- Calidad de datos: {w}")
    report.append("")

    trials = TrialRegistry()
    current: dict[str, dict[str, list[Trial]]] = {}
    for idea in spec.ideas:
        fn = get_signal(idea.signal)
        checks: dict[str, Any] = {}
        for asset in spec.assets:
            px = prices[[asset]].dropna()
            bad = []
            for combo in _combos(idea.grid):
                rep = check_lookahead(_bind(fn, combo), px, seed=spec.seed)
                if rep.has_lookahead or not rep.conclusive:
                    bad.append({"params": combo, "summary": rep.summary()})
            checks[asset] = {"combinations": len(_combos(idea.grid)), "failed": bad}
        entry: dict[str, Any] = {"signal": idea.signal, "grid": idea.grid, "lookahead": checks}
        result["ideas"][idea.name] = entry
        if any(c["failed"] for c in checks.values()):
            entry["status"] = "rechazada_por_anticipacion"
            continue
        table, cur = evaluate_grid(
            prices.loc[:eval_end],
            fn,
            idea.grid,
            spec.execution,
            risk_free=rf,
            registry=trials,
            name=idea.name,
        )
        entry["status"] = "evaluada"
        entry["configurations"] = to_jsonable(table)
        current[idea.name] = cur

    for es in spec.econometric:
        px_e: pd.Series = bundle.assets([es.asset])[es.asset].loc[spec.start : spec.end].dropna()
        y, x = _econ_inputs(bundle, px_e, es, rf)
        model = PredictiveRegression(
            ar_lags=es.ar_lags, scheme=es.scheme, window=es.window, min_train=es.min_train
        )

        def pipeline(
            data: dict[str, Any], es: EconometricSpec = es, model: PredictiveRegression = model
        ) -> pd.DataFrame:
            wf = model.walk_forward(data["y"].loc[data["x"].index], data["x"])
            return forecast_to_weights(wf.forecasts, data["y"], es.position).to_frame()

        look = check_lookahead(pipeline, {"y": y, "x": x}, n_cuts=6, seed=spec.seed)
        n_specs = max(
            es.n_specifications, prior_specifications(history, es.asset, econ_keys[es.name]) + 1
        )
        cfg = dataclasses.replace(spec.execution, rebalance=es.rebalance)
        res = backtest_econometric(
            px_e,
            y,
            x,
            model,
            position=es.position,
            config=cfg,
            risk_free=rf,
            alpha=spec.alpha,
            n_specifications=n_specs,
            reps=spec.reps,
            seed=spec.seed,
        )
        bt = res.backtest
        window = bt.evaluation_window()
        exposure = float(bt.weights.abs().sum(axis=1).loc[window.index].mean())
        assert bt.benchmark_excess_returns is not None
        econ_trial = Trial(
            es.asset,
            {"idea": es.name},
            window,
            bt.benchmark_excess_returns.loc[window.index],
            exposure,
            bt.periods_per_year,
        )
        trials.add(econ_trial)
        bench_cash = bool((res.benchmark_backtest.weights.abs().sum(axis=1) == 0).all())
        v, ev = res.verdict, res.forecast_evaluation
        e = {
            "asset": es.asset,
            "regressors": es.regressors,
            "position": es.position,
            "n_specifications_counted": n_specs,
            "lookahead": look.summary(),
            "lookahead_ok": not look.has_lookahead and look.conclusive,
            "verdict": to_jsonable(v),
            "oos_r2": ev.oos_r2,
            "clark_west_p": ev.clark_west.p_value,
            "pesaran_timmermann_p": ev.pesaran_timmermann.p_value,
            "hit_rate": ev.hit_rate,
            "n_forecasts": ev.n_forecasts,
            "sharpe_model": res.economic_test.sharpe_a,
            "sharpe_benchmark_rule": res.economic_test.sharpe_b,
            "benchmark_rule_is_cash": bench_cash,
            "economic_p": res.economic_test.p_value,
            "timing_ir": sharpe_per_period(econ_trial.active_returns)
            * np.sqrt(bt.periods_per_year),
            "diagnostics_passed": res.validation.diagnostics_passed,
            "warnings": list(res.validation.warnings),
            "notes": list(res.notes),
        }
        result["econometric"][es.name] = e
        label = (
            "efectivo (la media histórica es negativa)"
            if bench_cash
            else "regla con media histórica"
        )
        report += [
            f"## Modelo econométrico `{es.name}` ({es.asset})",
            "",
            f"Especificaciones contadas sobre {es.asset}: {n_specs} · benchmark: {label} · "
            f"anticipación del flujo: {look.summary()}",
            "",
            "```text",
            res.summary(),
            "```",
            "",
        ]
        lines.append(
            {
                **common,
                "kind": "econometric",
                "key": econ_keys[es.name],
                "asset": es.asset,
                "idea": es.name,
                "params": dataclasses.asdict(es),
                "quadrant": v.quadrant,
                "oos_r2": ev.oos_r2,
                "timing_ir_per_period": sharpe_per_period(econ_trial.active_returns),
                "periods_per_year": bt.periods_per_year,
            }
        )

    # Selección al final: N por activo incluye TODAS las pruebas (orden irrelevante).
    for name, cur in current.items():
        sel = select(
            trials,
            cur,
            alpha=spec.alpha,
            reps=spec.reps,
            seed=spec.seed,
            prior_information_ratios=prior,
        )
        result["ideas"][name]["selection"] = to_jsonable(sel.reset_index())
        idea = next(i for i in spec.ideas if i.name == name)
        report += [
            f"## Idea `{name}` ({idea.signal}, malla {idea.grid}) — selección hasta "
            f"{eval_end or 'el final'}",
            "",
            "```text",
            sel[
                [
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
            ].to_string(float_format=lambda v: f"{v:.3f}"),
            "```",
            "",
        ]
        for asset, ts in cur.items():
            for t in ts:
                params = {k: v for k, v in t.params.items() if k != "idea"}
                lines.append(
                    {
                        **common,
                        "kind": "signal",
                        "key": signal_key(asset, idea.signal, params),
                        "asset": asset,
                        "idea": name,
                        "signal": idea.signal,
                        "params": params,
                        "sharpe_per_period": sharpe_per_period(t.excess_returns),
                        "timing_ir_per_period": sharpe_per_period(t.active_returns),
                        "exposure": t.exposure,
                        "periods_per_year": t.periods_per_year,
                        "n_obs": len(t.excess_returns),
                        "eval_start": str(t.excess_returns.index[0].date()),
                        "eval_end": str(t.excess_returns.index[-1].date()),
                    }
                )
    for idea in spec.ideas:
        if idea.name not in current:
            report += [f"## Idea `{idea.name}`: RECHAZADA por anticipación", ""]

    # Validación única: la configuración elegida en calibración, evaluada después.
    if spec.train_end:
        for name in current:
            idea = next(i for i in spec.ideas if i.name == name)
            sel = result["ideas"][name]["selection"]
            vkey = trial_key(
                kind="validation",
                experiment=spec.id,
                signal=idea.signal,
                grid=idea.grid,
                assets=spec.assets,
                **base_identity,
            )
            seen = validation_seen(history, vkey)
            if seen:
                reasons.append(f"validación de '{name}' ya abierta {seen} vez(es) antes")
            fn = get_signal(idea.signal)
            rows = []
            for i, asset in sel["asset"].items():
                best = next(t for t in current[name][asset] if t.label == sel["best"][i])
                params = {k: v for k, v in best.params.items() if k != "idea"}
                px = prices[[asset]].dropna()
                from tsinsurance.backtest import run_backtest

                full = run_backtest(px, fn(px, **params), spec.execution, risk_free=rf)
                after = full.excess_returns.loc[spec.train_end :].iloc[1:]
                assert full.benchmark_excess_returns is not None
                bench = full.benchmark_excess_returns.loc[after.index]
                exp_oos = float(full.weights.abs().sum(axis=1).loc[after.index].mean())
                inf = sharpe_inference(after, full.periods_per_year, reps=spec.reps, seed=spec.seed)
                vs_cash_p = 1 - inf.psr
                timing = sharpe_difference(after, exp_oos * bench, reps=spec.reps, seed=spec.seed)
                rows.append(
                    {
                        "asset": asset,
                        "params": params,
                        "sharpe_oos": inf.sharpe,
                        "ci95": [inf.ci_low, inf.ci_high],
                        "p_vs_cash": vs_cash_p,
                        "buy_hold_sharpe_oos": sharpe_per_period(bench) * np.sqrt(252),
                        "exposure_oos": exp_oos,
                        "timing_sharpe_diff": timing.difference,
                        "timing_p": timing.p_value,
                    }
                )
            result["calibration"][name] = {
                "train_end": spec.train_end,
                "key": vkey,
                "times_opened_before": seen,
                "assets": rows,
            }
            lines.append(
                {
                    **common,
                    "kind": "validation",
                    "key": vkey,
                    "idea": name,
                    "train_end": spec.train_end,
                }
            )
            report += [
                f"## Validación única `{name}` (desde {spec.train_end})",
                "",
                "| Activo | Parámetros | Sharpe fuera de muestra | IC 95 % | p vs efectivo | "
                "Sharpe comprar y mantener | Dif. vs exposición constante (p) |",
                "|---|---|---|---|---|---|---|",
            ]
            for r in rows:
                report.append(
                    f"| {r['asset']} | {r['params']} | {r['sharpe_oos']:+.2f} | "
                    f"[{r['ci95'][0]:+.2f}; {r['ci95'][1]:+.2f}] | {r['p_vs_cash']:.3f} | "
                    f"{r['buy_hold_sharpe_oos']:+.2f} | {r['timing_sharpe_diff']:+.2f} "
                    f"({r['timing_p']:.3f}) |"
                )
            report.append("")

    written = append_trials(spec.registry, lines) + 1 if record else 0
    significant = {
        n: [
            a
            for a, s in zip(
                e["selection"]["asset"].values(),
                e["selection"]["significant"].values(),
                strict=True,
            )
            if s
        ]
        for n, e in result["ideas"].items()
        if "selection" in e
    }
    econ_q = {n: e["verdict"]["quadrant"] for n, e in result["econometric"].items()}
    result["status"] = {
        "exploratory_reasons": reasons,
        "significant_by_idea": significant,
        "econometric_quadrants": econ_q,
        "lines_registered": written,
    }
    conclusion = [
        "## Conclusión automática",
        "",
        f"- Estado: {'EXPLORATORIO — ' + '; '.join(reasons) if reasons else 'confirmatorio'}",
        "- Ideas con timing significativo (DSR > 1−α y SPA-Holm < α): "
        + (", ".join(f"{n}: {a}" for n, a in significant.items() if a) or "ninguna"),
        "- Modelos econométricos: " + (", ".join(f"{n} → {q}" for n, q in econ_q.items()) or "n/d"),
        "- La ganancia CER no tiene inferencia propia; en activos apalancados refleja sobre todo "
        "la penalización de varianza, no habilidad.",
        "",
    ]
    report = report[:9] + conclusion + report[9:]

    out_dir = (Path(output_root) if output_root else spec.path.parent / "results") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    clean = _round(to_jsonable(result))
    (out_dir / "result.json").write_text(
        json.dumps(clean, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    text = "\n".join(report) + "\n"
    (out_dir / "report.md").write_text(text, encoding="utf-8")
    return ExperimentResult(run_id, out_dir, clean, text, written)
