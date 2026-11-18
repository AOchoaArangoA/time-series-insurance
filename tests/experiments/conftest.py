from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixtures.synthetic_bundle import synthetic_bundle


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
