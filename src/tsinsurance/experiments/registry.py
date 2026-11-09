"""Bitácora permanente de pruebas (JSONL de sólo agregado, encadenada por hash).

Cada línea es un evento: ``preregistration`` (hash de ``experiment.toml`` antes de
ejecutar), ``signal`` (una configuración evaluada), ``econometric`` (una especificación
evaluada) o ``validation`` (una evaluación fuera de muestra). La bitácora alimenta el
ajuste por pruebas múltiples de los experimentos siguientes; nunca se editan ni se
borran líneas (Principio VIII). Cada línea guarda ``prev_hash`` (hash de la línea
anterior), de modo que cualquier edición o borrado se detecta con
:func:`verify_registry`.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

__all__ = [
    "append_trials",
    "line_hash",
    "prior_information_ratios",
    "prior_specifications",
    "read_registry",
    "trial_key",
    "validation_seen",
    "verify_registry",
]

GENESIS = "0" * 64


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
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{p}:{n} no es JSON válido: {exc}") from exc
    return rows


def verify_registry(path: str | os.PathLike[str]) -> list[str]:
    """Verifica la cadena de hashes; devuelve los problemas (lista vacía = íntegra)."""
    problems = []
    prev = GENESIS
    for n, row in enumerate(read_registry(path), start=1):
        if row.get("prev_hash") != prev:
            problems.append(f"línea {n}: prev_hash no coincide (edición, borrado o reordenamiento)")
        prev = line_hash(row)
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
    return count


def prior_information_ratios(
    rows: Iterable[Mapping[str, Any]],
    *,
    exclude_keys: Iterable[str] = (),
    periods_per_year: int | None = None,
) -> dict[str, list[float]]:
    """Ratios de *timing* por periodo de pruebas previas, por activo.

    Cuenta cada clave una sola vez (re-ejecuciones idénticas). Sólo combina pruebas con
    la misma frecuencia (``periods_per_year``) para no mezclar escalas. Las pruebas de
    señales y las econométricas cuentan por igual: ambas son intentos sobre el activo.
    """
    skip = set(exclude_keys)
    latest: dict[str, tuple[str, float]] = {}
    for r in rows:
        if r.get("kind") not in ("signal", "econometric") or "key" not in r:
            continue
        if r["key"] in skip:
            continue
        if periods_per_year is not None and r.get("periods_per_year") not in (
            None,
            periods_per_year,
        ):
            continue
        ir = r.get("timing_ir_per_period")
        latest[r["key"]] = (str(r["asset"]), 0.0 if ir is None else float(ir))
    out: dict[str, list[float]] = {}
    for asset, ir in latest.values():
        out.setdefault(asset, []).append(ir)
    return out


def prior_specifications(rows: Iterable[Mapping[str, Any]], asset: str, exclude: str) -> int:
    """Especificaciones econométricas distintas ya probadas sobre ``asset``."""
    keys = {r["key"] for r in rows if r.get("kind") == "econometric" and r.get("asset") == asset}
    keys.discard(exclude)
    return len(keys)


def validation_seen(rows: Iterable[Mapping[str, Any]], key: str) -> int:
    """Veces que ya se abrió la misma ventana de validación (misma clave)."""
    return sum(1 for r in rows if r.get("kind") == "validation" and r.get("key") == key)
