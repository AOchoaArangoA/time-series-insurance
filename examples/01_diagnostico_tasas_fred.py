"""Ejercicio 01 — Diagnóstico de estacionariedad de la tasa del Tesoro de EE. UU. a 10 años.

Datos reales de FRED (serie GS10, mensual, en porcentaje). El ejercicio es replicable:
por defecto usa la instantánea versionada en ``examples/data/fred_gs10``. Para
descargarla de nuevo (requiere la variable de entorno ``FRED_API_KEY``)::

    uv run python examples/01_diagnostico_tasas_fred.py --refresh

Para usar sus propios datos, genere la plantilla de insumos con
``tsinsurance template market -o mis_datos.csv`` y cambie ``SERIES_ID``/la fuente.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tsinsurance.data import Snapshot, prepare, to_wide
from tsinsurance.data.sources import get_source
from tsinsurance.diagnostics import describe, stationarity

SNAPSHOT_DIR = Path(__file__).parent / "data" / "fred_gs10"
SERIES_ID = "GS10"
START, END = "1990-01-01", "2025-12-31"


def get_snapshot(refresh: bool) -> Snapshot:
    """Carga la instantánea (o la descarga de FRED si ``refresh``)."""
    if refresh or not SNAPSHOT_DIR.exists():
        snap = get_source("fred").fetch([SERIES_ID], START, END)
        snap.save(SNAPSHOT_DIR)
        print(f"Instantánea guardada en {SNAPSHOT_DIR} (sha256={snap.sha256[:12]}…)")
        return snap
    return Snapshot.load(SNAPSHOT_DIR)


def main() -> None:
    """Ejecuta el diagnóstico completo e imprime los reportes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Descarga de nuevo desde FRED.")
    args = parser.parse_args()

    snap = get_snapshot(args.refresh)
    print(f"Fuente: {snap.source} {dict(snap.query)} — consultado {snap.retrieved_at}")
    print(f"Contrato v{snap.schema_version}, sha256={snap.sha256[:12]}…\n")

    wide = to_wide(snap.data)
    level = prepare(wide[SERIES_ID], freq="M", missing="error")
    print(level.summary(), "\n")

    print(describe(level.data).summary(), "\n")
    print(stationarity(level.data, trend="c").summary(), "\n")

    changes = prepare(wide[SERIES_ID], freq="M", transform="diff")
    print(describe(changes.data).summary())


if __name__ == "__main__":
    main()
