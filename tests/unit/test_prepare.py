import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tsinsurance.data import prepare
from tsinsurance.data.prepare import regular_index
from tsinsurance.errors import DataValidationError, InsufficientDataError


def bseries(values: list[float], start: str = "2024-01-01") -> pd.Series:
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), name="x")


def test_index_errors() -> None:
    s = bseries([1.0, 2.0, 3.0])
    with pytest.raises(DataValidationError, match="duplicadas"):
        prepare(s.iloc[[0, 0, 1]], freq="B")
    with pytest.raises(DataValidationError, match="monótono"):
        prepare(s.iloc[[1, 0, 2]], freq="B")
    with pytest.raises(InsufficientDataError):
        prepare(s.iloc[:1], freq="B")
    with pytest.raises(DataValidationError, match="fechas"):
        prepare(pd.Series([1.0, 2.0], index=["a", "b"]), freq="B")


def test_missing_dates_detected_and_error_by_default() -> None:
    s = bseries([1.0, 2.0, 3.0, 4.0]).drop(pd.Timestamp("2024-01-02"))
    with pytest.raises(DataValidationError, match="faltante"):
        prepare(s, freq="B")


def test_missing_methods_are_logged() -> None:
    s = bseries([np.nan, 1.0, np.nan, 3.0, 4.0])
    ff = prepare(s, freq="B", missing="ffill")
    assert ff.n_missing == 2 and ff.n_imputed == 1 and ff.n_dropped == 1
    assert list(ff.data) == [1.0, 1.0, 3.0, 4.0]
    assert any("imputado" in entry for entry in ff.log)
    dr = prepare(s, freq="B", missing="drop")
    assert list(dr.data) == [1.0, 3.0, 4.0] and dr.n_dropped == 2
    it = prepare(s, freq="B", missing="interpolate")
    assert it.data.iloc[1] == pytest.approx(2.0)
    assert it.uses_future_information and not ff.uses_future_information
    assert any("ADVERTENCIA" in entry for entry in it.log)
    assert "ffill" in ff.summary()


def test_transforms() -> None:
    s = bseries([100.0, 110.0, 99.0])
    assert prepare(s, freq="B", transform="simple").data.tolist() == pytest.approx([0.1, -0.1])
    log = prepare(s, freq="B", transform="log").data
    assert log.tolist() == pytest.approx([np.log(1.1), np.log(0.9)])
    assert prepare(s, freq="B", transform="diff").data.tolist() == [10.0, -11.0]
    with pytest.raises(DataValidationError, match="positivos"):
        prepare(bseries([1.0, 0.0, 2.0]), freq="B", transform="log")
    with pytest.raises(DataValidationError, match="positivos"):
        prepare(bseries([1.0, 0.0, 2.0]), freq="B", transform="simple")


def test_drop_with_transform_never_spans_gaps() -> None:
    s = bseries([100.0, 110.0, np.nan, 121.0, 133.1])
    out = prepare(s, freq="B", missing="drop", transform="simple")
    # El retorno 121/110 (dos días) no debe aparecer: tras el hueco queda NaN y se descarta.
    assert out.data.tolist() == pytest.approx([0.1, 0.1])
    assert list(out.data.index) == [s.index[1], s.index[4]]
    assert out.n_dropped == 3


def test_frequencies() -> None:
    monthly = pd.Series(
        [1.0, 2.0, 3.0], index=pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-31"])
    )
    out = prepare(monthly, freq="M")
    assert list(out.data.index.day) == [31, 29, 31] and out.data.index.freqstr == "ME"
    starts = pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-01-01", "2024-02-01"]))
    assert list(prepare(starts, freq="M").data.index.day) == [31, 29]  # fin de mes
    weekly = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2024-01-05", periods=3, freq="W-FRI"))
    assert prepare(weekly, freq="W").data.index.freqstr == "W-FRI"
    daily = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2024-01-06", periods=3, freq="D"))
    assert len(prepare(daily, freq="D").data) == 3
    with pytest.raises(DataValidationError, match="fin de semana"):
        prepare(daily, freq="B")
    with pytest.raises(DataValidationError, match="mismo día"):
        regular_index(pd.DatetimeIndex(["2024-01-05", "2024-01-09"]), "W")
    with pytest.raises(DataValidationError, match="dos observaciones"):
        regular_index(pd.DatetimeIndex(["2024-01-05", "2024-01-09"]), "M")
    with pytest.raises(DataValidationError, match="no soportada"):
        regular_index(pd.DatetimeIndex(["2024-01-05"]), "Q")  # type: ignore[arg-type]


def test_dataframe_input() -> None:
    df = bseries([1.0, 2.0, 3.0]).to_frame()
    assert len(prepare(df, freq="B").data) == 3
    with pytest.raises(DataValidationError, match="una sola serie"):
        prepare(df.assign(y=1.0), freq="B")


@settings(max_examples=40, deadline=None)
@given(
    values=st.lists(
        st.one_of(st.none(), st.floats(min_value=0.01, max_value=1e6)), min_size=6, max_size=40
    ),
    cut=st.integers(min_value=4, max_value=39),
    transform=st.sampled_from(["none", "simple", "log", "diff"]),
)
def test_property_truncation_invariance_ffill(
    values: list[float | None], cut: int, transform: str
) -> None:
    # Principio II: preparar la serie truncada en t da lo mismo que truncar la preparada.
    s = bseries([np.nan if v is None else v for v in values])
    cut = min(cut, len(s))
    try:
        full = prepare(s, freq="B", missing="ffill", transform=transform).data  # type: ignore[arg-type]
        part = prepare(s.iloc[:cut], freq="B", missing="ffill", transform=transform).data  # type: ignore[arg-type]
    except (DataValidationError, InsufficientDataError):
        return
    common = part.index
    pd.testing.assert_series_equal(full.loc[common], part, check_freq=False)


@settings(max_examples=50, deadline=None)
@given(st.lists(st.floats(min_value=0.01, max_value=1e6), min_size=3, max_size=60))
def test_property_log_returns_invert_to_prices(prices: list[float]) -> None:
    s = bseries(prices)
    r = prepare(s, freq="B", transform="log").data
    rebuilt = prices[0] * np.exp(np.cumsum(r.to_numpy()))
    np.testing.assert_allclose(rebuilt, prices[1:], rtol=1e-9)
