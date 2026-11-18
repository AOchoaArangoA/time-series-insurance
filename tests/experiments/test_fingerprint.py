"""Huella del código de las señales (spec 004, US3: T035; revisión I2 del diseño)."""

import functools
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tsinsurance.experiments.fingerprint import fingerprint
from tsinsurance.experiments.signals import get_signal

VENTANA = 120


def base(prices: pd.DataFrame, ventana: int = 120) -> pd.DataFrame:
    """Ruptura de máximos."""
    return (prices > prices.rolling(ventana).max().shift(1)).astype(float)


def same_but_comments(prices: pd.DataFrame, ventana: int = 120) -> pd.DataFrame:
    """Otro docstring distinto."""
    # un comentario
    return (prices  >  prices.rolling(ventana).max().shift(1)).astype(float)  # fmt: skip


def other_body(prices: pd.DataFrame, ventana: int = 120) -> pd.DataFrame:
    return (prices >= prices.rolling(ventana).max().shift(1)).astype(float)


def other_default(prices: pd.DataFrame, ventana: int = 121) -> pd.DataFrame:
    return (prices > prices.rolling(ventana).max().shift(1)).astype(float)


def uses_global(prices: pd.DataFrame) -> pd.DataFrame:
    return (prices > prices.rolling(VENTANA).max().shift(1)).astype(float)


def _helper(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.rolling(20).mean()


def uses_helper(prices: pd.DataFrame) -> pd.DataFrame:
    return (prices > _helper(prices)).astype(float)


def _rename(fn, name):  # type: ignore[no-untyped-def]
    fn.__name__ = name
    return fn


def test_same_code_same_hash_and_cosmetics_ignored() -> None:
    a = fingerprint(base)
    assert a.coverage == "source" and len(a.hash) == 32
    assert fingerprint(base) == a
    # docstring, comentarios y espacios no cambian la huella (sólo el nombre de la función)
    assert (
        fingerprint(same_but_comments).hash == fingerprint(_rename(same_but_comments, "base")).hash
    )


def test_body_and_default_changes_change_hash() -> None:
    h = fingerprint(base).hash
    assert fingerprint(_rename(other_body, "base")).hash != h
    assert fingerprint(_rename(other_default, "base")).hash != h


def test_global_constant_and_helper_are_covered(monkeypatch: pytest.MonkeyPatch) -> None:
    g1 = fingerprint(uses_global)
    monkeypatch.setitem(uses_global.__globals__, "VENTANA", 121)
    assert fingerprint(uses_global).hash != g1.hash
    h1 = fingerprint(uses_helper)
    assert any("_helper" in c for c in h1.covered)

    def _helper2(prices: pd.DataFrame) -> pd.DataFrame:
        return prices.rolling(21).mean()

    monkeypatch.setitem(uses_helper.__globals__, "_helper", _helper2)
    assert fingerprint(uses_helper).hash != h1.hash


def test_numpy_closure_hashed_by_bytes() -> None:
    def make(w: np.ndarray):  # type: ignore[no-untyped-def]
        def sig(prices: pd.DataFrame) -> pd.DataFrame:
            return prices * w[0]

        return sig

    a = fingerprint(make(np.arange(2000.0)))
    b = fingerprint(make(np.arange(2000.0) + np.r_[np.zeros(1999), 1.0]))
    assert a.hash != b.hash  # repr truncaría con "..."; el hash usa los bytes


def test_partial_is_covered() -> None:
    p1 = fingerprint(functools.partial(base, ventana=60))
    p2 = fingerprint(functools.partial(base, ventana=61))
    assert p1.hash != p2.hash and p1.coverage == "source"


def test_lambda_without_source_uses_bytecode() -> None:
    ns: dict[str, object] = {}
    exec("f = lambda prices: prices * 2", ns)  # noqa: S102 - sin código fuente disponible
    fp = fingerprint(ns["f"])  # type: ignore[arg-type]
    assert fp.coverage == "bytecode"
    ns2: dict[str, object] = {}
    exec("f = lambda prices: prices * 3", ns2)  # noqa: S102
    assert fingerprint(ns2["f"]).hash != fp.hash  # type: ignore[arg-type]


def test_unhashable_closure_is_partial() -> None:
    class Opaque:
        pass

    obj = Opaque()

    def sig(prices: pd.DataFrame) -> pd.DataFrame:
        return prices if obj else prices

    fp = fingerprint(sig)
    assert fp.coverage == "partial" and any("obj" in c for c in fp.uncovered)


def test_builtin_signals_are_fingerprinted_by_source() -> None:
    fp = fingerprint(get_signal("sma_crossover"))
    assert fp.coverage == "builtin" and fp.hash


def test_deterministic_across_processes(tmp_path: Path) -> None:
    mod = tmp_path / "mi_senal.py"
    mod.write_text(
        textwrap.dedent(
            """
            import numpy as np
            UMBRAL = np.array([1.0, 2.0])

            def senal(prices, k=2):
                return prices * UMBRAL[0] * k
            """
        )
    )
    code = (
        f"import sys; sys.path.insert(0, {str(tmp_path)!r}); import mi_senal;"
        "from tsinsurance.experiments.fingerprint import fingerprint;"
        "print(fingerprint(mi_senal.senal).hash)"
    )
    outs = {
        subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        ).stdout.strip()
        for _ in range(2)
    }
    assert len(outs) == 1 and len(next(iter(outs))) == 32
