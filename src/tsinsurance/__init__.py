"""tsinsurance: series de tiempo para la gestión de inversiones de aseguradoras.

Los módulos se implementan siguiendo las especificaciones en ``specs/``
(Spec-Driven Development con GitHub Spec Kit) y la constitución del proyecto en
``.specify/memory/constitution.md``.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tsinsurance")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = ["__version__"]
