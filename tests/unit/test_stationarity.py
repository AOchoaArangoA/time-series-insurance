import importlib

import numpy as np
import pandas as pd
import pytest

from tsinsurance.diagnostics import adf, kpss, pp, stationarity, zivot_andrews
from tsinsurance.diagnostics.stationarity import MIN_OBS, MIN_OBS_BREAK
from tsinsurance.errors import DataValidationError, InsufficientDataError


def test_random_walk_is_i1(make_random_walk) -> None:  # type: ignore[no-untyped-def]
    # Semilla fija: con alpha=5 % ~5 % de los paseos aleatorios rechazan por azar (ver SC-001).
    rep = stationarity(make_random_walk(np.random.default_rng(0), 500))
    assert rep.conclusion == "I(1)" and rep.integration_order == 1
    assert {t.name for t in rep.tests_at(0)} >= {"ADF", "PP", "KPSS", "ZA"}
    assert {t.name for t in rep.tests_at(1)} == {"ADF", "PP", "KPSS"}
    assert "jerárquica" in rep.decision_rule
    text = rep.summary()
    assert "I(1)" in text and "d=1" in text and "KPSS" in text


@pytest.mark.parametrize("alpha", [0.01, 0.025, 0.05, 0.10])
def test_rule_works_at_every_admitted_alpha(make_random_walk, alpha: float) -> None:  # type: ignore[no-untyped-def]
    # Revisión econométrica: con alpha=0.01 el valor p acotado de KPSS anulaba la regla.
    rep = stationarity(make_random_walk(np.random.default_rng(0), 500), alpha=alpha, breaks=False)
    assert rep.conclusion == "I(1)"


def test_kpss_bounded_pvalue_uses_critical_values(make_random_walk) -> None:  # type: ignore[no-untyped-def]
    r = kpss(make_random_walk(np.random.default_rng(0), 1000) * 10)
    assert r.p_value_bound == "below" and r.p_value_label == "<0.0100"
    assert r.rejects(0.01)  # decide por valor crítico, no por p < alpha
    wn = kpss(pd.Series(np.tile([1.0, -1.0], 250)))  # sumas parciales acotadas: p > 0,10
    assert wn.p_value_bound == "above" and not wn.rejects(0.10)
    assert "2.5%" in wn.critical_values


def test_ar1_is_i0(rng, make_ar1) -> None:  # type: ignore[no-untyped-def]
    rep = stationarity(make_ar1(rng, 500, 0.5), breaks=False)
    assert rep.conclusion == "I(0)" and rep.integration_order == 0
    assert rep.tests_at(1) == []


def test_i2_detected() -> None:
    rng = np.random.default_rng(0)
    x = pd.Series(np.cumsum(np.cumsum(rng.normal(size=600))))
    rep = stationarity(x, breaks=False)
    assert rep.conclusion == "I(2)"


def test_level_shift_reports_break(rng) -> None:  # type: ignore[no-untyped-def]
    idx = pd.bdate_range("2010-01-01", periods=400)
    e = rng.normal(scale=0.5, size=400)
    y = np.where(np.arange(400) < 250, 0.0, 6.0) + e
    rep = stationarity(pd.Series(y, index=idx, name="shift"))
    assert rep.break_date is not None and rep.break_significant
    # Convención: la fecha es la última observación antes del quiebre (posición 249).
    assert idx.get_loc(rep.break_date) == 249
    assert "significativo" in rep.summary()


def test_inconclusive_when_tests_disagree(monkeypatch: pytest.MonkeyPatch, rng) -> None:  # type: ignore[no-untyped-def]
    mod = importlib.import_module("tsinsurance.diagnostics.stationarity")

    real_pp = mod.pp

    def flipped(series, **kw):  # type: ignore[no-untyped-def]
        r = real_pp(series, **kw)
        return mod.HypothesisTestResult(r.name, r.statistic, 0.9, r.null_hypothesis)

    monkeypatch.setattr(mod, "pp", flipped)
    rep = mod.stationarity(pd.Series(rng.normal(size=300)), breaks=False)
    assert rep.conclusion == "inconclusive" and rep.integration_order is None
    assert any("contradictorios" in n for n in rep.notes)


def test_low_power_is_inconclusive(monkeypatch: pytest.MonkeyPatch, rng) -> None:  # type: ignore[no-untyped-def]
    mod = importlib.import_module("tsinsurance.diagnostics.stationarity")

    def never(series, **kw):  # type: ignore[no-untyped-def]
        return mod.HypothesisTestResult("X", 0.0, 0.9, "h0")

    for name in ("adf", "pp", "kpss"):
        monkeypatch.setattr(mod, name, never)
    rep = mod.stationarity(pd.Series(rng.normal(size=100)), breaks=False)
    assert rep.conclusion == "inconclusive"
    assert any("baja potencia" in n for n in rep.notes)


def test_short_series_raise_with_minimum(rng) -> None:  # type: ignore[no-untyped-def]
    short = pd.Series(rng.normal(size=MIN_OBS - 1))
    for fn in (adf, pp, kpss):
        with pytest.raises(InsufficientDataError) as info:
            fn(short)
        assert info.value.required == MIN_OBS
    with pytest.raises(InsufficientDataError) as info:
        zivot_andrews(pd.Series(rng.normal(size=MIN_OBS_BREAK - 1)))
    assert info.value.required == MIN_OBS_BREAK
    rep = stationarity(pd.Series(rng.normal(size=40)))
    assert any("Zivot-Andrews omitida" in n for n in rep.notes)


def test_input_validation(rng) -> None:  # type: ignore[no-untyped-def]
    x = pd.Series(rng.normal(size=100))
    with pytest.raises(DataValidationError, match="faltantes"):
        adf(x.where(x > 0))
    with pytest.raises(DataValidationError, match="constante"):
        adf(pd.Series(np.ones(100)))
    with pytest.raises(DataValidationError, match="infinitos"):
        adf(x.replace(x.iloc[0], np.inf))
    with pytest.raises(ValueError):
        adf(x, trend="n")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="alpha"):
        stationarity(x, alpha=0.20)
    with pytest.raises(ValueError):
        stationarity(x, max_d=3)
    assert adf(rng.normal(size=100)).name == "ADF"  # type: ignore[arg-type]


def test_kpss_notes_bounded_pvalue(rng, make_random_walk) -> None:  # type: ignore[no-untyped-def]
    r = kpss(make_random_walk(rng, 1000) * 10)
    assert r.p_value == pytest.approx(0.01)
    assert r.notes and "menor" in r.notes[0]
    assert r.specification["lower_tail"] is False


def test_trend_specification_recorded(rng) -> None:  # type: ignore[no-untyped-def]
    x = pd.Series(np.arange(200) * 0.1 + rng.normal(size=200))
    for fn in (adf, pp, kpss):
        assert fn(x, trend="ct").specification["deterministic"] == "constante y tendencia"
    za, brk = zivot_andrews(x.reset_index(drop=True), trend="ct")
    assert isinstance(brk, int) and za.specification["break_in"] == "intercepto y tendencia"
