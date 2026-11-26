"""Ejecución de experimentos declarativos con registro permanente.

Salvaguardas (Principio VIII):

1. **Pre-registro**: antes de ejecutar se agrega a la bitácora el hash de
   ``experiment.toml`` y del paquete de insumos.
2. **Anticipación**: cada combinación de cada idea pasa :func:`check_lookahead`.
3. **Calibración separada (spec 004, US2)**: con ``train_end`` la ejecución recibe el
   paquete truncado en esa fecha (``Bundle.as_of``), selecciona y FIJA la configuración
   en un evento ``calibration``; la validación se abre después, una vez, con
   :func:`tsinsurance.experiments.validate_experiment`.
4. **Pruebas múltiples**: todas las pruebas (señales y modelos econométricos) de todas
   las ejecuciones se cuentan por activo en el DSR (identidad completa: señal,
   parámetros, ejecución, ventana, huella del paquete); la selección se calcula al final
   (independiente del orden de las ideas) y la SPA se ajusta por activos (Holm).
5. **Marcas automáticas**: el resultado es exploratorio si git está sucio, la bitácora no
   es la declarada, no se registra, el paquete no está sellado, hay variables no
   punto-en-el-tiempo, los diagnósticos de algún modelo no se superan o un régimen no
   declara la justificación de sus umbrales (la validación hereda estas razones).
"""

from __future__ import annotations

import contextlib
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
    sharpe_se_hac,
)
from tsinsurance.backtest.econometric import forecast_to_weights
from tsinsurance.backtest.metrics import sharpe_per_period
from tsinsurance.backtest.sweep import Trial, evaluate_grid, select
from tsinsurance.data.bundle import Bundle
from tsinsurance.errors import TSInsuranceError
from tsinsurance.experiments.fingerprint import fingerprint
from tsinsurance.experiments.portfolio_signals import get_portfolio_signal
from tsinsurance.experiments.registry import (
    append_trials,
    prior_information_ratios,
    prior_specifications,
    prior_trials_after,
    read_registry,
    registry_head,
    registry_lock,
    trial_key,
    verify_registry,
)
from tsinsurance.experiments.signals import SignalFn, get_signal
from tsinsurance.experiments.spec import (
    EconometricSpec,
    ExperimentSpec,
    alpha_split,
    load_experiment,
)
from tsinsurance.results import to_jsonable

__all__ = ["ExperimentResult", "run_experiment"]

RESULT_VERSION = "1.2"


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


def _canonical(obj: Any) -> str:
    return json.dumps(to_jsonable(obj), sort_keys=True, ensure_ascii=False, default=str)


def _frozen(
    spec: ExperimentSpec,
    result: Mapping[str, Any],
    current: Mapping[str, Mapping[str, list[Trial]]],
    econ_keys: Mapping[str, str],
    bundle: Bundle,
) -> dict[str, Any]:
    """Lo que la calibración fija para la validación: parámetros, exposición y familia."""
    ideas: dict[str, Any] = {}
    for name, per_asset in current.items():
        idea = next(i for i in spec.ideas if i.name == name)
        sel = result["ideas"][name]["selection"]
        chosen: dict[str, Any] = {}
        for i, asset in sel["asset"].items():
            best = next(t for t in per_asset[asset] if t.label == sel["best"][i])
            chosen[asset] = {
                "params": {k: v for k, v in best.params.items() if k != "idea"},
                "exposure_calibration": best.exposure,
            }
        ideas[name] = {
            "signal": idea.signal,
            "assets": chosen,
            "fingerprint": result["ideas"][name]["fingerprint"]["hash"],
        }
    econ = {
        es.name: {
            "spec": dataclasses.asdict(es),
            "key": econ_keys[es.name],
            "n_specifications_counted": result["econometric"][es.name]["n_specifications_counted"],
        }
        for es in spec.econometric
        if es.name in result["econometric"]
    }
    portfolios = {
        n: {
            "universe": v["universe"],
            "universe_id": v["universe_id"],
            "signal": v["signal"],
            "fingerprint": v["fingerprint"]["hash"],
            "min_history_m": v["min_history_m"],
            "params": v["best_params"],
            "exposure_calibration": v["best_exposure"],
        }
        for n, v in result.get("portfolios", {}).items()
        if v.get("best_params") is not None
    }
    regimes = {
        n: {"spec": v["spec"], "selected": v["selected"]}
        for n, v in result.get("regimes", {}).items()
    }
    family = (
        [f"idea:{n}:{a}" for n, v in ideas.items() for a in v["assets"]]
        + [f"modelo:{n}" for n in econ]
        + [f"cartera:{n}" for n in portfolios]
    )
    regime_family = [h["label"] for v in regimes.values() for h in v["selected"]]
    panels = {
        n: {
            "spec": v["spec"],
            "hypotheses": v["validated"],
            "calibration": v["calibration"],
            "prior_tests_in_holm": v["prior_tests_in_holm"],
        }
        for n, v in result.get("panels", {}).items()
    }
    panel_family = [h["label"] for v in panels.values() for h in v["hypotheses"]]
    return {
        "ideas": ideas,
        "econometric": econ,
        "portfolios": portfolios,
        "regimes": regimes,
        "regime_family": regime_family,
        "panels": panels,
        "panel_family": panel_family,
        "alpha_split": _alpha_split(spec),
        "package_version": __version__,
        "bundle_as_of_sha256": bundle.as_of_sha256,
        "execution": _execution_identity(spec.execution),
        "alpha": spec.alpha,
        "family": family,
    }


def _alpha_split(spec: ExperimentSpec) -> dict[str, float]:
    """Reparto de α entre las familias presentes en el experimento (revisión B1)."""
    return alpha_split(
        spec.alpha,
        strategies=bool(spec.ideas or spec.econometric or spec.portfolios),
        regimes=bool(spec.regimes),
        panels=bool(spec.panels),
    )


def _se_hac(x: pd.Series) -> float | None:
    """EE HAC del IR por periodo para la bitácora (``None`` si no es finito)."""
    try:
        v = sharpe_se_hac(x)
    except TSInsuranceError:
        return None
    return v if np.isfinite(v) else None


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
    exp_sha = hashlib.sha256(spec.path.read_bytes()).hexdigest()
    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "-" + exp_sha[:6]
    # Un solo escritor: el bloqueo cubre TODA la ejecución, desde la lectura de la bitácora
    # (pruebas previas para el DSR) hasta la última escritura (spec 004, revisión I1).
    lock = registry_lock(spec.registry, run_id) if record else contextlib.nullcontext()
    with lock:
        return _run_locked(declared, spec, started, exp_sha, run_id, record, output_root)


def _run_locked(
    declared: ExperimentSpec,
    spec: ExperimentSpec,
    started: dt.datetime,
    exp_sha: str,
    run_id: str,
    record: bool,
    output_root: str | os.PathLike[str] | None,
) -> ExperimentResult:
    full_bundle = Bundle.load(spec.bundle)
    # Calibración: el paquete se trunca en train_end ANTES de cualquier otro uso (US2).
    bundle = full_bundle.as_of(spec.train_end) if spec.train_end else full_bundle
    eval_end = spec.train_end or spec.end
    prices = bundle.assets(spec.assets).loc[spec.start : spec.end]
    rf = bundle.risk_free()
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
    # Pruebas hechas fuera de la bitácora (spec 005, B2): cuentan desde esta ejecución.
    declared_lines = _declared_lines(spec, history)
    history = [*history, *declared_lines]
    head_before = registry_head(spec.registry)
    base_identity = {
        # Con train_end, la huella del paquete TRUNCADO (revisión I6): agregar datos
        # posteriores no cambia la identidad de las pruebas de calibración.
        "bundle": bundle.as_of_sha256 or bundle.sha256,
        "execution": _execution_identity(spec.execution),
        "start": spec.start,
        "end": eval_end,
    }

    # Huella del código de cada señal en la identidad de la prueba (spec 004, US3).
    fingerprints = {i.signal: fingerprint(get_signal(i.signal)) for i in spec.ideas}
    for ps in spec.portfolios:
        fingerprints[f"cartera:{ps.signal}"] = fingerprint(get_portfolio_signal(ps.signal))
    weak = sorted(name for name, fp in fingerprints.items() if fp.coverage in ("partial", "none"))
    if weak:
        reasons.append(f"huella de código incompleta en las señales: {weak}")

    def signal_key(asset: str, signal: str, params: Mapping[str, Any]) -> str:
        return trial_key(
            kind="signal",
            asset=asset,
            signal=signal,
            signal_fingerprint=fingerprints[signal].hash,
            params=dict(params),
            **base_identity,
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
    excluded = [*current_keys, *econ_keys.values()]
    # FR-022a: la varianza del umbral del DSR sólo usa pruebas cuya ventana termina antes
    # del corte; las demás cuentan en N (conservador) pero no en la varianza.
    prior = prior_information_ratios(
        history, exclude_keys=excluded, periods_per_year=252, max_eval_end=spec.train_end
    )
    prior_extra = prior_trials_after(
        history, exclude_keys=excluded, periods_per_year=252, cut=spec.train_end
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
    lines += [{**common, **d} for d in declared_lines]
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

    # Con train_end la ejecución sólo calibra (spec 004, US2); sin él, muestra completa.
    phase = "calibration" if spec.train_end else "full_sample"
    result: dict[str, Any] = {
        "result_version": RESULT_VERSION,
        "phase": phase,
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
        "portfolios": {},
        "regimes": {},
        "panels": {},
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
    quality = bundle.quality_warnings()
    if quality:
        report.append(f"- Calidad de datos: {len(quality)} advertencia(s), ver el anexo")
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
        entry: dict[str, Any] = {
            "signal": idea.signal,
            "grid": idea.grid,
            "lookahead": checks,
            "fingerprint": fingerprints[idea.signal].to_dict(),
        }
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
                # n_obs en las unidades del IR (días), nunca n_forecasts (meses): revisión B6.
                "n_obs": len(econ_trial.active_returns),
                "eval_start": str(econ_trial.active_returns.index[0].date()),
                "eval_end": str(econ_trial.active_returns.index[-1].date()),
                "sharpe_se_hac": _se_hac(econ_trial.active_returns),
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
            prior_extra_trials=prior_extra,
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
                        "n_obs": len(t.active_returns),
                        "eval_start": str(t.active_returns.index[0].date()),
                        "eval_end": str(t.active_returns.index[-1].date()),
                        "sharpe_se_hac": _se_hac(t.active_returns),
                    }
                )
    for idea in spec.ideas:
        if idea.name not in current:
            report += [f"## Idea `{idea.name}`: RECHAZADA por anticipación", ""]

    if spec.portfolios or spec.regimes:
        extra_report, extra_lines, extra_reasons = _portfolios_and_regimes(
            spec, bundle, rf, history, base_identity, result
        )
        report += extra_report
        lines += [{**common, **ln} for ln in extra_lines]
        reasons += extra_reasons
    if spec.panels:
        p_report, p_lines, p_reasons = _panels(spec, bundle, history, base_identity, result)
        report += p_report
        lines += [{**common, **ln} for ln in p_lines]
        reasons += p_reasons

    # Fase de calibración (spec 004, US2): se FIJAN las configuraciones; la validación se
    # abre después, explícitamente, con `tsinsurance experiment validate`.
    if spec.train_end:
        frozen = _frozen(spec, result, current, econ_keys, bundle)
        frozen_sha = hashlib.sha256(_canonical(frozen).encode("utf-8")).hexdigest()
        result["calibration"] = {
            "train_end": spec.train_end,
            "frozen": frozen,
            "frozen_sha256": frozen_sha,
            "validate_with": f"tsinsurance experiment validate {spec.path} --calibration {run_id}",
        }
        lines.append(
            {
                **common,
                "kind": "calibration",
                "experiment_sha256": exp_sha,
                "train_end": spec.train_end,
                "bundle_as_of_sha256": bundle.as_of_sha256,
                "frozen": frozen,
                "frozen_sha256": frozen_sha,
            }
        )
        report += [
            "## Próximo paso: validación única",
            "",
            "Las configuraciones quedaron fijadas en la bitácora. Para evaluarlas UNA vez en el "
            f"periodo posterior a {spec.train_end}, confirme los cambios en git y ejecute:",
            "",
            "```bash",
            f"tsinsurance experiment validate {spec.path} --calibration {run_id}",
            "```",
            "",
        ]

    failed_diag = [n for n, e in result["econometric"].items() if not e["diagnostics_passed"]]
    if failed_diag:
        reasons.append(f"diagnósticos de modelos no superados: {failed_diag}")
    # La validación hereda las razones de exploratorio de la calibración (revisión I1).
    for ln in lines:
        if ln.get("kind") == "calibration":
            ln["exploratory_reasons"] = list(reasons)
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
        "out_of_sample": "pendiente" if spec.train_end else "ninguna",
    }
    pending = "validación fuera de muestra PENDIENTE (aún no hay evidencia confirmatoria)"
    if reasons:
        suffix = f" · {pending}" if spec.train_end else ""
        state = "EXPLORATORIO — " + "; ".join(reasons) + suffix
    elif spec.train_end:
        state = f"calibración terminada; {pending}"
    else:
        state = "muestra completa sin validación fuera de muestra (no confirmatorio)"
    conclusion = [
        "## Conclusión automática",
        "",
        f"- Estado: {state}",
        "- Ideas con timing significativo (DSR > 1−α y SPA-Holm < α): "
        + (", ".join(f"{n}: {a}" for n, a in significant.items() if a) or "ninguna"),
        "- Modelos econométricos: " + (", ".join(f"{n} → {q}" for n, q in econ_q.items()) or "n/d"),
        "- La ganancia CER no tiene inferencia propia; en activos apalancados refleja sobre todo "
        "la penalización de varianza, no habilidad.",
        "",
    ]
    report = report[:9] + conclusion + report[9:]
    if quality:
        report += ["## Anexo: calidad de datos", "", *(f"- {w}" for w in quality), ""]

    out_dir = (Path(output_root) if output_root else spec.path.parent / "results") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    # Ancla contra recortes al final: el resultado publicado delata líneas borradas (US1).
    result["registry_head_before"] = head_before.to_dict()
    result["registry_head"] = registry_head(spec.registry).to_dict()
    result["provenance"]["registry_relpath"] = os.path.relpath(
        Path(spec.registry).resolve(), out_dir.resolve()
    )
    clean = _round(to_jsonable(result))
    (out_dir / "result.json").write_text(
        json.dumps(clean, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    text = "\n".join(report) + "\n"
    (out_dir / "report.md").write_text(text, encoding="utf-8")
    return ExperimentResult(run_id, out_dir, clean, text, written)


def _declared_lines(spec: ExperimentSpec, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Líneas ``declared_prior`` nuevas (idempotentes por clave; spec 005, B2)."""
    known = {r.get("key") for r in history if r.get("kind") == "declared_prior"}
    out = []
    for d in spec.declared_prior_tests:
        body = dataclasses.asdict(d)
        key = trial_key(record="declared_prior", **body)
        if key in known:
            continue
        assets = sorted({*d.assets, *d.universe})
        per_asset = -(-d.n_tests // len(assets)) if assets else 0  # I4: assets ∪ universe
        out.append(
            {
                "kind": "declared_prior",
                "key": key,
                "experiment_id": spec.id,
                "declared_kind": d.kind,
                "n_tests": d.n_tests,
                "n_tests_per_asset": per_asset,
                "universe": sorted(d.universe),
                "assets": assets,
                "period_start": d.period_start,
                "eval_start": d.period_start,
                "eval_end": d.period_end,
                "script_sha256": d.script_sha256,
                "regime_key": d.regime_key,
                "description": d.description,
            }
        )
    return out


def _portfolios_and_regimes(
    spec: ExperimentSpec,
    bundle: Bundle,
    rf: pd.Series | None,
    history: list[dict[str, Any]],
    base_identity: Mapping[str, Any],
    result: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    """Calibración de ideas de cartera y de regímenes (spec 005)."""
    from tsinsurance.experiments.portfolio_eval import evaluate_portfolio
    from tsinsurance.experiments.regimes import analyze_regime, holm_extended
    from tsinsurance.experiments.registry import prior_portfolio_trials, prior_regime_variants

    report: list[str] = []
    lines: list[dict[str, Any]] = []
    reasons: list[str] = []
    cut = spec.train_end
    for ps in spec.portfolios:
        px = bundle.assets(ps.universe).loc[spec.start : spec.end]
        run = evaluate_portfolio(px, ps, spec.execution, rf, seed=spec.seed)
        fp = fingerprint(get_portfolio_signal(ps.signal))
        entry: dict[str, Any] = {
            "fingerprint": fp.to_dict(),
            "universe": sorted(ps.universe),
            "universe_id": run.universe_id,
            "signal": ps.signal,
            "min_history_m": ps.min_history_m,
            "benchmark": "equal_weight (elegibles, mismos costos, rebalanceo M)",
            "rejected_lookahead": run.rejected,
            "window_start": str(run.window_start.date()) if run.window_start is not None else None,
            "configurations": run.configurations,
            "best_params": None,
            "best_exposure": None,
        }
        result["portfolios"][ps.name] = entry
        if not run.trials:
            report += [f"## Cartera `{ps.name}`: RECHAZADA por anticipación", ""]
            continue
        keys = [
            trial_key(
                kind="portfolio",
                signal_fingerprint=fp.hash,
                universe=run.universe_id,
                signal=ps.signal,
                params={k: v for k, v in t.params.items() if k != "idea"},
                min_history_m=ps.min_history_m,
                rebalance="M",
                **base_identity,
            )
            for t in run.trials
        ]
        ratios, extra = prior_portfolio_trials(
            history, ps.universe, exclude_keys=keys, periods_per_year=252, cut=cut
        )
        reg = TrialRegistry()
        for t in run.trials:
            reg.add(t)
        sel = select(
            reg,
            {run.universe_id: run.trials},
            alpha=spec.alpha,
            reps=spec.reps,
            seed=spec.seed,
            prior_information_ratios={run.universe_id: ratios},
            prior_extra_trials={run.universe_id: extra},
        )
        best_label = str(sel.iloc[0]["best"])
        best = next(t for t in run.trials if t.label == best_label)
        entry["selection"] = to_jsonable(sel.reset_index())
        entry["best_params"] = {k: v for k, v in best.params.items() if k != "idea"}
        entry["best_exposure"] = best.exposure
        entry["prior_trials"] = {"in_variance": len(ratios), "count_only": extra}
        for t, key in zip(run.trials, keys, strict=True):
            ar = t.active_returns
            lines.append(
                {
                    "kind": "portfolio",
                    "key": key,
                    "asset": run.universe_id,
                    "universe": sorted(ps.universe),
                    "idea": ps.name,
                    "signal": ps.signal,
                    "params": {k: v for k, v in t.params.items() if k != "idea"},
                    "sharpe_per_period": sharpe_per_period(t.excess_returns),
                    "timing_ir_per_period": sharpe_per_period(ar),
                    "exposure": t.exposure,
                    "periods_per_year": t.periods_per_year,
                    "n_obs": len(ar),
                    "eval_start": str(ar.index[0].date()),
                    "eval_end": str(ar.index[-1].date()),
                    "sharpe_se_hac": _se_hac(ar),
                }
            )
        row = sel.iloc[0]
        report += [
            f"## Cartera `{ps.name}` ({ps.signal} sobre {len(ps.universe)} activos)",
            "",
            f"- Benchmark: igual ponderado de los elegibles (≥ {ps.min_history_m} meses), "
            f"mismos costos, rebalanceo mensual · ventana desde {entry['window_start']}",
            f"- Mejor configuración: {best_label} · Sharpe {row['sharpe']:.2f} · "
            f"IR frente al igual ponderado {row['timing_ir']:+.2f} · "
            f"pruebas N={int(row['n_trials'])} (incluye universos parecidos y pruebas "
            f"declaradas, que pueden repetir configuraciones registradas: conservador) · "
            f"DSR {row['dsr']:.3f} · SPA p {row['spa_p']:.3f} · "
            f"significativa: {'sí' if bool(row['significant']) else 'no'}",
            "",
        ]

    alpha_r = _alpha_split(spec).get("regimes", 0.0)
    all_rows = []
    for rs in spec.regimes:
        if not rs.justification:
            reasons.append(f"régimen '{rs.name}' sin justificación previa de sus umbrales")
        for v in rs.variables:
            if bundle.spec(v).role == "exogenous" and not bundle.spec(v).point_in_time:
                reasons.append(f"régimen '{rs.name}' usa variables no punto-en-el-tiempo")
        rows = analyze_regime(bundle, rs, start=spec.start, end=spec.end)
        all_rows += [(rs, r) for r in rows]
    valid = [(rs, r) for rs, r in all_rows if not r.inconclusive]
    current_variants: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for rs, r in valid:
        current_variants.setdefault((r.asset, rs.memory_key), []).append(
            rs.canonical_variant(r.variant)
        )
    # Las pruebas declaradas SIN clave de régimen cuentan una sola vez por activo (M1).
    extra_m = 0
    unkeyed_counted: set[str] = set()
    for (asset, mk), vs in current_variants.items():
        extra_m += prior_regime_variants(
            history,
            asset,
            mk,
            exclude_variants=vs,
            include_unkeyed_declared=asset not in unkeyed_counted,
        )
        unkeyed_counted.add(asset)
    adjusted = holm_extended([r.p for _, r in valid], extra_m) if valid else []
    holm_by_label = {r.label: p for (_, r), p in zip(valid, adjusted, strict=True)}
    for rs in spec.regimes:
        mine = [r for s2, r in all_rows if s2 is rs]
        selected = [
            {
                "label": r.label,
                "asset": r.asset,
                "variant": r.variant,
                "sign": float(np.sign(r.diff_ann)),
            }
            for r in mine
            if not r.inconclusive and holm_by_label[r.label] < alpha_r
        ]
        result["regimes"][rs.name] = {
            "spec": dataclasses.asdict(rs),
            "memory_key": rs.memory_key,
            "rows": [
                {**dataclasses.asdict(r), "label": r.label, "p_holm": holm_by_label.get(r.label)}
                for r in mine
            ],
            "prior_variants_in_holm": extra_m,
            "alpha_family": alpha_r,
            "selected": selected,
        }
        for r in mine:
            lines.append(
                {
                    "kind": "regime",
                    "key": trial_key(
                        kind="regime",
                        asset=r.asset,
                        key=rs.memory_key,
                        variant=r.variant,
                        **base_identity,
                    ),
                    "asset": r.asset,
                    "regime": rs.name,
                    "regime_key": rs.memory_key,
                    "variant": rs.canonical_variant(r.variant),
                    "variant_declared": r.variant,
                    "months_on": r.months_on,
                    "months_off": r.months_off,
                    "diff_ann": None if r.inconclusive else r.diff_ann,
                    "t_hc3": None if r.inconclusive else r.t,
                    "p": None if r.inconclusive else r.p,
                    "eval_start": r.eval_start,
                    "eval_end": r.eval_end,
                    "n_obs": r.months_on + r.months_off,
                }
            )
        report += [
            f"## Régimen `{rs.name}` ({rs.type}, clave {rs.memory_key})",
            "",
            f"- Justificación: {rs.justification or 'NINGUNA (exploratorio)'} · variantes previas "
            f"en el Holm de la familia: {extra_m} · α de la familia de regímenes = {alpha_r:.3f}",
            "",
            "| Activo | Variante | Meses en / fuera | Exceso anual en / fuera | Dif. | t (HC3) "
            "| p | p Holm |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in mine:
            ph = holm_by_label.get(r.label)
            report.append(
                f"| {r.asset} | {r.variant} | {r.months_on} / {r.months_off} | "
                + (
                    "no concluyente | | | | |"
                    if r.inconclusive
                    else f"{r.ann_on:+.1%} / {r.ann_off:+.1%} | {r.diff_ann:+.1%} | {r.t:+.2f} | "
                    f"{r.p:.3f} | {ph:.3f} |"
                )
            )
        report += ["", f"- Seleccionadas para la validación: {len(selected)}", ""]
    return report, lines, reasons


def _panels(
    spec: ExperimentSpec,
    bundle: Bundle,
    history: list[dict[str, Any]],
    base_identity: Mapping[str, Any],
    result: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    """Calibración de paneles predictivos (spec 006, US3).

    Las hipótesis están pre-registradas con su signo: no se seleccionan; todas las
    concluyentes pasan a la validación única. El Holm de la calibración suma las pruebas
    previas con la misma memoria (variable dependiente, universo con Jaccard ≥ 0,5).
    """
    from tsinsurance.experiments.panels import Y, analyze_panel
    from tsinsurance.experiments.regimes import holm_extended
    from tsinsurance.experiments.registry import prior_panel_tests

    report: list[str] = []
    lines: list[dict[str, Any]] = []
    reasons: list[str] = []
    alpha_p = _alpha_split(spec).get("panels", spec.alpha)
    result.setdefault("panels", {})
    for ps in spec.panels:
        if not ps.justification:
            reasons.append(f"panel '{ps.name}' sin justificación previa de sus hipótesis")
        for v in ps.regressors:
            vs = bundle.spec(v)
            if vs.role == "exogenous" and not vs.point_in_time:
                reasons.append(f"panel '{ps.name}' usa variables no punto-en-el-tiempo ({v})")
        run = analyze_panel(bundle, ps, start=spec.start, end=spec.end, seed=spec.seed)
        if not run.diagnostics_passed:
            reasons.append(f"diagnósticos del panel '{ps.name}' no superados")
        window = {"start": spec.start, "end": spec.end, "train_end": spec.train_end}
        prior = prior_panel_tests(
            history,
            ps.units,
            dependent=Y,
            exclude_variant=ps.variant,
            exclude_universe=sorted(ps.units),
            exclude_window=window,
        )
        valid = [r for r in run.rows if not r.inconclusive]
        adjusted = holm_extended([r.p_one_sided for r in valid], prior) if valid else []
        holm_by = {r.label: p for r, p in zip(valid, adjusted, strict=True)}
        validated = [
            {
                "label": r.label,
                "coef": r.coef,
                "sign": r.sign,
                "estimate_calibration": r.estimate,
                "se_calibration": r.se,
                "n_periods_calibration": r.n_periods,
            }
            for r in valid
        ]
        spec_dict = dataclasses.asdict(ps)
        result["panels"][ps.name] = {
            "spec": spec_dict,
            "universe_id": ps.universe_id,
            "variant": ps.variant,
            "dependent": Y,
            "rows": [
                {**dataclasses.asdict(r), "label": r.label, "p_holm": holm_by.get(r.label)}
                for r in run.rows
            ],
            "params": run.params,
            "std_errors": run.std_errors,
            "diagnostics": run.diagnostics,
            "diagnostics_passed": run.diagnostics_passed,
            "fe_vs_re": run.fe_vs_re,
            "warnings": run.warnings,
            "prior_tests_in_holm": prior,
            "alpha_family": alpha_p,
            "validated": validated,
            "calibration": {
                "bandwidth_rule": "floor(4·(T/100)^(2/9))" if ps.bandwidth is None else None,
                "bandwidth_calibration": run.bandwidth,
                "bootstrap_draws": ps.bootstrap_draws,
                "seed": spec.seed,
            },
        }
        for r in run.rows:
            lines.append(
                {
                    "kind": "panel",
                    "key": trial_key(
                        kind="panel",
                        universe=ps.universe_id,
                        variant=ps.variant,
                        coef=r.coef,
                        **base_identity,
                    ),
                    "asset": ps.universe_id,
                    "universe": sorted(ps.units),
                    "panel": ps.name,
                    "dependent": Y,
                    "variant": ps.variant,
                    "window": window,
                    "coef": r.coef,
                    "sign": r.sign,
                    "estimate": None if r.inconclusive else r.estimate,
                    "t": None if r.inconclusive else r.t,
                    "p": None if r.inconclusive else r.p_one_sided,
                    "eval_start": r.eval_start,
                    "eval_end": r.eval_end,
                    "n_obs": r.n_periods * r.n_entities,
                }
            )
        report += [
            f"## Panel `{ps.name}` ({ps.estimator.upper()}, errores {ps.cov}, "
            f"{len(ps.units)} unidades)",
            "",
            f"- Variable dependiente: exceso de retorno del mes siguiente · justificación: "
            f"{ps.justification or 'NINGUNA (exploratorio)'}",
            f"- Pruebas previas en el Holm (misma memoria): {prior} · α de la familia de "
            f"paneles = {alpha_p:.4f} · diagnósticos "
            f"{'superados' if run.diagnostics_passed else 'NO superados'}",
            "",
            "| Hipótesis | Estimación | ee | t | p unilateral | p WCR (sensibilidad) | G₁ "
            "| p Holm |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in run.rows:
            if r.inconclusive:
                report.append(f"| {r.coef} {r.sign} | no concluyente: {r.reason} | | | | | | |")
                continue
            wcr = f"{r.wcr_p_one_sided:.3f}" if r.wcr_p_one_sided is not None else "n/d"
            report.append(
                f"| {r.coef} {r.sign} | {r.estimate:+.4f} | {r.se:.4f} | {r.t:+.2f} | "
                f"{r.p_one_sided:.3f} ({r.p_distribution}) | {wcr} | "
                f"{r.treated_clusters if r.treated_clusters is not None else '—'} | "
                f"{holm_by[r.label]:.3f} |"
            )
        report.append("")
        if run.fe_vs_re.get("recommendation"):
            report += [f"- FE frente a RE (Mundlak): {run.fe_vs_re['recommendation']}", ""]
        report += [f"- Advertencia: {w}" for w in run.warnings]
        report += [
            "",
            "- Lectura causal: los efectos fijos de unidad quitan confusores constantes en el "
            "tiempo, no los que cambian ni la causalidad inversa (Facure, cap. 14); las "
            "interacciones estiman efectos diferenciales.",
            "",
        ]
    return report, lines, reasons
