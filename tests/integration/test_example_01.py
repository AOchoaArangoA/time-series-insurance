"""Ejercicio 01 reproducible desde la instantánea versionada (SC-009, sin red)."""

import runpy
import sys
from pathlib import Path

import pandas as pd
import pytest

from tsinsurance.data import Snapshot, prepare, to_wide
from tsinsurance.diagnostics import stationarity

EXAMPLE = Path(__file__).parents[2] / "examples" / "01_diagnostico_tasas_fred.py"
SNAPSHOT = EXAMPLE.parent / "data" / "fred_gs10"
EXPECTED_SHA = "e6bb192cce25f78e72d7e2720cb3d8b57abbd6d93b1cbea9b31716dbc96f948c"


def test_snapshot_integrity() -> None:
    snap = Snapshot.load(SNAPSHOT)
    assert snap.sha256 == EXPECTED_SHA
    assert snap.source == "fred" and snap.query["ids"] == ["GS10"]


def test_gs10_diagnosis_is_reproducible() -> None:
    wide = to_wide(Snapshot.load(SNAPSHOT).data)
    level = prepare(wide["GS10"], freq="M").data
    a = stationarity(level)
    b = stationarity(level)
    assert a.to_json() == b.to_json()
    assert a.conclusion == "I(1)"
    assert a.break_date is not None and not a.break_significant
    assert a.break_date.to_period("M") == pd.Period("2020-08", "M")


def test_example_runs_offline(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", [str(EXAMPLE)])
    runpy.run_path(str(EXAMPLE), run_name="__main__")
    out = capsys.readouterr().out
    assert "Conclusión: I(1)" in out and "e6bb192cce25" in out
