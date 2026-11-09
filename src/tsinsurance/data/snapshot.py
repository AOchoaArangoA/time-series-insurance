"""Instantáneas de datos replicables (FR-019a).

Una instantánea guarda los datos descargados (Parquet) junto con sus metadatos
(fuente, consulta, fecha de consulta, versión del contrato y hash SHA-256 de un
contenido canónico) para que cualquier ejercicio pueda re-ejecutarse aunque la
fuente original cambie.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from tsinsurance.data.schemas import SCHEMA_VERSION, InputKind
from tsinsurance.errors import DataValidationError

__all__ = ["Snapshot", "content_hash"]

DATA_FILE = "data.parquet"
META_FILE = "metadata.json"


def content_hash(df: pd.DataFrame) -> str:
    """SHA-256 de una representación CSV canónica de ``df``.

    Independiente de la versión de Parquet/pyarrow: las fechas se escriben en ISO
    y los flotantes con 17 dígitos significativos (ida y vuelta exacta).
    """
    frame = df.reset_index(drop=True).copy()
    for col in frame.columns:
        if pd.api.types.is_datetime64_any_dtype(frame[col]):
            frame[col] = frame[col].dt.strftime("%Y-%m-%d")
    text = frame.to_csv(index=False, lineterminator="\n", float_format="%.17g", na_rep="")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True, eq=False)
class Snapshot:
    """Datos de un insumo con los metadatos necesarios para replicar su obtención.

    Attributes
    ----------
    data : pandas.DataFrame
        Datos en el formato del contrato (largo para ``market``).
    kind : str
        Tipo de insumo (``"market"``, ``"portfolio"``, ``"rate_nodes"``).
    source : str
        Conector de origen (p. ej. ``"fred"``, ``"yahoo"``, ``"file:precios.csv"``).
    query : Mapping[str, Any]
        Parámetros de la consulta (identificadores, rango). Nunca incluye credenciales.
    retrieved_at : str
        Fecha y hora UTC de la consulta (ISO 8601).
    sha256 : str
        Hash del contenido canónico (ver :func:`content_hash`).
    schema_version : str
        Versión del contrato de datos.
    """

    data: pd.DataFrame
    kind: InputKind
    source: str
    query: Mapping[str, Any] = field(default_factory=dict)
    retrieved_at: str = ""
    sha256: str = ""
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        data: pd.DataFrame,
        *,
        kind: InputKind,
        source: str,
        query: Mapping[str, Any] | None = None,
        retrieved_at: dt.datetime | None = None,
    ) -> Snapshot:
        """Crea una instantánea calculando el hash y la fecha de consulta."""
        moment = retrieved_at or dt.datetime.now(dt.UTC)
        frame = data.reset_index(drop=True)
        return cls(
            data=frame,
            kind=kind,
            source=source,
            query=dict(query or {}),
            retrieved_at=moment.replace(microsecond=0).isoformat(),
            sha256=content_hash(frame),
        )

    @property
    def metadata(self) -> dict[str, Any]:
        """Metadatos serializables (sin los datos)."""
        return {
            "kind": self.kind,
            "source": self.source,
            "query": dict(self.query),
            "retrieved_at": self.retrieved_at,
            "sha256": self.sha256,
            "schema_version": self.schema_version,
            "n_rows": len(self.data),
        }

    def save(self, directory: str | os.PathLike[str]) -> Path:
        """Guarda ``data.parquet`` y ``metadata.json`` en ``directory``."""
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        self.data.to_parquet(out / DATA_FILE, index=False)
        (out / META_FILE).write_text(
            json.dumps(self.metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return out

    @classmethod
    def load(cls, directory: str | os.PathLike[str], *, verify: bool = True) -> Snapshot:
        """Carga una instantánea y verifica su hash.

        Raises
        ------
        DataValidationError
            Si faltan archivos o el contenido no coincide con el hash registrado.
        """
        src = Path(directory)
        meta_path, data_path = src / META_FILE, src / DATA_FILE
        if not meta_path.exists() or not data_path.exists():
            raise DataValidationError(f"'{src}' no contiene {META_FILE} y {DATA_FILE}.")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        data = pd.read_parquet(data_path)
        snap = cls(
            data=data,
            kind=meta["kind"],
            source=meta["source"],
            query=meta.get("query", {}),
            retrieved_at=meta.get("retrieved_at", ""),
            sha256=meta.get("sha256", ""),
            schema_version=meta.get("schema_version", SCHEMA_VERSION),
        )
        if verify and content_hash(data) != snap.sha256:
            raise DataValidationError(
                f"El contenido de '{src}' no coincide con su hash registrado; "
                "la instantánea fue modificada."
            )
        return snap
