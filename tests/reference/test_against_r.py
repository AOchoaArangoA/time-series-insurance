"""Comparación con implementaciones independientes de R (SC-003 de la spec 001, T044/T082).

Paquetes: urca (ur.df, ur.pp), tseries (kpss.test, jarque.bera.test), stats (Box.test),
FinTS (ArchTest) y forecast (dm.test). Se omite si ``Rscript`` no está instalado.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tsinsurance.data import Snapshot, prepare, to_wide
from tsinsurance.diagnostics import adf, arch_lm, jarque_bera, kpss, ljung_box, pp
from tsinsurance.validation import diebold_mariano

ROOT = Path(__file__).parents[2]
R_SCRIPT = Path(__file__).parent / "r" / "reference_gs10.R"

pytestmark = pytest.mark.skipif(shutil.which("Rscript") is None, reason="R no instalado")

# Phillips-Perron: urca usa otra convención para la varianza de largo plazo (≈5e-4).
TOLERANCE = {"PP Z-tau (c)": 1e-3}


def test_statistics_match_r(tmp_path: Path) -> None:
    x = prepare(
        to_wide(Snapshot.load(ROOT / "examples/data/fred_gs10").data)["GS10"], freq="M"
    ).data
    d = x.diff().dropna()
    rng = np.random.default_rng(0)
    e1, e2 = rng.normal(0, 2, 300), rng.normal(0, 1.5, 300)
    pd.DataFrame({"x": x.to_numpy()}).to_csv(tmp_path / "gs10.csv", index=False)
    pd.DataFrame({"d": d.to_numpy()}).to_csv(tmp_path / "dgs10.csv", index=False)
    pd.DataFrame({"e1": e1, "e2": e2}).to_csv(tmp_path / "dm.csv", index=False)
    pp_result = pp(x)
    ours = {
        "ADF(c, 3 rezagos fijos)": adf(x, autolag=None, maxlag=3).statistic,
        "PP Z-tau (c)": pp_result.statistic,
        "KPSS nivel (rezagos 5)": kpss(x, nlags=5).statistic,
        "Ljung-Box(10) dGS10": ljung_box(d, lags=10).statistic,
        "Jarque-Bera dGS10": jarque_bera(d).statistic,
        "ARCH-LM(5) dGS10": arch_lm(d, lags=5).statistic,
        "Diebold-Mariano (HLN) h=1": diebold_mariano(e1, e2).statistic,
    }
    out = subprocess.run(
        ["Rscript", str(R_SCRIPT), str(tmp_path), str(pp_result.specification["lags"])],
        capture_output=True,
        text=True,
        check=True,
    )
    ref = json.loads(out.stdout)
    for name, value in ours.items():
        assert value == pytest.approx(ref[name], rel=TOLERANCE.get(name, 1e-8)), name
