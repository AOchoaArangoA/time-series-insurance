"""Contrato de datos (esquema de insumos) versionado.

Una única fuente de verdad (:data:`COLUMN_SPECS`) genera tanto los esquemas
``pandera`` de validación como las exportaciones (JSON Schema, Frictionless) y las
plantillas para el usuario (FR-019b).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeAlias

import numpy as np
import pandas as pd
import pandera.pandas as pa

__all__ = [
    "COLUMN_SPECS",
    "SCHEMA_VERSION",
    "ColumnSpec",
    "InputKind",
    "MarketSeriesSchema",
    "PortfolioSchema",
    "RateNodesSchema",
    "get_schema",
]

SCHEMA_VERSION = "1.0"

InputKind: TypeAlias = Literal["market", "portfolio", "rate_nodes"]
INPUT_KINDS: tuple[InputKind, ...] = ("market", "portfolio", "rate_nodes")

ColumnType: TypeAlias = Literal["date", "string", "number"]


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    """Definición de una columna del contrato de datos."""

    name: str
    type: ColumnType
    required: bool
    nullable: bool
    description: str
    enum: tuple[str, ...] | None = None
    pattern: str | None = None
    minimum_exclusive: float | None = None
    example: str = ""


SERIES_ID_PATTERN = r"^[A-Za-z0-9_.:^=-]+$"
CURRENCY_PATTERN = r"^[A-Z]{3}$"

COLUMN_SPECS: dict[InputKind, tuple[ColumnSpec, ...]] = {
    "market": (
        ColumnSpec(
            "date", "date", True, False, "Fecha de la observación (ISO 8601).", example="2024-01-02"
        ),
        ColumnSpec(
            "series_id",
            "string",
            True,
            False,
            "Identificador de la serie (letras, dígitos, _ . : ^ = -).",
            pattern=SERIES_ID_PATTERN,
            example="DGS10",
        ),
        ColumnSpec(
            "value",
            "number",
            True,
            True,
            "Valor observado; vacío = faltante explícito.",
            example="3.95",
        ),
        ColumnSpec(
            "kind",
            "string",
            True,
            False,
            "Naturaleza del dato.",
            enum=("price", "return", "rate", "index"),
            example="rate",
        ),
        ColumnSpec(
            "unit",
            "string",
            True,
            False,
            "Unidad del valor.",
            enum=("level", "percent", "decimal", "bps"),
            example="percent",
        ),
        ColumnSpec(
            "currency",
            "string",
            True,
            False,
            "Moneda ISO 4217.",
            pattern=CURRENCY_PATTERN,
            example="USD",
        ),
        ColumnSpec(
            "frequency",
            "string",
            True,
            False,
            "Frecuencia: D diaria, B hábil, W semanal, M mensual.",
            enum=("D", "B", "W", "M"),
            example="B",
        ),
        ColumnSpec(
            "source",
            "string",
            False,
            True,
            "Origen del dato (p. ej. fred:DGS10).",
            example="fred:DGS10",
        ),
    ),
    "portfolio": (
        ColumnSpec(
            "as_of",
            "date",
            True,
            False,
            "Fecha de corte del portafolio (única).",
            example="2024-06-30",
        ),
        ColumnSpec(
            "asset_id",
            "string",
            True,
            False,
            "Activo; debe existir como series_id en las series de mercado.",
            pattern=SERIES_ID_PATTERN,
            example="SPX",
        ),
        ColumnSpec(
            "weight",
            "number",
            False,
            True,
            "Peso en el portafolio; si se usa, la suma debe ser 1.",
            example="0.25",
        ),
        ColumnSpec(
            "amount",
            "number",
            False,
            True,
            "Monto invertido; obligatorio si no hay peso.",
            example="",
        ),
        ColumnSpec(
            "currency",
            "string",
            True,
            False,
            "Moneda ISO 4217.",
            pattern=CURRENCY_PATTERN,
            example="USD",
        ),
        ColumnSpec(
            "asset_class",
            "string",
            True,
            False,
            "Clase de activo.",
            enum=("fixed_income", "equity", "real_estate", "cash", "other"),
            example="equity",
        ),
    ),
    "rate_nodes": (
        ColumnSpec("date", "date", True, False, "Fecha de la curva.", example="2024-01-02"),
        ColumnSpec(
            "curve_id",
            "string",
            True,
            False,
            "Identificador de la curva.",
            pattern=SERIES_ID_PATTERN,
            example="USD_TSY",
        ),
        ColumnSpec(
            "tenor_years",
            "number",
            True,
            False,
            "Plazo en años (> 0).",
            minimum_exclusive=0.0,
            example="10",
        ),
        ColumnSpec("rate", "number", True, False, "Tasa en la unidad declarada.", example="3.95"),
        ColumnSpec(
            "unit",
            "string",
            True,
            False,
            "Unidad de la tasa.",
            enum=("percent", "decimal", "bps"),
            example="percent",
        ),
        ColumnSpec(
            "compounding",
            "string",
            True,
            False,
            "Capitalización.",
            enum=("continuous", "annual", "semiannual", "simple"),
            example="annual",
        ),
        ColumnSpec(
            "day_count",
            "string",
            True,
            False,
            "Convención de conteo de días (p. ej. ACT/365, 30/360).",
            pattern=r"^\S+$",
            example="ACT/365",
        ),
    ),
}

WEIGHT_TOLERANCE = 1e-8


def _column(spec: ColumnSpec) -> pa.Column:
    checks: list[pa.Check] = []
    if spec.enum is not None:
        checks.append(pa.Check.isin(list(spec.enum)))
    if spec.pattern is not None:
        checks.append(pa.Check.str_matches(spec.pattern))
    if spec.minimum_exclusive is not None:
        checks.append(pa.Check.gt(spec.minimum_exclusive))
    if spec.type == "number":
        checks.append(
            pa.Check(lambda s: np.isfinite(s) | s.isna(), element_wise=False, name="finite")
        )
    dtype: object = {"date": "datetime64[ns]", "string": str, "number": float}[spec.type]
    return pa.Column(
        dtype,
        checks=checks,
        nullable=spec.nullable,
        required=spec.required,
        coerce=True,
        description=spec.description,
    )


# --- Reglas a nivel de fila (devuelven una serie booleana por fila) -------------------


def _market_monotonic(df: pd.DataFrame) -> pd.Series:
    prev = df.groupby("series_id", sort=False)["date"].shift(1)
    return prev.isna() | (df["date"] > prev)


def _market_price_positive(df: pd.DataFrame) -> pd.Series:
    return (df["kind"] != "price") | df["value"].isna() | (df["value"] > 0)


def _single_per_series(column: str) -> Callable[[pd.DataFrame], pd.Series]:
    def check(df: pd.DataFrame) -> pd.Series:
        counts = df.groupby("series_id", sort=False)[column].transform("nunique")
        return counts <= 1

    check.__name__ = f"single_{column}_per_series"
    return check


def _portfolio_single_as_of(df: pd.DataFrame) -> pd.Series:
    single = df.empty or bool((df["as_of"] == df["as_of"].iloc[0]).all())
    return pd.Series(single, index=df.index)


def _portfolio_weight_or_amount(df: pd.DataFrame) -> pd.Series:
    weight = df["weight"] if "weight" in df else pd.Series(np.nan, index=df.index)
    amount = df["amount"] if "amount" in df else pd.Series(np.nan, index=df.index)
    return weight.notna() | amount.notna()


def _portfolio_weights_sum_to_one(df: pd.DataFrame) -> pd.Series:
    if "weight" not in df or df["weight"].isna().all():
        return pd.Series(True, index=df.index)
    ok = abs(float(df["weight"].sum()) - 1.0) <= WEIGHT_TOLERANCE
    return pd.Series(ok, index=df.index)


def _build(kind: InputKind) -> pa.DataFrameSchema:
    columns = {spec.name: _column(spec) for spec in COLUMN_SPECS[kind]}
    checks: list[pa.Check] = []
    unique: list[str] | None = None
    if kind == "market":
        unique = ["series_id", "date"]
        checks = [
            pa.Check(_market_monotonic, name="date_monotonic_per_series"),
            pa.Check(_market_price_positive, name="price_positive"),
            pa.Check(_single_per_series("frequency"), name="single_frequency_per_series"),
            pa.Check(_single_per_series("unit"), name="single_unit_per_series"),
            pa.Check(_single_per_series("currency"), name="single_currency_per_series"),
        ]
    elif kind == "portfolio":
        unique = ["asset_id"]
        checks = [
            pa.Check(_portfolio_single_as_of, name="single_as_of"),
            pa.Check(_portfolio_weight_or_amount, name="weight_or_amount_required"),
            pa.Check(_portfolio_weights_sum_to_one, name="weights_sum_to_one"),
        ]
    else:
        unique = ["curve_id", "date", "tenor_years"]
    return pa.DataFrameSchema(
        columns,
        checks=checks,
        unique=unique,
        strict=False,
        coerce=True,
        name=f"{kind}@{SCHEMA_VERSION}",
    )


MarketSeriesSchema: pa.DataFrameSchema = _build("market")
PortfolioSchema: pa.DataFrameSchema = _build("portfolio")
RateNodesSchema: pa.DataFrameSchema = _build("rate_nodes")

_SCHEMAS: dict[InputKind, pa.DataFrameSchema] = {
    "market": MarketSeriesSchema,
    "portfolio": PortfolioSchema,
    "rate_nodes": RateNodesSchema,
}


def get_schema(kind: InputKind) -> pa.DataFrameSchema:
    """Devuelve el esquema ``pandera`` del insumo ``kind``."""
    if kind not in _SCHEMAS:
        raise ValueError(f"Tipo de insumo desconocido '{kind}'. Opciones: {INPUT_KINDS}")
    return _SCHEMAS[kind]
