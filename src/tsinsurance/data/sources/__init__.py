"""Conectores de datos (archivos locales, FRED, Yahoo Finance y extensiones)."""

from tsinsurance.data.sources.base import (
    DataSource,
    available_sources,
    get_source,
    register_source,
)

__all__ = ["DataSource", "available_sources", "get_source", "register_source"]
