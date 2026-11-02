"""Preparación de series: validación del índice temporal, faltantes y transformaciones."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from tsinsurance._types import FREQUENCIES, Frequency
from tsinsurance.errors import DataValidationError, InsufficientDataError
from tsinsurance.results import ResultMixin

__all__ = ["PreparedSeries", "prepare", "regular_index"]

Transform = Literal["none", "simple", "log", "diff"]
MissingMethod = Literal["drop", "ffill", "interpolate", "error"]


@dataclass(frozen=True, slots=True, eq=False)
class PreparedSeries(ResultMixin):
    """Serie lista para el análisis, con el registro de lo que se hizo.

    Attributes
    ----------
    data : pandas.Series
        Serie resultante con ``DatetimeIndex``.
    frequency : str
        Frecuencia validada (``D``, ``B``, ``W`` o ``M``).
    transform : str
        Transformación aplicada.
    missing_method : str
        Método de tratamiento de faltantes.
    n_input : int
        Observaciones recibidas.
    n_missing : int
        Faltantes detectados sobre la malla regular (incluye fechas ausentes).
    n_imputed : int
        Valores imputados.
    n_dropped : int
        Observaciones eliminadas (faltantes o primera observación de la transformación).
    log : tuple[str, ...]
        Registro legible de cada paso.
    """

    data: pd.Series
    frequency: str
    transform: str
    missing_method: str
    n_input: int
    n_missing: int
    n_imputed: int
    n_dropped: int
    log: tuple[str, ...]

    def summary(self) -> str:
        """Resumen del procesamiento."""
        name = self.data.name if self.data.name is not None else "serie"
        lines = [
            f"Serie preparada '{name}': {len(self.data)} obs, frecuencia {self.frequency}, "
            f"transformación '{self.transform}', faltantes '{self.missing_method}'",
        ]
        lines.extend(f"  - {entry}" for entry in self.log)
        return "\n".join(lines)


def regular_index(index: pd.DatetimeIndex, freq: Frequency) -> pd.DatetimeIndex:
    """Malla regular de fechas para ``freq`` que cubre ``index``.

    Raises
    ------
    DataValidationError
        Si las observaciones no son compatibles con la frecuencia declarada.
    """
    start, end = index[0], index[-1]
    if freq == "D":
        grid = pd.date_range(start, end, freq="D")
    elif freq == "B":
        if (index.day_of_week >= 5).any():
            raise DataValidationError("Frecuencia 'B' declarada pero hay fechas en fin de semana.")
        grid = pd.date_range(start, end, freq="B")
    elif freq == "W":
        days = set(index.day_of_week)
        if len(days) != 1:
            raise DataValidationError(
                "Frecuencia 'W' requiere que todas las observaciones caigan "
                "el mismo día de la semana."
            )
        anchor = start.day_name()[:3].upper()
        grid = pd.date_range(start, end, freq=f"W-{anchor}")
    elif freq == "M":
        periods = index.to_period("M")
        if periods.has_duplicates:
            raise DataValidationError(
                "Frecuencia 'M' declarada pero hay dos observaciones en un mes."
            )
        grid = pd.period_range(periods[0], periods[-1], freq="M").to_timestamp(how="start")
    else:
        raise DataValidationError(f"Frecuencia '{freq}' no soportada. Use una de {FREQUENCIES}.")
    grid.name = index.name
    return grid


def _as_series(series: pd.Series | pd.DataFrame) -> pd.Series:
    if isinstance(series, pd.DataFrame):
        if series.shape[1] != 1:
            raise DataValidationError(
                "prepare() recibe una sola serie; use una columna del DataFrame."
            )
        series = series.iloc[:, 0]
    if not isinstance(series, pd.Series):
        raise DataValidationError("Se esperaba un pandas.Series.")
    if not isinstance(series.index, pd.DatetimeIndex):
        try:
            series = series.copy()
            series.index = pd.DatetimeIndex(series.index)
        except (TypeError, ValueError) as exc:
            raise DataValidationError("El índice debe ser de fechas (DatetimeIndex).") from exc
    if series.index.tz is not None:
        series = series.tz_localize(None)
    return series.astype(float)


def prepare(
    series: pd.Series | pd.DataFrame,
    *,
    freq: Frequency,
    transform: Transform = "none",
    missing: MissingMethod = "error",
) -> PreparedSeries:
    """Valida, alinea, trata faltantes y transforma una serie.

    Pasos (en orden, sin usar información futura salvo en ``interpolate``):

    1. Índice de fechas monótono creciente y sin duplicados.
    2. Alineación a una malla regular de la frecuencia ``freq``; las fechas
       ausentes se convierten en faltantes explícitos.
    3. Tratamiento de faltantes con ``missing``.
    4. Transformación ``transform``: ``simple`` (retorno simple), ``log`` (retorno
       logarítmico, exige valores > 0) o ``diff`` (primera diferencia).

    Parameters
    ----------
    series : pandas.Series
        Serie con índice de fechas.
    freq : {"D", "B", "W", "M"}
        Frecuencia declarada.
    transform : {"none", "simple", "log", "diff"}
        Transformación a aplicar.
    missing : {"drop", "ffill", "interpolate", "error"}
        ``interpolate`` usa el valor siguiente: no debe usarse antes de validar
        pronósticos fuera de muestra (Principio II).

    Returns
    -------
    PreparedSeries
    """
    s = _as_series(series)
    n_input = len(s)
    log: list[str] = []
    if n_input < 2:
        raise InsufficientDataError("prepare", required=2, actual=n_input)
    if s.index.has_duplicates:
        dups = s.index[s.index.duplicated()].unique()
        raise DataValidationError(f"Fechas duplicadas en el índice: {list(dups[:5])}")
    if not s.index.is_monotonic_increasing:
        raise DataValidationError("El índice de fechas no es monótono creciente.")

    idx = pd.DatetimeIndex(s.index)
    if freq == "M":
        idx = idx.to_period("M").to_timestamp(how="start")
        s.index = idx
    grid = regular_index(idx, freq)
    aligned = s.reindex(grid)
    n_missing = int(aligned.isna().sum())
    if len(aligned) != n_input:
        log.append(f"{len(aligned) - n_input} fecha(s) ausente(s) agregada(s) como faltante.")
    log.append(f"{n_missing} faltante(s) detectado(s) sobre la malla '{freq}'.")

    n_imputed = 0
    n_dropped = 0
    if n_missing:
        if missing == "error":
            raise DataValidationError(
                f"La serie tiene {n_missing} faltante(s) sobre la malla '{freq}'; "
                "elija missing='drop', 'ffill' o 'interpolate'."
            )
        if missing == "drop":
            aligned = aligned.dropna()
            n_dropped += n_missing
            log.append(f"{n_missing} faltante(s) eliminado(s).")
        elif missing in {"ffill", "interpolate"}:
            filled = aligned.ffill() if missing == "ffill" else aligned.interpolate(method="time")
            leading = int(filled.isna().sum())
            n_imputed = n_missing - leading
            aligned = filled.dropna()
            n_dropped += leading
            log.append(f"{n_imputed} valor(es) imputado(s) con '{missing}'.")
            if leading:
                log.append(f"{leading} faltante(s) inicial(es) eliminado(s) (sin valor previo).")
        else:
            raise DataValidationError(f"Método de faltantes desconocido: '{missing}'.")

    if transform == "none":
        out = aligned
    elif transform == "simple":
        out = aligned / aligned.shift(1) - 1.0
    elif transform == "log":
        if (aligned <= 0).any():
            raise DataValidationError(
                "Retornos logarítmicos requieren valores estrictamente positivos."
            )
        out = pd.Series(np.log(aligned.to_numpy()), index=aligned.index, name=aligned.name).diff()
    elif transform == "diff":
        out = aligned.diff()
    else:
        raise DataValidationError(f"Transformación desconocida: '{transform}'.")
    if transform != "none":
        out = out.iloc[1:]
        n_dropped += 1
        log.append(f"Transformación '{transform}' aplicada (se pierde la primera observación).")
    if len(out) < 2:
        raise InsufficientDataError("prepare", required=2, actual=len(out))
    out.name = s.name
    out_index = pd.DatetimeIndex(out.index)
    if missing == "drop" and n_missing:
        out_index = pd.DatetimeIndex(out_index.to_numpy(), name=out_index.name)
    elif out_index.freq is None and len(out_index) > 2:
        inferred = pd.infer_freq(out_index)
        if inferred is not None:
            out_index = pd.DatetimeIndex(out_index, freq=inferred)
    out.index = out_index
    return PreparedSeries(
        data=out,
        frequency=freq,
        transform=transform,
        missing_method=missing,
        n_input=n_input,
        n_missing=n_missing,
        n_imputed=n_imputed,
        n_dropped=n_dropped,
        log=tuple(log),
    )
