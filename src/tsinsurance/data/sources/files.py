"""Conectores a archivos locales CSV y Excel."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from tsinsurance.data.schemas import InputKind
from tsinsurance.data.snapshot import Snapshot
from tsinsurance.data.sources.base import DateLike, to_timestamp
from tsinsurance.data.validate import load, read_table

__all__ = ["CSVSource", "ExcelSource"]


class _FileSource:
    name = "file"

    def __init__(
        self, path: str | os.PathLike[str], kind: InputKind = "market", sheet: str | int = 0
    ) -> None:
        self.path = Path(path)
        self.kind: InputKind = kind
        self.sheet = sheet

    def fetch(
        self, ids: Sequence[str] | None = None, start: DateLike = None, end: DateLike = None
    ) -> Snapshot:
        """Lee, valida y filtra el archivo; devuelve una :class:`Snapshot`."""
        raw = read_table(self.path, sheet=self.sheet)
        data = load(raw, self.kind)
        id_col = {"market": "series_id", "portfolio": "asset_id", "rate_nodes": "curve_id"}[
            self.kind
        ]
        date_col = "as_of" if self.kind == "portfolio" else "date"
        if ids is not None:
            data = data[data[id_col].isin(list(ids))]
        lo, hi = to_timestamp(start), to_timestamp(end)
        if lo is not None:
            data = data[data[date_col] >= pd.Timestamp(lo)]
        if hi is not None:
            data = data[data[date_col] <= pd.Timestamp(hi)]
        query = {
            "path": self.path.name,
            "ids": None if ids is None else list(ids),
            "start": None if lo is None else lo.isoformat(),
            "end": None if hi is None else hi.isoformat(),
        }
        return Snapshot.create(data, kind=self.kind, source=f"file:{self.path.name}", query=query)


class CSVSource(_FileSource):
    """Conector a un archivo CSV que cumple el contrato de datos."""

    name = "csv"


class ExcelSource(_FileSource):
    """Conector a un archivo Excel (hoja ``sheet``) que cumple el contrato de datos."""

    name = "excel"
