"""Regenera localmente las instantáneas de datos de terceros de los ejercicios.

Los precios de Yahoo Finance y la serie BAA10Y (Moody's) no se pueden redistribuir, por
eso no se versionan. Este script repite exactamente las consultas originales:

    export FRED_API_KEY=...
    uv run python examples/fetch_data.py

Al terminar compara la huella con la de la instantánea usada en los resultados
publicados (``examples/data/expected_sha256.json``). Si difiere (Yahoo recalcula
los precios ajustados hacia atrás con cada dividendo), los ejercicios corren igual pero
sus cifras pueden diferir levemente de las publicadas.
"""

from __future__ import annotations

import json
from pathlib import Path

from tsinsurance.data.sources import get_source

DATA = Path(__file__).parent / "data"
QUERIES = {
    "yahoo_etfs": (
        "yahoo",
        ["TLT", "IEF", "SHY", "TIP", "LQD", "HYG", "AGG", "SPY"],
        "2003-01-01",
        "2025-12-31",
    ),
    "fred_daily": ("fred", ["DTB3", "DGS10", "T10Y2Y", "BAA10Y"], "2002-01-01", "2025-12-31"),
}


def main() -> None:
    """Descarga y guarda cada instantánea; informa si coincide con la publicada."""
    expected = json.loads((DATA / "expected_sha256.json").read_text(encoding="utf-8"))
    for name, (source, ids, start, end) in QUERIES.items():
        snap = get_source(source).fetch(ids, start, end)
        snap.save(DATA / name)
        status = "coincide" if snap.sha256 == expected[name] else "DIFIERE de la publicada"
        print(f"{name}: {len(snap.data)} filas, sha256={snap.sha256[:12]}… ({status})")


if __name__ == "__main__":
    main()
