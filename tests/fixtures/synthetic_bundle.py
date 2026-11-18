"""Paquetes de insumos sintéticos reutilizables y mutaciones para pruebas de aislamiento.

``synthetic_bundle`` escribe un paquete con 2 activos diarios, una exógena diaria con
rezago, un IPC mensual y una tasa libre de riesgo. ``mutate_after`` altera los datos
posteriores a una fecha de corte para comprobar que la calibración no los ve (SC-003).
Las categorías de mutación de tiempo real (versiones) se agregan con el contrato 1.1
(spec 004, US4).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tsinsurance.data import Snapshot
from tsinsurance.data.bundle import DATA, Bundle, seal_bundle

__all__ = ["MUTATION_KINDS", "mutate_after", "synthetic_bundle"]

MUTATION_KINDS = ("observations",)


def synthetic_bundle(directory: Path, seed: int = 0) -> Bundle:
    """Paquete sintético: 2 activos diarios, 1 exógena diaria, 1 mensual y rf."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2010-01-01", "2019-12-31")
    rows = []
    for sid, drift in (("AAA", 3e-4), ("BBB", -1e-4)):
        px = 100 * np.exp(np.cumsum(rng.normal(drift, 0.01, len(days))))
        rows.append(
            pd.DataFrame(
                {
                    "date": days,
                    "series_id": sid,
                    "value": px,
                    "kind": "price",
                    "unit": "level",
                    "currency": "USD",
                    "frequency": "B",
                }
            )
        )
    rows.append(
        pd.DataFrame(
            {
                "date": days,
                "series_id": "SPREAD",
                "value": np.cumsum(rng.normal(0, 0.02, len(days))) + 1.0,
                "kind": "rate",
                "unit": "percent",
                "currency": "USD",
                "frequency": "B",
            }
        )
    )
    rows.append(
        pd.DataFrame(
            {
                "date": days,
                "series_id": "RF",
                "value": 2.0,
                "kind": "rate",
                "unit": "percent",
                "currency": "USD",
                "frequency": "B",
            }
        )
    )
    months = pd.date_range("2009-01-01", "2019-12-01", freq="MS")
    rows.append(
        pd.DataFrame(
            {
                "date": months,
                "series_id": "CPI",
                "value": 100 * np.exp(np.cumsum(rng.normal(0.002, 0.003, len(months)))),
                "kind": "index",
                "unit": "level",
                "currency": "USD",
                "frequency": "M",
            }
        )
    )
    daily = Snapshot.create(
        pd.concat(rows[:4], ignore_index=True), kind="market", source="sintetico"
    )
    monthly = Snapshot.create(rows[4], kind="market", source="sintetico")
    lic = {"license": "sintética (pruebas)", "redistributable": True}
    bundle = Bundle.from_snapshots(
        "sintetico",
        [
            (
                daily,
                [
                    {"id": "AAA", "role": "asset", **lic},
                    {"id": "BBB", "role": "asset", **lic},
                    {
                        "id": "SPREAD",
                        "role": "exogenous",
                        "release_lag": "1B",
                        "point_in_time": True,
                        **lic,
                    },
                    {
                        "id": "RF",
                        "role": "risk_free",
                        "release_lag": "1B",
                        "rf_convention": "annual_percent",
                        **lic,
                    },
                ],
            ),
            (
                monthly,
                [
                    {
                        "id": "CPI",
                        "role": "exogenous",
                        "release_lag": "20D",
                        "transform": "yoy",
                        "point_in_time": True,
                        **lic,
                    }
                ],
            ),
        ],
    )
    bundle.save(directory)
    return bundle


def mutate_after(
    directory: Path, cut: str | pd.Timestamp, kind: str = "observations", seed: int = 99
) -> int:
    """Altera al azar los datos del paquete posteriores a ``cut`` y lo vuelve a sellar.

    Devuelve el número de filas alteradas.

    ``kind``:
    - ``"observations"``: multiplica por un factor aleatorio todas las observaciones con
      fecha posterior a ``cut`` (precios, exógenas y tasa libre de riesgo).
    """
    if kind not in MUTATION_KINDS:
        raise ValueError(f"mutación desconocida: {kind!r}; disponibles {MUTATION_KINDS}")
    path = Path(directory) / DATA
    df = pd.read_csv(path, dtype={"series_id": str})
    after = pd.to_datetime(df["date"]) > pd.Timestamp(cut)
    rng = np.random.default_rng(seed)
    df.loc[after, "value"] = df.loc[after, "value"] * rng.uniform(0.5, 1.5, int(after.sum()))
    df.to_csv(path, index=False)
    seal_bundle(directory)
    return int(after.sum())
