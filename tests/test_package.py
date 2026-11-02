import tsinsurance


def test_version_is_exposed() -> None:
    assert isinstance(tsinsurance.__version__, str)
