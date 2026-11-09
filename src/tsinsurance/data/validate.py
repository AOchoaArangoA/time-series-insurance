"""Validación de insumos contra el contrato de datos y carga a estructuras de análisis."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
import pandera.errors as pa_errors

from tsinsurance.data.schemas import SCHEMA_VERSION, InputKind, get_schema
from tsinsurance.errors import DataValidationError
from tsinsurance.results import ResultMixin

if TYPE_CHECKING:
    from tsinsurance.data.snapshot import Snapshot

__all__ = ["ValidationReport", "load", "read_table", "to_wide", "validate"]

ERROR_COLUMNS = ["row", "column", "check", "failure_case"]

# Columna a la que se atribuye cada regla a nivel de fila.
_CHECK_COLUMN = {
    "date_monotonic_per_series": "date",
    "price_positive": "value",
    "single_frequency_per_series": "frequency",
    "single_unit_per_series": "unit",
    "single_currency_per_series": "currency",
    "single_as_of": "as_of",
    "weight_or_amount_required": "weight|amount",
    "weights_sum_to_one": "weight",
}


@dataclass(frozen=True, slots=True, eq=False)
class ValidationReport(ResultMixin):
    """Resultado de validar un insumo contra el contrato de datos.

    Attributes
    ----------
    kind : str
        Tipo de insumo validado.
    schema_version : str
        Versión del contrato de datos.
    n_rows : int
        Filas evaluadas.
    errors : pandas.DataFrame
        Un registro por error con columnas ``row`` (índice de la fila de datos, base 0;
        ``None`` para errores de estructura), ``column``, ``check`` y ``failure_case``.
    """

    kind: str
    schema_version: str
    n_rows: int
    errors: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=ERROR_COLUMNS))

    @property
    def is_valid(self) -> bool:
        """``True`` si no hay errores."""
        return self.errors.empty

    def raise_if_invalid(self) -> None:
        """Lanza :class:`DataValidationError` si hay errores."""
        if not self.is_valid:
            raise DataValidationError(self.summary(), report=self)

    def summary(self) -> str:
        """Resumen legible con todos los errores."""
        head = f"Validación '{self.kind}' (contrato v{self.schema_version}): {self.n_rows} filas"
        if self.is_valid:
            return f"{head} — sin errores."
        lines = [f"{head} — {len(self.errors)} error(es):"]
        records: list[dict[Any, Any]] = self.errors.to_dict("records")
        for rec in records:
            row = rec["row"]
            where = "estructura" if row is None or row != row else f"fila {row}"
            lines.append(
                f"  [{where}] columna={rec['column']} regla={rec['check']} "
                f"valor={rec['failure_case']}"
            )
        return "\n".join(lines)


def _failure_table(exc: pa_errors.SchemaErrors) -> pd.DataFrame:
    fc = exc.failure_cases.copy()
    is_frame = fc["schema_context"] == "DataFrameSchema"
    checks = fc["check"].astype(str)
    mapped = checks.map(_CHECK_COLUMN)
    fc["column"] = fc["column"].astype(object).where(~(is_frame & mapped.notna()), mapped)
    fc["failure_case"] = fc["failure_case"].where(~(is_frame & mapped.notna()), None)
    out = pd.DataFrame(
        {
            "row": fc["index"].astype(object).where(fc["index"].notna(), None),
            "column": fc["column"],
            "check": checks,
            "failure_case": fc["failure_case"].astype(object),
        }
    )
    out["_frame"] = is_frame.to_numpy()
    out = out.drop_duplicates(subset=["row", "column", "check"])
    # Una regla entre filas no se reporta en una celda que ya tiene un error propio.
    cells = {
        (r, c) for r, c, f in zip(out["row"], out["column"], out["_frame"], strict=True) if not f
    }
    keep = [
        not (f and (r, c) in cells)
        for r, c, f in zip(out["row"], out["column"], out["_frame"], strict=True)
    ]
    out = out[keep].reset_index(drop=True)
    return out[ERROR_COLUMNS]


def validate(df: pd.DataFrame, kind: InputKind) -> ValidationReport:
    """Valida ``df`` contra el contrato ``kind`` reportando **todos** los errores.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos en el formato del contrato (ver ``export_schema``).
    kind : {"market", "portfolio", "rate_nodes"}
        Tipo de insumo.

    Returns
    -------
    ValidationReport
        Reporte con un registro por error (validación *lazy*).
    """
    schema = get_schema(kind)
    try:
        schema.validate(df, lazy=True)
    except pa_errors.SchemaErrors as exc:
        return ValidationReport(kind, SCHEMA_VERSION, len(df), _failure_table(exc))
    return ValidationReport(kind, SCHEMA_VERSION, len(df))


def read_table(path: str | os.PathLike[str], *, sheet: str | int = 0) -> pd.DataFrame:
    """Lee un CSV o Excel como texto (la conversión de tipos la hace el contrato)."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(p, dtype=str, keep_default_na=True)
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(p, sheet_name=sheet, dtype=str)
    raise DataValidationError(f"Formato no soportado: '{suffix}'. Use .csv o .xlsx.")


def load(source: str | os.PathLike[str] | pd.DataFrame | Snapshot, kind: InputKind) -> pd.DataFrame:
    """Carga y valida un insumo desde archivo, ``DataFrame`` o ``Snapshot``.

    Returns
    -------
    pandas.DataFrame
        Datos con tipos convertidos según el contrato.

    Raises
    ------
    DataValidationError
        Si hay errores; el reporte completo está en ``exc.report``.
    """
    from tsinsurance.data.snapshot import Snapshot

    if isinstance(source, Snapshot):
        df = source.data
    elif isinstance(source, pd.DataFrame):
        df = source
    else:
        df = read_table(source)
    report = validate(df, kind)
    report.raise_if_invalid()
    out: pd.DataFrame = get_schema(kind).validate(df)
    return out


def to_wide(market: pd.DataFrame) -> pd.DataFrame:
    """Convierte series de mercado en formato largo a formato ancho.

    El resultado tiene ``DatetimeIndex`` ordenado y una columna por ``series_id``.
    Los metadatos por serie (``kind``, ``unit``, ``currency``, ``frequency``,
    ``source``) quedan en ``DataFrame.attrs``.

    Raises
    ------
    DataValidationError
        Si los datos no cumplen el contrato o mezclan frecuencias.
    """
    data = load(market, "market")
    freqs = data["frequency"].unique()
    if len(freqs) != 1:
        raise DataValidationError(
            f"Todas las series deben tener la misma frecuencia para combinarse; hay {list(freqs)}."
        )
    wide = data.pivot(index="date", columns="series_id", values="value").sort_index()
    wide.index = pd.DatetimeIndex(wide.index, name="date")
    wide.columns.name = None
    meta = data.drop_duplicates("series_id").set_index("series_id")
    wide.attrs["frequency"] = str(freqs[0])
    for col in ("kind", "unit", "currency", "source"):
        if col in meta:
            wide.attrs[col] = {
                str(k): (None if pd.isna(v) else str(v)) for k, v in meta[col].items()
            }
    return wide
