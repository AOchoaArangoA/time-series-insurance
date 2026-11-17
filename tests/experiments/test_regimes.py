"""Regímenes del ciclo: estados punto en el tiempo, inferencia y memoria (spec 005, US2)."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tsinsurance.backtest import monthly_decision_dates
from tsinsurance.data.bundle import Bundle
from tsinsurance.experiments.regimes import analyze_regime, holm_extended, regime_state
from tsinsurance.experiments.spec import RegimeSpec


def _spec(**kw: object) -> RegimeSpec:
    base = {
        "name": "r",
        "type": "threshold",
        "variables": ["SPREAD"],
        "op": ">",
        "values": [1.0],
        "asset": None,
        "months": [],
        "assets": ["AAA", "BBB"],
        "min_months": 12,
        "justification": "prueba",
    }
    base.update(kw)
    return RegimeSpec(**base)  # type: ignore[arg-type]


@pytest.fixture
def bundle(bundle_dir: Path) -> Bundle:
    return Bundle.load(bundle_dir)


def test_states_are_point_in_time(bundle: Bundle) -> None:
    """SC-005: alterar lo posterior a d no cambia el estado en d."""
    dates = monthly_decision_dates(bundle.assets(["AAA"])["AAA"].dropna())
    for spec in (
        _spec(),
        _spec(type="spread", variables=["SPREAD", "RF"], values=[-1.0]),
        _spec(type="trend", asset="AAA", months=[10], variables=[], values=[]),
    ):
        variant = spec.variants()[0]
        full = regime_state(bundle, spec, variant, dates)
        for d in dates[[30, 60, 90]]:
            data = bundle.data.copy()
            later = pd.to_datetime(data["date"]) > d
            data.loc[later, "value"] *= 3.0
            cut = regime_state(replace(bundle, data=data), spec, variant, dates[dates <= d])
            pd.testing.assert_series_equal(full.loc[:d], cut, check_names=False)


def test_spread_with_stale_series_is_missing(bundle: Bundle) -> None:
    dates = monthly_decision_dates(bundle.assets(["AAA"])["AAA"].dropna())
    data = bundle.data.copy()
    gap = (data["series_id"] == "SPREAD") & (pd.to_datetime(data["date"]).dt.year == 2014)
    stale = replace(bundle, data=data[~gap].reset_index(drop=True))
    spec = _spec(type="spread", variables=["SPREAD", "RF"], values=[-1.0])
    s = regime_state(stale, spec, spec.variants()[0], dates)
    assert s.loc["2014-03-01":"2014-12-31"].isna().all()
    assert s.loc["2013-01-01":"2013-12-31"].notna().all()


def test_detects_effect_and_reports_hc3(bundle: Bundle) -> None:
    """Con un efecto fuerte inyectado, la diferencia es significativa y del signo correcto."""
    px = bundle.assets(["AAA"])["AAA"].dropna()
    dates = monthly_decision_dates(px)
    spec = _spec(assets=["AAA"])
    state = regime_state(bundle, spec, spec.variants()[0], dates)
    # Sumar +4 % al mes siguiente a cada estado activo (precio diario reescalado).
    bump = pd.Series(1.0, index=px.index)
    for d, on in state.items():
        if on == 1.0:
            nxt = px.index[px.index > d][:21]
            bump.loc[nxt] *= 1.04 ** (1 / 21)
    data = bundle.data.copy()
    rows = data["series_id"] == "AAA"
    data.loc[rows, "value"] = (px * bump.cumprod()).to_numpy()
    out = analyze_regime(replace(bundle, data=data), spec)
    row = out[0]
    assert not row.inconclusive and row.months_on >= 12
    assert row.diff_ann > 0 and row.p < 0.01


def test_min_months_marks_inconclusive(bundle: Bundle) -> None:
    out = analyze_regime(bundle, _spec(values=[1e9], min_months=12))  # nunca activo
    assert all(r.inconclusive and np.isnan(r.p) for r in out)


def test_grid_variants_are_separate_hypotheses(bundle: Bundle) -> None:
    out = analyze_regime(bundle, _spec(values=[0.5, 1.0, 1.5], assets=["AAA"]))
    assert len(out) == 3 and len({r.label for r in out}) == 3


def test_validation_window_uses_only_post_cut_targets(bundle: Bundle) -> None:
    out = analyze_regime(bundle, _spec(assets=["AAA"]), after="2016-12-30")
    assert out[0].eval_start >= "2016-12-30"


def test_holm_extended_counts_prior_variants() -> None:
    assert holm_extended([0.01, 0.04]) == [0.02, 0.04]
    assert holm_extended([0.01, 0.04], extra_m=2) == [0.04, 0.12]
