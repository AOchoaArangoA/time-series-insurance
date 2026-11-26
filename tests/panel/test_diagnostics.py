"""Diagnósticos del panel (spec 006 T002; revisión B3, I2, I5)."""

import numpy as np
import pandas as pd

from tsinsurance.panel.diagnostics import panel_diagnostics, pesaran_cd, wooldridge_serial


def _panel(
    n: int = 15, t: int = 120, *, rho_e: float = 0.0, factor: float = 0.0, seed: int = 1
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    f = rng.normal(size=t)
    rows = []
    for i in range(n):
        a = rng.normal()
        x = rng.normal(size=t)
        e = np.zeros(t)
        for s in range(t):
            e[s] = (rho_e * e[s - 1] if s else 0.0) + rng.normal()
        y = a + 0.5 * x + factor * (1 + 0.5 * i / n) * f + e
        for s in range(t):
            rows.append((f"U{i}", s, y[s], x[s]))
    return pd.DataFrame(rows, columns=["entity", "time", "y", "x"]).set_index(["entity", "time"])


def test_wooldridge_detects_serial_correlation() -> None:
    assert wooldridge_serial(_panel(), "y", ["x"])["pvalue"] > 0.01
    assert wooldridge_serial(_panel(rho_e=0.6), "y", ["x"])["pvalue"] < 0.01


def test_pesaran_cd_detects_common_factor() -> None:
    quiet = _panel()
    loud = _panel(factor=2.0)

    def resid(df: pd.DataFrame) -> pd.Series:
        dm = df - df.groupby(level=0).transform("mean")
        beta = (dm.x * dm.y).sum() / (dm.x**2).sum()
        return dm.y - beta * dm.x

    assert pesaran_cd(resid(quiet))["pvalue"] > 0.01
    assert pesaran_cd(resid(loud))["pvalue"] < 1e-6


def test_panel_diagnostics_flags_persistent_correlated_regressor() -> None:
    rng = np.random.default_rng(4)
    n, t = 11, 240
    common = np.zeros(t)
    shocks = rng.normal(size=t)
    for s in range(1, t):
        common[s] = 0.97 * common[s - 1] + shocks[s]
    rows = []
    for i in range(n):
        # Innovaciones del regresor correlacionadas con los errores de y (Stambaugh).
        e = -0.8 * shocks + 0.6 * rng.normal(size=t)
        y = 0.1 * common * (1 + i / n) + e
        for s in range(t):
            rows.append((f"U{i}", s, y[s], common[s] * (1 + i / n)))
    df = pd.DataFrame(rows, columns=["entity", "time", "y", "x"]).set_index(["entity", "time"])
    d = panel_diagnostics(df, "y", ["x"])
    assert d.persistence["x"]["rho"] > 0.9
    assert not d.passed and any("Stambaugh" in w for w in d.warnings)


def test_time_effects_warning_on_cd() -> None:
    d = panel_diagnostics(_panel(), "y", ["x"], time_effects=True)
    assert any("Juodis" in w for w in d.warnings)
