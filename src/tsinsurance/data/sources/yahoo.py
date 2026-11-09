"""Conector a Yahoo Finance mediante ``yfinance`` (extra opcional ``[yahoo]``).

Yahoo Finance no es una fuente oficial; por eso cada descarga debe guardarse como
instantánea para garantizar la replicabilidad.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from typing import Any

import pandas as pd

from tsinsurance.data.snapshot import Snapshot
from tsinsurance.data.sources.base import DateLike, to_timestamp
from tsinsurance.data.validate import load
from tsinsurance.errors import TSInsuranceError

__all__ = ["YahooSource"]


def _default_download(ticker: str, start: str | None, end: str | None) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise TSInsuranceError(
            "Instale el extra opcional: pip install 'tsinsurance[yahoo]'"
        ) from exc
    frame: pd.DataFrame = yf.download(
        ticker, start=start, end=end, progress=False, auto_adjust=True, multi_level_index=False
    )
    return frame


class YahooSource:
    """Descarga precios de cierre ajustados de Yahoo Finance (contrato ``market``).

    Parameters
    ----------
    currency : str
        Moneda ISO 4217 de los precios.
    download : callable, optional
        Función ``(ticker, start, end) -> DataFrame`` con columna ``Close``
        (inyectable para pruebas sin red).
    """

    name = "yahoo"

    def __init__(
        self,
        *,
        currency: str = "USD",
        download: Callable[[str, str | None, str | None], pd.DataFrame] | None = None,
    ) -> None:
        self.currency = currency
        self._download = download or _default_download

    def fetch(
        self, ids: Sequence[str] | None = None, start: DateLike = None, end: DateLike = None
    ) -> Snapshot:
        """Descarga los tickers ``ids``; ``end`` es inclusivo."""
        if not ids:
            raise TSInsuranceError("Indique al menos un ticker.")
        lo, hi = to_timestamp(start), to_timestamp(end)
        s = None if lo is None else lo.isoformat()
        # yfinance trata `end` como exclusivo.
        e = None if hi is None else (hi + dt.timedelta(days=1)).isoformat()
        frames: list[pd.DataFrame] = []
        for ticker in ids:
            raw = self._download(ticker, s, e)
            if raw.empty or "Close" not in raw:
                raise TSInsuranceError(f"Yahoo no devolvió precios para '{ticker}'.")
            close = raw["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            frames.append(
                pd.DataFrame(
                    {
                        "date": pd.DatetimeIndex(close.index).tz_localize(None).normalize(),
                        "series_id": ticker,
                        "value": close.to_numpy(dtype=float),
                        "kind": "price",
                        "unit": "level",
                        "currency": self.currency,
                        "frequency": "B",
                        "source": f"yahoo:{ticker}",
                    }
                )
            )
        data = load(pd.concat(frames, ignore_index=True), "market")
        query: dict[str, Any] = {
            "ids": list(ids),
            "start": s,
            "end": None if hi is None else hi.isoformat(),
            "field": "Close (auto_adjust=True)",
        }
        return Snapshot.create(data, kind="market", source="yahoo", query=query)
