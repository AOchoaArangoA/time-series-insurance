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

__all__ = [
    "ALPHA_WEIGHTS",
    "EconometricSpec",
    "ExperimentSpec",
    "IdeaSpec",
    "PanelHypothesis",
    "PanelSpec",
    "alpha_split",
    "load_experiment",
    "panel_spec_from_dict",
]

#: Reparto pre-declarado de α entre familias (spec 006, revisión B1).
ALPHA_WEIGHTS = {"strategies": 0.7, "regimes": 0.15, "panels": 0.15}


def alpha_split(alpha: float, *, strategies: bool, regimes: bool, panels: bool) -> dict[str, float]:
    """α por familia: suma α; las familias ausentes reparten su peso proporcionalmente.

    Por defecto estrategias 0,7α, regímenes 0,15α y paneles 0,15α. Se congela en la
    calibración (``frozen.alpha_split``) y la validación lee el valor congelado.
    """
    present = {"strategies": strategies, "regimes": regimes, "panels": panels}
    total = sum(w for k, w in ALPHA_WEIGHTS.items() if present[k])
    if total == 0:
        return {}
    return {k: alpha * w / total for k, w in ALPHA_WEIGHTS.items() if present[k]}


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
class PortfolioSpec:
    """Idea de cartera: pesos entre los activos de un universo (spec 005)."""

    name: str
    universe: list[str]
    signal: str
    grid: dict[str, list[Any]]
    min_history_m: int
    description: str = ""

    @property
    def universe_id(self) -> str:
        """Identidad del universo: ids ordenados (el orden declarado no la cambia)."""
        return "U:" + "+".join(sorted(self.universe))


RegimeType = Literal["threshold", "spread", "trend"]


@dataclass(frozen=True, slots=True)
class RegimeSpec:
    """Estado del ciclo observable al cierre de mes; cada valor de la malla es una variante."""

    name: str
    type: RegimeType
    variables: list[str]
    op: Literal[">", "<"]
    values: list[float]
    asset: str | None
    months: list[int]
    assets: list[str]
    min_months: int
    justification: str

    @property
    def memory_key(self) -> str:
        """Clave de memoria entre experimentos: tipo y variables (o activo de referencia).

        En ``spread`` las variables se ordenan: ``a − b < v`` y ``b − a > −v`` son la misma
        hipótesis y comparten memoria (revisión M7).
        """
        if self.type == "trend":
            ref = str(self.asset)
        elif self.type == "spread":
            ref = "-".join(sorted(self.variables))
        else:
            ref = "-".join(self.variables)
        return f"{self.type}:{ref}"

    def canonical_variant(self, variant: dict[str, Any]) -> dict[str, Any]:
        """Variante en la orientación canónica de la clave de memoria."""
        if self.type != "spread" or self.variables == sorted(self.variables):
            return dict(variant)
        flipped = "<" if variant["op"] == ">" else ">"
        return {"op": flipped, "value": -float(variant["value"])}

    def variants(self) -> list[dict[str, Any]]:
        """Cada umbral (o número de meses) declarado es una hipótesis distinta."""
        if self.type == "trend":
            return [{"months": m} for m in self.months]
        return [{"op": self.op, "value": v} for v in self.values]


@dataclass(frozen=True, slots=True)
class PanelHypothesis:
    """Hipótesis pre-registrada: un coeficiente y su signo esperado."""

    coef: str
    sign: Literal["+", "-"]


@dataclass(frozen=True, slots=True)
class PanelSpec:
    """Panel predictivo unidades × meses (spec 006, US3).

    La variable dependiente es el exceso de retorno del mes siguiente a la decisión; los
    regresores son series del paquete alineadas punto en el tiempo al cierre de mes.
    ``interactions`` son pares (regresor, característica): ``x_t × D_i`` estima el efecto
    **diferencial** de las unidades con la característica.
    """

    name: str
    units: list[str]
    regressors: list[str]
    transforms: dict[str, str]
    characteristics: dict[str, list[str]]
    interactions: list[tuple[str, str]]
    estimator: Literal["pooled", "fe", "twfe", "fd", "re"]
    cov: Literal[
        "unadjusted",
        "robust",
        "clustered_entity",
        "clustered_time",
        "clustered_twoway",
        "driscoll_kraay",
    ]
    bandwidth: int | None
    hypotheses: list[PanelHypothesis]
    bootstrap_draws: int
    min_months: int
    justification: str

    @property
    def universe_id(self) -> str:
        """Identidad del universo (ids ordenados)."""
        return "P:" + "+".join(sorted(self.units))

    @property
    def columns(self) -> list[str]:
        """Regresores del modelo: los declarados y las interacciones ``x:carac``."""
        return [*self.regressors, *(f"{x}:{c}" for x, c in self.interactions)]

    @property
    def variant(self) -> dict[str, Any]:
        """Variante (revisión I3): cambiar cualquiera de estos campos es otra especificación."""
        return {
            "regressors": sorted(self.regressors),
            "transforms": dict(sorted(self.transforms.items())),
            "interactions": sorted(
                [x, c, sorted(self.characteristics[c])] for x, c in self.interactions
            ),
            "estimator": self.estimator,
            "cov": self.cov,
            "bandwidth": self.bandwidth,
            "hypotheses": sorted([h.coef, h.sign] for h in self.hypotheses),
        }


@dataclass(frozen=True, slots=True)
class DeclaredPriorSpec:
    """Pruebas hechas fuera de la bitácora que deben contarse (spec 005, B2)."""

    kind: Literal["portfolio", "regime", "signal", "panel"]
    n_tests: int
    period_start: str
    period_end: str
    universe: list[str]
    assets: list[str]
    script_sha256: str
    description: str
    regime_key: str = ""


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
    portfolios: list[PortfolioSpec] = field(default_factory=list)
    regimes: list[RegimeSpec] = field(default_factory=list)
    declared_prior_tests: list[DeclaredPriorSpec] = field(default_factory=list)
    panels: list[PanelSpec] = field(default_factory=list)


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
    portfolios = _portfolios(raw)
    regimes = _regimes(raw, [str(a) for a in data.get("assets", [])])
    declared = _declared(raw)
    panels = _panels(raw)
    if not ideas and not econ and not portfolios and not regimes and not panels:
        raise TSInsuranceError(
            "El experimento no define [[ideas]], [[econometric]], [[portfolios]], [[regimes]] "
            "ni [[panels]]."
        )
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
        portfolios=portfolios,
        regimes=regimes,
        declared_prior_tests=declared,
        panels=panels,
    )


def _grid(block: dict[str, Any]) -> dict[str, list[Any]]:
    return {k: list(v) if isinstance(v, list) else [v] for k, v in block.get("grid", {}).items()}


def _portfolios(raw: dict[str, Any]) -> list[PortfolioSpec]:
    from tsinsurance.experiments.portfolio_signals import get_portfolio_signal

    out = []
    for i, block in enumerate(raw.get("portfolios", [])):
        where = f"portfolios[{i}]"
        universe = [str(a) for a in _require(block, "universe", where)]
        if len(set(universe)) < 2:
            raise TSInsuranceError(
                f"{where}: el universo necesita al menos 2 activos (para un activo use [[ideas]])."
            )
        signal = str(_require(block, "signal", where))
        get_portfolio_signal(signal)
        grid = _grid(block)
        default_hist = max(
            [
                int(lb) + int(sk)
                for lb in grid.get("lookback_m", [12])
                for sk in grid.get("skip_m", [1])
            ]
        )
        out.append(
            PortfolioSpec(
                name=str(_require(block, "name", where)),
                universe=universe,
                signal=signal,
                grid=grid,
                min_history_m=int(block.get("min_history_m", default_hist)),
                description=str(block.get("description", "")),
            )
        )
    if len({p.name for p in out}) != len(out):
        raise TSInsuranceError("Los nombres de [[portfolios]] deben ser únicos.")
    return out


def _as_list(v: Any) -> list[Any]:
    return list(v) if isinstance(v, list) else [v]


def _regimes(raw: dict[str, Any], default_assets: list[str]) -> list[RegimeSpec]:
    out = []
    for i, block in enumerate(raw.get("regimes", [])):
        where = f"regimes[{i}]"
        kind = str(_require(block, "type", where))
        if kind not in ("threshold", "spread", "trend"):
            raise TSInsuranceError(f"{where}.type debe ser threshold, spread o trend.")
        op = str(block.get("op", ">"))
        if op not in (">", "<"):
            raise TSInsuranceError(f"{where}.op debe ser '>' o '<'.")
        if kind == "threshold":
            variables = [str(_require(block, "variable", where))]
        elif kind == "spread":
            variables = [str(v) for v in _require(block, "variables", where)]
            if len(variables) != 2:
                raise TSInsuranceError(f"{where}.variables debe tener 2 series (a − b).")
        else:
            variables = []
        values = [float(v) for v in _as_list(block.get("value", []))]
        months = [int(m) for m in _as_list(block.get("months", []))]
        if kind != "trend" and not values:
            raise TSInsuranceError(f"{where}: falta 'value' (umbral o lista de umbrales).")
        if kind == "trend" and (not months or min(months) < 2):
            raise TSInsuranceError(f"{where}: 'months' (≥ 2) es obligatorio en type='trend'.")
        min_months = int(block.get("min_months", 24))
        if min_months < 6:
            raise TSInsuranceError(f"{where}.min_months debe ser ≥ 6.")
        out.append(
            RegimeSpec(
                name=str(_require(block, "name", where)),
                type=kind,  # type: ignore[arg-type]
                variables=variables,
                op=op,  # type: ignore[arg-type]
                values=values,
                asset=str(_require(block, "asset", where)) if kind == "trend" else None,
                months=months,
                assets=[str(a) for a in block.get("assets", default_assets)],
                min_months=min_months,
                justification=str(block.get("justification", "")).strip(),
            )
        )
    if len({r.name for r in out}) != len(out):
        raise TSInsuranceError("Los nombres de [[regimes]] deben ser únicos.")
    return out


PANEL_KEYS = {
    "name",
    "units",
    "regressors",
    "transforms",
    "characteristics",
    "interactions",
    "estimator",
    "cov",
    "bandwidth",
    "hypotheses",
    "bootstrap_draws",
    "min_months",
    "justification",
}


def _panels(raw: dict[str, Any]) -> list[PanelSpec]:
    out = []
    for i, block in enumerate(raw.get("panels", [])):
        where = f"panels[{i}]"
        unknown = set(block) - PANEL_KEYS
        if unknown:
            raise TSInsuranceError(f"{where} tiene claves desconocidas: {sorted(unknown)}")
        units = [str(u) for u in _require(block, "units", where)]
        if len(set(units)) < 3:
            raise TSInsuranceError(f"{where}.units necesita al menos 3 unidades distintas.")
        regressors = [str(r) for r in block.get("regressors", [])]
        transforms = {str(k): str(v) for k, v in block.get("transforms", {}).items()}
        for k, v in transforms.items():
            if k not in regressors:
                raise TSInsuranceError(f"{where}.transforms: '{k}' no es un regresor.")
            if v not in ("level", "diff"):
                raise TSInsuranceError(f"{where}.transforms['{k}'] debe ser 'level' o 'diff'.")
        chars = {str(k): [str(u) for u in v] for k, v in block.get("characteristics", {}).items()}
        for c, members in chars.items():
            if set(members) - set(units):
                raise TSInsuranceError(f"{where}.characteristics['{c}'] usa unidades ajenas.")
        inter: list[tuple[str, str]] = []
        for pair in block.get("interactions", []):
            if len(pair) != 2 or pair[0] not in regressors or pair[1] not in chars:
                raise TSInsuranceError(
                    f"{where}.interactions: cada par es [regresor, característica] declarados."
                )
            inter.append((str(pair[0]), str(pair[1])))
        if not regressors:
            raise TSInsuranceError(f"{where}: declare al menos un regresor.")
        estimator = str(block.get("estimator", "fe"))
        if estimator not in ("pooled", "fe", "twfe", "fd", "re"):
            raise TSInsuranceError(f"{where}.estimator debe ser pooled, fe, twfe, fd o re.")
        cov = str(block.get("cov", "driscoll_kraay"))
        if cov not in (
            "unadjusted",
            "robust",
            "clustered_entity",
            "clustered_time",
            "clustered_twoway",
            "driscoll_kraay",
        ):
            raise TSInsuranceError(f"{where}.cov inválido: {cov}")
        columns = [*regressors, *(f"{x}:{c}" for x, c in inter)]
        hyps = []
        for h in _require(block, "hypotheses", where):
            coef, sign = str(h.get("coef", "")), str(h.get("sign", ""))
            if coef not in columns:
                raise TSInsuranceError(f"{where}.hypotheses: '{coef}' no está en {columns}.")
            if sign not in ("+", "-"):
                raise TSInsuranceError(f"{where}.hypotheses: el signo de '{coef}' es '+' o '-'.")
            hyps.append(PanelHypothesis(coef, sign))  # type: ignore[arg-type]
        if not hyps:
            raise TSInsuranceError(f"{where}: pre-registre al menos una hipótesis.")
        draws = int(block.get("bootstrap_draws", 9999))
        if draws < 999:
            raise TSInsuranceError(f"{where}.bootstrap_draws debe ser ≥ 999.")
        min_months = int(block.get("min_months", 36))
        if min_months < 12:
            raise TSInsuranceError(f"{where}.min_months debe ser ≥ 12.")
        bw = block.get("bandwidth")
        out.append(
            PanelSpec(
                name=str(_require(block, "name", where)),
                units=units,
                regressors=regressors,
                transforms=transforms,
                characteristics=chars,
                interactions=inter,
                estimator=estimator,  # type: ignore[arg-type]
                cov=cov,  # type: ignore[arg-type]
                bandwidth=None if bw is None else int(bw),
                hypotheses=hyps,
                bootstrap_draws=draws,
                min_months=min_months,
                justification=str(block.get("justification", "")).strip(),
            )
        )
    if len({p.name for p in out}) != len(out):
        raise TSInsuranceError("Los nombres de [[panels]] deben ser únicos.")
    return out


def _declared(raw: dict[str, Any]) -> list[DeclaredPriorSpec]:
    out = []
    for i, block in enumerate(raw.get("declared_prior_tests", [])):
        where = f"declared_prior_tests[{i}]"
        kind = str(_require(block, "kind", where))
        if kind not in ("portfolio", "regime", "signal", "panel"):
            raise TSInsuranceError(f"{where}.kind debe ser portfolio, regime, signal o panel.")
        if not block.get("assets") and not block.get("universe"):
            raise TSInsuranceError(f"{where}: declare 'assets' o 'universe' (a qué se probó).")
        n = int(_require(block, "n_tests", where))
        if n < 1:
            raise TSInsuranceError(f"{where}.n_tests debe ser ≥ 1.")
        out.append(
            DeclaredPriorSpec(
                kind=kind,  # type: ignore[arg-type]
                n_tests=n,
                period_start=str(_require(block, "period_start", where)),
                period_end=str(_require(block, "period_end", where)),
                universe=[str(a) for a in block.get("universe", [])],
                assets=[str(a) for a in block.get("assets", [])],
                script_sha256=str(_require(block, "script_sha256", where)),
                description=str(block.get("description", "")),
                regime_key=str(block.get("regime_key", "")),
            )
        )
    return out


def panel_spec_from_dict(d: dict[str, Any]) -> PanelSpec:
    """Reconstruye un :class:`PanelSpec` congelado (``dataclasses.asdict`` → JSON)."""
    body = dict(d)
    body["interactions"] = [(str(x), str(c)) for x, c in body.get("interactions", [])]
    body["hypotheses"] = [
        PanelHypothesis(str(h["coef"]), h["sign"]) for h in body.get("hypotheses", [])
    ]
    return PanelSpec(**body)
