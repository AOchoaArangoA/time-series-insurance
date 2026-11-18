"""La prueba de conexión de docs/integracion/manual-de-uso.md funciona tal como se documenta."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

EJEMPLO = Path(__file__).parents[2] / "examples" / "integracion"


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


@pytest.fixture
def carpeta(tmp_path: Path) -> Path:
    destino = tmp_path / "integracion"
    shutil.copytree(EJEMPLO, destino, ignore=shutil.ignore_patterns("data", "results", "*.jsonl"))
    return destino


def test_prueba_de_conexion_documentada(carpeta: Path) -> None:
    cli = [sys.executable, "-m", "tsinsurance.cli"]
    pasos = [
        ([sys.executable, "generar_paquete_sintetico.py", "data"], "sellado"),
        ([*cli, "bundle", "validate", "data"], "Paquete válido"),
        ([*cli, "experiment", "run", "experiment.toml"], "registradas"),
        ([*cli, "experiment", "verify", "registry.jsonl"], "Bitácora íntegra."),
        ([sys.executable, "senal_propia.py"], "evaluada"),
    ]
    for cmd, esperado in pasos:
        out = _run(*cmd, cwd=carpeta)
        assert out.returncode == 0, out.stderr
        assert esperado in out.stdout

    resultados = sorted((carpeta / "results").glob("*/result.json"))
    assert len(resultados) == 2
    for path in resultados:
        r = json.loads(path.read_text(encoding="utf-8"))
        assert r["result_version"].startswith("1.")
        assert r["status"]["exploratory_reasons"] == []
        # datos simulados sin habilidad: nada significativo
        assert all(not v for v in r["status"]["significant_by_idea"].values())
