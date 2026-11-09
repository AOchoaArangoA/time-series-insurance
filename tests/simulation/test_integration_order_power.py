"""SC-001: precisión del diagnóstico del orden de integración (Monte Carlo)."""

import numpy as np
import pytest

from tests.conftest import simulate_ar1, simulate_random_walk
from tsinsurance.diagnostics import stationarity

pytestmark = pytest.mark.slow

REPLICATIONS = 500
N = 500


def _rates(simulate, expected: str, seed: int) -> tuple[float, float]:  # type: ignore[no-untyped-def]
    rng = np.random.default_rng(seed)
    correct = wrong = 0
    for _ in range(REPLICATIONS):
        c = stationarity(simulate(rng), breaks=False).conclusion
        correct += c == expected
        wrong += c not in (expected, "inconclusive")
    return correct / REPLICATIONS, wrong / REPLICATIONS


def test_sc001_i0() -> None:
    acc, wrong = _rates(lambda r: simulate_ar1(r, N, 0.5), "I(0)", 11)
    assert acc >= 0.90 and wrong <= 0.07


def test_sc001_i1() -> None:
    acc, wrong = _rates(lambda r: simulate_random_walk(r, N), "I(1)", 12)
    assert acc >= 0.85 and wrong <= 0.07
