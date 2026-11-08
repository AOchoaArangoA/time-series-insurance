"""Prueba automática de sesgo de anticipación (*look-ahead*).

Compara la señal calculada con todos los datos frente a la calculada con datos
truncados en varias fechas de corte. Si una señal es causal, ambas coinciden en todas
las fechas hasta el corte. Las :class:`Exogenous` se truncan por **fecha de
disponibilidad**, de modo que también se detecta un rezago de publicación omitido.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from tsinsurance.backtest.pit import Exogenous
from tsinsurance.errors import LookaheadBiasError, TSInsuranceError
from tsinsurance.results import ResultMixin

__all__ = ["LookaheadReport", "check_lookahead"]


@dataclass(frozen=True, slots=True, eq=False)
class LookaheadReport(ResultMixin):
    """Resultado de la prueba de anticipación."""

    has_lookahead: bool
    cuts: tuple[pd.Timestamp, ...]
    affected_dates: tuple[pd.Timestamp, ...]
    max_abs_diff: float
    skipped_cuts: int = 0

    def raise_if_biased(self) -> None:
        """Lanza :class:`LookaheadBiasError` si se detectó anticipación."""
        if self.has_lookahead:
            raise LookaheadBiasError(self.summary())

    def summary(self) -> str:
        """Resumen legible."""
        if not self.has_lookahead:
            return (
                f"Sin anticipación detectada en {len(self.cuts)} cortes "
                f"({self.skipped_cuts} omitidos por datos insuficientes)."
            )
        first = ", ".join(str(d.date()) for d in self.affected_dates[:5])
        return (
            f"ANTICIPACIÓN DETECTADA: {len(self.affected_dates)} fecha(s) cambian al truncar "
            f"los datos (p. ej. {first}); diferencia máxima {self.max_abs_diff:.3g}. "
            "El backtest no es válido."
        )


def _truncate(obj: Any, cut: pd.Timestamp) -> Any:
    if isinstance(obj, Exogenous):
        return obj.truncate_available(cut)
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        return obj.loc[:cut]
    if isinstance(obj, Mapping):
        return {k: _truncate(v, cut) for k, v in obj.items()}
    if isinstance(obj, Sequence) and not isinstance(obj, str):
        return [_truncate(v, cut) for v in obj]
    return obj


def _index_of(obj: Any) -> pd.DatetimeIndex:
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        return pd.DatetimeIndex(obj.index)
    if isinstance(obj, Mapping):
        for v in obj.values():
            if isinstance(v, (pd.DataFrame, pd.Series)):
                return pd.DatetimeIndex(v.index)
    raise TSInsuranceError("data debe contener al menos un DataFrame o Series con fechas.")


def _as_frame(x: pd.Series | pd.DataFrame) -> pd.DataFrame:
    return x.to_frame() if isinstance(x, pd.Series) else x


def check_lookahead(
    signal_fn: Callable[[Any], pd.Series | pd.DataFrame],
    data: Any,
    *,
    n_cuts: int = 10,
    seed: int = 0,
    tol: float = 1e-10,
) -> LookaheadReport:
    """Detecta si ``signal_fn`` usa información posterior a cada fecha.

    Parameters
    ----------
    signal_fn : callable
        Función ``data -> señal`` (Series o DataFrame con índice de fechas).
    data : DataFrame, Series o Mapping
        Entradas de la señal. Un ``Mapping`` puede contener DataFrames, Series,
        :class:`Exogenous` o listas de ellas.
    n_cuts : int
        Cortes aleatorios adicionales a los deterministas (posiciones 5, 20, 60, 250,
        n/4, n/2, n−3 y n−2 del índice principal).
    seed : int
        Semilla de los cortes aleatorios.
    tol : float
        Tolerancia numérica; un valor frente a ``NaN`` siempre cuenta como diferencia.
    """
    full = _as_frame(signal_fn(data))
    index = _index_of(data)
    n = len(index)
    positions = {p for p in (5, 20, 60, 250, n // 4, n // 2, n - 3, n - 2) if 0 <= p < n - 1}
    rng = np.random.default_rng(seed)
    if n > 3:
        positions |= set(rng.integers(1, n - 1, size=n_cuts).tolist())
    cuts = sorted(index[p] for p in positions)
    affected: set[pd.Timestamp] = set()
    max_diff = 0.0
    skipped = 0
    for cut in cuts:
        try:
            part = _as_frame(signal_fn(_truncate(data, cut)))
        except (TSInsuranceError, ValueError):
            skipped += 1
            continue
        ref = full.loc[:cut].reindex(columns=part.columns)
        part = part.loc[:cut].reindex(ref.index)
        a, b = ref.to_numpy(dtype=float), part.to_numpy(dtype=float)
        nan_mismatch = np.isnan(a) != np.isnan(b)
        both = ~np.isnan(a) & ~np.isnan(b)
        diff = np.where(both, np.abs(a - b), 0.0)
        bad = nan_mismatch | (diff > tol)
        if bad.any():
            rows = np.where(bad.any(axis=1))[0]
            affected.update(ref.index[rows])
            max_diff = max(max_diff, float(diff.max()) if both.any() else 0.0)
            if nan_mismatch.any():
                max_diff = max(max_diff, float("inf"))
    return LookaheadReport(
        has_lookahead=bool(affected),
        cuts=tuple(cuts),
        affected_dates=tuple(sorted(affected)),
        max_abs_diff=max_diff,
        skipped_cuts=skipped,
    )
