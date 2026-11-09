"""Pruebas de referencia (SC-003).

(a) Igualdad con las implementaciones de referencia (statsmodels / arch) con diferencia
relativa < 1e-6 sobre un conjunto de datos publicado (statsmodels macrodata: PIB real
de EE. UU., 1959T1-2009T3).
(b) Valores críticos publicados: MacKinnon (2010) para ADF y la tabla 1 de KPSS (1992).
"""

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from arch.unitroot import PhillipsPerron
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.stattools import kpss as sm_kpss

from tsinsurance.diagnostics import adf, kpss, pp

REL = 1e-6


@pytest.fixture(scope="module")
def log_gdp() -> pd.Series:
    data = sm.datasets.macrodata.load_pandas().data
    return pd.Series(np.log(data["realgdp"].to_numpy()), name="log_realgdp")


@pytest.mark.parametrize("trend", ["c", "ct"])
def test_adf_matches_statsmodels(log_gdp: pd.Series, trend: str) -> None:
    ours = adf(log_gdp, trend=trend)  # type: ignore[arg-type]
    ref = adfuller(log_gdp.to_numpy(), regression=trend, autolag="AIC", result_object=True)
    assert ours.statistic == pytest.approx(ref.statistic, rel=REL)
    assert ours.p_value == pytest.approx(ref.pvalue, rel=REL)
    assert ours.specification["lags"] == ref.lags


@pytest.mark.parametrize("trend", ["c", "ct"])
def test_pp_matches_arch(log_gdp: pd.Series, trend: str) -> None:
    ours = pp(log_gdp, trend=trend)  # type: ignore[arg-type]
    ref = PhillipsPerron(log_gdp.to_numpy(), trend=trend)
    assert ours.statistic == pytest.approx(ref.stat, rel=REL)
    assert ours.p_value == pytest.approx(ref.pvalue, rel=REL)


@pytest.mark.parametrize("trend", ["c", "ct"])
def test_kpss_matches_statsmodels(log_gdp: pd.Series, trend: str) -> None:
    ours = kpss(log_gdp, trend=trend)  # type: ignore[arg-type]
    ref = sm_kpss(log_gdp.to_numpy(), regression=trend, nlags="auto", result_object=True)
    assert ours.statistic == pytest.approx(ref.statistic, rel=REL)


def test_adf_asymptotic_critical_values_mackinnon(rng) -> None:  # type: ignore[no-untyped-def]
    # MacKinnon (2010), tabla 1, caso con constante, n -> infinito: -3.43, -2.86, -2.57.
    cv = adf(pd.Series(rng.normal(size=100_000)), autolag=None, maxlag=0).critical_values
    assert cv["1%"] == pytest.approx(-3.43, abs=0.01)
    assert cv["5%"] == pytest.approx(-2.86, abs=0.01)
    assert cv["10%"] == pytest.approx(-2.57, abs=0.01)


@pytest.mark.parametrize(
    ("trend", "expected"),
    [
        ("c", {"10%": 0.347, "5%": 0.463, "1%": 0.739}),
        ("ct", {"10%": 0.119, "5%": 0.146, "1%": 0.216}),
    ],
)
def test_kpss_critical_values_published(rng, trend: str, expected: dict[str, float]) -> None:  # type: ignore[no-untyped-def]
    cv = kpss(pd.Series(rng.normal(size=200)), trend=trend).critical_values  # type: ignore[arg-type]
    for level, value in expected.items():
        assert cv[level] == pytest.approx(value, abs=1e-3)


def test_log_gdp_is_unit_root_in_levels(log_gdp: pd.Series) -> None:
    # Resultado clásico (Nelson & Plosser 1982): el PIB real en logaritmos tiene raíz unitaria.
    assert not adf(log_gdp, trend="ct").rejects(0.05)
    assert kpss(log_gdp, trend="c").rejects(0.05)
