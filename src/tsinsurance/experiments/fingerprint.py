"""Huella del código de una señal (spec 004, US3; research R2 y revisión I2).

La identidad de una prueba incluye **lo que la señal hace**, no sólo su nombre: dos
señales con el mismo nombre y distinto código son pruebas distintas, y la misma señal
re-ejecutada comparte identidad.

Qué se cubre:

- el código fuente de la función como AST, sin docstrings, comentarios, formato ni su
  propio nombre;
- los valores por defecto y las variables de cierre;
- de forma **transitiva**, las funciones del usuario y los objetos globales que la señal
  referencia por nombre o atributo (``VENTANA``, ``_helper``, ``mi_lib.f``), incluso de
  otros módulos del usuario;
- ``functools.partial``, con su función, argumentos y palabras clave.

Los valores se resumen por su contenido: los arreglos y DataFrames por sus bytes, nunca
por ``repr`` (no es determinista y trunca). Las bibliotecas instaladas (site-packages) y la
biblioteca estándar no se recorren: se identifican por nombre y versión.

Cobertura (``coverage``):

- ``builtin``: señal del propio paquete, cubierta por su AST;
- ``source``: todo lo referenciado quedó cubierto;
- ``bytecode``: sin código fuente (p. ej. una lambda creada con ``exec``); se usa el código
  compilado, que depende de la versión de Python;
- ``partial``: hay referencias que no se pudieron resumir (listadas en ``uncovered``);
- ``none``: nada pudo resumirse.

Con ``partial`` o ``none`` el resultado se marca exploratorio. Una refactorización sin
cambio de comportamiento cambia la huella y cuenta una prueba más: es conservador.
"""

from __future__ import annotations

import ast
import functools
import hashlib
import importlib.metadata
import inspect
import json
import sys
import sysconfig
import textwrap
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = ["SignalFingerprint", "fingerprint"]

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_LIB_DIRS = tuple(
    Path(p).resolve()
    for p in {sysconfig.get_paths()[k] for k in ("stdlib", "platstdlib", "purelib", "platlib")}
)


@dataclass(frozen=True, slots=True)
class SignalFingerprint:
    """Huella de una señal."""

    hash: str
    coverage: str
    covered: tuple[str, ...] = field(default=())
    uncovered: tuple[str, ...] = field(default=())

    def to_dict(self) -> dict[str, Any]:
        """Forma serializable."""
        return {
            "hash": self.hash,
            "coverage": self.coverage,
            "covered": list(self.covered),
            "uncovered": list(self.uncovered),
        }


class _Strip(ast.NodeTransformer):
    """Quita docstrings y el nombre de la función raíz (cosmético)."""

    def __init__(self) -> None:
        self.root = True

    def _strip_doc(self, node: Any) -> Any:
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:  # noqa: N802 - API de ast
        if self.root:
            node.name = "_"
            self.root = False
        node.decorator_list = []
        self.generic_visit(node)
        return self._strip_doc(node)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]  # noqa: N815

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:  # noqa: N802 - API de ast
        self.generic_visit(node)
        return self._strip_doc(node)


def _is_library(obj: Any) -> bool:
    """``True`` si el objeto viene de la biblioteca estándar o de site-packages."""
    mod = inspect.getmodule(obj)
    if mod is None:
        return isinstance(obj, types.BuiltinFunctionType)
    if mod.__name__ in sys.builtin_module_names:
        return True
    file = getattr(mod, "__file__", None)
    if file is None:
        return False
    path = Path(file).resolve()
    if _PACKAGE_ROOT in path.parents:
        return False  # tsinsurance se cubre por AST (cambia entre commits de una versión)
    return any(d in path.parents for d in _LIB_DIRS)


def _library_id(obj: Any) -> str:
    mod = inspect.getmodule(obj)
    top = (mod.__name__ if mod else "?").split(".")[0]
    try:
        ver = importlib.metadata.version(top)
    except importlib.metadata.PackageNotFoundError:
        ver = sys.version.split()[0] if top in sys.stdlib_module_names else "?"
    return f"lib:{getattr(obj, '__qualname__', type(obj).__name__)}@{top}=={ver}"


def _value_digest(value: Any) -> str | None:
    """Resumen determinista de un valor no llamable (``None`` si no es posible)."""
    if value is None or isinstance(value, bool | int | float | str | bytes | complex):
        return json.dumps([type(value).__name__, repr(value)])
    if isinstance(value, np.ndarray):
        arr = np.ascontiguousarray(value)
        return f"ndarray:{arr.dtype}:{arr.shape}:" + hashlib.sha256(arr.tobytes()).hexdigest()
    if isinstance(value, pd.Series | pd.DataFrame | pd.Index):
        h = pd.util.hash_pandas_object(value, index=True).to_numpy()
        return f"pandas:{type(value).__name__}:" + hashlib.sha256(h.tobytes()).hexdigest()
    if isinstance(value, tuple | list | set | frozenset):
        parts = [_value_digest(v) for v in value]
        if any(p is None for p in parts):
            return None
        items = sorted(parts) if isinstance(value, set | frozenset) else parts  # type: ignore[type-var]
        return f"{type(value).__name__}:" + json.dumps(items)
    if isinstance(value, dict):
        kv = [(_value_digest(k), _value_digest(v)) for k, v in value.items()]
        if any(k is None or v is None for k, v in kv):
            return None
        return "dict:" + json.dumps(sorted(kv))
    return None


def _code_digest(code: types.CodeType) -> str:
    consts = []
    for c in code.co_consts:
        consts.append(_code_digest(c) if isinstance(c, types.CodeType) else repr(c))
    payload = [code.co_code.hex(), consts, list(code.co_names), list(code.co_varnames)]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


class _Walker:
    def __init__(self) -> None:
        self.parts: dict[str, str] = {}
        self.uncovered: list[str] = []
        self.used_bytecode = False
        self.seen: set[int] = set()

    def callable_(self, fn: Any, label: str) -> None:
        if id(fn) in self.seen:
            return
        self.seen.add(id(fn))
        if isinstance(fn, functools.partial):
            self.callable_(fn.func, f"{label}.func")
            for i, a in enumerate(fn.args):
                self.value(a, f"{label}.args[{i}]")
            for k, v in sorted(fn.keywords.items()):
                self.value(v, f"{label}.kw[{k}]")
            return
        if isinstance(fn, types.MethodType):
            self.value(fn.__self__, f"{label}.__self__")
            self.callable_(fn.__func__, f"{label}.__func__")
            return
        if _is_library(fn):
            self.parts[label] = _library_id(fn)
            return
        if not isinstance(fn, types.FunctionType):
            self.uncovered.append(f"{label} ({type(fn).__name__})")
            return
        try:
            src = textwrap.dedent(inspect.getsource(fn))
            tree = ast.parse(src)
        except (OSError, TypeError, SyntaxError):
            self.parts[label] = (
                "bytecode:" + sys.version.split()[0] + ":" + _code_digest(fn.__code__)
            )
            self.used_bytecode = True
            tree = None
        if tree is not None:
            tree = _Strip().visit(tree)
            self.parts[label] = ast.dump(tree, annotate_fields=False, include_attributes=False)
        for i, d in enumerate(fn.__defaults__ or ()):
            self.value(d, f"{label}.defaults[{i}]")
        for kw, d in sorted((fn.__kwdefaults__ or {}).items()):
            self.value(d, f"{label}.kwdefaults[{kw}]")
        for name, cell in zip(fn.__code__.co_freevars, fn.__closure__ or (), strict=True):
            try:
                self.value(cell.cell_contents, f"{label}.closure[{name}]")
            except ValueError:  # celda vacía
                continue
        self.globals_(fn, label)

    def globals_(self, fn: types.FunctionType, label: str) -> None:
        g = fn.__globals__
        names = set(fn.__code__.co_names)
        for c in fn.__code__.co_consts:
            if isinstance(c, types.CodeType):
                names |= set(c.co_names)
        for name in sorted(names):
            if name not in g:
                continue  # atributo o builtin
            obj = g[name]
            if isinstance(obj, types.ModuleType):
                if _is_library(obj):
                    continue
                # Módulo del usuario: cubrir los atributos usados (mi_lib.f).
                for attr in sorted(names):
                    if attr != name and hasattr(obj, attr):
                        self.value(getattr(obj, attr), f"{label}.{name}.{attr}")
                continue
            self.value(obj, f"{label}.global[{name}]")

    def value(self, v: Any, label: str) -> None:
        if callable(v) and not isinstance(v, type):
            self.callable_(v, label)
            return
        if isinstance(v, type):
            if _is_library(v):
                self.parts[label] = _library_id(v)
            else:
                try:
                    tree = _Strip().visit(ast.parse(textwrap.dedent(inspect.getsource(v))))
                    self.parts[label] = ast.dump(tree, annotate_fields=False)
                except (OSError, TypeError, SyntaxError):
                    self.uncovered.append(f"{label} (clase sin fuente)")
            return
        if isinstance(v, types.ModuleType):
            if not _is_library(v):
                self.uncovered.append(f"{label} (módulo)")
            return
        d = _value_digest(v)
        if d is None:
            self.uncovered.append(f"{label} ({type(v).__name__})")
        else:
            self.parts[label] = d


def fingerprint(fn: Callable[..., Any]) -> SignalFingerprint:
    """Huella del código de ``fn`` (ver el docstring del módulo)."""
    w = _Walker()
    w.callable_(fn, "signal")
    if not w.parts:
        return SignalFingerprint("", "none", (), tuple(w.uncovered))
    payload = json.dumps(sorted(w.parts.items()), ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    target = fn.func if isinstance(fn, functools.partial) else fn
    mod = inspect.getmodule(target)
    builtin = mod is not None and mod.__name__.startswith("tsinsurance.")
    if w.uncovered:
        coverage = "partial"
    elif w.used_bytecode:
        coverage = "bytecode"
    elif builtin:
        coverage = "builtin"
    else:
        coverage = "source"
    return SignalFingerprint(digest, coverage, tuple(sorted(w.parts)), tuple(w.uncovered))
