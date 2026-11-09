from pathlib import Path

import pandas as pd
import pytest

from tsinsurance.data import load, to_wide, validate
from tsinsurance.data.validate import read_table
from tsinsurance.errors import DataValidationError

FIX = Path(__file__).parents[1] / "fixtures"


def test_lazy_validation_reports_every_error_with_row_column_check() -> None:
    report = validate(read_table(FIX / "market_bad.csv"), "market")
    assert not report.is_valid
    errs = report.errors
    assert list(errs.columns) == ["row", "column", "check", "failure_case"]
    found = {(r, c) for r, c in zip(errs["row"], errs["column"], strict=True)}
    assert (1, "value") in found  # precio negativo
    assert (2, "unit") in found  # 'pct'
    assert (3, "currency") in found  # 'usd'
    # Consecuencias entre filas: la serie DGS10 queda con unidades/monedas mezcladas.
    assert (3, "unit") in found and (2, "currency") in found
    assert len(errs) == 5
    text = report.summary()
    assert "fila 1" in text and "5 error(es)" in text


def test_load_raises_with_report() -> None:
    with pytest.raises(DataValidationError) as info:
        load(FIX / "market_bad.csv", "market")
    assert info.value.report is not None and len(info.value.report.errors) == 5


def test_load_coerces_types() -> None:
    df = load(FIX / "market_good.csv", "market")
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert df["value"].dtype == float and df["value"].isna().sum() == 1


def test_to_wide() -> None:
    wide = to_wide(load(FIX / "market_good.csv", "market"))
    assert isinstance(wide.index, pd.DatetimeIndex)
    assert list(wide.columns) == ["DGS10", "SPX"]
    assert wide.attrs["frequency"] == "B"
    assert wide.attrs["unit"] == {"SPX": "level", "DGS10": "percent"}
    assert wide.attrs["source"]["DGS10"] == "fred:DGS10"


def test_to_wide_rejects_mixed_frequencies() -> None:
    df = read_table(FIX / "market_good.csv")
    df.loc[df["series_id"] == "DGS10", "frequency"] = "D"
    with pytest.raises(DataValidationError, match="misma frecuencia"):
        to_wide(df)


def test_read_table_rejects_unknown_format(tmp_path: Path) -> None:
    f = tmp_path / "x.json"
    f.write_text("{}")
    with pytest.raises(DataValidationError, match="no soportado"):
        read_table(f)


def test_valid_summary() -> None:
    assert "sin errores" in validate(read_table(FIX / "market_good.csv"), "market").summary()
