"""Estimadores de panel: sesgo por confusor fijo, absorción y advertencias (spec 006, US1)."""

import numpy as np
import pandas as pd
import pytest

from tsinsurance.errors import DataValidationError
from tsinsurance.panel.estimators import fit_panel


def _panel(n: int = 30, t: int = 40, seed: int = 0, corr: float = 0.7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ent = np.repeat(np.arange(n), t)
    per = np.tile(np.arange(t), n)
    a = rng.normal(size=n)  # confusor constante por unidad
    f = rng.normal(size=t)  # choque común de tiempo
    x = corr * a[ent] + 0.5 * f[per] + rng.normal(size=n * t)
    y = 1.0 * x + 2.0 * a[ent] + f[per] + rng.normal(size=n * t)
    dates = pd.date_range("2000-01-31", periods=t, freq="ME")
    return pd.DataFrame(
        {
            "entity": [f"U{i}" for i in ent],
            "time": dates[per],
            "y": y,
            "x": x,
            "const_unit": a[ent],
            "common": f[per],
        }
    )


def test_fixed_effects_remove_time_invariant_confounder() -> None:
    df = _panel()
    pooled = fit_panel(df, "y", ["x"], estimator="pooled", cov="robust")
    fe = fit_panel(df, "y", ["x"], estimator="twfe", cov="clustered_entity")
    assert abs(pooled.params["x"] - 1.0) > 0.3  # sesgado por el confusor fijo
    assert abs(fe.params["x"] - 1.0) < 0.1


def test_within_equals_dummy_regression() -> None:
    import statsmodels.formula.api as smf

    df = _panel(n=10, t=15)
    fe = fit_panel(df, "y", ["x"], estimator="fe", cov="unadjusted")
    dummies = smf.ols("y ~ x + C(entity)", data=df).fit()
    assert fe.params["x"] == pytest.approx(dummies.params["x"], rel=1e-8)
    # Within manual (Facure, cap. 14)
    d = df.assign(
        yw=df.y - df.groupby("entity").y.transform("mean"),
        xw=df.x - df.groupby("entity").x.transform("mean"),
    )
    manual = smf.ols("yw ~ xw - 1", data=d).fit()
    assert fe.params["x"] == pytest.approx(manual.params["xw"], rel=1e-8)


def test_absorbed_regressors_are_reported() -> None:
    df = _panel()
    fe = fit_panel(df, "y", ["x", "const_unit"], estimator="fe")
    assert "const_unit" in fe.absorbed and "const_unit" not in fe.params
    tw = fit_panel(df, "y", ["x", "common"], estimator="twfe")
    assert "common" in tw.absorbed and "interacción" in tw.absorbed["common"]
    with pytest.raises(DataValidationError, match="absorbidos"):
        fit_panel(df, "y", ["const_unit"], estimator="fe")


def test_few_clusters_warning_and_alternative() -> None:
    df = _panel(n=11, t=200)
    res = fit_panel(df, "y", ["x"], estimator="twfe", cov="clustered_entity")
    assert any("11 unidades" in w for w in res.warnings)
    assert "x" in res.diagnostics["driscoll_kraay_std_errors"]


def test_assumptions_are_explicit_and_unbalanced_supported() -> None:
    df = _panel().iloc[5:]  # desbalanceado
    res = fit_panel(df, "y", ["x"], estimator="fe")
    assert not res.balanced
    text = " ".join(res.assumptions)
    assert "CONSTANTES EN EL TIEMPO" in text and "causalidad inversa" in text
    assert "Supuesto:" in res.summary()


def test_random_effects_components() -> None:
    rng = np.random.default_rng(3)
    n, t = 40, 20
    ent = np.repeat(np.arange(n), t)
    a = rng.normal(size=n)
    x = rng.normal(size=n * t)  # sin correlación con a: RE consistente
    y = 0.5 * x + a[ent] + rng.normal(size=n * t)
    df = pd.DataFrame({"entity": ent, "time": np.tile(np.arange(t), n), "y": y, "x": x})
    re = fit_panel(df, "y", ["x"], estimator="re", cov="clustered_entity")
    assert abs(re.params["x"] - 0.5) < 0.1
    assert re.re_components["sigma2_entity"] > 0 and 0 < re.re_components["theta_mean"] < 1
