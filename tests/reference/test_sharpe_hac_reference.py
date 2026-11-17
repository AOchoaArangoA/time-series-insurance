"""EE HAC (Newey-West) del Sharpe por periodo frente a sandwich de R, con valores guardados.

Los valores vienen de ``tests/reference/r/prewhite_reference.R`` y se versionan para que la
integración continua verifique sin R (spec 004, revisión I10).
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from tsinsurance.backtest import sharpe_se_hac

DATA = Path(__file__).parents[1] / "data" / "reference"


def test_newey_west_matches_sandwich() -> None:
    ref = json.loads((DATA / "prewhite_reference.json").read_text(encoding="utf-8"))
    r = pd.read_csv(DATA / ref["input"])["r"].to_numpy()
    assert len(r) == ref["n"]
    assert sharpe_se_hac(r) == pytest.approx(ref["se_newey_west"], rel=1e-10)


def test_constant_series_has_no_se() -> None:
    assert sharpe_se_hac(pd.Series([0.0] * 50)) != sharpe_se_hac(pd.Series([0.0] * 50))  # nan
