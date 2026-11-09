import pytest

from tsinsurance.errors import (
    ConvergenceError,
    DataValidationError,
    InadequateModelWarning,
    InsufficientDataError,
    TSInsuranceError,
)


def test_hierarchy() -> None:
    assert issubclass(DataValidationError, TSInsuranceError)
    assert issubclass(DataValidationError, ValueError)
    assert issubclass(InsufficientDataError, ValueError)
    assert issubclass(ConvergenceError, RuntimeError)
    assert issubclass(InadequateModelWarning, UserWarning)


def test_insufficient_data_message_reports_minimum() -> None:
    err = InsufficientDataError("ADF", required=25, actual=10)
    assert err.required == 25 and err.actual == 10
    assert "25" in str(err) and "10" in str(err)
    with pytest.raises(ValueError):
        raise err


def test_data_validation_error_carries_report() -> None:
    err = DataValidationError("bad", report=None)
    assert err.report is None
