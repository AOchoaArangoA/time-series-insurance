"""Paneles frente a plm de R con valores guardados (spec 006, T004; revisión M1).

Se generan con ``tests/reference/r/plm_reference.R`` y se versionan para que la CI verifique
sin R.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from tsinsurance.panel.diagnostics import pesaran_cd, wooldridge_serial
from tsinsurance.panel.estimators import fit_panel
from tsinsurance.panel.inference import driscoll_kraay, hausman_test

DATA = Path(__file__).parents[1] / "data" / "reference"
REF = json.loads((DATA / "plm_reference.json").read_text(encoding="utf-8"))
DF = pd.read_csv(DATA / REF["input"]).set_index(["entity", "time"])


def test_fixed_effects_and_clustered_errors() -> None:
    fe = fit_panel(DF, "y", ["x"], estimator="fe", cov="unadjusted")
    assert fe.params["x"] == pytest.approx(REF["fe_coef"], rel=1e-10)
    assert fe.std_errors["x"] == pytest.approx(REF["fe_se_unadjusted"], rel=1e-8)
    cl = fit_panel(DF, "y", ["x"], estimator="fe", cov="clustered_entity")
    assert cl.std_errors["x"] == pytest.approx(REF["fe_se_cluster_hc1"], rel=1e-8)
    tw = fit_panel(DF, "y", ["x"], estimator="twfe", cov="unadjusted")
    assert tw.params["x"] == pytest.approx(REF["twfe_coef"], rel=1e-10)


def test_driscoll_kraay_matches_vcovscc() -> None:
    fe = driscoll_kraay(DF, "y", ["x"], time_effects=False, maxlag=3)
    tw = driscoll_kraay(DF, "y", ["x"], time_effects=True, maxlag=3)
    assert fe["x"] == pytest.approx(REF["fe_se_scc_hc0_lag3"], rel=1e-8)
    assert tw["x"] == pytest.approx(REF["twfe_se_scc_hc0_lag3"], rel=1e-8)


def test_random_effects() -> None:
    re = fit_panel(DF, "y", ["x"], estimator="re", cov="unadjusted")
    assert re.params["x"] == pytest.approx(REF["re_coef"], rel=1e-6)
    assert re.re_components["theta_mean"] == pytest.approx(REF["re_theta"], abs=1e-8)


def test_diagnostics() -> None:
    dm = DF - DF.groupby(level=0).transform("mean")
    b = (dm.x * dm.y).sum() / (dm.x**2).sum()
    assert pesaran_cd(dm.y - b * dm.x)["CD"] == pytest.approx(REF["pesaran_cd"], rel=1e-10)
    assert wooldridge_serial(DF, "y", ["x"])["F"] == pytest.approx(REF["wooldridge_fd_F"], rel=1e-8)


def test_hausman_close_to_plm() -> None:
    """Hausman con la corrección "sigmamore" (deliberada): difiere de phtest en < 3 %."""
    stat, _ = hausman_test(DF, "y", ["x"])
    assert stat == pytest.approx(REF["hausman_chisq"], rel=0.03)
