import json
from pathlib import Path

import pandas as pd
import pytest

from tsinsurance.data import data_dictionary, export_schema, validate, write_template
from tsinsurance.data.validate import read_table


@pytest.mark.parametrize("kind", ["market", "portfolio", "rate_nodes"])
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_templates_are_valid(tmp_path: Path, kind: str, fmt: str) -> None:
    empty = write_template(kind, tmp_path / f"t.{fmt}", fmt)  # type: ignore[arg-type]
    assert validate(read_table(empty), kind).is_valid  # type: ignore[arg-type]
    example = write_template(kind, tmp_path / f"e.{fmt}", fmt, with_example=True)  # type: ignore[arg-type]
    df = read_table(example)
    assert len(df) == 1
    if kind != "portfolio":  # un solo peso de ejemplo (0.25) no suma 1
        assert validate(df, kind).is_valid  # type: ignore[arg-type]


def test_excel_template_has_dictionary(tmp_path: Path) -> None:
    path = write_template("market", tmp_path / "m.xlsx", "xlsx")
    sheets = pd.read_excel(path, sheet_name=None)
    assert set(sheets) == {"data", "diccionario"}
    assert "series_id" in set(sheets["diccionario"]["columna"])


def test_json_schema_export() -> None:
    schema = export_schema("market")
    json.dumps(schema)
    items = schema["items"]
    assert items["properties"]["kind"]["enum"] == ["price", "return", "rate", "index"]
    assert "date" in items["required"] and "source" not in items["required"]
    assert items["properties"]["value"]["anyOf"][1] == {"type": "null"}
    assert any("monótona" in r or "creciente" in r for r in schema["x-row-rules"])
    nodes = export_schema("rate_nodes")["items"]["properties"]["tenor_years"]
    assert nodes["exclusiveMinimum"] == 0.0


def test_frictionless_export() -> None:
    schema = export_schema("portfolio", "frictionless")
    assert schema["primaryKey"] == ["asset_id"]
    names = [f["name"] for f in schema["fields"]]
    assert names[:2] == ["as_of", "asset_id"]


def test_invalid_options(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        export_schema("market", "xml")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        write_template("market", tmp_path / "x.txt", "txt")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        data_dictionary("bonds")  # type: ignore[arg-type]
