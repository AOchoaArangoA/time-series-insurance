"""Conector a FRED (Federal Reserve Bank of St. Louis).

Usa la API REST oficial (``https://api.stlouisfed.org/fred``) con la biblioteca
estándar. La clave se lee de la variable de entorno ``FRED_API_KEY`` y nunca se
registra en la instantánea ni en los mensajes de error.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import pandas as pd

from tsinsurance.data.snapshot import Snapshot
from tsinsurance.data.sources.base import DateLike, to_timestamp
from tsinsurance.data.validate import load
from tsinsurance.errors import TSInsuranceError

__all__ = ["FredSource"]

BASE_URL = "https://api.stlouisfed.org/fred"
_FREQ = {"D": "B", "W": "W", "M": "M"}


def _default_http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "tsinsurance"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - URL fija https
        data: bytes = resp.read()
    return data


class FredSource:
    """Descarga series de FRED en el formato del contrato ``market``.

    Parameters
    ----------
    api_key : str, optional
        Clave de FRED; por defecto ``os.environ["FRED_API_KEY"]``.
    currency : str
        Moneda ISO 4217 a registrar (FRED publica mayoritariamente series en USD).
    http_get : callable, optional
        Función ``url -> bytes`` (inyectable para pruebas sin red).
    """

    name = "fred"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        currency: str = "USD",
        http_get: Callable[[str], bytes] | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("FRED_API_KEY")
        self.currency = currency
        self._get = http_get or _default_http_get

    def _call(self, endpoint: str, **params: str) -> dict[str, Any]:
        if not self._api_key:
            raise TSInsuranceError(
                "FRED requiere una clave de API: defina la variable de entorno FRED_API_KEY."
            )
        query = urllib.parse.urlencode({**params, "api_key": self._api_key, "file_type": "json"})
        try:
            payload = self._get(f"{BASE_URL}/{endpoint}?{query}")
        except urllib.error.HTTPError as exc:
            raise TSInsuranceError(
                f"FRED respondió HTTP {exc.code} en '{endpoint}' para {params}."
            ) from None
        out: dict[str, Any] = json.loads(payload)
        return out

    def _series_frame(self, series_id: str, start: str | None, end: str | None) -> pd.DataFrame:
        info = self._call("series", series_id=series_id)["seriess"][0]
        freq = _FREQ.get(str(info.get("frequency_short", "")).upper())
        if freq is None:
            raise TSInsuranceError(
                f"Frecuencia FRED '{info.get('frequency_short')}' de {series_id} no soportada "
                "(use series diarias, semanales o mensuales)."
            )
        units = str(info.get("units", ""))
        is_percent = "percent" in units.lower()
        params = {"series_id": series_id}
        if start:
            params["observation_start"] = start
        if end:
            params["observation_end"] = end
        obs = self._call("series/observations", **params)["observations"]
        values = [np.nan if o["value"] in {".", ""} else float(o["value"]) for o in obs]
        return pd.DataFrame(
            {
                "date": pd.to_datetime([o["date"] for o in obs]),
                "series_id": series_id,
                "value": values,
                "kind": "rate" if is_percent else "index",
                "unit": "percent" if is_percent else "level",
                "currency": self.currency,
                "frequency": freq,
                "source": f"fred:{series_id}",
            }
        )

    def fetch(
        self, ids: Sequence[str] | None = None, start: DateLike = None, end: DateLike = None
    ) -> Snapshot:
        """Descarga ``ids`` y devuelve una instantánea validada contra el contrato."""
        if not ids:
            raise TSInsuranceError("Indique al menos un identificador de serie FRED.")
        lo, hi = to_timestamp(start), to_timestamp(end)
        s = None if lo is None else lo.isoformat()
        e = None if hi is None else hi.isoformat()
        frames = [self._series_frame(i, s, e) for i in ids]
        data = load(pd.concat(frames, ignore_index=True), "market")
        query = {"ids": list(ids), "start": s, "end": e, "units": "lin"}
        return Snapshot.create(data, kind="market", source="fred", query=query)
