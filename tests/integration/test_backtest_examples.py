"""Ejercicios de backtesting con ETFs reales: sin red y reproducibles (SC-007)."""

import json
import runpy
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).parents[2] / "examples"


def _run(script: str, report: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", [script, "--report", str(report)])
    runpy.run_path(str(EXAMPLES / script), run_name="__main__")
    data: dict[str, object] = json.loads(report.read_text(encoding="utf-8"))
    return data


def test_macro_tlt_is_reproducible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    a = _run("backtest_02_macro_tlt.py", tmp_path / "a.json", monkeypatch)
    b = _run("backtest_02_macro_tlt.py", tmp_path / "b.json", monkeypatch)
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()
    assert a == b
    long_cash = a["long_cash"]
    assert isinstance(long_cash, dict) and long_cash["exploratory"] is True
    assert long_cash["quadrant"] in {
        "estadistica_y_economica",
        "solo_estadistica",
        "solo_economica",
        "sin_evidencia",
    }


@pytest.mark.slow
def test_etf_trend_vol_is_reproducible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    a = _run("backtest_01_tendencia_volatilidad_etfs.py", tmp_path / "a.json", monkeypatch)
    b = _run("backtest_01_tendencia_volatilidad_etfs.py", tmp_path / "b.json", monkeypatch)
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()
    assert a == b and set(a) >= {"TLT_tendencia", "sweep_trend", "calibration"}
