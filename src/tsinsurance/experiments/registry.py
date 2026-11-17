"""Bitácora permanente de pruebas (JSONL de sólo agregado, encadenada por hash).

Cada línea es un evento: ``preregistration`` (hash de ``experiment.toml`` antes de
ejecutar), ``signal`` (una configuración evaluada), ``econometric`` (una especificación
evaluada) o ``validation`` (una evaluación fuera de muestra). La bitácora alimenta el
ajuste por pruebas múltiples de los experimentos siguientes; nunca se editan ni se
borran líneas (Principio VIII). Cada línea guarda ``prev_hash`` (hash de la línea
anterior), de modo que cualquier edición, reordenamiento o borrado intermedio se detecta
con :func:`verify_registry`.

La cadena sola no detecta un **recorte al final** (spec 004, US1). Para eso hay dos anclas:

- cada ``result.json`` guarda el :class:`RegistryHead` de la bitácora al terminar, y
  ``verify_registry(..., results=DIR)`` exige que la bitácora lo siga conteniendo;
- ``verify_registry(..., base=ARCHIVO)`` exige que la bitácora comience byte a byte con la
  de la rama base (lo usa la integración continua).

Un solo escritor a la vez: :func:`registry_lock` crea ``<bitácora>.lock`` de forma
exclusiva durante toda la ejecución; un bloqueo vencido sólo se libera con
:func:`unlock_registry` (``tsinsurance experiment unlock``), nunca automáticamente.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import socket
import sys
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tsinsurance.errors import RegistryLockedError

__all__ = [
    "GENESIS",
    "STALE_HOURS",
    "LockInfo",
    "RegistryHead",
    "append_trials",
    "lock_path",
    "read_lock",
    "registry_head",
    "registry_lock",
    "unlock_registry",
    "line_hash",
    "prior_information_ratios",
    "jaccard",
    "prior_portfolio_trials",
    "prior_regime_variants",
    "prior_specifications",
    "prior_trials_after",
    "read_registry",
    "trial_key",
    "validation_seen",
    "verify_registry",
]

GENESIS = "0" * 64
STALE_HOURS = 6.0


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def line_hash(row: Mapping[str, Any]) -> str:
    """Hash SHA-256 canónico de una línea (incluye su ``prev_hash``)."""
    return hashlib.sha256(_canonical(row).encode("utf-8")).hexdigest()


def trial_key(**identity: Any) -> str:
    """Identidad de una prueba: hash canónico de todo lo que la define.

    Debe incluir la señal o el modelo, sus parámetros, los supuestos de ejecución, la
    ventana de evaluación y la huella del paquete de insumos. Sólo re-ejecuciones
    idénticas comparten clave.
    """
    return hashlib.sha256(_canonical(identity).encode("utf-8")).hexdigest()[:32]


def read_registry(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Lee todas las líneas registradas (lista vacía si no existe)."""
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    for n, line in enumerate(lines, start=1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                if n == len(lines) and not text.endswith("\n"):
                    raise ValueError(
                        f"{p}:{n} última línea incompleta (escritura interrumpida); "
                        "repárela con `tsinsurance experiment unlock` (la aparta, no la borra)"
                    ) from exc
                raise ValueError(f"{p}:{n} no es JSON válido: {exc}") from exc
    return rows


@dataclass(frozen=True, slots=True)
class RegistryHead:
    """Estado de la bitácora: número de líneas y huella de la última (``GENESIS`` si vacía)."""

    n_lines: int
    last_hash: str

    def to_dict(self) -> dict[str, Any]:
        """Forma serializable (se guarda en ``result.json``)."""
        return {"n_lines": self.n_lines, "last_hash": self.last_hash}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> RegistryHead:
        """Inversa de :meth:`to_dict`."""
        return cls(int(d["n_lines"]), str(d["last_hash"]))


def registry_head(path: str | os.PathLike[str]) -> RegistryHead:
    """Estado actual de la bitácora (``RegistryHead(0, GENESIS)`` si no existe o está vacía)."""
    rows = read_registry(path)
    return RegistryHead(len(rows), line_hash(rows[-1]) if rows else GENESIS)


def verify_registry(
    path: str | os.PathLike[str],
    *,
    base: str | os.PathLike[str] | None = None,
    results: str | os.PathLike[str] | None = None,
) -> list[str]:
    """Verifica la bitácora; devuelve los problemas (lista vacía = íntegra).

    Parameters
    ----------
    path : PathLike
        Bitácora a verificar. Siempre se verifica la cadena de hashes.
    base : PathLike, optional
        Bitácora de la rama base: ``path`` debe comenzar **byte a byte** con ella (sólo se
        aceptan líneas agregadas al final). Si no existe, cualquier bitácora íntegra pasa.
    results : PathLike, optional
        Carpeta con ``result.json`` publicados: cada resultado de esta bitácora (según
        ``provenance.registry_relpath``) exige que la línea ``registry_head.n_lines`` exista
        y tenga la huella ``registry_head.last_hash``; así se detectan los recortes al final.
    """
    problems = []
    prev = GENESIS
    rows = read_registry(path)
    for n, row in enumerate(rows, start=1):
        if row.get("prev_hash") != prev:
            problems.append(f"línea {n}: prev_hash no coincide (edición, borrado o reordenamiento)")
        prev = line_hash(row)
    if base is not None:
        problems += _verify_prefix(Path(path), Path(base))
    if results is not None:
        problems += _verify_against_results(Path(path), Path(results), rows)
    return problems


def _verify_prefix(path: Path, base: Path) -> list[str]:
    if not base.exists():
        return []
    old, new = base.read_bytes(), path.read_bytes() if path.exists() else b""
    if new.startswith(old):
        return []
    old_lines, new_lines = old.splitlines(keepends=True), new.splitlines(keepends=True)
    for n, (a, b) in enumerate(zip(old_lines, new_lines, strict=False), start=1):
        if a != b:
            return [f"línea {n}: distinta de la base (sólo se permite agregar líneas al final)"]
    return [
        f"la bitácora tiene menos líneas que la base ({len(new_lines)} < {len(old_lines)}): "
        "se borraron líneas"
    ]


def _verify_against_results(path: Path, results: Path, rows: list[dict[str, Any]]) -> list[str]:
    problems = []
    target = path.resolve()
    for rfile in sorted(results.rglob("result.json")):
        try:
            data = json.loads(rfile.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        head = data.get("registry_head")
        rel = data.get("provenance", {}).get("registry_relpath")
        if not head or not rel or (rfile.parent / rel).resolve() != target:
            continue  # resultado antiguo o de otra bitácora
        expected = RegistryHead.from_dict(head)
        if expected.n_lines == 0:
            continue
        if len(rows) < expected.n_lines:
            problems.append(
                f"recorte: {rfile} registra {expected.n_lines} líneas y la bitácora tiene "
                f"{len(rows)}"
            )
        elif line_hash(rows[expected.n_lines - 1]) != expected.last_hash:
            problems.append(
                f"la línea {expected.n_lines} no coincide con la registrada en {rfile} "
                "(recorte y reescritura del final)"
            )
    return problems


def append_trials(path: str | os.PathLike[str], trials: Iterable[Mapping[str, Any]]) -> int:
    """Agrega líneas al final de la bitácora encadenándolas; devuelve cuántas escribió."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = read_registry(p)
    prev = line_hash(rows[-1]) if rows else GENESIS
    count = 0
    with p.open("a", encoding="utf-8") as fh:
        for t in trials:
            row = {**dict(t), "prev_hash": prev}
            fh.write(_canonical(row) + "\n")
            prev = line_hash(row)
            count += 1
        fh.flush()
        os.fsync(fh.fileno())
    return count


def prior_information_ratios(
    rows: Iterable[Mapping[str, Any]],
    *,
    exclude_keys: Iterable[str] = (),
    periods_per_year: int | None = None,
    max_eval_end: str | None = None,
) -> dict[str, list[float]]:
    """Ratios de *timing* por periodo de pruebas previas, por activo.

    Cuenta cada clave una sola vez (re-ejecuciones idénticas). Sólo combina pruebas con
    la misma frecuencia (``periods_per_year``) para no mezclar escalas. Las pruebas de
    señales y las econométricas cuentan por igual: ambas son intentos sobre el activo.
    Las líneas ``validation`` nunca entran.

    Con ``max_eval_end`` (fecha de corte de una calibración) sólo devuelve las pruebas
    cuya ventana termina en o antes del corte: sus ratios no contienen información del
    periodo de validación (spec 004, FR-022a). Las demás se cuentan con
    :func:`prior_trials_after`.
    """
    skip = set(exclude_keys)
    latest: dict[str, tuple[str, float]] = {}
    for r in _prior_rows(rows, skip, periods_per_year):
        if max_eval_end is not None and not _ends_by(r, max_eval_end):
            continue
        ir = r.get("timing_ir_per_period")
        latest[r["key"]] = (str(r["asset"]), 0.0 if ir is None else float(ir))
    out: dict[str, list[float]] = {}
    for asset, ir in latest.values():
        out.setdefault(asset, []).append(ir)
    return out


def _prior_rows(
    rows: Iterable[Mapping[str, Any]], skip: set[str], periods_per_year: int | None
) -> Iterator[Mapping[str, Any]]:
    for r in rows:
        if r.get("kind") not in ("signal", "econometric", "portfolio") or "key" not in r:
            continue
        if r["key"] in skip:
            continue
        if periods_per_year is not None and r.get("periods_per_year") not in (
            None,
            periods_per_year,
        ):
            continue
        yield r


def _ends_by(row: Mapping[str, Any], cut: str) -> bool:
    """``True`` si la ventana de la prueba termina en o antes de ``cut``.

    Una línea sin ``eval_end`` (versiones anteriores; p. ej. modelos econométricos de la
    v0.1 evaluados sobre toda la ventana) se trata como posterior al corte.
    """
    end = row.get("eval_end")
    return end is not None and str(end)[:10] <= str(cut)[:10]


def prior_trials_after(
    rows: Iterable[Mapping[str, Any]],
    *,
    exclude_keys: Iterable[str] = (),
    periods_per_year: int | None = None,
    cut: str | None = None,
) -> dict[str, int]:
    """Pruebas previas por activo cuya ventana pasa del corte (o es desconocida).

    Cuentan en el número de pruebas N del Sharpe deflactado (conservador), pero no en la
    varianza de su umbral (FR-022a). Sin ``cut`` devuelve un diccionario vacío.
    """
    if cut is None:
        return {}
    keys: dict[str, str] = {}
    for r in _prior_rows(rows, set(exclude_keys), periods_per_year):
        if not _ends_by(r, cut):
            keys[r["key"]] = str(r["asset"])
    out: dict[str, int] = {}
    for asset in keys.values():
        out[asset] = out.get(asset, 0) + 1
    return out


def prior_specifications(rows: Iterable[Mapping[str, Any]], asset: str, exclude: str) -> int:
    """Especificaciones econométricas distintas ya probadas sobre ``asset``."""
    keys = {r["key"] for r in rows if r.get("kind") == "econometric" and r.get("asset") == asset}
    keys.discard(exclude)
    return len(keys)


def validation_seen(rows: Iterable[Mapping[str, Any]], key: str) -> int:
    """Veces que ya se abrió la misma ventana de validación (misma clave)."""
    return sum(1 for r in rows if r.get("kind") == "validation" and r.get("key") == key)


# --- Bloqueo: un solo escritor a la vez --------------------------------------------------


@dataclass(frozen=True, slots=True)
class LockInfo:
    """Contenido de ``<bitácora>.lock``."""

    path: str
    pid: int
    host: str
    run_id: str
    created_at: str
    repaired: str | None = None

    @property
    def age_hours(self) -> float:
        """Antigüedad del bloqueo en horas."""
        created = dt.datetime.fromisoformat(self.created_at)
        return (dt.datetime.now(dt.UTC) - created).total_seconds() / 3600

    @property
    def stale(self) -> bool:
        """Vencido: en esta máquina, si el proceso no existe; en otra, si tiene > 6 h.

        En la misma máquina con el proceso vivo nunca está vencido, por antiguo que sea
        (sólo ``--force`` lo libera).
        """
        if self.host == socket.gethostname():
            return not _pid_alive(self.pid)
        return self.age_hours > STALE_HOURS

    def describe(self) -> str:
        """Descripción para mensajes."""
        return (
            f"run_id={self.run_id}, pid={self.pid}, máquina={self.host}, "
            f"hace {self.age_hours:.1f} h"
        )


def lock_path(path: str | os.PathLike[str]) -> Path:
    """Ruta del archivo de bloqueo de una bitácora."""
    p = Path(path)
    return p.with_name(p.name + ".lock")


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":  # pragma: no cover - CI corre en Linux
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel32.CloseHandle(handle)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_lock(path: str | os.PathLike[str]) -> LockInfo | None:
    """Bloqueo vigente de la bitácora, o ``None`` si está libre."""
    lp = lock_path(path)
    try:
        d = json.loads(lp.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        d = {"pid": -1, "host": "?", "run_id": "?", "created_at": "1970-01-01T00:00:00+00:00"}
    return LockInfo(str(lp), int(d["pid"]), str(d["host"]), str(d["run_id"]), str(d["created_at"]))


@contextlib.contextmanager
def registry_lock(path: str | os.PathLike[str], run_id: str) -> Iterator[None]:
    """Toma la bitácora en exclusiva mientras dura el bloque ``with``.

    Raises
    ------
    RegistryLockedError
        Si otra ejecución la tiene tomada (o quedó un bloqueo vencido sin liberar).
    """
    lp = lock_path(path)
    lp.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        info = read_lock(path)
        detail = info.describe() if info else "desconocido"
        hint = (
            "El bloqueo está vencido: libérelo con `tsinsurance experiment unlock "
            f"{os.fspath(path)}`."
            if info is not None and info.stale
            else "Espere a que termine esa ejecución."
        )
        raise RegistryLockedError(
            f"La bitácora {os.fspath(path)} está bloqueada por otra ejecución ({detail}). " + hint
        ) from None
    try:
        payload = {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "run_id": run_id,
            "created_at": dt.datetime.now(dt.UTC).isoformat(),
        }
        os.write(fd, json.dumps(payload).encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lp.unlink()


def _repair_tail(path: Path) -> str | None:
    """Aparta una última línea incompleta (escritura interrumpida); devuelve dónde quedó."""
    if not path.exists():
        return None
    data = path.read_bytes()
    if not data or data.endswith(b"\n"):
        return None
    cut = data.rfind(b"\n") + 1
    tail = data[cut:]
    try:
        json.loads(tail)
    except ValueError:
        pass
    else:
        return None  # línea completa sin salto final: no es una escritura interrumpida
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    aside = path.with_name(f"{path.name}.partial-{stamp}")
    aside.write_bytes(tail)
    with path.open("r+b") as fh:
        fh.truncate(cut)
        fh.flush()
        os.fsync(fh.fileno())
    return str(aside)


def unlock_registry(path: str | os.PathLike[str], *, force: bool = False) -> LockInfo | None:
    """Libera un bloqueo vencido (o cualquiera con ``force``) y repara una escritura cortada.

    Devuelve el bloqueo liberado (``None`` si no había). Si la bitácora termina en una línea
    incompleta, esa línea se mueve a ``<bitácora>.partial-<fecha>`` (``LockInfo.repaired``).

    Raises
    ------
    RegistryLockedError
        Si el bloqueo no está vencido y no se usa ``force``.
    """
    info = read_lock(path)
    if info is None:
        return None
    if not (force or info.stale):
        raise RegistryLockedError(
            f"El bloqueo sigue activo ({info.describe()}); use --force sólo si está seguro de "
            "que esa ejecución terminó."
        )
    repaired = _repair_tail(Path(path))
    with contextlib.suppress(FileNotFoundError):
        lock_path(path).unlink()
    return LockInfo(info.path, info.pid, info.host, info.run_id, info.created_at, repaired)


# --- Memoria de carteras y regímenes (spec 005) -------------------------------------------

JACCARD_MIN = 0.5


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """Similitud de Jaccard entre dos universos."""
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa | sb else 0.0


def prior_portfolio_trials(
    rows: Iterable[Mapping[str, Any]],
    universe: Iterable[str],
    *,
    exclude_keys: Iterable[str] = (),
    periods_per_year: int | None = None,
    cut: str | None = None,
) -> tuple[list[float], int]:
    """Pruebas de cartera previas sobre universos parecidos (Jaccard ≥ 0,5; revisión B3).

    Devuelve ``(ratios, extra)``: los ratios de *timing* por periodo de las pruebas con la
    misma frecuencia y ventana terminada antes del corte (entran en la varianza del umbral
    del DSR) y el número de pruebas que sólo cuentan en N (ventana posterior al corte, otra
    frecuencia o declaradas fuera de la bitácora con ``declared_prior``). Cambiar un
    constituyente del universo no reinicia la cuenta.
    """
    uni = list(universe)
    skip = set(exclude_keys)
    latest: dict[str, tuple[float, bool]] = {}
    extra = 0
    for r in rows:
        kind = r.get("kind")
        if kind == "declared_prior" and r.get("declared_kind") == "portfolio":
            if jaccard(r.get("universe", []), uni) >= JACCARD_MIN:
                extra += int(r.get("n_tests", 0))
            continue
        if kind != "portfolio" or "key" not in r or r["key"] in skip:
            continue
        if jaccard(r.get("universe", []), uni) < JACCARD_MIN:
            continue
        same_freq = periods_per_year is None or r.get("periods_per_year") in (
            None,
            periods_per_year,
        )
        in_window = cut is None or _ends_by(r, cut)
        ir = r.get("timing_ir_per_period")
        latest[r["key"]] = (0.0 if ir is None else float(ir), same_freq and in_window)
    ratios = [ir for ir, ok in latest.values() if ok]
    extra += sum(1 for _, ok in latest.values() if not ok)
    return ratios, extra


def prior_regime_variants(
    rows: Iterable[Mapping[str, Any]],
    asset: str,
    memory_key: str,
    *,
    exclude_keys: Iterable[str] = (),
) -> int:
    """Variantes previas de un régimen sobre ``asset`` con la misma clave de memoria (B1).

    Cuenta variantes distintas (umbral u op) ya registradas, más las declaradas fuera de la
    bitácora; entran en la m de Holm de la calibración.
    """
    skip = set(exclude_keys)
    variants: set[str] = set()
    declared = 0
    for r in rows:
        if r.get("kind") == "regime" and r.get("asset") == asset:
            if r.get("regime_key") == memory_key and r.get("key") not in skip:
                variants.add(_canonical(r.get("variant")))
        elif (
            r.get("kind") == "declared_prior"
            and r.get("declared_kind") == "regime"
            and asset in r.get("assets", [])
            and r.get("regime_key") in (memory_key, "", None)
        ):
            declared += int(r.get("n_tests_per_asset", r.get("n_tests", 0)))
    return len(variants) + declared
