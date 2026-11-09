from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tsinsurance.data import Snapshot
from tsinsurance.data.bundle import Bundle


def synthetic_bundle(directory: Path, seed: int = 0) -> Bundle:
    """Paquete sintético: 2 activos diarios, 1 exógena diaria, 1 mensual y rf."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2010-01-01", "2019-12-31")
    rows = []
    for sid, drift in (("AAA", 3e-4), ("BBB", -1e-4)):
        px = 100 * np.exp(np.cumsum(rng.normal(drift, 0.01, len(days))))
        rows.append(
            pd.DataFrame(
                {
                    "date": days,
                    "series_id": sid,
                    "value": px,
                    "kind": "price",
                    "unit": "level",
                    "currency": "USD",
                    "frequency": "B",
                }
            )
        )
    rows.append(
        pd.DataFrame(
            {
                "date": days,
                "series_id": "SPREAD",
                "value": np.cumsum(rng.normal(0, 0.02, len(days))) + 1.0,
                "kind": "rate",
                "unit": "percent",
                "currency": "USD",
                "frequency": "B",
            }
        )
    )
    rows.append(
        pd.DataFrame(
            {
                "date": days,
                "series_id": "RF",
                "value": 2.0,
                "kind": "rate",
                "unit": "percent",
                "currency": "USD",
                "frequency": "B",
            }
        )
    )
    months = pd.date_range("2009-01-01", "2019-12-01", freq="MS")
    rows.append(
        pd.DataFrame(
            {
                "date": months,
                "series_id": "CPI",
                "value": 100 * np.exp(np.cumsum(rng.normal(0.002, 0.003, len(months)))),
                "kind": "index",
                "unit": "level",
                "currency": "USD",
                "frequency": "M",
            }
        )
    )
    daily = Snapshot.create(
        pd.concat(rows[:4], ignore_index=True), kind="market", source="sintetico"
    )
    monthly = Snapshot.create(rows[4], kind="market", source="sintetico")
    lic = {"license": "sintética (pruebas)", "redistributable": True}
    bundle = Bundle.from_snapshots(
        "sintetico",
        [
            (
                daily,
                [
                    {"id": "AAA", "role": "asset", **lic},
                    {"id": "BBB", "role": "asset", **lic},
                    {
                        "id": "SPREAD",
                        "role": "exogenous",
                        "release_lag": "1B",
                        "point_in_time": True,
                        **lic,
                    },
                    {
                        "id": "RF",
                        "role": "risk_free",
                        "release_lag": "1B",
                        "rf_convention": "annual_percent",
                        **lic,
                    },
                ],
            ),
            (
                monthly,
                [
                    {
                        "id": "CPI",
                        "role": "exogenous",
                        "release_lag": "20D",
                        "transform": "yoy",
                        "point_in_time": True,
                        **lic,
                    }
                ],
            ),
        ],
    )
    bundle.save(directory)
    return bundle


@pytest.fixture
def bundle_dir(tmp_path: Path) -> Path:
    synthetic_bundle(tmp_path / "data")
    return tmp_path / "data"


EXPERIMENT = """
[experiment]
id = "prueba"
hypothesis = "sintética"
registry = "registry.jsonl"

[data]
bundle = "data"
assets = ["AAA", "BBB"]

[execution]
lag = 1
cost_bps = 5.0

[validation]
reps = 50
seed = 1
train_end = "2016-12-30"

[[ideas]]
name = "tendencia"
signal = "sma_crossover"
  [ideas.grid]
  fast = [20, 50]
  slow = [150]

[[econometric]]
name = "macro"
asset = "AAA"
regressors = ["SPREAD", "d_SPREAD", "CPI"]
derived = { d_SPREAD = { from = "SPREAD", op = "diff" } }
min_train = 36
"""


@pytest.fixture
def experiment_file(bundle_dir: Path) -> Path:
    path = bundle_dir.parent / "experiment.toml"
    path.write_text(EXPERIMENT, encoding="utf-8")
    return path
