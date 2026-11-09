"""Paquete de insumos: formato base independiente de la fuente.

Un paquete es un directorio con:

- ``bundle.toml``: manifiesto versionado. Describe cada serie (rol, unidades, moneda,
  frecuencia, rezago de publicación, transformación, procedencia y licencia).
- ``market_series.csv``: los datos en el contrato ``market`` v1.0 (formato largo).

Las fuentes (Yahoo, FRED, archivos internos, proveedores comerciales) son **adaptadores**
que producen paquetes; el resto del sistema sólo lee paquetes. Una *receta*
(``recipe.toml``) describe cómo descargar un paquete y es lo único que depende de la
fuente.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import os
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pandas.tseries.frequencies import to_offset

from tsinsurance import __version__
from tsinsurance.data.schemas import SCHEMA_VERSION
from tsinsurance.data.snapshot import Snapshot, content_hash
from tsinsurance.data.validate import load, read_table, to_wide
from tsinsurance.errors import DataValidationError, TSInsuranceError

__all__ = [
    "BUNDLE_VERSION",
    "Bundle",
    "BundleIssue",
    "SeriesSpec",
    "fetch_recipe",
    "seal_bundle",
    "seal_hash",
    "validate_bundle",
    "write_bundle_template",
]

BUNDLE_VERSION = "1.0"
MANIFEST = "bundle.toml"
DATA = "market_series.csv"

Role = Literal["asset", "exogenous", "risk_free"]
RiskFreeConvention = Literal["dtb3_discount", "annual_percent", "period_decimal"]
ROLES = ("asset", "exogenous", "risk_free")
TRANSFORMS = ("level", "diff", "pct_change", "yoy")
RF_CONVENTIONS = ("dtb3_discount", "annual_percent", "period_decimal")


@dataclass(frozen=True, slots=True)
class SeriesSpec:
    """Declaración de una serie en el manifiesto.

    Los campos ``kind``, ``unit``, ``currency`` y ``frequency`` deben coincidir con los
    datos; ``release_lag``, ``transform`` y ``point_in_time`` aplican a exógenas;
    ``rf_convention`` a la tasa libre de riesgo.
    """

    id: str
    role: Role
    description: str = ""
    release_lag: str = "0D"
    transform: str = "level"
    point_in_time: bool = True
    rf_convention: str = ""
    source: str = ""
    query: str = ""
    retrieved_at: str = ""
    license: str = ""
    redistributable: bool = False


@dataclass(frozen=True, slots=True)
class BundleIssue:
    """Inconsistencia de un paquete."""

    series: str
    field: str
    message: str


def seal_hash(data: pd.DataFrame, series: Sequence[Mapping[str, Any]]) -> str:
    """Huella del paquete: datos canónicos **y** declaraciones del manifiesto.

    Cambiar un rezago de publicación, una transformación o ``point_in_time`` cambia la
    huella, igual que cambiar un dato.
    """
    decl = sorted(
        ({k: v for k, v in dict(s).items()} for s in series), key=lambda d: str(d.get("id"))
    )
    payload = content_hash(data) + json.dumps(decl, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _issues(manifest: Mapping[str, Any], data: pd.DataFrame | None) -> list[BundleIssue]:
    out: list[BundleIssue] = []
    head = manifest.get("bundle", {})
    if str(head.get("version", "")) != BUNDLE_VERSION:
        out.append(BundleIssue("*", "bundle.version", f"se esperaba '{BUNDLE_VERSION}'"))
    if str(head.get("schema_version", "")) != SCHEMA_VERSION:
        out.append(BundleIssue("*", "bundle.schema_version", f"se esperaba '{SCHEMA_VERSION}'"))
    specs = manifest.get("series", [])
    names = [str(s.get("id", "")) for s in specs]
    for s in specs:
        sid = str(s.get("id", "")) or "?"
        role = s.get("role")
        if role not in ROLES:
            out.append(BundleIssue(sid, "role", f"debe ser uno de {ROLES}"))
        if s.get("transform", "level") not in TRANSFORMS:
            out.append(BundleIssue(sid, "transform", f"debe ser uno de {TRANSFORMS}"))
        try:
            to_offset(str(s.get("release_lag", "0D")))
        except ValueError:
            out.append(BundleIssue(sid, "release_lag", "no es un rezago válido (p. ej. '1B')"))
        if role == "risk_free" and s.get("rf_convention") not in RF_CONVENTIONS:
            out.append(BundleIssue(sid, "rf_convention", f"debe ser uno de {RF_CONVENTIONS}"))
        if not s.get("license"):
            out.append(BundleIssue(sid, "license", "falta la licencia o condiciones de uso"))
        if role in ("exogenous", "risk_free") and "release_lag" not in s:
            out.append(
                BundleIssue(sid, "release_lag", "obligatorio: declare el rezago de publicación")
            )
        if role == "exogenous" and "point_in_time" not in s:
            out.append(BundleIssue(sid, "point_in_time", "obligatorio: ¿la serie se revisa?"))
    dup = {n for n in names if names.count(n) > 1}
    out.extend(BundleIssue(n, "id", "serie declarada más de una vez") for n in sorted(dup))
    if sum(1 for s in specs if s.get("role") == "risk_free") > 1:
        out.append(BundleIssue("*", "role", "a lo sumo una serie risk_free"))
    if data is not None:
        in_data = set(data["series_id"].astype(str))
        for sid in sorted(in_data - set(names)):
            out.append(BundleIssue(sid, "id", "está en los datos pero no en el manifiesto"))
        for sid in sorted(set(names) - in_data):
            out.append(BundleIssue(sid, "id", "está en el manifiesto pero no en los datos"))
        expected = head.get("sha256")
        if expected and seal_hash(data, specs) != expected:
            out.append(
                BundleIssue(
                    "*", "bundle.sha256", "datos o declaraciones no coinciden con la huella"
                )
            )
    return out


@dataclass(frozen=True, slots=True, eq=False)
class Bundle:
    """Paquete de insumos validado."""

    name: str
    description: str
    series: tuple[SeriesSpec, ...]
    data: pd.DataFrame
    created_at: str = ""
    sha256: str = ""
    notes: tuple[str, ...] = field(default=())

    # --- Construcción ---------------------------------------------------------------

    @classmethod
    def from_snapshots(
        cls,
        name: str,
        parts: Sequence[tuple[Snapshot, Sequence[Mapping[str, Any]]]],
        *,
        description: str = "",
    ) -> Bundle:
        """Combina instantáneas de cualquier fuente con sus declaraciones de series."""
        frames, specs = [], []
        for snap, declared in parts:
            frames.append(snap.data)
            for d in declared:
                missing = [
                    k
                    for k in (
                        ("release_lag", "point_in_time")
                        if d.get("role") == "exogenous"
                        else ("release_lag",)
                        if d.get("role") == "risk_free"
                        else ()
                    )
                    if k not in d
                ]
                if missing:
                    raise DataValidationError(
                        f"Serie '{d.get('id')}': declare explícitamente {missing} "
                        "(punto en el tiempo)."
                    )
                specs.append(
                    SeriesSpec(
                        **{
                            "source": snap.source,
                            "query": str(dict(snap.query)),
                            "retrieved_at": snap.retrieved_at,
                            **d,
                        }
                    )
                )
        data = load(pd.concat(frames, ignore_index=True), "market")
        data = data.sort_values(["series_id", "date"]).reset_index(drop=True)
        bundle = cls(
            name=name,
            description=description,
            series=tuple(specs),
            data=data,
            created_at=dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        )
        bundle = dataclasses.replace(bundle, sha256=seal_hash(data, bundle.manifest()["series"]))
        problems = _issues(bundle.manifest(), data)
        if problems:
            raise DataValidationError(_format(problems))
        return bundle

    @classmethod
    def load(cls, directory: str | os.PathLike[str]) -> Bundle:
        """Lee y valida un paquete (contrato de datos, manifiesto y huella)."""
        src = Path(directory)
        report = validate_bundle(src)
        if report:
            raise DataValidationError(_format(report))
        manifest = tomllib.loads((src / MANIFEST).read_text(encoding="utf-8"))
        data = load(read_table(src / DATA), "market")
        data = data.sort_values(["series_id", "date"]).reset_index(drop=True)
        head = manifest["bundle"]
        allowed = {f.name for f in fields(SeriesSpec)}
        specs = tuple(
            SeriesSpec(**{k: v for k, v in s.items() if k in allowed}) for s in manifest["series"]
        )
        return cls(
            name=str(head.get("name", src.name)),
            description=str(head.get("description", "")),
            series=specs,
            data=data,
            created_at=str(head.get("created_at", "")),
            sha256=str(head.get("sha256", "")),
        )

    # --- Persistencia ---------------------------------------------------------------

    def manifest(self) -> dict[str, Any]:
        """Manifiesto como diccionario."""
        return {
            "bundle": {
                "version": BUNDLE_VERSION,
                "schema_version": SCHEMA_VERSION,
                "name": self.name,
                "description": self.description,
                "created_at": self.created_at,
                "created_with": f"tsinsurance {__version__}",
                "sha256": self.sha256,
            },
            "series": [
                {f.name: getattr(s, f.name) for f in fields(SeriesSpec)} for s in self.series
            ],
        }

    def save(self, directory: str | os.PathLike[str]) -> Path:
        """Escribe ``bundle.toml`` y ``market_series.csv``."""
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        frame = self.data.copy()
        frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
        frame.to_csv(out / DATA, index=False, float_format="%.17g", lineterminator="\n")
        (out / MANIFEST).write_text(_to_toml(self.manifest()), encoding="utf-8")
        return out

    # --- Acceso para el análisis ------------------------------------------------------

    def ids(self, role: Role) -> list[str]:
        """Identificadores de las series con un rol."""
        return [s.id for s in self.series if s.role == role]

    def spec(self, series_id: str) -> SeriesSpec:
        """Declaración de una serie."""
        for s in self.series:
            if s.id == series_id:
                return s
        raise TSInsuranceError(f"La serie '{series_id}' no está en el paquete '{self.name}'.")

    def _wide(self, ids: Sequence[str]) -> pd.DataFrame:
        sub = self.data[self.data["series_id"].isin(list(ids))]
        if sub.empty:
            return pd.DataFrame()
        frames = [to_wide(g) for _, g in sub.groupby("frequency")]
        return pd.concat(frames, axis=1)

    def assets(self, ids: Sequence[str] | None = None) -> pd.DataFrame:
        """Precios de los activos (formato ancho, ``NaN`` antes del inicio de cada uno)."""
        wanted = list(ids) if ids is not None else self.ids("asset")
        bad = [i for i in wanted if self.spec(i).role != "asset"]
        if bad:
            raise TSInsuranceError(f"No son activos: {bad}")
        return self._wide(wanted)[wanted]

    def exogenous(self, ids: Sequence[str] | None = None) -> list[Any]:
        """Variables explicativas como :class:`tsinsurance.backtest.Exogenous`."""
        from tsinsurance.backtest.pit import Exogenous

        wanted = list(ids) if ids is not None else self.ids("exogenous")
        out = []
        for sid in wanted:
            spec = self.spec(sid)
            if spec.role != "exogenous":
                raise TSInsuranceError(f"'{sid}' no es exógena.")
            rows = self.data[self.data["series_id"] == sid]
            series = pd.Series(rows["value"].to_numpy(), index=pd.DatetimeIndex(rows["date"]))
            out.append(
                Exogenous(
                    sid,
                    series.dropna(),
                    str(rows["frequency"].iloc[0]),  # type: ignore[arg-type]
                    release_lag=spec.release_lag,
                    transform=spec.transform,  # type: ignore[arg-type]
                    point_in_time=spec.point_in_time,
                )
            )
        return out

    def risk_free(self) -> pd.Series | None:
        """Tasa libre de riesgo por día hábil, indexada por fecha de disponibilidad."""
        from tsinsurance.backtest.pit import dtb3_to_daily

        ids = self.ids("risk_free")
        if not ids:
            return None
        spec = self.spec(ids[0])
        rows = self.data[self.data["series_id"] == spec.id]
        s = pd.Series(rows["value"].to_numpy(), index=pd.DatetimeIndex(rows["date"])).dropna()
        lag = to_offset(spec.release_lag)
        if spec.rf_convention == "dtb3_discount":
            return dtb3_to_daily(s, lag=spec.release_lag)
        annual = spec.rf_convention == "annual_percent"
        daily = (1 + s / 100.0) ** (1 / 252) - 1 if annual else s
        daily.index = pd.DatetimeIndex(daily.index) + lag
        return daily.rename("rf_daily")

    @property
    def sealed(self) -> bool:
        """``True`` si el paquete tiene huella (verificada al cargar)."""
        return bool(self.sha256)

    def quality_warnings(self, threshold: float = 8.0) -> list[str]:
        """Posibles datos erróneos en precios: picos seguidos de reversión.

        Marca días con |r| > ``threshold`` desviaciones robustas (MAD) cuyo retorno
        siguiente revierte más de la mitad. No modifica los datos.
        """
        out = []
        for sid in self.ids("asset"):
            rows = self.data[self.data["series_id"] == sid]
            px = pd.Series(rows["value"].to_numpy(), index=pd.DatetimeIndex(rows["date"])).dropna()
            r = px.pct_change().dropna()
            if len(r) < 30:
                continue
            mad = float((r - r.median()).abs().median()) * 1.4826
            if mad == 0:
                continue
            nxt = r.shift(-1)
            flag = (r.abs() > threshold * mad) & (nxt * r < 0) & (nxt.abs() > 0.5 * r.abs())
            for d in r.index[flag.to_numpy()]:
                out.append(
                    f"{sid} {d.date()}: retorno {r[d]:+.2%} y {nxt[d]:+.2%} al día siguiente "
                    f"(> {threshold:g} desviaciones robustas): posible dato erróneo"
                )
        return out

    @property
    def redistributable(self) -> bool:
        """``True`` si todas las series permiten redistribución."""
        return all(s.redistributable for s in self.series)

    def summary(self) -> str:
        """Resumen legible."""
        lines = [
            f"Paquete '{self.name}' v{BUNDLE_VERSION} (contrato v{SCHEMA_VERSION}), "
            f"{len(self.data)} filas, sha256={self.sha256[:12]}…",
            f"Redistribuible: {'sí' if self.redistributable else 'no'}",
        ]
        for s in self.series:
            rows = self.data[self.data["series_id"] == s.id]
            lines.append(
                f"  [{s.role:<9}] {s.id:<10} {rows['date'].min().date()} a "
                f"{rows['date'].max().date()} freq={rows['frequency'].iloc[0]} "
                f"rezago={s.release_lag} fuente={s.source or 'manual'} licencia={s.license}"
            )
        return "\n".join(lines)


def validate_bundle(directory: str | os.PathLike[str]) -> list[BundleIssue]:
    """Valida un paquete y devuelve todas las inconsistencias (lista vacía = válido)."""
    src = Path(directory)
    issues: list[BundleIssue] = []
    if not (src / MANIFEST).exists():
        return [BundleIssue("*", MANIFEST, "no existe")]
    if not (src / DATA).exists():
        return [BundleIssue("*", DATA, "no existe")]
    try:
        manifest = tomllib.loads((src / MANIFEST).read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [BundleIssue("*", MANIFEST, f"TOML inválido: {exc}")]
    from tsinsurance.data.validate import validate

    raw = read_table(src / DATA)
    report = validate(raw, "market")
    if not report.is_valid:
        for rec in report.errors.to_dict("records"):
            issues.append(
                BundleIssue(
                    str(rec["row"]), str(rec["column"]), f"{rec['check']}: {rec['failure_case']}"
                )
            )
        return issues
    data = load(raw, "market").sort_values(["series_id", "date"]).reset_index(drop=True)
    return _issues(manifest, data)


def _format(issues: Sequence[BundleIssue]) -> str:
    lines = [f"Paquete inválido: {len(issues)} problema(s)"]
    lines += [f"  serie={i.series} campo={i.field}: {i.message}" for i in issues]
    return "\n".join(lines)


def write_bundle_template(directory: str | os.PathLike[str], name: str = "mi_paquete") -> Path:
    """Escribe un paquete de ejemplo (2 activos, 1 exógena, tasa libre de riesgo)."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    dates = pd.bdate_range("2024-01-02", periods=5)
    rows = []
    for sid, kind, unit, base in (
        ("ETF_A", "price", "level", 100.0),
        ("ETF_B", "price", "level", 50.0),
        ("TASA_10A", "rate", "percent", 4.0),
        ("LETRA_3M", "rate", "percent", 5.0),
    ):
        for i, d in enumerate(dates):
            rows.append(
                [d.strftime("%Y-%m-%d"), sid, base + i * 0.1, kind, unit, "USD", "B", "manual"]
            )
    frame = pd.DataFrame(
        rows,
        columns=["date", "series_id", "value", "kind", "unit", "currency", "frequency", "source"],
    )
    frame.to_csv(out / DATA, index=False)
    manifest = {
        "bundle": {
            "version": BUNDLE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "name": name,
            "description": "Plantilla: reemplace los datos y las declaraciones.",
            "created_at": "",
            "created_with": f"tsinsurance {__version__}",
            "sha256": "",
        },
        "series": [
            {
                "id": "ETF_A",
                "role": "asset",
                "description": "Precio ajustado (retorno total)",
                "license": "interna",
                "redistributable": False,
            },
            {
                "id": "ETF_B",
                "role": "asset",
                "description": "Precio ajustado (retorno total)",
                "license": "interna",
                "redistributable": False,
            },
            {
                "id": "TASA_10A",
                "role": "exogenous",
                "description": "Tasa a 10 años",
                "release_lag": "1B",
                "transform": "level",
                "point_in_time": True,
                "license": "interna",
                "redistributable": False,
            },
            {
                "id": "LETRA_3M",
                "role": "risk_free",
                "description": "Tasa libre de riesgo",
                "release_lag": "1B",
                "rf_convention": "annual_percent",
                "license": "interna",
                "redistributable": False,
            },
        ],
    }
    (out / MANIFEST).write_text(_to_toml(manifest), encoding="utf-8")
    return out


def fetch_recipe(recipe: str | os.PathLike[str], directory: str | os.PathLike[str]) -> Bundle:
    """Descarga un paquete según una receta TOML y lo guarda en ``directory``.

    La receta tiene ``[bundle]`` (``name``, ``description``) y bloques ``[[fetch]]`` con
    ``source`` (``yahoo``, ``fred``, ``csv``...), ``ids``, ``start``, ``end``, parámetros
    del conector en ``[fetch.options]`` y ``[[fetch.series]]`` con la declaración de cada
    serie (``id``, ``role``, ``release_lag``, ``license``, ...).
    """
    from tsinsurance.data.sources import get_source

    spec = tomllib.loads(Path(recipe).read_text(encoding="utf-8"))
    parts = []
    for block in spec.get("fetch", []):
        source = get_source(block["source"], **block.get("options", {}))
        snap = source.fetch(block.get("ids"), block.get("start"), block.get("end"))
        parts.append((snap, block.get("series", [])))
    head = spec.get("bundle", {})
    bundle = Bundle.from_snapshots(
        str(head.get("name", Path(directory).name)),
        parts,
        description=str(head.get("description", "")),
    )
    bundle.save(directory)
    return bundle


# --- TOML mínimo (manifiestos planos) ---------------------------------------------------


def _toml_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    text = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def _to_toml(doc: Mapping[str, Any]) -> str:
    lines: list[str] = []
    for key, value in doc.items():
        if isinstance(value, Mapping):
            lines.append(f"[{key}]")
            lines += [f"{k} = {_toml_value(v)}" for k, v in value.items()]
            lines.append("")
        elif isinstance(value, list) and value and isinstance(value[0], Mapping):
            for item in value:
                lines.append(f"[[{key}]]")
                lines += [f"{k} = {_toml_value(v)}" for k, v in item.items()]
                lines.append("")
        else:
            lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines).rstrip() + "\n"


def seal_bundle(directory: str | os.PathLike[str]) -> Bundle:
    """Calcula y escribe la huella de un paquete escrito a mano (deja de ser exploratorio)."""
    src = Path(directory)
    manifest = tomllib.loads((src / MANIFEST).read_text(encoding="utf-8"))
    manifest["bundle"]["sha256"] = ""
    (src / MANIFEST).write_text(_to_toml(manifest), encoding="utf-8")
    problems = validate_bundle(src)
    if problems:
        raise DataValidationError(_format(problems))
    data = load(read_table(src / DATA), "market")
    data = data.sort_values(["series_id", "date"]).reset_index(drop=True)
    manifest["bundle"]["sha256"] = seal_hash(data, manifest["series"])
    manifest["bundle"]["created_at"] = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    (src / MANIFEST).write_text(_to_toml(manifest), encoding="utf-8")
    return Bundle.load(src)


def bundle_digest(directory: str | os.PathLike[str]) -> str:
    """Huella SHA-256 de los archivos del paquete (manifiesto + datos)."""
    h = hashlib.sha256()
    for name in (MANIFEST, DATA):
        h.update((Path(directory) / name).read_bytes())
    return h.hexdigest()
