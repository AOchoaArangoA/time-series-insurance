import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from tsinsurance.backtest import (
    clark_west,
    deflated_sharpe,
    effective_number_of_trials,
    evaluate_forecasts,
    expected_max_sharpe,
    oos_r2,
    pesaran_timmermann,
    probabilistic_sharpe,
    psr_from_moments,
    sharpe_difference,
    sharpe_inference,
    spa_test,
)
from tsinsurance.errors import DataValidationError, InsufficientDataError
from tsinsurance.validation import diebold_mariano


def test_deflated_sharpe_published_example() -> None:
    # Bailey & López de Prado (2014): SR anual 2,5 (250 días), T=1250, asimetría −3,
    # curtosis 10, N=100, V[SR anual]=0,5  ⇒  DSR ≈ 0,9004.
    sr0 = expected_max_sharpe(0.5 / 250, 100)
    assert sr0 == pytest.approx(0.1132, abs=1e-4)
    dsr = psr_from_moments(2.5 / math.sqrt(250), 1250, -3.0, 10.0, sr0)
    assert dsr == pytest.approx(0.9004, abs=1e-4)
    assert expected_max_sharpe(0.1, 1) == 0.0


def test_psr_and_dsr_from_returns(rng) -> None:  # type: ignore[no-untyped-def]
    x = rng.normal(0.001, 0.01, 2000)
    assert probabilistic_sharpe(x) > 0.95
    d = deflated_sharpe(x, n_trials=50, trials_sharpe_variance=0.001, n_effective=20)
    assert d.n_effective == 20 and d.sr0 > 0 and d.dsr < probabilistic_sharpe(x)
    assert "DSR" in d.summary()
    with pytest.raises(InsufficientDataError):
        probabilistic_sharpe(x[:5])


def test_effective_number_of_trials(rng) -> None:  # type: ignore[no-untyped-def]
    base = rng.normal(size=(500, 1))
    identical = pd.DataFrame(np.repeat(base, 10, axis=1))
    independent = pd.DataFrame(rng.normal(size=(500, 10)))
    assert effective_number_of_trials(identical) == pytest.approx(1.0, abs=0.01)
    assert effective_number_of_trials(independent) > 8
    assert effective_number_of_trials(independent.iloc[:, :1]) == 1.0


def test_sharpe_inference(rng) -> None:  # type: ignore[no-untyped-def]
    x = rng.normal(0.0005, 0.01, 2520)
    inf = sharpe_inference(x, 252, reps=300, seed=1)
    assert inf.ci_low < inf.sharpe < inf.ci_high
    # Bajo iid normal el EE ≈ sqrt((1 + SR²/2)/T) anualizado y el HAC es similar.
    sr = x.mean() / x.std(ddof=1)
    assert inf.se_iid == pytest.approx(math.sqrt((1 + sr**2 / 2) / 2520) * math.sqrt(252), rel=0.05)
    assert inf.se_hac == pytest.approx(inf.se_iid, rel=0.25)
    assert sharpe_inference(x, 252, reps=300, seed=1).ci_low == inf.ci_low  # semilla
    assert "Sharpe" in inf.summary()


def test_sharpe_difference(rng) -> None:  # type: ignore[no-untyped-def]
    noise = rng.normal(0, 0.01, 2000)
    better = noise + 0.002
    res = sharpe_difference(better, noise, reps=300)
    assert res.difference > 0 and res.p_value < 0.05 and res.cer_gain > 0
    same = sharpe_difference(noise, noise, reps=300)
    assert same.p_value > 0.4
    assert "CER" in res.summary()


def test_spa(rng) -> None:  # type: ignore[no-untyped-def]
    bench = rng.normal(0.0002, 0.01, 1500)
    strategies = pd.DataFrame({"a": bench + rng.normal(0, 0.002, 1500), "b": bench + 0.001})
    res = spa_test(bench, strategies, reps=300, seed=0)
    assert res.pvalue_consistent < 0.05 and res.n_models == 2
    null = spa_test(bench, pd.DataFrame({"a": bench + rng.normal(0, 0.002, 1500)}), reps=300)
    assert null.pvalue_consistent > 0.05
    absolute = spa_test(bench, strategies, reps=200, relative=False)
    assert absolute.pvalue_lower <= absolute.pvalue_upper
    with pytest.raises(DataValidationError):
        spa_test(bench[:10], strategies)


def test_pesaran_timmermann(rng) -> None:  # type: ignore[no-untyped-def]
    y = rng.normal(size=3000)
    f = y + rng.normal(scale=2.0, size=3000)
    pt = pesaran_timmermann(f, y)
    assert pt.rejects(0.01)
    # Equivalencia asintótica con chi-cuadrado 2×2 sin corrección de continuidad.
    table = pd.crosstab(f > 0, y > 0).to_numpy()
    chi2 = stats.chi2_contingency(table, correction=False)[0]
    assert pt.statistic**2 == pytest.approx(chi2, rel=0.02)
    noise = pesaran_timmermann(rng.normal(size=3000), y)
    assert not noise.rejects(0.01)
    degenerate = pesaran_timmermann(np.abs(f) + 1, y)
    assert degenerate.p_value is None and "No aplicable" in degenerate.notes[0]


def test_clark_west_and_oos_r2_definitions(rng) -> None:  # type: ignore[no-untyped-def]
    n = 400
    y = rng.normal(size=n)
    f1 = np.zeros(n)
    f2 = 0.5 * y + rng.normal(scale=0.5, size=n)
    adj = (y - f1) ** 2 - ((y - f2) ** 2 - (f1 - f2) ** 2)
    cw = clark_west(y, f1, f2)
    assert cw.statistic == pytest.approx(adj.mean() / (adj.std(ddof=1) / math.sqrt(n)), rel=1e-10)
    assert oos_r2(y, f1, f2) == pytest.approx(1 - np.sum((y - f2) ** 2) / np.sum(y**2), rel=1e-10)
    # Invariancia a la escala.
    assert clark_west(10 * y, 10 * f1, 10 * f2).statistic == pytest.approx(cw.statistic)
    assert oos_r2(10 * y, 10 * f1, 10 * f2) == pytest.approx(oos_r2(y, f1, f2))
    ev = evaluate_forecasts(y, f1, f2)
    assert ev.n_forecasts == n and "anidados" in ev.diebold_mariano.notes[0]
    assert "Clark-West" in ev.summary()
    with pytest.raises(DataValidationError):
        clark_west(y, f1[:-1], f2)


def test_diebold_mariano(rng) -> None:  # type: ignore[no-untyped-def]
    e1 = rng.normal(scale=2.0, size=500)
    e2 = rng.normal(scale=1.0, size=500)
    dm = diebold_mariano(e1, e2)
    assert dm.statistic > 0 and dm.rejects(0.01)
    assert not diebold_mariano(e2, rng.normal(scale=1.0, size=500), loss="mae").rejects(0.01)
    assert diebold_mariano(e1, e2, h=3).specification["h"] == 3
    with pytest.raises(InsufficientDataError):
        diebold_mariano(e1[:5], e2[:5])
    with pytest.raises(DataValidationError):
        diebold_mariano(e1, e2[:-1])
