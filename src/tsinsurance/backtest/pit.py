"""Datos punto-en-el-tiempo: rezagos de publicación y fechas de decisión.

Una observación con fecha de periodo ``p`` sólo se considera disponible en
``fin_de_periodo(p) + release_lag``. Todas las alineaciones son hacia atrás
(``merge_asof``): nunca se usa un valor antes de que se publique.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from pandas.tseries.frequencies import to_offset
from pandas.tseries.offsets import BaseOffset

from tsinsurance.errors import DataValidationError

__all__ = [
    "Exogenous",
    "align_point_in_time",
    "dtb3_to_daily",
    "monthly_decision_dates",
    "monthly_returns",
]

Transform = Literal["level", "diff", "pct_change", "yoy"]
_PERIODS_PER_YEAR = {"B": 252, "D": 365, "W": 52, "M": 12}


@dataclass(frozen=True, slots=True, eq=False)
class Exogenous:
    """Variable explicativa con su rezago de publicación.

    Parameters
    ----------
    name : str
    series : pandas.Series
        Observaciones indexadas por la fecha del periodo (p. ej. FRED fecha los meses
        el día 1).
    frequency : {"B", "D", "W", "M"}
    release_lag : str or DateOffset
        Tiempo desde el **fin del periodo** hasta la publicación (p. ej. ``"1B"`` para
        tasas de mercado, ``"20D"`` para el IPC).
    transform : {"level", "diff", "pct_change", "yoy"}
        Transformación aplicada sobre las observaciones (antes de alinear).
    point_in_time : bool
        ``False`` si la serie se revisa y se usa su versión actual (no punto en el tiempo).
    """

    name: str
    series: pd.Series
    frequency: Literal["B", "D", "W", "M"]
    release_lag: str | BaseOffset = "0D"
    transform: Transform = "level"
    point_in_time: bool = True

    def __post_init__(self) -> None:
        if self.frequency not in _PERIODS_PER_YEAR:
            raise DataValidationError(f"{self.name}: frecuencia '{self.frequency}' no soportada.")
        if not isinstance(self.series.index, pd.DatetimeIndex):
            raise DataValidationError(f"{self.name}: el índice debe ser DatetimeIndex.")

    @property
    def lag_offset(self) -> BaseOffset:
        """Rezago de publicación como ``DateOffset``."""
        return to_offset(self.release_lag)

    def availability(self, index: pd.DatetimeIndex | None = None) -> pd.DatetimeIndex:
        """Fecha de disponibilidad de cada observación."""
        idx = pd.DatetimeIndex(self.series.index if index is None else index)
        if self.frequency in ("B", "D"):
            end = idx.normalize()
        else:
            end = idx.to_period("M" if self.frequency == "M" else "W").end_time.normalize()
        return pd.DatetimeIndex(end + self.lag_offset)

    def transformed(self) -> pd.Series:
        """Serie transformada, indexada por fecha de observación."""
        s = self.series.astype(float).dropna().sort_index()
        if self.transform == "level":
            out = s
        elif self.transform == "diff":
            out = s.diff()
        elif self.transform == "pct_change":
            out = s.pct_change()
        else:
            out = s.pct_change(_PERIODS_PER_YEAR[self.frequency] if self.frequency != "D" else 365)
        return out.dropna().rename(self.name)

    def available_series(self) -> pd.Series:
        """Valores transformados indexados por su fecha de disponibilidad."""
        t = self.transformed()
        return pd.Series(
            t.to_numpy(), index=self.availability(pd.DatetimeIndex(t.index)), name=self.name
        )

    def truncate_available(self, cut: pd.Timestamp) -> Exogenous:
        """Copia con sólo las observaciones publicadas hasta ``cut``."""
        avail = self.availability()
        return Exogenous(
            self.name,
            self.series[np.asarray(avail <= cut)],
            self.frequency,
            self.release_lag,
            self.transform,
            self.point_in_time,
        )


def align_point_in_time(
    exogs: Sequence[Exogenous], decision_dates: pd.DatetimeIndex
) -> pd.DataFrame:
    """Último valor publicado de cada variable en cada fecha de decisión."""
    dates = pd.DatetimeIndex(decision_dates).sort_values()
    left = pd.DataFrame({"date": dates.astype("datetime64[ns]")})
    out = pd.DataFrame(index=dates)
    for ex in exogs:
        avail = ex.available_series()
        right = pd.DataFrame(
            {"date": avail.index.astype("datetime64[ns]"), ex.name: avail.to_numpy()}
        ).sort_values("date")
        right = right.drop_duplicates("date", keep="last")
        merged = pd.merge_asof(left, right, on="date", direction="backward")
        out[ex.name] = merged[ex.name].to_numpy()
    return out


def monthly_decision_dates(prices: pd.Series | pd.DataFrame) -> pd.DatetimeIndex:
    """Último día con precio de cada mes (fecha de decisión mensual)."""
    idx = pd.DatetimeIndex(prices.index)
    last = pd.Series(idx, index=idx).groupby(idx.to_period("M")).max()
    return pd.DatetimeIndex(last.to_numpy(), name="date")


def monthly_returns(prices: pd.Series) -> pd.Series:
    """Retornos de cierre de fin de mes a cierre de fin de mes, fechados en el cierre."""
    dates = monthly_decision_dates(prices)
    px = prices.astype(float).loc[dates]
    out: pd.Series = (px / px.shift(1) - 1.0).dropna()
    out.name = prices.name
    return out


def dtb3_to_daily(dtb3: pd.Series, *, days_to_maturity: int = 91, lag: str = "1B") -> pd.Series:
    """Convierte la tasa de descuento de letras (DTB3, % anual) en tasa diaria.

    Rendimiento equivalente ``y = 365·d / (360 − n·d)``; tasa diaria
    ``(1 + y)^{1/252} − 1``. El índice se desplaza ``lag`` (fecha de disponibilidad).
    """
    d = dtb3.astype(float).dropna() / 100.0
    y = 365.0 * d / (360.0 - days_to_maturity * d)
    daily = (1.0 + y) ** (1.0 / 252.0) - 1.0
    daily.index = pd.DatetimeIndex(daily.index) + to_offset(lag)
    return daily.rename("rf_daily")
