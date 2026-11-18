"""result.json 1.2: claves nuevas aditivas; las de 1.1 se conservan (T008, FR-025)."""

from pathlib import Path

from tsinsurance.experiments import run_experiment

KEYS_1_1 = {
    "assumptions",
    "calibration",
    "econometric",
    "experiment",
    "ideas",
    "provenance",
    "result_version",
    "status",
}
STATUS_1_1 = {"exploratory_reasons", "significant_by_idea", "econometric_quadrants"}


def test_result_1_2_is_additive(experiment_file: Path) -> None:
    r = run_experiment(experiment_file).result
    assert r["result_version"] == "1.2"
    assert set(r) >= KEYS_1_1
    assert STATUS_1_1 | {"lines_registered"} <= set(r["status"])


def test_phase_and_out_of_sample_with_train_end(experiment_file: Path) -> None:
    r = run_experiment(experiment_file).result
    # US2: con train_end la ejecución sólo calibra; la validación queda pendiente.
    assert r["phase"] == "calibration"
    assert r["status"]["out_of_sample"] == "pendiente"


def test_phase_full_sample_without_train_end(experiment_file: Path) -> None:
    text = experiment_file.read_text().replace('train_end = "2016-12-30"\n', "")
    experiment_file.write_text(text)
    r = run_experiment(experiment_file).result
    assert r["phase"] == "full_sample"
    assert r["status"]["out_of_sample"] == "ninguna"
