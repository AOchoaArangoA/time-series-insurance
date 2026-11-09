import shutil
from pathlib import Path

import pandas as pd
import pytest

from tsinsurance.backtest import Exogenous
from tsinsurance.data.bundle import (
    Bundle,
    bundle_digest,
    validate_bundle,
    write_bundle_template,
)
from tsinsurance.errors import DataValidationError, TSInsuranceError


def test_hand_written_and_generated_bundles_are_equivalent(
    tmp_path: Path, bundle_dir: Path
) -> None:
    """SC-001: un paquete escrito a mano y uno generado producen el mismo objeto."""
    hand = write_bundle_template(tmp_path / "hand")
    assert validate_bundle(hand) == []
    a, b = Bundle.load(hand), Bundle.load(bundle_dir)
    assert type(a) is type(b)
    assert a.ids("asset") == ["ETF_A", "ETF_B"] and b.ids("asset") == ["AAA", "BBB"]
    assert isinstance(a.exogenous()[0], Exogenous) and isinstance(b.exogenous()[0], Exogenous)
    assert a.risk_free() is not None and b.risk_free() is not None


def test_accessors(bundle_dir: Path) -> None:
    b = Bundle.load(bundle_dir)
    px = b.assets()
    assert list(px.columns) == ["AAA", "BBB"] and isinstance(px.index, pd.DatetimeIndex)
    cpi = b.exogenous(["CPI"])[0]
    assert cpi.frequency == "M" and cpi.transform == "yoy" and str(cpi.release_lag) == "20D"
    rf = b.risk_free()
    assert rf is not None and rf.iloc[0] == pytest.approx(1.02 ** (1 / 252) - 1)
    assert rf.index[0] == pd.Timestamp("2010-01-04")  # disponible un día hábil después
    assert b.redistributable and "AAA" in b.summary()
    with pytest.raises(TSInsuranceError):
        b.assets(["SPREAD"])
    with pytest.raises(TSInsuranceError):
        b.spec("ZZZ")
    with pytest.raises(TSInsuranceError):
        b.exogenous(["AAA"])


def _edit_manifest(path: Path, old: str, new: str) -> None:
    text = (path / "bundle.toml").read_text(encoding="utf-8")
    assert old in text
    (path / "bundle.toml").write_text(text.replace(old, new, 1), encoding="utf-8")


@pytest.mark.parametrize(
    ("old", "new", "field"),
    [
        ('role = "asset"', 'role = "precio"', "role"),
        ('release_lag = "20D"', 'release_lag = "veinte"', "release_lag"),
        ('transform = "yoy"', 'transform = "log"', "transform"),
        ('rf_convention = "annual_percent"', 'rf_convention = "x"', "rf_convention"),
        ('license = "sintética (pruebas)"', 'license = ""', "license"),
        ('id = "BBB"', 'id = "AAA"', "id"),
        ('version = "1.0"', 'version = "9.9"', "bundle.version"),
    ],
)
def test_manifest_issue_catalogue(
    tmp_path: Path, bundle_dir: Path, old: str, new: str, field: str
) -> None:
    """SC-002: cada inconsistencia nombra la serie y el campo."""
    target = tmp_path / "b"
    shutil.copytree(bundle_dir, target)
    _edit_manifest(target, old, new)
    issues = validate_bundle(target)
    assert any(i.field == field for i in issues), issues
    with pytest.raises(DataValidationError):
        Bundle.load(target)


def test_data_issues(tmp_path: Path, bundle_dir: Path) -> None:
    target = tmp_path / "b"
    shutil.copytree(bundle_dir, target)
    csv = target / "market_series.csv"
    lines = csv.read_text(encoding="utf-8").splitlines()
    csv.write_text("\n".join(lines[:1] + [lines[1].replace("AAA", "ZZZ")] + lines[2:]) + "\n")
    fields = {(i.series, i.field) for i in validate_bundle(target)}
    assert ("ZZZ", "id") in fields and ("*", "bundle.sha256") in fields
    csv.write_text("\n".join(lines[:1] + [lines[1].replace(",price,", ",acciones,")] + lines[2:]))
    assert any("isin" in i.message for i in validate_bundle(target))
    assert validate_bundle(tmp_path / "nada")[0].field == "bundle.toml"
    (target / "bundle.toml").write_text("[[[", encoding="utf-8")
    assert "TOML" in validate_bundle(target)[0].message


def test_seal_covers_declarations_and_template_unsealed(tmp_path: Path, bundle_dir: Path) -> None:
    """Revisión I7: cambiar un rezago sin cambiar datos invalida la huella."""
    target = tmp_path / "b"
    shutil.copytree(bundle_dir, target)
    _edit_manifest(target, 'release_lag = "20D"', 'release_lag = "0D"')
    assert any(i.field == "bundle.sha256" for i in validate_bundle(target))
    hand = write_bundle_template(tmp_path / "hand")
    assert not Bundle.load(hand).sealed
    from tsinsurance.data.bundle import seal_bundle

    assert seal_bundle(hand).sealed and Bundle.load(hand).sealed


def test_required_point_in_time_fields(tmp_path: Path, bundle_dir: Path) -> None:
    target = tmp_path / "b"
    shutil.copytree(bundle_dir, target)
    text = (target / "bundle.toml").read_text(encoding="utf-8")
    head, tail = text.split('id = "SPREAD"', 1)
    tail = tail.replace("point_in_time = true\n", "", 1)
    (target / "bundle.toml").write_text(head + 'id = "SPREAD"' + tail, encoding="utf-8")
    assert any(i.field == "point_in_time" for i in validate_bundle(target))


def test_quality_warning_spike_reversal(tmp_path: Path, bundle_dir: Path) -> None:
    b = Bundle.load(bundle_dir)
    data = b.data.copy()
    i = data.index[(data["series_id"] == "AAA")][500]
    data.loc[i, "value"] *= 1.2
    from dataclasses import replace

    assert any("AAA" in w for w in replace(b, data=data).quality_warnings())
    assert b.quality_warnings() == []


def test_generated_bundle_requires_explicit_declarations(tmp_path: Path) -> None:
    from tsinsurance.data import Snapshot

    df = pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-01", periods=3),
            "series_id": "X",
            "value": [1.0, 2.0, 3.0],
            "kind": "rate",
            "unit": "percent",
            "currency": "USD",
            "frequency": "B",
        }
    )
    snap = Snapshot.create(df, kind="market", source="t")
    with pytest.raises(DataValidationError, match="point_in_time"):
        Bundle.from_snapshots(
            "x", [(snap, [{"id": "X", "role": "exogenous", "license": "l", "release_lag": "1B"}])]
        )


def test_digest_changes(bundle_dir: Path) -> None:
    d = bundle_digest(bundle_dir)
    assert len(d) == 64 and d == bundle_digest(bundle_dir)
