"""Paquetes de insumos sintéticos reutilizables y mutaciones para pruebas de aislamiento.

``synthetic_bundle`` escribe un paquete con 2 activos diarios, una exógena diaria con
rezago, un IPC mensual y una tasa libre de riesgo. ``mutate_after`` altera los datos
posteriores a una fecha de corte para comprobar que la calibración no los ve (SC-003).
Las categorías de mutación de tiempo real (versiones) se agregan con el contrato 1.1
(spec 004, US4).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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


def panel_bundle(directory: Path, seed: int = 0, effect: float = -0.05) -> Bundle:
    """Paquete con 6 activos: los 3 "sensibles" responden al cambio mensual de SPREAD.

    El exceso de retorno del mes m+1 de U0-U2 incluye ``effect · ΔSPREAD_m`` (proceso
    generador del panel predictivo con interacción); U3-U5 no responden.
    """
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2008-01-01", "2019-12-31")
    month = days.to_period("M")
    shocks = rng.normal(0, 0.3, len(month.unique()))
    level = pd.Series(1.0 + np.cumsum(shocks), index=month.unique())
    spread_daily = level.reindex(month).to_numpy() + rng.normal(0, 0.001, len(days))
    change = level.diff().shift(1).fillna(0.0)  # cambio del mes previo
    n_days = pd.Series(1, index=month).groupby(level=0).sum()
    rows = []
    specs: list[dict[str, Any]] = []
    lic = {"license": "sintética (pruebas)", "redistributable": True}
    for i in range(6):
        b = effect if i < 3 else 0.0
        alpha_i = rng.normal(3e-4, 1e-4)
        daily = alpha_i + rng.normal(0, 0.008, len(days))
        daily += (b * change.reindex(month).to_numpy()) / n_days.reindex(month).to_numpy()
        px = 100 * np.exp(np.cumsum(daily))
        rows.append(
            pd.DataFrame(
                {
                    "date": days,
                    "series_id": f"U{i}",
                    "value": px,
                    "kind": "price",
                    "unit": "level",
                    "currency": "USD",
                    "frequency": "B",
                }
            )
        )
        specs.append({"id": f"U{i}", "role": "asset", **lic})
    rows.append(
        pd.DataFrame(
            {
                "date": days,
                "series_id": "SPREAD",
                "value": spread_daily,
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
    snap = Snapshot.create(pd.concat(rows, ignore_index=True), kind="market", source="sintetico")
    specs += [
        {"id": "SPREAD", "role": "exogenous", "release_lag": "1B", "point_in_time": True, **lic},
        {
            "id": "RF",
            "role": "risk_free",
            "release_lag": "1B",
            "rf_convention": "annual_percent",
            **lic,
        },
    ]
    bundle = Bundle.from_snapshots("panel_sintetico", [(snap, specs)])
    bundle.save(directory)
    return bundle
