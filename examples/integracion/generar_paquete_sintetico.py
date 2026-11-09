"""Genera un paquete de insumos sintético para probar la conexión con ``tsinsurance``.

No necesita red ni claves: escribe ``<destino>/bundle.toml`` y
``<destino>/market_series.csv`` con dos activos, una variable exógena y una tasa libre
de riesgo (días hábiles 2010-2024), y lo sella con su huella.

Uso::

    python generar_paquete_sintetico.py demo/data
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from tsinsurance.data.bundle import seal_bundle

MANIFIESTO = """\
[bundle]
version = "1.0"
schema_version = "1.0"
name = "sintetico"
description = "Datos simulados para la prueba de conexión (sin valor económico)."
sha256 = ""

[[series]]
id = "ACT_A"
role = "asset"
description = "Precio de retorno total simulado"
license = "sintetico"
redistributable = true

[[series]]
id = "ACT_B"
role = "asset"
description = "Precio de retorno total simulado"
license = "sintetico"
redistributable = true

[[series]]
id = "TASA_10A"
role = "exogenous"
description = "Tasa a 10 años simulada (en %)"
release_lag = "1B"
transform = "level"
point_in_time = true
license = "sintetico"
redistributable = true

[[series]]
id = "RF_3M"
role = "risk_free"
description = "Tasa libre de riesgo anual en %"
release_lag = "1B"
rf_convention = "annual_percent"
license = "sintetico"
redistributable = true
"""


def main(destino: str) -> None:
    """Escribe y sella el paquete en ``destino``."""
    out = Path(destino)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    fechas = pd.bdate_range("2010-01-01", "2024-12-31")
    n = len(fechas)
    series = {
        ("ACT_A", "price", "level"): 100 * np.exp(np.cumsum(rng.normal(2e-4, 0.010, n))),
        ("ACT_B", "price", "level"): 100 * np.exp(np.cumsum(rng.normal(1e-4, 0.006, n))),
        ("TASA_10A", "rate", "percent"): 3 + np.cumsum(rng.normal(0, 0.03, n)),
        ("RF_3M", "rate", "percent"): np.full(n, 2.0),
    }
    filas = [
        pd.DataFrame(
            {
                "date": fechas.date,
                "series_id": sid,
                "value": valores,
                "kind": kind,
                "unit": unit,
                "currency": "USD",
                "frequency": "B",
                "source": "sintetico",
            }
        )
        for (sid, kind, unit), valores in series.items()
    ]
    pd.concat(filas).to_csv(out / "market_series.csv", index=False)
    (out / "bundle.toml").write_text(MANIFIESTO, encoding="utf-8")
    seal_bundle(out)
    print(f"Paquete sintético escrito y sellado en {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo/data")
