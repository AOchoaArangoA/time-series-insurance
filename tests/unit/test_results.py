import json
import math

import numpy as np
import pandas as pd
import pytest

from tsinsurance.results import HypothesisTestResult, to_jsonable


def make(p: float | None = 0.03, stat: float = -3.1) -> HypothesisTestResult:
    return HypothesisTestResult(
        name="ADF",
        statistic=stat,
        p_value=p,
        null_hypothesis="raíz unitaria",
        critical_values={"1%": -3.43, "5%": -2.86, "10%": -2.57},
        specification={"trend": "c", "lags": 2},
        reference="Dickey & Fuller (1979)",
    )


def test_reject_at_levels() -> None:
    assert make(0.03).reject_at == {"1%": False, "5%": True, "10%": True}


def test_rejects_with_critical_values_when_no_p_value() -> None:
    r = make(p=None, stat=-3.0)
    assert r.rejects(0.05) and not r.rejects(0.01)
    upper = HypothesisTestResult(
        "KPSS", 0.5, None, "estacionaria", {"5%": 0.463}, {"lower_tail": False}
    )
    assert upper.rejects(0.05)
    with pytest.raises(ValueError):
        upper.rejects(0.02)


def test_is_frozen() -> None:
    r = make()
    with pytest.raises(AttributeError):
        r.statistic = 0.0  # type: ignore[misc]


def test_summary_and_json_roundtrip() -> None:
    r = make()
    text = r.summary()
    assert "ADF" in text and "H0" in text and "5%" in text
    data = json.loads(r.to_json())
    assert data["name"] == "ADF" and data["specification"]["lags"] == 2
    assert r.to_json() == make().to_json()  # determinista


def test_to_jsonable_handles_numpy_pandas_and_nan() -> None:
    idx = pd.date_range("2024-01-01", periods=2)
    obj = {
        "a": np.float64(math.nan),
        "b": np.int64(3),
        "s": pd.Series([1.0, 2.0], index=idx),
        "d": pd.DataFrame({"x": [1, 2]}, index=idx),
        "t": pd.Timestamp("2024-01-01"),
        "arr": np.array([1.0, np.inf]),
        "flag": np.bool_(True),
        "other": complex(1, 2),
    }
    out = to_jsonable(obj)
    assert out["a"] is None and out["b"] == 3
    assert out["s"]["2024-01-01T00:00:00"] == 1.0
    assert out["d"]["x"]["2024-01-02T00:00:00"] == 2
    assert out["arr"] == [1.0, None] and out["flag"] is True
    json.dumps(out)
