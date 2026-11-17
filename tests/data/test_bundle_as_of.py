"""Bundle.as_of: el paquete truncado en la fecha de corte (spec 004 US2, T019)."""

from pathlib import Path

import pandas as pd
import pytest

from tests.fixtures.synthetic_bundle import mutate_after, synthetic_bundle
from tsinsurance.data.bundle import Bundle

CUT = "2016-12-30"


@pytest.fixture
def bundle(tmp_path: Path) -> Bundle:
    synthetic_bundle(tmp_path / "data")
    return Bundle.load(tmp_path / "data")


def test_assets_and_rf_end_at_cut(bundle: Bundle) -> None:
    cut = bundle.as_of(CUT)
    assert cut.assets().index.max() <= pd.Timestamp(CUT)
    rf = cut.risk_free()
    assert rf is not None and rf.index.max() <= pd.Timestamp(CUT)  # por disponibilidad


def test_exogenous_truncated_by_availability(bundle: Bundle) -> None:
    """El IPC de diciembre (rezago 20D desde fin de mes) aún no está disponible el 30-dic."""
    cut = bundle.as_of(CUT)
    cpi = next(e for e in cut.exogenous(["CPI"]))
    last_obs = cpi.series.index.max()
    assert cpi.availability().max() <= pd.Timestamp(CUT)
    assert last_obs < pd.Timestamp("2016-12-01")
    spread = next(e for e in cut.exogenous(["SPREAD"]))
    assert spread.availability().max() <= pd.Timestamp(CUT)  # rezago 1B


def test_hashes_and_metadata(bundle: Bundle) -> None:
    cut = bundle.as_of(CUT)
    assert cut.sha256 == bundle.sha256  # procedencia: el paquete completo
    assert cut.as_of_date == CUT and cut.as_of_sha256 and cut.as_of_sha256 != bundle.sha256
    assert bundle.as_of(CUT).as_of_sha256 == cut.as_of_sha256  # determinista
    assert bundle.as_of("2015-12-31").as_of_sha256 != cut.as_of_sha256
    assert len(cut.data) < len(bundle.data)


def test_as_of_hash_ignores_data_after_cut(tmp_path: Path) -> None:
    d = tmp_path / "data"
    synthetic_bundle(d)
    before = Bundle.load(d)
    mutate_after(d, CUT)
    after = Bundle.load(d)
    assert after.sha256 != before.sha256
    assert after.as_of(CUT).as_of_sha256 == before.as_of(CUT).as_of_sha256


def test_cannot_cut_twice_later(bundle: Bundle) -> None:
    cut = bundle.as_of(CUT)
    with pytest.raises(ValueError, match="ya está truncado"):
        cut.as_of("2018-12-31")
