import numpy as np
import pandas as pd
import pytest

from tsinsurance.backtest import (
    Exogenous,
    align_point_in_time,
    check_lookahead,
    ewma_volatility,
    garch_volatility_forecast,
    sma_crossover,
    tsmom,
    vol_target,
)
from tsinsurance.errors import InsufficientDataError, LookaheadBiasError


def test_sma_and_tsmom(prices: pd.DataFrame) -> None:
    s = sma_crossover(prices, 20, 100)
    assert s.iloc[:99].isna().all().all() and set(np.unique(s.iloc[99:])) <= {0.0, 0.5}
    assert set(np.unique(sma_crossover(prices, 20, 100, short=True, normalize=False).dropna())) <= {
        -1.0,
        1.0,
    }
    m = tsmom(prices, 252, 21)
    assert m.iloc[:252].isna().all().all()
    with pytest.raises(ValueError):
        sma_crossover(prices, 100, 20)
    with pytest.raises(ValueError):
        tsmom(prices, 10, 10)


def test_vol_signals(prices: pd.DataFrame) -> None:
    r = prices.pct_change()
    vol = ewma_volatility(r)
    assert vol.iloc[:20].isna().all().all()
    assert 0.05 < float(vol["A0"].iloc[-1]) < 0.4
    w = vol_target(prices.notna().astype(float), vol, target=0.05, max_leverage=1.5)
    assert float(w.max().max()) <= 1.5
    with pytest.raises(ValueError):
        ewma_volatility(r, lam=1.5)
    with pytest.raises(ValueError):
        vol_target(w, vol, target=0)


def test_garch_forecast_is_causal(prices: pd.DataFrame) -> None:
    r = prices["A0"].pct_change().dropna()
    g = garch_volatility_forecast(r, refit_every=250, min_train=600)
    assert g.iloc[:598].isna().all().all() and g.iloc[600:].notna().all().all()
    # Truncar los datos no cambia pronósticos pasados (walk-forward real).
    g_cut = garch_volatility_forecast(r.iloc[:1100], refit_every=250, min_train=600)
    pd.testing.assert_frame_equal(g.iloc[:1100], g_cut, rtol=1e-6)
    with pytest.raises(InsufficientDataError):
        garch_volatility_forecast(r.iloc[:100], min_train=500)


CAUSAL = {
    "sma": lambda p: sma_crossover(p, 20, 100),
    "tsmom": lambda p: tsmom(p, 120, 5),
    "ewma_target": lambda p: vol_target(p.notna().astype(float), ewma_volatility(p.pct_change())),
}


@pytest.mark.parametrize("name", list(CAUSAL))
def test_included_signals_have_no_lookahead(prices: pd.DataFrame, name: str) -> None:
    assert not check_lookahead(CAUSAL[name], prices).has_lookahead


LEAKS = {
    "shift_-1": lambda p: sma_crossover(p, 20, 100).shift(-1),
    "full_sample_zscore": lambda p: ((p - p.mean()) / p.std() > 0).astype(float),
    "bfill_warmup": lambda p: sma_crossover(p, 20, 100).bfill(),
    # Fuga sólo en las últimas fechas: usa el retorno del día siguiente.
    "point_leak_at_end": lambda p: (
        p.pct_change()
        .shift(-1)
        .where(pd.Series(p.index >= p.index[-3], index=p.index), 0.0, axis=0)
    ),
}


@pytest.mark.parametrize("name", list(LEAKS))
def test_lookahead_catalogue_detected(prices: pd.DataFrame, name: str) -> None:
    rep = check_lookahead(LEAKS[name], prices)
    assert rep.has_lookahead, name
    with pytest.raises(LookaheadBiasError):
        rep.raise_if_biased()
    assert "ANTICIPACIÓN" in rep.summary()


def _macro_data() -> dict[str, object]:
    days = pd.bdate_range("2015-01-01", "2019-12-31")
    px = pd.Series(np.linspace(100, 150, len(days)), index=days, name="P")
    months = pd.date_range("2014-01-01", "2019-12-01", freq="MS")
    cpi = pd.Series(np.arange(len(months), dtype=float) ** 1.1, index=months)
    return {"prices": px, "cpi": Exogenous("cpi", cpi, "M", release_lag="20D")}


def _pipeline(respect_lag: bool):  # type: ignore[no-untyped-def]
    def fn(data):  # type: ignore[no-untyped-def]
        px, ex = data["prices"], data["cpi"]
        if respect_lag:
            x = align_point_in_time([ex], px.index)["cpi"]
        else:  # fuga: usa la fecha de observación como si fuera la de publicación
            x = ex.transformed().reindex(px.index, method="ffill")
        return (x.diff(21) > 0).astype(float).where(x.notna()).rename("P")

    return fn


def test_lookahead_publication_lag() -> None:
    data = _macro_data()
    assert not check_lookahead(_pipeline(True), data, n_cuts=30).has_lookahead
    assert check_lookahead(_pipeline(False), data, n_cuts=30).has_lookahead
