import json
import urllib.error
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from tsinsurance.data.sources import DataSource, available_sources, get_source, register_source
from tsinsurance.data.sources.fred import FredSource
from tsinsurance.data.sources.yahoo import YahooSource
from tsinsurance.errors import DataValidationError, TSInsuranceError

FIX = Path(__file__).parents[1] / "fixtures"


def fake_fred(urls: list[str]) -> Any:
    def get(url: str) -> bytes:
        urls.append(url)
        if "/series?" in url:
            return json.dumps({"seriess": [{"frequency_short": "D", "units": "Percent"}]}).encode()
        return json.dumps(
            {
                "observations": [
                    {"date": "2024-01-01", "value": "."},
                    {"date": "2024-01-02", "value": "3.95"},
                    {"date": "2024-01-03", "value": "3.91"},
                ]
            }
        ).encode()

    return get


def test_fred_fetch_without_network() -> None:
    urls: list[str] = []
    src = FredSource(api_key="SECRET", http_get=fake_fred(urls))
    snap = src.fetch(["DGS10"], "2024-01-01", "2024-01-03")
    df = snap.data
    assert snap.source == "fred" and snap.query["ids"] == ["DGS10"]
    assert df["value"].isna().sum() == 1
    assert set(df["kind"]) == {"rate"} and set(df["unit"]) == {"percent"}
    assert set(df["frequency"]) == {"B"}
    assert "SECRET" not in json.dumps(snap.metadata)
    assert all("api_key=SECRET" in u for u in urls)


def test_fred_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(TSInsuranceError, match="FRED_API_KEY"):
        FredSource(http_get=fake_fred([])).fetch(["DGS10"])
    with pytest.raises(TSInsuranceError, match="al menos"):
        FredSource(api_key="x").fetch([])


def test_fred_http_error_hides_key() -> None:
    def failing(url: str) -> bytes:
        raise urllib.error.HTTPError(url, 400, "Bad", {}, None)  # type: ignore[arg-type]

    with pytest.raises(TSInsuranceError) as info:
        FredSource(api_key="SECRET", http_get=failing).fetch(["XXX"])
    assert "SECRET" not in str(info.value) and "400" in str(info.value)


def test_fred_rejects_quarterly() -> None:
    def get(url: str) -> bytes:
        return json.dumps({"seriess": [{"frequency_short": "Q", "units": "Billions"}]}).encode()

    with pytest.raises(TSInsuranceError, match="no soportada"):
        FredSource(api_key="k", http_get=get).fetch(["GDP"])


def test_yahoo_fetch_without_network() -> None:
    calls: list[tuple[str, str | None, str | None]] = []

    def download(ticker: str, start: str | None, end: str | None) -> pd.DataFrame:
        calls.append((ticker, start, end))
        idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], tz="America/New_York")
        return pd.DataFrame({"Close": [4742.83, 4704.81]}, index=idx)

    snap = YahooSource(download=download).fetch(["^GSPC"], "2024-01-02", "2024-01-03")
    assert calls == [("^GSPC", "2024-01-02", "2024-01-04")]  # end exclusivo en yfinance
    assert snap.query["end"] == "2024-01-03"
    assert list(snap.data["value"]) == [4742.83, 4704.81]
    assert set(snap.data["kind"]) == {"price"}


def test_yahoo_empty_raises() -> None:
    src = YahooSource(download=lambda t, s, e: pd.DataFrame())
    with pytest.raises(TSInsuranceError, match="no devolvió"):
        src.fetch(["NOPE"])
    with pytest.raises(TSInsuranceError):
        src.fetch([])


def test_csv_source_filters() -> None:
    src = get_source("csv", path=FIX / "market_good.csv")
    assert isinstance(src, DataSource)
    snap = src.fetch(["SPX"], "2024-01-03", "2024-01-04")
    assert list(snap.data["series_id"].unique()) == ["SPX"] and len(snap.data) == 2
    assert snap.source == "file:market_good.csv"


def test_excel_source(tmp_path: Path) -> None:
    df = pd.read_csv(FIX / "market_good.csv")
    path = tmp_path / "m.xlsx"
    df.to_excel(path, index=False)
    assert len(get_source("excel", path=path).fetch().data) == 6


def test_csv_source_invalid_file() -> None:
    with pytest.raises(DataValidationError):
        get_source("csv", path=FIX / "market_bad.csv").fetch()


def test_registry() -> None:
    assert {"csv", "excel", "fred", "yahoo"} <= set(available_sources())
    register_source("dummy", lambda **kw: get_source("csv", **kw))
    assert "dummy" in available_sources()
    with pytest.raises(TSInsuranceError, match="no disponible"):
        get_source("bloomberg")
