"""Descargas reales (marca ``network``; excluidas por defecto). Ejecutar con ``-m network``."""

import os

import pytest

from tsinsurance.data.sources import get_source

pytestmark = pytest.mark.network


@pytest.mark.skipif(not os.environ.get("FRED_API_KEY"), reason="requiere FRED_API_KEY")
def test_fred_live() -> None:
    snap = get_source("fred").fetch(["DGS10"], "2024-01-01", "2024-01-31")
    assert len(snap.data) > 15 and snap.data["unit"].iloc[0] == "percent"


def test_yahoo_live() -> None:
    pytest.importorskip("yfinance")
    snap = get_source("yahoo").fetch(["^GSPC"], "2024-01-02", "2024-01-31")
    assert len(snap.data) > 15
