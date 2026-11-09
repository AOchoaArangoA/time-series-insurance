"""Ejercicios de backtesting con ETFs reales: sin red y reproducibles (SC-007)."""

import json
import runpy
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).parents[2] / "examples"
DATA = EXAMPLES / "data"
EXPECTED = json.loads((DATA / "expected_sha256.json").read_text(encoding="utf-8"))

# Datos de terceros no redistribuibles: se omiten si no se regeneraron con
# examples/fetch_data.py; las cifras fijadas sólo se comparan con la instantánea publicada.
pytestmark = pytest.mark.skipif(
    not all((DATA / n / "metadata.json").exists() for n in EXPECTED),
    reason="instantáneas de terceros no descargadas (examples/fetch_data.py)",
)


def _published() -> bool:
    return all(
        json.loads((DATA / n / "metadata.json").read_text())["sha256"] == sha
        for n, sha in EXPECTED.items()
    )


PINNED = {"oos_r2": -0.1411, "sharpe_model": 0.3736, "quadrant": "solo_estadistica"}


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
    if not _published():
        return  # datos regenerados distintos de los publicados: sólo se verifica reproducibilidad
    # Huella fijada de los resultados (redondeo a 4 decimales, portable entre plataformas).
    assert round(float(long_cash["oos_r2"]), 4) == PINNED["oos_r2"]
    assert round(float(long_cash["sharpe_model"]), 4) == PINNED["sharpe_model"]
    assert long_cash["quadrant"] == PINNED["quadrant"]
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
