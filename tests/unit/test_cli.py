import json
from pathlib import Path

import pytest

from tsinsurance.cli import main

FIX = Path(__file__).parents[1] / "fixtures"


def test_template_and_validate_roundtrip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "m.csv"
    assert main(["template", "market", "-o", str(out), "--example"]) == 0
    assert main(["validate", "market", str(out)]) == 0
    assert "sin errores" in capsys.readouterr().out


def test_validate_bad_file_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", "market", str(FIX / "market_bad.csv")]) == 1
    out = capsys.readouterr().out
    assert "fila 1" in out and "línea del CSV" in out
    assert main(["validate", "market", str(FIX / "market_bad.csv"), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["kind"] == "market"


def test_schema_export(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["schema", "rate_nodes", "--format", "frictionless"]) == 0
    assert "tenor_years" in capsys.readouterr().out


def test_errors_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", "market", str(tmp_path / "nope.csv")]) == 2
    assert "error" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["template", "bonds", "-o", "x.csv"])
