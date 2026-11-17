"""Señales de cartera: causalidad, empates, historia desigual (spec 005, R2, SC-003)."""

import numpy as np
import pandas as pd
import pytest

from tsinsurance.backtest import check_lookahead
from tsinsurance.errors import TSInsuranceError
from tsinsurance.experiments.portfolio_signals import (
    available_portfolio_signals,
    cross_sectional_momentum,
    equal_weight,
    get_portfolio_signal,
    inverse_volatility,
    register_portfolio_signal,
)


def _prices(n: int = 900, k: int = 5, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2010-01-01", periods=n)
    r = rng.normal(2e-4, 0.01, (n, k))
    return pd.DataFrame(100 * np.exp(np.cumsum(r, axis=0)), index=idx, columns=list("ABCDE"))


def test_momentum_picks_top_k_and_sums_to_one() -> None:
    px = _prices()
    w = cross_sectional_momentum(px, lookback_m=6, skip_m=1, top_k=2)
    full = w.iloc[-1]
    assert full.sum() == pytest.approx(1.0) and (full > 0).sum() == 2
    mom = px.shift(21) / px.shift(21 * 7) - 1
    assert set(full[full > 0].index) == set(mom.iloc[-1].nlargest(2).index)
    assert (w.iloc[: 21 * 7] == 0).all().all()  # sin historia: efectivo


def test_momentum_ties_are_deterministic_by_column_order() -> None:
    idx = pd.bdate_range("2010-01-01", periods=200)
    px = pd.DataFrame({"B": 100.0, "A": 100.0, "C": 100.0}, index=idx)
    w = cross_sectional_momentum(px, lookback_m=2, skip_m=0, top_k=1)
    assert w.iloc[-1].to_dict() == {"B": 1.0, "A": 0.0, "C": 0.0}


def test_assets_without_history_do_not_compete() -> None:
    px = _prices()
    px.loc[: px.index[600], "E"] = np.nan  # E empieza tarde
    w = cross_sectional_momentum(px, lookback_m=6, top_k=2)
    assert (w["E"].iloc[: 600 + 21 * 7] == 0).all()
    ew = equal_weight(px)
    assert ew.iloc[100].to_dict()["E"] == 0 and ew.iloc[100].sum() == pytest.approx(1.0)


def test_inverse_volatility_weights() -> None:
    px = _prices()
    px["E"] = 100 * np.exp(np.cumsum(np.random.default_rng(2).normal(0, 0.03, len(px))))
    w = inverse_volatility(px, lookback=63)
    last = w.iloc[-1]
    assert last.sum() == pytest.approx(1.0) and last["E"] == last.min()


@pytest.mark.parametrize(
    "fn",
    [
        lambda p: cross_sectional_momentum(p, 6, 1, 2),
        lambda p: inverse_volatility(p, 63),
        equal_weight,
    ],
)
def test_builtin_signals_are_causal(fn) -> None:  # type: ignore[no-untyped-def]
    rep = check_lookahead(fn, _prices())
    assert not rep.has_lookahead and rep.conclusive


def test_future_ranking_is_rejected() -> None:
    """Rankear con precios futuros (SC-003) se detecta."""

    def cheat(p: pd.DataFrame) -> pd.DataFrame:
        fut = p.shift(-21) / p - 1
        return (fut.rank(axis=1, ascending=False) <= 2).astype(float) / 2

    assert check_lookahead(cheat, _prices()).has_lookahead


def test_registry() -> None:
    assert {"cross_sectional_momentum", "inverse_volatility"} <= set(available_portfolio_signals())
    register_portfolio_signal("propia", equal_weight)
    assert get_portfolio_signal("propia") is equal_weight
    with pytest.raises(TSInsuranceError, match="desconocida"):
        get_portfolio_signal("nope")
    with pytest.raises(TSInsuranceError):
        cross_sectional_momentum(_prices(), top_k=0)
