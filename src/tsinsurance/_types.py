"""Alias de tipos compartidos."""

from __future__ import annotations

from typing import Literal, TypeAlias

import pandas as pd

Frequency: TypeAlias = Literal["D", "B", "W", "M"]
"""Frecuencias soportadas: diaria, días hábiles, semanal y mensual."""

SeriesKind: TypeAlias = Literal["price", "return", "rate", "index"]
Unit: TypeAlias = Literal["level", "percent", "decimal", "bps"]
Trend: TypeAlias = Literal["c", "ct"]
SeriesLike: TypeAlias = "pd.Series[float]"

FREQUENCIES: tuple[str, ...] = ("D", "B", "W", "M")
