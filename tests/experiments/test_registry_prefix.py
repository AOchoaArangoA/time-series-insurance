"""La bitácora sólo agrega líneas respecto de la rama base (T010, SC-002)."""

from pathlib import Path

from tsinsurance.experiments.registry import append_trials, verify_registry


def _base(tmp_path: Path, n: int = 4) -> tuple[Path, Path]:
    base = tmp_path / "base.jsonl"
    append_trials(base, [{"kind": "signal", "i": i} for i in range(n)])
    head = tmp_path / "registry.jsonl"
    head.write_bytes(base.read_bytes())
    return base, head


def _lines(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines(keepends=True)


def test_appending_is_accepted(tmp_path: Path) -> None:
    base, head = _base(tmp_path)
    append_trials(head, [{"kind": "signal", "new": True}])
    assert verify_registry(head, base=base) == []
    assert verify_registry(base, base=base) == []


def test_empty_or_missing_base_accepts_any_intact_registry(tmp_path: Path) -> None:
    _, head = _base(tmp_path)
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert verify_registry(head, base=empty) == []
    assert verify_registry(head, base=tmp_path / "missing.jsonl") == []


def test_edit_is_rejected_with_line(tmp_path: Path) -> None:
    base, head = _base(tmp_path)
    lines = _lines(head)
    lines[1] = lines[1].replace('"i": 1', '"i": 7')
    head.write_text("".join(lines), encoding="utf-8")
    problems = verify_registry(head, base=base)
    assert any("línea 2" in p and "base" in p for p in problems)


def test_reorder_is_rejected(tmp_path: Path) -> None:
    base, head = _base(tmp_path)
    lines = _lines(head)
    lines[0], lines[1] = lines[1], lines[0]
    head.write_text("".join(lines), encoding="utf-8")
    assert any("línea 1" in p and "base" in p for p in verify_registry(head, base=base))


def test_deletion_is_rejected(tmp_path: Path) -> None:
    base, head = _base(tmp_path)
    head.write_text("".join(_lines(head)[:-1]), encoding="utf-8")
    problems = verify_registry(head, base=base)
    assert any("menos líneas que la base" in p for p in problems)


def test_whitespace_change_is_rejected(tmp_path: Path) -> None:
    """El prefijo es byte a byte: ni siquiera un cambio de formato se acepta."""
    base, head = _base(tmp_path)
    head.write_text(head.read_text(encoding="utf-8").replace(", ", ",  ", 1), encoding="utf-8")
    assert verify_registry(head, base=base)
