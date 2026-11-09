"""Plantillas de insumos y exportación del contrato de datos (FR-019b)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from tsinsurance.data.schemas import COLUMN_SPECS, SCHEMA_VERSION, ColumnSpec, InputKind

__all__ = ["data_dictionary", "export_schema", "write_template"]

_JSON_TYPES = {"date": "string", "string": "string", "number": "number"}
_FRICTIONLESS_TYPES = {"date": "date", "string": "string", "number": "number"}


def _specs(kind: InputKind) -> tuple[ColumnSpec, ...]:
    if kind not in COLUMN_SPECS:
        raise ValueError(f"Tipo de insumo desconocido '{kind}'. Opciones: {list(COLUMN_SPECS)}")
    return COLUMN_SPECS[kind]


def data_dictionary(kind: InputKind) -> pd.DataFrame:
    """Diccionario de datos legible del insumo ``kind``."""
    rows = [
        {
            "columna": s.name,
            "tipo": s.type,
            "obligatoria": s.required,
            "admite_vacio": s.nullable,
            "valores_permitidos": ", ".join(s.enum) if s.enum else "",
            "patron": s.pattern or "",
            "descripcion": s.description,
            "ejemplo": s.example,
        }
        for s in _specs(kind)
    ]
    return pd.DataFrame(rows)


def export_schema(
    kind: InputKind, fmt: Literal["json-schema", "frictionless"] = "json-schema"
) -> dict[str, Any]:
    """Exporta el contrato de datos de ``kind`` como JSON Schema o Frictionless Table Schema.

    Las reglas entre filas (unicidad, monotonicidad, suma de pesos) se describen en
    ``x-row-rules`` / ``primaryKey`` porque no son expresables por columna.
    """
    specs = _specs(kind)
    if fmt == "json-schema":
        props: dict[str, Any] = {}
        for s in specs:
            base: dict[str, Any] = {"type": _JSON_TYPES[s.type], "description": s.description}
            if s.type == "date":
                base["format"] = "date"
            if s.enum:
                base["enum"] = list(s.enum)
            if s.pattern:
                base["pattern"] = s.pattern
            if s.minimum_exclusive is not None:
                base["exclusiveMinimum"] = s.minimum_exclusive
            props[s.name] = {"anyOf": [base, {"type": "null"}]} if s.nullable else base
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"tsinsurance:{kind}:{SCHEMA_VERSION}",
            "title": f"tsinsurance {kind} v{SCHEMA_VERSION}",
            "type": "array",
            "items": {
                "type": "object",
                "properties": props,
                "required": [s.name for s in specs if s.required],
            },
            "x-row-rules": _row_rules(kind),
        }
    if fmt == "frictionless":
        fields = []
        for s in specs:
            constraints: dict[str, Any] = {"required": s.required and not s.nullable}
            if s.enum:
                constraints["enum"] = list(s.enum)
            if s.pattern:
                constraints["pattern"] = s.pattern
            fields.append(
                {
                    "name": s.name,
                    "type": _FRICTIONLESS_TYPES[s.type],
                    "description": s.description,
                    "constraints": constraints,
                }
            )
        keys = {
            "market": ["series_id", "date"],
            "portfolio": ["asset_id"],
            "rate_nodes": ["curve_id", "date", "tenor_years"],
        }[kind]
        return {"fields": fields, "primaryKey": keys, "x-schema-version": SCHEMA_VERSION}
    raise ValueError("fmt debe ser 'json-schema' o 'frictionless'.")


def _row_rules(kind: InputKind) -> list[str]:
    return {
        "market": [
            "(series_id, date) único",
            "date creciente dentro de cada series_id",
            "value > 0 cuando kind = price",
            "una sola frequency, unit y currency por series_id",
        ],
        "portfolio": [
            "asset_id único",
            "as_of único en el archivo",
            "weight o amount en cada fila",
            "suma de weight = 1 ± 1e-8 si se usan pesos",
            "asset_id debe existir como series_id en las series de mercado",
        ],
        "rate_nodes": ["(curve_id, date, tenor_years) único"],
    }[kind]


def write_template(
    kind: InputKind,
    path: str | os.PathLike[str],
    fmt: Literal["csv", "xlsx"] = "csv",
    *,
    with_example: bool = False,
) -> Path:
    """Escribe una plantilla vacía (o con una fila de ejemplo) del insumo ``kind``.

    En Excel se agrega una hoja ``diccionario`` con la descripción de cada columna.
    """
    specs = _specs(kind)
    columns = [s.name for s in specs]
    rows = [[s.example for s in specs]] if with_example else []
    frame = pd.DataFrame(rows, columns=columns)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv":
        frame.to_csv(out, index=False)
    elif fmt == "xlsx":
        with pd.ExcelWriter(out) as writer:
            frame.to_excel(writer, sheet_name="data", index=False)
            data_dictionary(kind).to_excel(writer, sheet_name="diccionario", index=False)
    else:
        raise ValueError("fmt debe ser 'csv' o 'xlsx'.")
    return out
