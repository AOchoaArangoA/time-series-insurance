"""Perfiles de jurisdicción: parámetros regulatorios y de mercado inyectables.

Ningún módulo del paquete fija constantes regulatorias: todas provienen de un
:class:`JurisdictionProfile` (Principio IV de la constitución).
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Any

from tsinsurance.errors import TSInsuranceError

__all__ = ["JurisdictionProfile", "available_profiles", "load_profile"]


@dataclass(frozen=True, slots=True)
class JurisdictionProfile:
    """Parámetros de jurisdicción usados por los cálculos de riesgo.

    Attributes
    ----------
    name : str
        Identificador del perfil.
    confidence_level : float
        Nivel de confianza para VaR/ES, en (0, 1).
    horizon_days : int
        Horizonte de riesgo en días hábiles.
    base_currency : str or None
        Moneda base ISO 4217; ``None`` si el perfil es agnóstico de moneda.
    business_calendar : str
        Calendario de días hábiles (``"weekdays"`` por defecto).
    stress_shocks : Mapping[str, float]
        Choques de estrés por factor (se consumen en especificaciones futuras).
    """

    name: str
    confidence_level: float
    horizon_days: int
    base_currency: str | None = None
    business_calendar: str = "weekdays"
    stress_shocks: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 < self.confidence_level < 1.0:
            raise TSInsuranceError("confidence_level debe estar en (0, 1).")
        if self.horizon_days < 1:
            raise TSInsuranceError("horizon_days debe ser un entero positivo.")
        if self.base_currency is not None and (
            len(self.base_currency) != 3 or not self.base_currency.isupper()
        ):
            raise TSInsuranceError("base_currency debe ser un código ISO 4217 (p. ej. 'USD').")
        shocks = {str(k): float(v) for k, v in self.stress_shocks.items()}
        object.__setattr__(self, "stress_shocks", MappingProxyType(shocks))

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> JurisdictionProfile:
        """Crea un perfil desde un diccionario (p. ej. leído de TOML)."""
        allowed = {
            "name",
            "confidence_level",
            "horizon_days",
            "base_currency",
            "business_calendar",
            "stress_shocks",
        }
        unknown = set(data) - allowed
        if unknown:
            raise TSInsuranceError(f"Claves desconocidas en el perfil: {sorted(unknown)}")
        return cls(
            name=str(data["name"]),
            confidence_level=float(data["confidence_level"]),
            horizon_days=int(data["horizon_days"]),
            base_currency=data.get("base_currency"),
            business_calendar=str(data.get("business_calendar", "weekdays")),
            stress_shocks=dict(data.get("stress_shocks", {})),
        )


def available_profiles() -> list[str]:
    """Nombres de los perfiles incluidos en el paquete."""
    root = resources.files("tsinsurance") / "profiles"
    return sorted(p.name.removesuffix(".toml") for p in root.iterdir() if p.name.endswith(".toml"))


def load_profile(name_or_path: str | os.PathLike[str] = "generic") -> JurisdictionProfile:
    """Carga un perfil por nombre (incluido en el paquete) o desde un archivo TOML.

    Parameters
    ----------
    name_or_path : str or PathLike
        Nombre de un perfil incluido (``"generic"``) o ruta a un archivo ``.toml``.
    """
    path = Path(name_or_path)
    if path.suffix == ".toml" and path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        resource = resources.files("tsinsurance") / "profiles" / f"{name_or_path}.toml"
        if not resource.is_file():
            raise TSInsuranceError(
                f"Perfil '{name_or_path}' no encontrado. Disponibles: {available_profiles()}"
            )
        text = resource.read_text(encoding="utf-8")
    return JurisdictionProfile.from_mapping(tomllib.loads(text))
