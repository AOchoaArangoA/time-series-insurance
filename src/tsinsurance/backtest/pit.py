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

    def _on_calendar(self) -> pd.Series:
        """Serie sobre el calendario completo de su frecuencia (huecos = NaN)."""
        s = self.series.astype(float).sort_index()
        idx = pd.DatetimeIndex(s.index)
        if self.frequency in ("M", "W"):
            per = idx.to_period("M" if self.frequency == "M" else "W")
            s = pd.Series(s.to_numpy(), index=per).groupby(level=0).last()
            full = pd.period_range(per.min(), per.max(), freq=per.freq)
            s = s.reindex(full)
            s.index = full.start_time
            return s
        grid = (pd.bdate_range if self.frequency == "B" else pd.date_range)(idx.min(), idx.max())
        return s.reindex(grid.union(idx))

    def transformed(self) -> pd.Series:
        """Serie transformada, indexada por fecha de observación.

        Las diferencias y variaciones se calculan **por fecha** sobre el calendario de la
        frecuencia: un dato faltante deja NaN en lugar de comparar contra el periodo
        equivocado.
        """
        s = self._on_calendar()
        if self.transform == "level":
            out = s
        elif self.transform == "diff":
            out = s.diff()
        elif self.transform == "pct_change":
            out = s.pct_change(fill_method=None)
        else:
            periods = _PERIODS_PER_YEAR[self.frequency] if self.frequency != "D" else 365
            out = s.pct_change(periods, fill_method=None)
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
    out.attrs["point_in_time"] = all(ex.point_in_time for ex in exogs)
    out.attrs["not_point_in_time"] = [ex.name for ex in exogs if not ex.point_in_time]
    return out


def monthly_decision_dates(
    prices: pd.Series | pd.DataFrame, *, complete_only: bool = True
) -> pd.DatetimeIndex:
    """Último día con precio de cada mes (fecha de decisión mensual).

    Con ``complete_only`` se descarta el último mes si sus datos terminan antes del
    último día hábil del mes (mes incompleto).
    """
    idx = pd.DatetimeIndex(prices.index)
    last = pd.DatetimeIndex(pd.Series(idx, index=idx).groupby(idx.to_period("M")).max())
    if complete_only and len(last):
        final = last[-1]
        month_end = (final + pd.offsets.BMonthEnd(0)).normalize()
        if final.normalize() < month_end:
            last = last[:-1]
    return pd.DatetimeIndex(last, name="date")


def monthly_returns(prices: pd.Series) -> pd.Series:
    """Retornos de cierre de fin de mes a cierre de fin de mes, fechados en el cierre."""
    dates = monthly_decision_dates(prices)
    px = prices.astype(float).loc[dates]
    out: pd.Series = (px / px.shift(1) - 1.0).dropna()
    out.name = prices.name
    return out


def dtb3_to_daily(dtb3: pd.Series, *, days_to_maturity: int = 91, lag: str = "1B") -> pd.Series:
    """Convierte la tasa de descuento de letras (DTB3, % anual) en tasa diaria.

    Retorno de la letra al vencimiento ``R = d·n / (360 − d·n)``; tasa efectiva anual
    ``(1 + R)^{365/n} − 1``; tasa por día hábil ``(1 + efectiva)^{1/252} − 1``. El índice
    se desplaza ``lag`` (publicación al día hábil siguiente). Nota: el motor aplica
    además la tasa conocida el día anterior, de modo que el periodo ``t`` usa la DTB3
    observada en ``t − 2`` (conservador, declarado).
    """
    d = dtb3.astype(float).dropna() / 100.0
    n = float(days_to_maturity)
    holding = d * n / (360.0 - d * n)
    effective = (1.0 + holding) ** (365.0 / n) - 1.0
    daily = (1.0 + effective) ** (1.0 / 252.0) - 1.0
    daily.index = pd.DatetimeIndex(daily.index) + to_offset(lag)
    return daily.rename("rf_daily")
