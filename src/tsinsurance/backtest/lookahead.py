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

__all__ = ["MIN_VALID_CUTS", "LookaheadReport", "check_lookahead"]

MIN_VALID_CUTS = 5
"""Cortes evaluados mínimos para certificar ausencia de anticipación."""


@dataclass(frozen=True, slots=True, eq=False)
class LookaheadReport(ResultMixin):
    """Resultado de la prueba de anticipación."""

    has_lookahead: bool
    cuts: tuple[pd.Timestamp, ...]
    affected_dates: tuple[pd.Timestamp, ...]
    max_abs_diff: float
    skipped_cuts: int = 0

    @property
    def valid_cuts(self) -> int:
        """Cortes efectivamente evaluados."""
        return len(self.cuts) - self.skipped_cuts

    @property
    def conclusive(self) -> bool:
        """``True`` si se evaluaron al menos ``MIN_VALID_CUTS`` cortes."""
        return self.has_lookahead or self.valid_cuts >= MIN_VALID_CUTS

    def raise_if_biased(self) -> None:
        """Lanza :class:`LookaheadBiasError` si hay anticipación o la prueba no concluye."""
        if self.has_lookahead or not self.conclusive:
            raise LookaheadBiasError(self.summary())

    def summary(self) -> str:
        """Resumen legible."""
        if not self.has_lookahead:
            if not self.conclusive:
                return (
                    f"NO CONCLUYENTE: sólo {self.valid_cuts} corte(s) evaluable(s) de "
                    f"{len(self.cuts)} (mínimo {MIN_VALID_CUTS}); la señal falló con datos "
                    "truncados. No se puede certificar ausencia de anticipación."
                )
            return (
                f"Sin anticipación detectada en {self.valid_cuts} cortes evaluados "
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
        Cortes aleatorios (dentro del tramo con señal) adicionales a los deterministas:
        fin del calentamiento de la señal y +1, +5, +20; posiciones 5, 20, 60, 250, n/4,
        n/2, n−3 y n−2 del índice principal. Si se evalúan menos de ``MIN_VALID_CUTS``
        cortes el resultado es no concluyente.
    seed : int
        Semilla de los cortes aleatorios.
    tol : float
        Tolerancia numérica; un valor frente a ``NaN`` siempre cuenta como diferencia.
    """
    full = _as_frame(signal_fn(data))
    index = _index_of(data)
    n = len(index)
    first_valid = full.dropna(how="all").index.min()
    fv = int(index.searchsorted(first_valid)) if not pd.isna(first_valid) else 0
    fixed = (5, 20, 60, 250, n // 4, n // 2, n - 3, n - 2, fv, fv + 1, fv + 5, fv + 20)
    positions = {p for p in fixed if 0 <= p < n - 1}
    rng = np.random.default_rng(seed)
    if n - 1 > max(fv, 1):
        positions |= set(rng.integers(max(fv, 1), n - 1, size=n_cuts).tolist())
    cuts = sorted(index[p] for p in positions)
    affected: set[pd.Timestamp] = set()
    max_diff = 0.0
    skipped = 0
    for cut in cuts:
        try:
            part = _as_frame(signal_fn(_truncate(data, cut)))
        except Exception:  # noqa: BLE001 - la señal del usuario puede fallar con pocos datos
            skipped += 1  # se cuenta; si quedan pocos cortes el resultado es no concluyente
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
