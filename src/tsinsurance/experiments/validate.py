"""Validación única fuera de muestra (spec 004, US2).

La calibración (:func:`tsinsurance.experiments.run_experiment` con ``train_end``) fija las
configuraciones en la bitácora sin ver el periodo posterior al corte. Esta función abre ese
periodo **una vez**, sólo si se cumplen las precondiciones (contracts/cli.md):

1. la bitácora es la declarada en el experimento, está íntegra y no está bloqueada;
2. existe el evento ``calibration`` con ese ``run_id``;
3. ``experiment.toml`` no cambió y el paquete truncado en ``train_end`` es idéntico;
4. la versión del paquete ``tsinsurance`` es la misma;
5. no hay cambios sin confirmar en git (incluidos archivos no rastreados en el directorio
   del experimento). Sin repositorio git se permite, pero el resultado es exploratorio.

Antes de evaluar, marca exploratorio todo activo cuyo periodo posterior al corte ya
aparezca en la bitácora (cualquier experimento, cualquier tipo de línea): la identidad del
periodo fuera de muestra es (activo, intervalo posterior al corte), no el nombre del
experimento (FR-009, FR-009a).

La familia de hipótesis declarada en la calibración se ajusta por Holm; el valor p frente
al efectivo usa el EE HAC del Sharpe; la comparación de *timing* usa la exposición media
de la calibración, no la observada fuera de muestra (FR-009b).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from tsinsurance import __version__
from tsinsurance.backtest import (
    PredictiveRegression,
    backtest_econometric,
    run_backtest,
    sharpe_difference,
    sharpe_inference,
)
from tsinsurance.backtest.metrics import sharpe_per_period
from tsinsurance.backtest.sweep import holm
from tsinsurance.data.bundle import Bundle
from tsinsurance.errors import ValidationPreconditionError
from tsinsurance.experiments.registry import (
    append_trials,
    read_registry,
    registry_head,
    registry_lock,
    trial_key,
    verify_registry,
)
from tsinsurance.experiments.runner import (
    ExperimentResult,
    _econ_inputs,
    _git,
    _round,
)
from tsinsurance.experiments.signals import get_signal
from tsinsurance.experiments.spec import EconometricSpec, load_experiment
from tsinsurance.results import to_jsonable

__all__ = ["validate_experiment"]


def _untracked(directory: Path) -> list[str] | None:
    """Archivos no rastreados bajo ``directory`` (``None`` si no es un repositorio git)."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", "."],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    # El bloqueo de la propia bitácora no es un cambio del experimento.
    return [ln[3:] for ln in out.splitlines() if ln.startswith("??") and not ln.endswith(".lock")]


def _seen_after(rows: list[dict[str, Any]], asset: str, cut: str, exclude_run: str) -> list[str]:
    """Ejecuciones previas que ya miraron fechas posteriores a ``cut`` en ``asset``."""
    # Validaciones antiguas sin activo: se infieren de las señales de la misma ejecución.
    assets_by_run_idea: dict[tuple[str, str], set[str]] = {}
    for r in rows:
        if r.get("kind") in ("signal", "econometric") and r.get("asset"):
            assets_by_run_idea.setdefault((str(r.get("run_id")), str(r.get("idea"))), set()).add(
                str(r["asset"])
            )
    seen: list[str] = []
    for r in rows:
        if r.get("run_id") == exclude_run:
            continue
        label = f"{r.get('experiment_id')} ({r.get('run_id')})"
        kind = r.get("kind")
        if kind in ("signal", "econometric") and r.get("asset") == asset:
            end = r.get("eval_end")
            if end is None or str(end)[:10] > cut[:10]:
                seen.append(label)
        elif kind == "validation":
            if r.get("asset") is not None:
                if r["asset"] == asset:
                    seen.append(label)
            elif asset in assets_by_run_idea.get((str(r.get("run_id")), str(r.get("idea"))), set()):
                seen.append(label)
    return sorted(set(seen))


def _fmt(p: float | None) -> str:
    return "n/a" if p is None else f"{p:.3f}"


def _p_hac_positive(sharpe_ann: float, se_ann: float) -> float:
    """Valor p unilateral H0: Sharpe ≤ 0 con EE HAC (normal asintótica)."""
    if not np.isfinite(se_ann) or se_ann <= 0:
        return float("nan")
    return float(1 - stats.norm.cdf(sharpe_ann / se_ann))


def validate_experiment(
    path: str | os.PathLike[str],
    calibration_run_id: str,
    *,
    registry: str | os.PathLike[str] | None = None,
    output_root: str | os.PathLike[str] | None = None,
) -> ExperimentResult:
    """Abre UNA vez la validación fuera de muestra de una calibración registrada.

    Raises
    ------
    ValidationPreconditionError
        Si no se cumple alguna precondición (ver el docstring del módulo).
    """
    spec = load_experiment(path)
    if registry is not None and Path(registry).resolve() != Path(spec.registry).resolve():
        raise ValidationPreconditionError(
            f"La validación sólo se abre con la bitácora declarada ({spec.registry}); "
            "validar contra otra bitácora ocultaría las aperturas previas."
        )
    if not spec.train_end:
        raise ValidationPreconditionError(
            "El experimento no tiene train_end: no hay periodo de validación que abrir."
        )
    started = dt.datetime.now(dt.UTC).replace(microsecond=0)
    exp_sha = hashlib.sha256(spec.path.read_bytes()).hexdigest()
    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "-" + exp_sha[:6] + "-val"
    with registry_lock(spec.registry, run_id):
        return _validate_locked(spec, calibration_run_id, started, exp_sha, run_id, output_root)


def _validate_locked(  # noqa: C901 - flujo lineal de precondiciones y evaluación
    spec: Any,
    calibration_run_id: str,
    started: dt.datetime,
    exp_sha: str,
    run_id: str,
    output_root: str | os.PathLike[str] | None,
) -> ExperimentResult:
    cut = str(spec.train_end)
    results_dir = spec.path.parent / "results"
    problems = verify_registry(spec.registry, results=results_dir)
    if problems:
        raise ValidationPreconditionError("La bitácora no está íntegra: " + "; ".join(problems[:3]))
    rows = read_registry(spec.registry)
    head_before = registry_head(spec.registry)
    cal = next(
        (
            r
            for r in rows
            if r.get("kind") == "calibration" and r.get("run_id") == calibration_run_id
        ),
        None,
    )
    if cal is None:
        raise ValidationPreconditionError(
            f"No hay una calibración registrada con run_id={calibration_run_id} en "
            f"{spec.registry}; ejecute primero `tsinsurance experiment run`."
        )
    if cal.get("experiment_sha256") != exp_sha:
        raise ValidationPreconditionError(
            "experiment.toml cambió desde la calibración: la validación sólo evalúa lo que "
            "se fijó entonces (vuelva a calibrar si quiere probar otra cosa)."
        )
    full = Bundle.load(spec.bundle)
    as_of = full.as_of(cut)
    if as_of.as_of_sha256 != cal.get("bundle_as_of_sha256"):
        raise ValidationPreconditionError(
            "Los datos hasta train_end no son los de la calibración (otra huella del paquete "
            "truncado). Si se volvió a descargar (p. ej. precios ajustados de Yahoo), use la "
            "instantánea original."
        )
    frozen: dict[str, Any] = cal["frozen"]
    if frozen.get("package_version") != __version__:
        raise ValidationPreconditionError(
            f"La calibración se hizo con tsinsurance {frozen.get('package_version')} y ésta es "
            f"{__version__}: valide con la misma versión."
        )
    git = _git(spec.path.parent)
    reasons: list[str] = []
    if git["commit"] is None:
        reasons.append("sin repositorio git: no se puede verificar que no hubo cambios")
    else:
        if git["dirty"]:
            raise ValidationPreconditionError(
                "Hay cambios sin confirmar en git: confirme la calibración (resultados y "
                "bitácora) y el código antes de validar."
            )
        untracked = _untracked(spec.path.parent) or []
        if untracked:
            raise ValidationPreconditionError(
                f"Hay archivos no rastreados en el directorio del experimento: {untracked[:5]}"
            )
    if not full.sealed:
        reasons.append("paquete de insumos sin sellar (sin huella)")

    family_assets = sorted(
        {a for v in frozen["ideas"].values() for a in v["assets"]}
        | {m["spec"]["asset"] for m in frozen["econometric"].values()}
    )
    seen = {a: _seen_after(rows, a, cut, calibration_run_id) for a in family_assets}
    for a, who in seen.items():
        if who:
            reasons.append(
                f"periodo posterior a {cut} de {a} ya visto en: {', '.join(who[:3])}"
                + (f" y {len(who) - 3} más" if len(who) > 3 else "")
            )

    rf = full.risk_free()
    prices = full.assets(family_assets).loc[spec.start : spec.end]
    hyp: list[dict[str, Any]] = []
    ideas_out: dict[str, Any] = {}
    for name, v in frozen["ideas"].items():
        fn = get_signal(v["signal"])
        per = []
        for asset, chosen in v["assets"].items():
            px = prices[[asset]].dropna()
            params = chosen["params"]
            bt = run_backtest(px, fn(px, **params), spec.execution, risk_free=rf)
            after = bt.excess_returns.loc[cut:].iloc[1:]
            assert bt.benchmark_excess_returns is not None
            bench = bt.benchmark_excess_returns.loc[after.index]
            exp_cal = float(chosen["exposure_calibration"])
            inf = sharpe_inference(after, bt.periods_per_year, reps=spec.reps, seed=spec.seed)
            timing = sharpe_difference(after, exp_cal * bench, reps=spec.reps, seed=spec.seed)
            row = {
                "asset": asset,
                "params": params,
                "sharpe_oos": inf.sharpe,
                "ci95": [inf.ci_low, inf.ci_high],
                "se_hac": inf.se_hac,
                "p_vs_cash_hac": _p_hac_positive(inf.sharpe, inf.se_hac),
                "buy_hold_sharpe_oos": sharpe_per_period(bench) * np.sqrt(bt.periods_per_year),
                "exposure_calibration": exp_cal,
                "exposure_oos": float(bt.weights.abs().sum(axis=1).loc[after.index].mean()),
                "timing_sharpe_diff": timing.difference,
                "timing_p": timing.p_value,
                "oos_start": str(after.index[0].date()),
                "oos_end": str(after.index[-1].date()),
                "previously_seen_in": seen[asset],
            }
            per.append(row)
            hyp.append({"id": f"idea:{name}:{asset}", "p": timing.p_value, "row": row})
        ideas_out[name] = {"signal": v["signal"], "assets": per}

    econ_out: dict[str, Any] = {}
    for name, m in frozen["econometric"].items():
        es = EconometricSpec(**m["spec"])
        px_e = full.assets([es.asset])[es.asset].loc[spec.start : spec.end].dropna()
        y, x = _econ_inputs(full, px_e, es, rf)
        model = PredictiveRegression(
            ar_lags=es.ar_lags, scheme=es.scheme, window=es.window, min_train=es.min_train
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
            n_specifications=int(m["n_specifications_counted"]),
            reps=spec.reps,
            seed=spec.seed,
            evaluation_start=cut,
        )
        ev, verdict = res.forecast_evaluation, res.verdict
        stat_p = (
            ev.clark_west.p_value
            if es.position == "proportional" or ev.pesaran_timmermann.p_value is None
            else ev.pesaran_timmermann.p_value
        )
        row = {
            "asset": es.asset,
            "verdict": to_jsonable(verdict),
            "oos_r2": ev.oos_r2,
            "clark_west_p": ev.clark_west.p_value,
            "pesaran_timmermann_p": ev.pesaran_timmermann.p_value,
            "hit_rate": ev.hit_rate,
            "n_forecasts": ev.n_forecasts,
            "sharpe_model": res.economic_test.sharpe_a,
            "sharpe_benchmark_rule": res.economic_test.sharpe_b,
            "economic_p": res.economic_test.p_value,
            "diagnostics_passed": res.validation.diagnostics_passed,
            "previously_seen_in": seen[es.asset],
            "notes": list(res.notes),
        }
        econ_out[name] = row
        hyp.append({"id": f"modelo:{name}", "p": stat_p, "row": row})

    # Holm sobre la familia pre-registrada (FR-009b).
    ps = [h["p"] if h["p"] is not None and np.isfinite(h["p"]) else 1.0 for h in hyp]
    for h, ph in zip(hyp, holm(ps) if ps else [], strict=True):
        h["row"]["p_holm"] = ph
    significant = [h["id"] for h in hyp if h["row"]["p_holm"] < spec.alpha]

    common = {
        "experiment_id": spec.id,
        "run_id": run_id,
        "created_at": started.isoformat(),
        "bundle_sha256": full.sha256,
        "package_version": __version__,
        "git_commit": git["commit"],
        "seed": spec.seed,
        "calibration_run_id": calibration_run_id,
        "frozen_sha256": cal["frozen_sha256"],
        "train_end": cut,
    }
    lines = []
    for name, v in ideas_out.items():
        for r in v["assets"]:
            lines.append(
                {
                    **common,
                    "kind": "validation",
                    "key": trial_key(kind="validation", asset=r["asset"], oos_start=cut),
                    "asset": r["asset"],
                    "idea": name,
                    "oos_start": r["oos_start"],
                    "oos_end": r["oos_end"],
                }
            )
    for name, r in econ_out.items():
        lines.append(
            {
                **common,
                "kind": "validation",
                "key": trial_key(kind="validation", asset=r["asset"], oos_start=cut),
                "asset": r["asset"],
                "model": name,
                "oos_start": cut,
            }
        )
    written = append_trials(spec.registry, lines)

    state = (
        "EXPLORATORIO — " + "; ".join(reasons)
        if reasons
        else "validación única abierta por primera vez sobre un periodo no visto"
    )
    result: dict[str, Any] = {
        "result_version": "1.2",
        "phase": "validation",
        "calibration_run_id": calibration_run_id,
        "experiment": {"id": spec.id, "file": str(spec.path), "sha256": exp_sha},
        "provenance": {
            "run_id": run_id,
            "started_at": started.isoformat(),
            "package_version": __version__,
            "python": platform.python_version(),
            "git": git,
            "bundle": {"sha256": full.sha256, "as_of_sha256": as_of.as_of_sha256},
            "registry": str(spec.registry),
            "seed": spec.seed,
        },
        "assumptions": {
            "execution": spec.execution.describe(),
            "alpha": spec.alpha,
            "train_end": cut,
            "family": [h["id"] for h in hyp],
            "multiple_testing": "Holm sobre la familia pre-registrada",
            "p_vs_cash": "unilateral con EE HAC del Sharpe",
            "timing_benchmark": "exposición media de la calibración × comprar y mantener",
        },
        "validation": {"ideas": ideas_out, "econometric": econ_out},
        "status": {
            "exploratory_reasons": reasons,
            "significant_after_holm": significant,
            "lines_registered": written,
            "out_of_sample": "abierta",
        },
    }
    report = [
        f"# Validación única — experimento {spec.id}",
        "",
        f"- Calibración `{calibration_run_id}` · validación `{run_id}` · periodo posterior a {cut}",
        f"- Estado: {state}",
        f"- Familia de hipótesis ({len(hyp)}), ajuste de Holm: significativas = "
        + (", ".join(significant) or "ninguna"),
        "",
    ]
    for name, v in ideas_out.items():
        report += [
            f"## Idea `{name}`",
            "",
            "| Activo | Parámetros | Sharpe fuera de muestra | IC 95 % | p vs efectivo (HAC) | "
            "Sharpe comprar y mantener | Dif. vs exposición de la calibración (p · Holm) |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in v["assets"]:
            report.append(
                f"| {r['asset']} | {r['params']} | {r['sharpe_oos']:+.2f} | "
                f"[{r['ci95'][0]:+.2f}; {r['ci95'][1]:+.2f}] | {r['p_vs_cash_hac']:.3f} | "
                f"{r['buy_hold_sharpe_oos']:+.2f} | {r['timing_sharpe_diff']:+.2f} "
                f"({r['timing_p']:.3f} · {r['p_holm']:.3f}) |"
            )
        report.append("")
    for name, r in econ_out.items():
        report += [
            f"## Modelo `{name}` ({r['asset']}), sólo pronósticos posteriores a {cut}",
            "",
            f"- Veredicto: {r['verdict']['quadrant']} · pronósticos={r['n_forecasts']} · "
            f"R² fuera de muestra={r['oos_r2']:+.2%} · Clark-West p={r['clark_west_p']:.3f} · "
            f"Pesaran-Timmermann p={_fmt(r['pesaran_timmermann_p'])} · "
            f"p Holm={r['p_holm']:.3f}",
            f"- Sharpe modelo {r['sharpe_model']:+.2f} vs regla con media histórica "
            f"{r['sharpe_benchmark_rule']:+.2f} (p={r['economic_p']:.3f})",
            "",
        ]

    out_dir = (Path(output_root) if output_root else spec.path.parent / "results") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
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
