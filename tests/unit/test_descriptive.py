import numpy as np
import pandas as pd
import pytest

from tsinsurance.diagnostics import arch_lm, describe, jarque_bera, ljung_box


def test_describe_white_noise() -> None:
    x = pd.Series(np.random.default_rng(0).normal(size=1000), name="wn")
    rep = describe(x)
    assert rep.series_id == "wn"
    assert rep.stats["n"] == 1000 and abs(rep.stats["mean"]) < 0.1
    assert len(rep.acf) == 20 and rep.acf.index[0] == 1
    assert rep.confidence_band == pytest.approx(1.96 / np.sqrt(1000))
    assert not rep.ljung_box.rejects(0.01)
    assert not rep.arch_lm.rejects(0.01)
    assert "Jarque-Bera" in rep.summary()


def test_describe_detects_heavy_tails_and_arch(rng, make_arma_garch) -> None:  # type: ignore[no-untyped-def]
    rep = describe(make_arma_garch(rng, 3000, alpha=0.15, beta=0.8, nu=5.0))
    assert rep.stats["excess_kurtosis"] > 1.0
    assert rep.jarque_bera.rejects(0.01)
    assert rep.arch_lm.rejects(0.01)
    assert rep.ljung_box_squared.rejects(0.01)


def test_arch_lm_no_false_positive_with_nonzero_mean() -> None:
    # Revisión econométrica: sin centrar, un AR(1) homocedástico con media 100 "tenía" ARCH.
    from tests.conftest import simulate_ar1

    rng = np.random.default_rng(7)
    # describe() aplica ARCH-LM sobre residuos de un AR(p): la dinámica de la media no se
    # confunde con heterocedasticidad condicional.
    rejections = sum(
        describe(simulate_ar1(rng, 500, 0.5) + 100.0).arch_lm.rejects(0.05) for _ in range(100)
    )
    assert rejections <= 12


def test_tests_reject_non_finite() -> None:
    from tsinsurance.errors import DataValidationError

    for fn in (jarque_bera, ljung_box, arch_lm):
        with pytest.raises(DataValidationError):
            fn(np.array([1.0, np.nan, 2.0] * 20))


def test_individual_tests(rng) -> None:  # type: ignore[no-untyped-def]
    x = rng.normal(size=500)
    assert jarque_bera(x).specification["df"] == 2
    lb = ljung_box(x, lags=10, model_df=2)
    assert lb.specification["df"] == 8
    with pytest.raises(ValueError):
        ljung_box(x, lags=2, model_df=2)
    assert arch_lm(x, lags=3).specification["lags"] == 3
