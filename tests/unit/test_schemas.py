import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tsinsurance.data import validate
from tsinsurance.data.schemas import COLUMN_SPECS, get_schema


def market(**over: list[object]) -> pd.DataFrame:
    base: dict[str, list[object]] = {
        "date": ["2024-01-02", "2024-01-03"],
        "series_id": ["SPX", "SPX"],
        "value": [100.0, 101.0],
        "kind": ["price", "price"],
        "unit": ["level", "level"],
        "currency": ["USD", "USD"],
        "frequency": ["B", "B"],
    }
    base.update(over)
    return pd.DataFrame(base)


def checks_failed(df: pd.DataFrame, kind: str = "market") -> set[str]:
    return set(validate(df, kind).errors["check"])  # type: ignore[arg-type]


def test_valid_market() -> None:
    assert validate(market(), "market").is_valid


@pytest.mark.parametrize(
    ("over", "expected"),
    [
        ({"date": ["2024-01-03", "2024-01-02"]}, "date_monotonic_per_series"),
        ({"date": ["2024-01-02", "2024-01-02"]}, "multiple_fields_uniqueness"),
        ({"series_id": ["S P X", "S P X"]}, "str_matches"),
        ({"kind": ["stock", "stock"]}, "isin"),
        ({"unit": ["pct", "pct"]}, "isin"),
        ({"currency": ["usd", "usd"]}, "str_matches"),
        ({"frequency": ["Q", "Q"]}, "isin"),
        ({"value": [100.0, 0.0]}, "price_positive"),
        ({"frequency": ["B", "D"]}, "single_frequency_per_series"),
        ({"unit": ["level", "percent"], "kind": ["rate", "rate"]}, "single_unit_per_series"),
        ({"currency": ["USD", "EUR"]}, "single_currency_per_series"),
    ],
)
def test_market_rules(over: dict[str, list[object]], expected: str) -> None:
    failed = checks_failed(market(**over))
    assert any(expected in c for c in failed), failed


def test_missing_value_allowed_and_missing_column_reported() -> None:
    assert validate(market(value=[100.0, None]), "market").is_valid
    errs = validate(market().drop(columns="currency"), "market").errors
    assert "currency" in set(errs["failure_case"].astype(str)) or "currency" in set(
        errs["column"].astype(str)
    )


def portfolio(**over: list[object]) -> pd.DataFrame:
    base: dict[str, list[object]] = {
        "as_of": ["2024-06-30"] * 3,
        "asset_id": ["SPX", "AGG", "CASH"],
        "weight": [0.25, 0.70, 0.05],
        "currency": ["USD"] * 3,
        "asset_class": ["equity", "fixed_income", "cash"],
    }
    base.update(over)
    return pd.DataFrame(base)


def test_portfolio_rules() -> None:
    assert validate(portfolio(), "portfolio").is_valid
    assert "weights_sum_to_one" in checks_failed(portfolio(weight=[0.3, 0.7, 0.05]), "portfolio")
    assert "single_as_of" in checks_failed(
        portfolio(as_of=["2024-06-30", "2024-06-30", "2024-07-01"]), "portfolio"
    )
    failed = checks_failed(portfolio(asset_class=["equity", "bonds", "cash"]), "portfolio")
    assert any(c.startswith("isin") for c in failed)
    amounts = portfolio().drop(columns="weight").assign(amount=[100.0, None, 5.0])
    assert "weight_or_amount_required" in checks_failed(amounts, "portfolio")
    ok_amounts = portfolio().drop(columns="weight").assign(amount=[100.0, 200.0, 5.0])
    assert validate(ok_amounts, "portfolio").is_valid


def test_rate_nodes_rules() -> None:
    df = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02"],
            "curve_id": ["USD_TSY", "USD_TSY"],
            "tenor_years": [0.25, 10.0],
            "rate": [5.37, 3.95],
            "unit": ["percent", "percent"],
            "compounding": ["annual", "annual"],
            "day_count": ["ACT/365", "ACT/365"],
        }
    )
    assert validate(df, "rate_nodes").is_valid
    bad = df.assign(tenor_years=[0.0, 10.0], compounding=["annual", "monthly"])
    assert {"greater_than(0.0)", "isin(['continuous', 'annual', 'semiannual', 'simple'])"} <= (
        checks_failed(bad, "rate_nodes")
    )


def test_unknown_kind() -> None:
    with pytest.raises(ValueError, match="desconocido"):
        get_schema("bonds")  # type: ignore[arg-type]


def test_specs_cover_schema_columns() -> None:
    for kind, specs in COLUMN_SPECS.items():
        assert {s.name for s in specs} == set(get_schema(kind).columns)


@settings(max_examples=50, deadline=None)
@given(
    values=st.lists(st.floats(min_value=1e-6, max_value=1e9), min_size=1, max_size=30),
    sid=st.from_regex(r"[A-Za-z0-9_]{1,10}", fullmatch=True),
)
def test_property_generated_valid_rows_always_pass(values: list[float], sid: str) -> None:
    n = len(values)
    df = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=n, freq="B"),
            "series_id": sid,
            "value": values,
            "kind": "price",
            "unit": "level",
            "currency": "EUR",
            "frequency": "B",
        }
    )
    assert validate(df, "market").is_valid
