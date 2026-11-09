from pathlib import Path

import pytest

from tsinsurance.config import JurisdictionProfile, available_profiles, load_profile
from tsinsurance.errors import TSInsuranceError


def test_generic_profile_defaults() -> None:
    p = load_profile()
    assert p.name == "generic"
    assert p.confidence_level == 0.995
    assert p.horizon_days == 252
    assert p.base_currency is None
    assert "generic" in available_profiles()


def test_profile_is_immutable() -> None:
    p = load_profile("generic")
    with pytest.raises(AttributeError):
        p.confidence_level = 0.99  # type: ignore[misc]
    with pytest.raises(TypeError):
        p.stress_shocks["x"] = 1.0  # type: ignore[index]


def test_load_from_toml(tmp_path: Path) -> None:
    f = tmp_path / "mi_pais.toml"
    f.write_text(
        'name = "mi_pais"\nconfidence_level = 0.99\nhorizon_days = 10\nbase_currency = "COP"\n'
        "[stress_shocks]\nrates_up_bps = 200\n",
        encoding="utf-8",
    )
    p = load_profile(f)
    assert p.base_currency == "COP" and p.stress_shocks["rates_up_bps"] == 200.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"confidence_level": 1.2},
        {"horizon_days": 0},
        {"base_currency": "usd"},
    ],
)
def test_invalid_profiles(kwargs: dict[str, object]) -> None:
    base: dict[str, object] = {"name": "x", "confidence_level": 0.99, "horizon_days": 1}
    base.update(kwargs)
    with pytest.raises(TSInsuranceError):
        JurisdictionProfile(**base)  # type: ignore[arg-type]


def test_unknown_profile_and_keys() -> None:
    with pytest.raises(TSInsuranceError, match="no encontrado"):
        load_profile("no_existe")
    with pytest.raises(TSInsuranceError, match="desconocidas"):
        JurisdictionProfile.from_mapping(
            {"name": "x", "confidence_level": 0.9, "horizon_days": 1, "foo": 1}
        )
