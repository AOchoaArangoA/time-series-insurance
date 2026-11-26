"""Curvas, conversiones y valoración afín (spec 007 T001, T004, T005)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from tsinsurance.errors import DataValidationError
from tsinsurance.stochastics import (
    HullWhite,
    NodeCurve,
    RateQuote,
    VasicekP,
    calibrate_q,
    ou_joint_moments,
    q_params,
    zero_coupon,
)
from tsinsurance.stochastics.curves import (
    continuous_from_discount,
    continuous_from_periodic,
    par_yield,
    periodic_from_continuous,
)

P = {"kappa": 0.3, "theta": 0.04, "sigma": 0.012}


def test_node_curve_interpolation_flat_ends_and_right_continuous_forward() -> None:
    c = NodeCurve.from_arrays([1, 2, 5], [0.02, 0.03, 0.04])
    assert c.zero_rate(1.5) == pytest.approx(0.025)
    assert c.zero_rate(0.5) == pytest.approx(0.02) and c.zero_rate(10) == pytest.approx(0.04)
    assert c.discount(2.0) == pytest.approx(math.exp(-0.06))
    # f = z + t·z': en el nodo t = 2 se usa la pendiente del tramo derecho (0,01/3).
    assert c.forward(2.0) == pytest.approx(0.03 + 2 * 0.01 / 3)
    assert c.forward(1.5) == pytest.approx(0.025 + 1.5 * 0.01)
    assert c.forward(7.0) == pytest.approx(0.04)
    with pytest.raises(DataValidationError):
        NodeCurve.from_arrays([2, 1], [0.01, 0.02])


def test_rate_conversions() -> None:
    d = 0.05
    r = continuous_from_discount(d, 91)
    price = 1 - d * 91 / 360
    assert math.exp(-r * 91 / 365) == pytest.approx(price)
    y = 0.045
    assert periodic_from_continuous(continuous_from_periodic(y)) == pytest.approx(y)
    flat = NodeCurve.from_arrays([1.0], [0.04])
    # Curva plana continua z ⇒ par semestral = 2(e^{z/2} − 1).
    assert par_yield(flat.discount, 10.0) == pytest.approx(2 * (math.exp(0.02) - 1), rel=1e-12)


def test_vasicek_zero_coupon_limits_and_long_rate() -> None:
    assert zero_coupon("vasicek", P, 0.03, 1e-10) == pytest.approx(1.0)
    long_rate = -math.log(float(zero_coupon("vasicek", P, 0.03, 500.0))) / 500.0
    r_inf = P["theta"] - P["sigma"] ** 2 / (2 * P["kappa"] ** 2)
    assert long_rate == pytest.approx(r_inf, abs=2e-4)


def test_vasicek_zero_coupon_matches_exact_joint_simulation() -> None:
    r0, tau = 0.02, 5.0
    mean, cov = ou_joint_moments(r0 - P["theta"], P["kappa"], P["sigma"], tau)
    rng = np.random.default_rng(1)
    integral = P["theta"] * tau + mean[1] + math.sqrt(cov[1, 1]) * rng.standard_normal(200_000)
    mc = np.exp(-integral)
    closed = float(zero_coupon("vasicek", P, r0, tau))
    assert abs(mc.mean() - closed) < 3 * mc.std() / math.sqrt(mc.size)


def test_cir_zero_coupon_matches_fine_grid_simulation() -> None:
    from tsinsurance.stochastics.short_rate import _simulate

    pq = {"kappa": 0.5, "theta": 0.04, "sigma": 0.08}
    r0, tau, dt = 0.03, 2.0, 1 / 365
    steps = int(tau / dt)
    paths = _simulate(
        "cir",
        pq["kappa"],
        pq["theta"],
        pq["sigma"],
        dt,
        r0,
        steps,
        20_000,
        np.random.default_rng(2),
    )
    integral = dt * (paths[:, 1:-1].sum(axis=1) + 0.5 * (paths[:, 0] + paths[:, -1]))
    mc = np.exp(-integral)
    closed = float(zero_coupon("cir", pq, r0, tau))
    assert abs(mc.mean() - closed) < 3 * mc.std() / math.sqrt(mc.size) + 1e-6


def test_cir_tends_to_vasicek_deterministic_limit() -> None:
    a, th, r0, tau = 0.4, 0.05, 0.02, 3.0
    det = math.exp(-(th * tau + (r0 - th) * (1 - math.exp(-a * tau)) / a))
    cir = float(zero_coupon("cir", {"kappa": a, "theta": th, "sigma": 1e-5}, r0, tau))
    vas = float(zero_coupon("vasicek", {"kappa": a, "theta": th, "sigma": 1e-5}, r0, tau))
    assert cir == pytest.approx(det, rel=1e-7) and vas == pytest.approx(det, rel=1e-7)


def test_hull_white_fits_initial_curve() -> None:
    curve = NodeCurve.from_arrays([0.25, 2, 5, 10, 30], [0.045, 0.040, 0.038, 0.041, 0.044])
    hw = HullWhite(a=0.1, sigma=0.01, curve=curve)
    for t in (1.0, 7.0, 20.0):
        d = hw.simulate_discount(t, 100_000, rng=3)
        assert abs(d.mean() - float(curve.discount(t))) < 3 * d.std() / math.sqrt(d.size)
    # P(0, T) cerrado con r_0 = α(0) = f(0, 0) reproduce la curva (identidad).
    r0 = float(hw.alpha(0.0))
    assert hw.zero_coupon(0.0, 5.0, r0) == pytest.approx(float(curve.discount(5.0)), rel=1e-12)
    paths = hw.simulate(np.linspace(0, 1, 13), 50, rng=4)
    assert paths.shape == (50, 13) and np.allclose(paths[:, 0], r0)


def test_q_params_girsanov_relations() -> None:
    fit = VasicekP.fit(
        np.full(200, 0.03) + np.random.default_rng(0).normal(0, 1e-4, 200), bootstrap=0
    )
    lam = 0.2
    vq = q_params("vasicek", fit, lam)
    assert vq["kappa"] == fit.kappa and vq["theta"] == pytest.approx(
        fit.theta - lam * fit.sigma / fit.kappa
    )
    assert vq["sigma"] == fit.sigma


def test_calibrate_q_recovers_market_price_of_risk() -> None:
    rng = np.random.default_rng(5)
    dt = 1 / 252
    fit = VasicekP.fit(_vasicek_path(rng, 3000, dt), dt, bootstrap=0)
    lam_true = -0.3
    pq = q_params("vasicek", fit, lam_true)
    dates = pd.bdate_range("2020-01-01", periods=250)
    r = pd.Series(0.03 + 0.01 * np.sin(np.arange(250) / 40), index=dates)
    conv = {
        "^IRX": RateQuote(0.25, "discount"),
        "^FVX": RateQuote(5.0, "par"),
        "^TNX": RateQuote(10.0, "par"),
    }
    from tsinsurance.stochastics.affine import _model_quote

    quotes = pd.DataFrame(
        {c: _model_quote("vasicek", pq, r.to_numpy(), q) for c, q in conv.items()}, index=dates
    )
    cal = calibrate_q("vasicek", quotes, conv, r, fit)
    assert cal.lam == pytest.approx(lam_true, abs=1e-6)
    assert max(cal.rmse_bp.values()) < 1e-3
    free = calibrate_q("vasicek", quotes, conv, r, fit, mode="free")
    assert free.params_q["theta"] == pytest.approx(pq["theta"], abs=1e-6)


def _vasicek_path(rng: np.random.Generator, n: int, dt: float) -> np.ndarray:
    k, th, s = 0.5, 0.04, 0.01
    e = math.exp(-k * dt)
    sd = s * math.sqrt((1 - e**2) / (2 * k))
    x = np.empty(n)
    x[0] = th
    for t in range(1, n):
        x[t] = th + (x[t - 1] - th) * e + sd * rng.standard_normal()
    return x
