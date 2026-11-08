import numpy as np
import pandas as pd
import pytest

from tsinsurance.backtest import (
    Exogenous,
    align_point_in_time,
    dtb3_to_daily,
    monthly_decision_dates,
    monthly_returns,
)
from tsinsurance.errors import DataValidationError


def test_monthly_fred_dates_available_after_period_end_plus_lag() -> None:
    cpi = pd.Series(
        [1.0, 2.0, 3.0], index=pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"])
    )
    ex = Exogenous("cpi", cpi, "M", release_lag="20D")
    assert list(ex.availability().strftime("%Y-%m-%d")) == [
        "2024-02-20",
        "2024-03-20",
        "2024-04-20",
    ]
    dates = pd.DatetimeIndex(["2024-02-19", "2024-02-20", "2024-03-29", "2024-04-30"])
    aligned = align_point_in_time([ex], dates)
    assert np.isnan(aligned["cpi"].iloc[0])  # enero aún no publicado
    assert aligned["cpi"].tolist()[1:] == [1.0, 2.0, 3.0]


def test_month_end_dates_from_prepare_convention() -> None:
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-01-31", "2024-02-29"]))
    ex = Exogenous("x", s, "M", release_lag="0D")
    assert list(ex.availability().strftime("%Y-%m-%d")) == ["2024-01-31", "2024-02-29"]


def test_daily_lag_and_transforms() -> None:
    idx = pd.bdate_range("2024-01-01", periods=300)
    s = pd.Series(np.arange(300, dtype=float) + 1, index=idx)
    ex = Exogenous("r", s, "B", release_lag="1B")
    assert ex.availability()[0] == pd.Timestamp("2024-01-02")
    assert Exogenous("d", s, "B", transform="diff").transformed().iloc[0] == 1.0
    assert Exogenous("p", s, "B", transform="pct_change").transformed().iloc[0] == 1.0
    yoy = Exogenous("y", s, "B", transform="yoy").transformed()
    assert yoy.index[0] == idx[252]
    cut = Exogenous("r", s, "B", release_lag="1B").truncate_available(pd.Timestamp("2024-01-03"))
    assert len(cut.series) == 2
    with pytest.raises(DataValidationError):
        Exogenous("bad", s, "Q")  # type: ignore[arg-type]
    with pytest.raises(DataValidationError):
        Exogenous("bad", s.reset_index(drop=True), "B")


def test_monthly_decision_dates_and_returns() -> None:
    idx = pd.bdate_range("2024-01-01", "2024-04-30")
    px = pd.Series(np.linspace(100, 110, len(idx)), index=idx, name="P")
    d = monthly_decision_dates(px)
    assert list(d.strftime("%Y-%m-%d")) == ["2024-01-31", "2024-02-29", "2024-03-29", "2024-04-30"]
    r = monthly_returns(px)
    assert r.index[0] == pd.Timestamp("2024-02-29")
    assert r.iloc[0] == pytest.approx(px.loc["2024-02-29"] / px.loc["2024-01-31"] - 1)


def test_dtb3_conversion() -> None:
    dtb3 = pd.Series([5.0], index=pd.to_datetime(["2024-01-02"]))
    daily = dtb3_to_daily(dtb3)
    holding = 0.05 * 91 / (360 - 0.05 * 91)
    assert daily.iloc[0] == pytest.approx((1 + holding) ** (365 / 91 / 252) - 1)
    assert daily.index[0] == pd.Timestamp("2024-01-03")
