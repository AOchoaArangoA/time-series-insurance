"""Objetos de resultado inmutables y utilidades de serialización."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

__all__ = ["HypothesisTestResult", "ResultMixin", "to_jsonable"]


def to_jsonable(obj: Any) -> Any:
    """Convierte recursivamente ``obj`` en tipos serializables a JSON.

    Los ``NaN`` e infinitos se convierten en ``None`` para producir JSON estándar.
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Mapping):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, pd.DataFrame):
        frame = obj.copy()
        frame.index = frame.index.map(_scalar_key)
        return {
            str(col): {k: to_jsonable(v) for k, v in frame[col].items()} for col in frame.columns
        }
    if isinstance(obj, pd.Series):
        return {_scalar_key(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, np.ndarray, pd.Index)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (pd.Timestamp, dt.datetime, dt.date)):
        return obj.isoformat()
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        value = float(obj)
        return value if math.isfinite(value) else None
    if obj is None or isinstance(obj, str):
        return obj
    if obj is pd.NaT or obj is pd.NA:
        return None
    return str(obj)


def _scalar_key(key: Any) -> str:
    if isinstance(key, (pd.Timestamp, dt.date)):
        return key.isoformat()
    return str(key)


class ResultMixin:
    """Comportamiento común de los resultados: ``to_dict``, ``to_json`` y ``summary``."""

    def to_dict(self) -> dict[str, Any]:
        """Representación serializable a JSON (sin ``NaN``)."""
        out = to_jsonable(self)
        assert isinstance(out, dict)
        return out

    def to_json(self) -> str:
        """JSON canónico (claves ordenadas, separadores fijos) para reproducibilidad."""
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False, indent=2)

    def summary(self) -> str:  # pragma: no cover - implementado por subclases
        """Resumen legible del resultado."""
        raise NotImplementedError

    def __str__(self) -> str:
        return self.summary()


_LEVELS: tuple[float, ...] = (0.01, 0.05, 0.10)


@dataclass(frozen=True, slots=True)
class HypothesisTestResult(ResultMixin):
    """Resultado de una prueba de hipótesis.

    Attributes
    ----------
    name : str
        Nombre corto de la prueba (p. ej. ``"ADF"``).
    statistic : float
        Valor del estadístico.
    p_value : float or None
        Valor p (``None`` si la prueba no lo provee).
    null_hypothesis : str
        Enunciado de la hipótesis nula.
    critical_values : Mapping[str, float]
        Valores críticos por nivel (claves ``"1%"``, ``"5%"``, ``"10%"``).
    specification : Mapping[str, Any]
        Especificación usada (determinísticos, rezagos, observaciones...).
    reference : str
        Referencia bibliográfica del método.
    notes : tuple[str, ...]
        Advertencias o aclaraciones (p. ej. valor p acotado por tablas).
    """

    name: str
    statistic: float
    p_value: float | None
    null_hypothesis: str
    critical_values: Mapping[str, float] = field(default_factory=dict)
    specification: Mapping[str, Any] = field(default_factory=dict)
    reference: str = ""
    notes: tuple[str, ...] = ()

    def rejects(self, alpha: float = 0.05) -> bool:
        """Indica si se rechaza la hipótesis nula al nivel ``alpha``.

        Usa el valor p si existe; si no, compara con el valor crítico del nivel.
        """
        if self.p_value is not None and math.isfinite(self.p_value):
            return self.p_value < alpha
        key = f"{round(alpha * 100):d}%"
        if key not in self.critical_values:
            raise ValueError(f"No hay valor p ni valor crítico para alpha={alpha}.")
        crit = self.critical_values[key]
        lower_tail = bool(self.specification.get("lower_tail", True))
        return self.statistic < crit if lower_tail else self.statistic > crit

    @property
    def reject_at(self) -> dict[str, bool]:
        """Decisión de rechazo a los niveles 1 %, 5 % y 10 %."""
        return {f"{round(a * 100):d}%": self.rejects(a) for a in _LEVELS}

    def summary(self) -> str:
        """Resumen de una línea más valores críticos."""
        p = "n/d" if self.p_value is None else f"{self.p_value:.4f}"
        spec = ", ".join(f"{k}={v}" for k, v in self.specification.items() if k != "lower_tail")
        crit = ", ".join(f"{k}: {v:.3f}" for k, v in self.critical_values.items())
        lines = [
            f"{self.name}: estadístico={self.statistic:.4f}, p={p} [{spec}]",
            f"  H0: {self.null_hypothesis}",
        ]
        if crit:
            lines.append(f"  Valores críticos: {crit}")
        lines.extend(f"  Nota: {n}" for n in self.notes)
        return "\n".join(lines)
