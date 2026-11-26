"""Inferencia de paneles: DK con t(T−1), WCR, G₁ y Mundlak (spec 006 T003, T005)."""

import numpy as np
import pandas as pd
import pytest

from tsinsurance.panel.estimators import fit_panel
from tsinsurance.panel.inference import mundlak_test, wild_cluster_bootstrap


def _sector_panel(
    seed: int = 0,
    n: int = 11,
    t: int = 120,
    beta: float = 0.0,
    treated: tuple[int, ...] = (0, 1, 2),
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    f = rng.normal(size=t)
    macro = np.cumsum(rng.normal(size=t)) * 0.1
    rows = []
    for i in range(n):
        d = 1.0 if i in treated else 0.0
        load = 1 + 0.5 * rng.normal()
        e = rng.normal(size=t)
        y = 0.3 * rng.normal() + load * f + beta * macro * d + e
        for s in range(t):
            rows.append((f"S{i:02d}", s, y[s], macro[s] * d, macro[s]))
    return pd.DataFrame(rows, columns=["entity", "time", "y", "x_int", "macro"]).set_index(
        ["entity", "time"]
    )


def test_dk_uses_fixed_b_with_dof_correction_and_reports_g1() -> None:
    df = _sector_panel()
    res = fit_panel(df, "y", ["x_int"], estimator="twfe", cov="driscoll_kraay")
    bw = res.diagnostics["bandwidth_driscoll_kraay"]
    assert res.pvalue_distribution == f"fixed-b(T=120, L={bw})"
    c = res.diagnostics["driscoll_kraay_dof_correction"]
    plm = res.diagnostics["driscoll_kraay_plm_hc0"]["x_int"]
    assert c > 1 and res.std_errors["x_int"] == pytest.approx(plm * c**0.5)
    assert res.treated_clusters == {"x_int": 3} and not res.inconclusive


def test_fixed_b_reference_is_wider_than_normal_and_converges() -> None:
    from scipy import stats

    from tsinsurance.panel.inference import dk_pvalue, fixed_b_reference

    short = np.quantile(fixed_b_reference(36, 3), 0.95)
    long_ = np.quantile(fixed_b_reference(1000, 0), 0.95)
    assert short > stats.t.ppf(0.95, 35) + 0.1  # sesgo del HAC con T corto
    assert long_ == pytest.approx(stats.norm.ppf(0.95), abs=0.04)
    p_two = dk_pvalue(2.0, 36, bandwidth=3)
    assert p_two == pytest.approx(2 * min(dk_pvalue(2.0, 36, "greater", 3), 0.5), rel=1e-9)
    assert dk_pvalue(2.0, 36, bandwidth=3) > dk_pvalue(2.0, 36)


def test_single_treated_cluster_is_inconclusive() -> None:
    df = _sector_panel(treated=(0,))
    res = fit_panel(df, "y", ["x_int"], estimator="twfe", cov="driscoll_kraay")
    assert res.inconclusive == ["x_int"]
    assert any("NO CONCLUYENTE" in w for w in res.warnings)


def test_wild_cluster_bootstrap_enumerates_with_11_clusters() -> None:
    df = _sector_panel(beta=0.0)
    wb = wild_cluster_bootstrap(df, "y", ["x_int"], "x_int")
    assert wb.enumerated and wb.draws == 2**11 and wb.weights == "rademacher"
    again = wild_cluster_bootstrap(df, "y", ["x_int"], "x_int")
    assert again.pvalue_two_sided == wb.pvalue_two_sided  # determinista
    assert 0 <= wb.pvalue_greater <= 1
    strong = wild_cluster_bootstrap(_sector_panel(beta=3.0), "y", ["x_int"], "x_int")
    assert strong.pvalue_greater < wb.pvalue_greater or wb.pvalue_greater > 0.2


def test_mundlak_rejects_with_correlated_effects() -> None:
    rng = np.random.default_rng(5)
    n, t = 50, 20
    rows = []
    for i in range(n):
        a = rng.normal()
        x = 0.8 * a + rng.normal(size=t)
        y = x + a + rng.normal(size=t)
        rows += [(i, s, y[s], x[s]) for s in range(t)]
    df = pd.DataFrame(rows, columns=["entity", "time", "y", "x"]).set_index(["entity", "time"])
    res = mundlak_test(df, "y", ["x"])
    assert res.mundlak_pvalue < 0.01 and "fijos" in res.recommendation
    assert res.hausman_pvalue is not None and res.hausman_pvalue < 0.01


def test_mundlak_does_not_reject_without_correlation_and_few_groups_uses_f() -> None:
    rng = np.random.default_rng(6)
    n, t = 11, 60
    rows = []
    for i in range(n):
        a = rng.normal()
        x = rng.normal(size=t)
        y = x + a + rng.normal(size=t)
        rows += [(i, s, y[s], x[s]) for s in range(t)]
    df = pd.DataFrame(rows, columns=["entity", "time", "y", "x"]).set_index(["entity", "time"])
    res = mundlak_test(df, "y", ["x"])
    assert res.mundlak_distribution.startswith("F(1,10)")
    assert res.mundlak_pvalue > 0.01
    assert any("θ ≈ 1" in n for n in res.notes)


def test_wcr_rejects_unknown_coefficient() -> None:
    with pytest.raises(Exception, match="no está"):
        wild_cluster_bootstrap(_sector_panel(), "y", ["x_int"], "otro")


def test_fixed_b_matches_kiefer_vogelsang_bartlett_limit() -> None:
    """Límite fixed-b de Bartlett (KV 2005): t = W(1)/√Q(b), con
    Q(b) = (2/b)[∫B̄² − ∫₀^{1−b} B̄(r+b)B̄(r)], simulado de forma independiente."""
    from tsinsurance.panel.inference import fixed_b_reference

    rng = np.random.default_rng(7)
    n, b = 2000, 0.1
    k = int(b * n)
    draws = []
    for _ in range(20):
        w = np.cumsum(rng.standard_normal((1000, n)), axis=1) / np.sqrt(n)
        bridge = w - (np.arange(1, n + 1) / n) * w[:, -1:]
        q = (2 / b) * ((bridge**2).mean(axis=1) - (bridge[:, k:] * bridge[:, :-k]).sum(axis=1) / n)
        draws.append(w[:, -1] / np.sqrt(q))
    limit = np.concatenate(draws)
    ref = fixed_b_reference(1000, 99)  # b = (L + 1)/T = 0,1
    assert np.quantile(ref, 0.95) == pytest.approx(np.quantile(limit, 0.95), abs=0.03)
    assert not ref.flags.writeable


def test_dk_wild_bootstrap_matches_dk_t_and_detects_effect() -> None:
    from tsinsurance.panel.inference import dk_wild_bootstrap

    df = _sector_panel(beta=0.0)
    res = fit_panel(df, "y", ["x_int"], estimator="twfe", cov="driscoll_kraay")
    bw = res.diagnostics["bandwidth_driscoll_kraay"]
    wb = dk_wild_bootstrap(df, "y", ["x_int"], "x_int", time_effects=True, maxlag=bw, draws=499)
    assert wb.tstat == pytest.approx(res.tstats["x_int"], rel=1e-8)
    assert wb.se == pytest.approx(res.std_errors["x_int"], rel=1e-8)
    assert 0.0 < wb.pvalue_greater <= 1.0 and "bloques" in wb.weights
    strong = _sector_panel(beta=3.0)
    wb2 = dk_wild_bootstrap(
        strong, "y", ["x_int"], "x_int", time_effects=True, maxlag=bw, draws=499
    )
    assert wb2.pvalue_two_sided < 0.01


def test_score_stability_detects_coefficient_break() -> None:
    from tsinsurance.panel.inference import score_stability

    df = _sector_panel(beta=0.3)
    stable = score_stability(df, "y", ["x_int"], "x_int", time_effects=True, maxlag=4)
    t_idx = df.index.get_level_values(1)
    late = t_idx >= sorted(set(t_idx))[len(set(t_idx)) // 2]
    broken = df.assign(y=df["y"] + np.where(late, 1.5, 0.0) * df["x_int"])
    moved = score_stability(broken, "y", ["x_int"], "x_int", time_effects=True, maxlag=4)
    assert stable["pvalue"] > 0.05 and moved["pvalue"] < 0.01


def test_mundlak_test_subset_keeps_all_regressors() -> None:
    from tsinsurance.panel.inference import mundlak_test

    df = _sector_panel()
    full = mundlak_test(df, "y", ["x_int", "macro"], test=["x_int"])
    assert full.mundlak_df == 1
