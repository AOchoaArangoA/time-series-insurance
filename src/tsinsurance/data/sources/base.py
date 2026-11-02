"""Interfaz de conectores de datos y registro extensible.

Terceros pueden registrar conectores (p. ej. bancos centrales) declarando un
*entry point* en el grupo ``tsinsurance.sources`` que apunte a una clase que
cumpla :class:`DataSource`.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from importlib.metadata import entry_points
from typing import Any, Protocol, runtime_checkable

from tsinsurance.data.snapshot import Snapshot
from tsinsurance.errors import TSInsuranceError

__all__ = ["DataSource", "available_sources", "get_source", "register_source"]

DateLike = str | dt.date | None


@runtime_checkable
class DataSource(Protocol):
    """Conector que entrega datos en el formato del contrato como :class:`Snapshot`."""

    name: str

    def fetch(
        self, ids: Sequence[str] | None = None, start: DateLike = None, end: DateLike = None
    ) -> Snapshot:
        """Obtiene las series ``ids`` entre ``start`` y ``end`` (inclusive)."""
        ...


_REGISTRY: dict[str, Callable[..., DataSource]] = {}
ENTRY_POINT_GROUP = "tsinsurance.sources"


def register_source(name: str, factory: Callable[..., DataSource]) -> None:
    """Registra un conector bajo ``name``."""
    _REGISTRY[name] = factory


def _builtin() -> dict[str, Callable[..., DataSource]]:
    from tsinsurance.data.sources.files import CSVSource, ExcelSource
    from tsinsurance.data.sources.fred import FredSource
    from tsinsurance.data.sources.yahoo import YahooSource

    return {"csv": CSVSource, "excel": ExcelSource, "fred": FredSource, "yahoo": YahooSource}


def available_sources() -> list[str]:
    """Nombres de conectores disponibles (incluidos, registrados y por entry points)."""
    names = set(_builtin()) | set(_REGISTRY)
    names |= {ep.name for ep in entry_points(group=ENTRY_POINT_GROUP)}
    return sorted(names)


def get_source(name: str, **kwargs: Any) -> DataSource:
    """Instancia el conector ``name`` con ``kwargs``."""
    factories = {**_builtin(), **_REGISTRY}
    if name not in factories:
        for ep in entry_points(group=ENTRY_POINT_GROUP):
            if ep.name == name:
                factories[name] = ep.load()
                break
    if name not in factories:
        raise TSInsuranceError(f"Conector '{name}' no disponible. Opciones: {available_sources()}")
    return factories[name](**kwargs)


def to_timestamp(value: DateLike) -> dt.date | None:
    """Normaliza una fecha opcional."""
    if value is None:
        return None
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(value)
