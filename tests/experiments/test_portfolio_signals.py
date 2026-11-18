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
    month_end_mask,
    register_portfolio_signal,
)


def _prices(n: int = 900, k: int = 5, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2010-01-01", periods=n)
    r = rng.normal(2e-4, 0.01, (n, k))
    return pd.DataFrame(100 * np.exp(np.cumsum(r, axis=0)), index=idx, columns=list("ABCDE"))


def test_momentum_picks_top_k_on_month_ends() -> None:
    px = _prices()
    w = cross_sectional_momentum(px, lookback_m=6, skip_m=1, top_k=2)
    ends = month_end_mask(pd.DatetimeIndex(px.index))
    assert w[~ends].isna().all().all()  # sólo decide en cierres de mes
    last = w[ends].iloc[-1]
    assert last.sum() == pytest.approx(1.0) and (last > 0).sum() == 2
    closes = px[ends]
    mom = closes.shift(1) / closes.shift(7) - 1
    assert set(last[last > 0].index) == set(mom.iloc[-1].nlargest(2).index)
    assert (w[ends].iloc[:7] == 0).all().all()  # sin historia: efectivo


def test_momentum_ties_are_broken_by_sorted_id() -> None:
    idx = pd.bdate_range("2010-01-01", periods=200)
    px = pd.DataFrame({"B": 100.0, "A": 100.0, "C": 100.0}, index=idx)
    w = cross_sectional_momentum(px, lookback_m=2, skip_m=0, top_k=1).dropna()
    assert w.iloc[-1].to_dict() == {"B": 0.0, "A": 1.0, "C": 0.0}


def test_assets_without_history_do_not_compete() -> None:
    px = _prices()
    px.loc[: px.index[600], "E"] = np.nan  # E empieza tarde
    w = cross_sectional_momentum(px, lookback_m=6, top_k=2)
    assert (w["E"].iloc[: 600 + 21 * 7].fillna(0) == 0).all()
    ew = equal_weight(px)
    assert ew.iloc[100].to_dict()["E"] == 0 and ew.iloc[100].sum() == pytest.approx(1.0)


def test_inverse_volatility_weights() -> None:
    px = _prices()
    px["E"] = 100 * np.exp(np.cumsum(np.random.default_rng(2).normal(0, 0.03, len(px))))
    w = inverse_volatility(px, lookback=63).dropna()
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
    with pytest.raises(TSInsuranceError, match="menor que el universo"):
        cross_sectional_momentum(_prices(), top_k=5)


def test_listing_tolerates_signals_without_docstring() -> None:
    register_portfolio_signal("sin_doc", lambda p: equal_weight(p))
    assert available_portfolio_signals()["sin_doc"] == ""


def test_month_end_respects_exchange_holidays() -> None:
    """I5: si el último día hábil del mes es feriado bursátil, decide el día anterior."""
    idx = pd.bdate_range("2002-03-01", "2002-04-30")  # 2002-03-29 fue Viernes Santo
    ends = idx[month_end_mask(idx)]
    assert list(ends.strftime("%Y-%m-%d")) == ["2002-03-28", "2002-04-30"]


def test_eligible_mask_restricts_ranking() -> None:
    """I6: sólo compiten los elegibles; no se elige un activo no elegible."""
    px = _prices()
    eligible = px.notna()
    eligible["A"] = False
    w = cross_sectional_momentum(px, lookback_m=6, top_k=2, eligible=eligible).dropna()
    assert (w["A"] == 0).all() and (w.iloc[-1].sum() == pytest.approx(1.0))
