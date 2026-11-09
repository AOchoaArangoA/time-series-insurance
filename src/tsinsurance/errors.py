"""Jerarquía de excepciones y advertencias de ``tsinsurance``."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tsinsurance.data.validate import ValidationReport

__all__ = [
    "ConvergenceError",
    "DataValidationError",
    "InadequateModelWarning",
    "InsufficientDataError",
    "LookaheadBiasError",
    "TSInsuranceError",
]


class TSInsuranceError(Exception):
    """Excepción base de todos los errores del paquete."""


class DataValidationError(TSInsuranceError, ValueError):
    """Los datos de entrada no cumplen el contrato de datos o las reglas de la API.

    Parameters
    ----------
    message : str
        Descripción legible del problema.
    report : ValidationReport, optional
        Reporte con todos los errores encontrados (fila, columna, regla).
    """

    def __init__(self, message: str, report: ValidationReport | None = None) -> None:
        super().__init__(message)
        self.report = report


class InsufficientDataError(TSInsuranceError, ValueError):
    """La serie es demasiado corta para el procedimiento solicitado.

    Parameters
    ----------
    procedure : str
        Nombre del procedimiento que no puede ejecutarse.
    required : int
        Número mínimo de observaciones requeridas.
    actual : int
        Número de observaciones disponibles.
    """

    def __init__(self, procedure: str, required: int, actual: int) -> None:
        super().__init__(
            f"{procedure} requiere al menos {required} observaciones; se recibieron {actual}."
        )
        self.procedure = procedure
        self.required = required
        self.actual = actual


class ConvergenceError(TSInsuranceError, RuntimeError):
    """El optimizador no convergió tras los reintentos permitidos."""


class InadequateModelWarning(UserWarning):
    """Se usa un modelo que no superó los diagnósticos de residuos."""


class LookaheadBiasError(TSInsuranceError):
    """Una señal usa información no disponible en la fecha de decisión."""
