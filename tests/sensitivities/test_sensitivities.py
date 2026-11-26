"""Sensibilidades (spec 007 T010-T011; SC-006, revisión I4)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from tsinsurance.sensitivities import (
    BondPortfolio,
    FixedBond,
    approximate,
    attribute_pnl,
    factor_greeks,
    full_revaluation,
    measures,
    node_hessian,
)
from tsinsurance.simulation import fit_factors
from tsinsurance.stochastics import NodeCurve
from tsinsurance.stochastics.curves import par_yield

CURVE = NodeCurve.from_arrays([0.25, 2, 5, 10, 30], [0.045, 0.040, 0.038, 0.041, 0.044])
BOND = FixedBond(7.3, 0.05, 2)
PORT = BondPortfolio.of([(BOND, 10), (FixedBond(25.0, 0.045, 2), 4), (FixedBond(1.5, 0.03, 2), -3)])


def test_par_bond_prices_at_par() -> None:
    y = par_yield(CURVE.discount, 10.0)
    assert FixedBond(10.0, y, 2).pv(CURVE) == pytest.approx(100.0, rel=1e-12)


def test_krd_sum_equals_fisher_weil_duration_sc006() -> None:
    for inst in (BOND, PORT):
        s = measures(inst, CURVE)
        assert sum(s.krd.values()) == pytest.approx(s.duration_eff, rel=1e-10)


def test_analytic_measures_match_central_differences() -> None:
    s = measures(PORT, CURVE)
    h = 1e-4
    up = PORT.pv(CURVE.shifted(h))
    dn = PORT.pv(CURVE.shifted(-h))
    d_fd = -(up - dn) / (2 * h) / s.pv
    c_fd = (up - 2 * s.pv + dn) / h**2 / s.pv
    assert s.duration_eff == pytest.approx(d_fd, rel=1e-6)
    assert s.convexity == pytest.approx(c_fd, rel=1e-4)
    assert s.dv01 == pytest.approx(s.pv * s.duration_eff * 1e-4)
    for i, name in enumerate(s.krd):
        bump = np.zeros(5)
        bump[i] = h
        fd = -(PORT.pv(CURVE.shifted(bump)) - PORT.pv(CURVE.shifted(-bump))) / (2 * h) / s.pv
        assert s.krd[name] == pytest.approx(fd, rel=1e-6, abs=1e-12)
    hess = node_hessian(PORT, CURVE)
    e2 = np.zeros(5)
    e2[3] = h
    e1 = np.zeros(5)
    e1[2] = h
    cross = (
        PORT.pv(CURVE.shifted(e1 + e2))
        - PORT.pv(CURVE.shifted(e1 - e2))
        - PORT.pv(CURVE.shifted(-e1 + e2))
        + PORT.pv(CURVE.shifted(-e1 - e2))
    ) / (4 * h * h)
    assert hess[2, 3] == pytest.approx(cross, rel=1e-4)


def test_zero_coupon_krd_is_on_its_bracketing_nodes() -> None:
    s = measures(FixedBond(7.5, 0.0, 1), CURVE)
    assert s.krd["5"] == pytest.approx(7.5 * 0.5) and s.krd["10"] == pytest.approx(7.5 * 0.5)
    assert s.krd["2"] == 0 and s.duration_eff == pytest.approx(7.5)


def _model():
    rng = np.random.default_rng(0)
    import pandas as pd

    from tsinsurance.simulation import nelson_siegel_loadings

    load = nelson_siegel_loadings(np.array(CURVE.tenors))
    shocks = rng.normal(size=(800, 3)) * np.array([6e-4, 4e-4, 2e-4])
    return fit_factors(pd.DataFrame(shocks @ load.T, columns=list(CURVE.tenors)), "pca", 3)


def test_delta_gamma_beats_delta_on_large_moves() -> None:
    rng = np.random.default_rng(1)
    dz = rng.normal(0, 0.01, (200, 5))  # 100 pb
    rep = approximate(PORT, CURVE, dz)
    assert rep.errors["delta_gamma"]["mae"] < 0.2 * rep.errors["delta"]["mae"]
    np.testing.assert_allclose(rep.full, full_revaluation(PORT, CURVE, dz))


def test_factor_greeks_and_attribution_close() -> None:
    model = _model()
    gk = factor_greeks(PORT, CURVE, model)
    assert gk.delta[0] < 0  # una subida del nivel reduce el valor de una cartera larga
    move = model.reconstruct(np.array([[25.0, -10.0, 5.0]]))[0]  # sólo factores
    att = attribute_pnl(PORT, CURVE, model, move, gk)
    assert abs(att.residual) < 1e-3 * abs(att.total)
    assert att.factor_moves_bp["nivel"] == pytest.approx(25.0, rel=1e-8)


def test_pv_matches_discounting_by_hand() -> None:
    t, c = BOND.cashflows()
    assert t[0] == pytest.approx(0.3) and c[-1] == pytest.approx(102.5)
    hand = sum(ci * math.exp(-float(CURVE.zero_rate(ti)) * ti) for ti, ci in zip(t, c, strict=True))
    assert BOND.pv(CURVE) == pytest.approx(hand)
