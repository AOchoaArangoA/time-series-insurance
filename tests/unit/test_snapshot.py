import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

from tsinsurance.data import SCHEMA_VERSION, Snapshot, load
from tsinsurance.data.snapshot import content_hash
from tsinsurance.errors import DataValidationError

FIX = Path(__file__).parents[1] / "fixtures"


def make() -> Snapshot:
    data = load(FIX / "market_good.csv", "market")
    return Snapshot.create(
        data,
        kind="market",
        source="file:market_good.csv",
        query={"ids": None},
        retrieved_at=dt.datetime(2026, 11, 2, 12, 0, tzinfo=dt.UTC),
    )


def test_roundtrip_preserves_hash(tmp_path: Path) -> None:
    snap = make()
    snap.save(tmp_path / "s")
    again = Snapshot.load(tmp_path / "s")
    assert again.sha256 == snap.sha256 == content_hash(again.data)
    assert again.schema_version == SCHEMA_VERSION
    assert again.retrieved_at == "2026-11-02T12:00:00+00:00"
    pd.testing.assert_frame_equal(again.data, snap.data, check_dtype=False)
    meta = json.loads((tmp_path / "s" / "metadata.json").read_text())
    assert meta["n_rows"] == 6 and "api_key" not in json.dumps(meta)


def test_hash_is_deterministic_and_sensitive() -> None:
    a = make()
    b = make()
    assert a.sha256 == b.sha256
    changed = a.data.copy()
    changed.loc[0, "value"] = 1.0
    assert content_hash(changed) != a.sha256


def test_tampering_detected(tmp_path: Path) -> None:
    snap = make()
    snap.save(tmp_path / "s")
    tampered = snap.data.copy()
    tampered.loc[0, "value"] = 1.0
    tampered.to_parquet(tmp_path / "s" / "data.parquet", index=False)
    with pytest.raises(DataValidationError, match="hash"):
        Snapshot.load(tmp_path / "s")
    assert Snapshot.load(tmp_path / "s", verify=False).sha256 == snap.sha256


def test_missing_files(tmp_path: Path) -> None:
    with pytest.raises(DataValidationError):
        Snapshot.load(tmp_path)


def test_snapshot_is_accepted_by_load() -> None:
    assert len(load(make(), "market")) == 6
