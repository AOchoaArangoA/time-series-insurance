"""Un solo escritor a la vez: bloqueo de la bitácora durante toda la ejecución (T011, I1, M2)."""

import json
import os
import socket
from pathlib import Path

import pytest

import tsinsurance.experiments.runner as runner_mod
from tsinsurance.cli import main
from tsinsurance.errors import RegistryLockedError
from tsinsurance.experiments import run_experiment
from tsinsurance.experiments.registry import (
    append_trials,
    lock_path,
    read_lock,
    read_registry,
    registry_lock,
    unlock_registry,
    verify_registry,
)


def _fake_lock(reg: Path, *, pid: int, host: str, hours_old: float = 0.0) -> Path:
    import datetime as dt

    created = dt.datetime.now(dt.UTC) - dt.timedelta(hours=hours_old)
    lp = lock_path(reg)
    lp.write_text(
        json.dumps(
            {"pid": pid, "host": host, "run_id": "otro-run", "created_at": created.isoformat()}
        ),
        encoding="utf-8",
    )
    return lp


def _dead_pid() -> int:
    pid = 2**22 - 7
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return pid
        except PermissionError:
            pass
        pid -= 1


def test_lock_is_exclusive_and_released(tmp_path: Path) -> None:
    reg = tmp_path / "registry.jsonl"
    with registry_lock(reg, "run-1"):
        info = read_lock(reg)
        assert info is not None and info.run_id == "run-1" and info.pid == os.getpid()
        with pytest.raises(RegistryLockedError, match="run-1"), registry_lock(reg, "run-2"):
            pass
    assert read_lock(reg) is None
    with registry_lock(reg, "run-3"):
        pass


def test_lock_released_on_error(tmp_path: Path) -> None:
    reg = tmp_path / "registry.jsonl"
    with pytest.raises(RuntimeError), registry_lock(reg, "run-1"):
        raise RuntimeError("falla")
    assert not lock_path(reg).exists()


def test_run_fails_when_registry_locked(experiment_file: Path) -> None:
    reg = experiment_file.parent / "registry.jsonl"
    with registry_lock(reg, "ocupada"):
        with pytest.raises(RegistryLockedError):
            run_experiment(experiment_file)
        assert main(["experiment", "run", str(experiment_file)]) == 3
    assert not reg.exists()  # no escribió nada


def test_lock_covers_whole_run(experiment_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Otra escritura entre la lectura de la bitácora y la escritura final queda excluida."""
    reg = experiment_file.parent / "registry.jsonl"
    seen: list[bool] = []
    original = runner_mod.select

    def spy(*args: object, **kwargs: object) -> object:
        # A mitad de la ejecución (después de leer la bitácora, antes de la escritura final).
        seen.append(lock_path(reg).exists())
        with pytest.raises(RegistryLockedError), registry_lock(reg, "intrusa"):
            pass
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(runner_mod, "select", spy)
    run_experiment(experiment_file)
    assert seen and all(seen)
    assert not lock_path(reg).exists()
    assert verify_registry(reg) == []


def test_record_false_does_not_lock(experiment_file: Path) -> None:
    reg = experiment_file.parent / "registry.jsonl"
    with registry_lock(reg, "ocupada"):
        res = run_experiment(experiment_file, record=False)
    assert res.n_trials_registered == 0


def test_stale_lock_dead_pid_same_host(tmp_path: Path) -> None:
    reg = tmp_path / "registry.jsonl"
    _fake_lock(reg, pid=_dead_pid(), host=socket.gethostname())
    info = read_lock(reg)
    assert info is not None and info.stale
    with pytest.raises(RegistryLockedError, match="vencido"), registry_lock(reg, "run"):
        pass  # nunca se libera solo
    assert unlock_registry(reg) is not None
    assert not lock_path(reg).exists()


def test_live_pid_same_host_needs_force_even_if_old(tmp_path: Path) -> None:
    reg = tmp_path / "registry.jsonl"
    _fake_lock(reg, pid=os.getpid(), host=socket.gethostname(), hours_old=48)
    info = read_lock(reg)
    assert info is not None and not info.stale
    with pytest.raises(RegistryLockedError, match="--force"):
        unlock_registry(reg)
    assert unlock_registry(reg, force=True) is not None


def test_other_host_stale_only_by_age(tmp_path: Path) -> None:
    reg = tmp_path / "registry.jsonl"
    _fake_lock(reg, pid=1, host="otra-maquina", hours_old=1)
    lock = read_lock(reg)
    assert lock is not None and not lock.stale
    _fake_lock(reg, pid=1, host="otra-maquina", hours_old=7)
    lock = read_lock(reg)
    assert lock is not None and lock.stale


def test_unlock_without_lock_returns_none(tmp_path: Path) -> None:
    assert unlock_registry(tmp_path / "registry.jsonl") is None


def test_interrupted_write_is_repaired_on_unlock(tmp_path: Path) -> None:
    """Una última línea JSON truncada (escritura interrumpida) se aparta, no se pierde."""
    reg = tmp_path / "registry.jsonl"
    append_trials(reg, [{"kind": "signal", "i": i} for i in range(3)])
    with reg.open("a", encoding="utf-8") as fh:
        fh.write('{"kind": "signal", "i": 3, "prev_ha')
    with pytest.raises(ValueError, match="incompleta"):
        read_registry(reg)
    _fake_lock(reg, pid=_dead_pid(), host=socket.gethostname())
    info = unlock_registry(reg)
    assert info is not None and info.repaired is not None
    assert Path(info.repaired).read_text(encoding="utf-8").startswith('{"kind": "signal", "i": 3')
    assert len(read_registry(reg)) == 3 and verify_registry(reg) == []


def test_cli_unlock(tmp_path: Path) -> None:
    reg = tmp_path / "registry.jsonl"
    _fake_lock(reg, pid=os.getpid(), host=socket.gethostname())
    assert main(["experiment", "unlock", str(reg)]) == 3
    assert main(["experiment", "unlock", str(reg), "--force"]) == 0
    assert main(["experiment", "unlock", str(reg)]) == 0
