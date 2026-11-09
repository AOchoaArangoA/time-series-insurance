"""Lectura y validación de ``experiment.toml``.

Ejemplo mínimo::

    [experiment]
    id = "mi-experimento"
    hypothesis = "La tendencia reduce caídas en ETFs de renta fija"

    [data]
    bundle = "data"                 # paquete de insumos (relativo a este archivo)
    assets = ["TLT"]

    [[ideas]]
    name = "tendencia"
    signal = "sma_crossover"
    [ideas.grid]
    fast = [20, 50]
    slow = [150, 200]
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from tsinsurance.backtest.config import ExecutionConfig
from tsinsurance.diagnostics.stationarity import ALPHAS
from tsinsurance.errors import TSInsuranceError
from tsinsurance.experiments.signals import get_signal

__all__ = ["EconometricSpec", "ExperimentSpec", "IdeaSpec", "load_experiment"]


@dataclass(frozen=True, slots=True)
class IdeaSpec:
    """Una idea: señal registrada y malla de parámetros."""

    name: str
    signal: str
    grid: dict[str, list[Any]]
    description: str = ""


@dataclass(frozen=True, slots=True)
class EconometricSpec:
    """Modelo econométrico mensual con variables del paquete."""

    name: str
    asset: str
    regressors: list[str]
    derived: dict[str, dict[str, str]] = field(default_factory=dict)
    position: Literal["long_cash", "long_short", "proportional"] = "long_cash"
    min_train: int = 60
    scheme: Literal["expanding", "rolling"] = "expanding"
    window: int | None = None
    ar_lags: int = 0
    n_specifications: int = 1
    rebalance: Literal["every_bar", "W", "M"] = "M"


@dataclass(frozen=True, slots=True)
class ExperimentSpec:
    """Experimento completo."""

    path: Path
    id: str
    title: str
    hypothesis: str
    author: str
    bundle: Path
    assets: list[str]
    start: str | None
    end: str | None
    execution: ExecutionConfig
    alpha: float
    reps: int
    seed: int
    train_end: str | None
    calibrate_ideas: list[str]
    ideas: list[IdeaSpec]
    econometric: list[EconometricSpec]
    registry: Path
    raw: dict[str, Any]


def _require(table: dict[str, Any], key: str, where: str) -> Any:
    if key not in table:
        raise TSInsuranceError(f"experiment.toml: falta '{key}' en [{where}].")
    return table[key]


def load_experiment(
    path: str | os.PathLike[str], *, registry: str | os.PathLike[str] | None = None
) -> ExperimentSpec:
    """Lee y valida un experimento; las rutas son relativas al archivo."""
    p = Path(path).resolve()
    raw = tomllib.loads(p.read_text(encoding="utf-8"))
    exp = _require(raw, "experiment", "raíz")
    data = _require(raw, "data", "raíz")
    base = p.parent
    val = raw.get("validation", {})
    if "calibrate_ideas" in val:
        raise TSInsuranceError(
            "[validation].calibrate_ideas ya no se admite: con train_end todas las ideas se "
            "calibran y validan (elegir cuáles validar es una forma de selección)."
        )
    alpha = float(val.get("alpha", 0.05))
    if alpha not in ALPHAS:
        raise TSInsuranceError(f"[validation].alpha debe ser uno de {ALPHAS}.")
    try:
        execution = ExecutionConfig(**raw.get("execution", {}))
    except TypeError as exc:
        raise TSInsuranceError(f"[execution] tiene claves inválidas: {exc}") from exc
    ideas = []
    for i, block in enumerate(raw.get("ideas", [])):
        name = str(_require(block, "name", f"ideas[{i}]"))
        signal = str(_require(block, "signal", f"ideas[{i}]"))
        get_signal(signal)  # valida que exista
        grid = {
            k: list(v) if isinstance(v, list) else [v] for k, v in block.get("grid", {}).items()
        }
        ideas.append(IdeaSpec(name, signal, grid, str(block.get("description", ""))))
    names = [i.name for i in ideas]
    if len(set(names)) != len(names):
        raise TSInsuranceError("Los nombres de [[ideas]] deben ser únicos.")
    econ = []
    for i, block in enumerate(raw.get("econometric", [])):
        known = {f for f in EconometricSpec.__dataclass_fields__}
        unknown = set(block) - known
        if unknown:
            raise TSInsuranceError(f"econometric[{i}] tiene claves desconocidas: {sorted(unknown)}")
        if block.get("position", "long_cash") not in ("long_cash", "long_short", "proportional"):
            raise TSInsuranceError(f"econometric[{i}].position inválida: {block.get('position')}")
        if block.get("scheme", "expanding") not in ("expanding", "rolling"):
            raise TSInsuranceError(f"econometric[{i}].scheme inválido: {block.get('scheme')}")
        econ.append(EconometricSpec(**block))
    if not ideas and not econ:
        raise TSInsuranceError("El experimento no define [[ideas]] ni [[econometric]].")
    reg = (
        Path(registry)
        if registry is not None
        else base / str(exp.get("registry", "../registry.jsonl"))
    )
    return ExperimentSpec(
        path=p,
        id=str(_require(exp, "id", "experiment")),
        title=str(exp.get("title", "")),
        hypothesis=str(exp.get("hypothesis", "")),
        author=str(exp.get("author", "")),
        bundle=(base / str(_require(data, "bundle", "data"))).resolve(),
        assets=[str(a) for a in _require(data, "assets", "data")],
        start=data.get("start"),
        end=data.get("end"),
        execution=execution,
        alpha=alpha,
        reps=int(val.get("reps", 500)),
        seed=int(val.get("seed", 0)),
        train_end=val.get("train_end"),
        calibrate_ideas=names,
        ideas=ideas,
        econometric=econ,
        registry=reg.resolve(),
        raw=raw,
    )
