from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_prices(seed: int = 0, n: int = 1500, assets: int = 2) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-01", periods=n)
    data = {
        f"A{i}": 100 * np.exp(np.cumsum(rng.normal(3e-4, 0.01 / (i + 1), n))) for i in range(assets)
    }
    return pd.DataFrame(data, index=idx)


@pytest.fixture
def prices() -> pd.DataFrame:
    return make_prices()
