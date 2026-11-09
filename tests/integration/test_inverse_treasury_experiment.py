"""SC-004 (spec 003): el experimento de ETFs inversos se reproduce desde su paquete.

El paquete contiene datos de Yahoo no redistribuibles y no se versiona: la prueba se
omite si no se ha generado con ``tsinsurance bundle fetch recipe.toml data``.
"""

from pathlib import Path

import pytest

from tsinsurance.experiments import run_experiment

EXP = Path(__file__).parents[2] / "experiments" / "inverse_treasury"
pytestmark = pytest.mark.skipif(
    not (EXP / "data" / "bundle.toml").exists(), reason="paquete no generado"
)


@pytest.mark.slow
def test_inverse_treasury_reproducible(tmp_path: Path) -> None:
    a = run_experiment(EXP / "experiment.toml", registry=tmp_path / "r.jsonl", output_root=tmp_path)
    b = run_experiment(
        EXP / "experiment.toml", registry=tmp_path / "r2.jsonl", output_root=tmp_path
    )
    for key in ("ideas", "calibration", "econometric"):
        assert a.result[key] == b.result[key]
