"""Series sintéticas con versiones (vintages) conocidas, para probar el tiempo real (US4).

Formato largo, el mismo del contrato de datos 1.1:

``date`` (fin del periodo) · ``value`` · ``realtime_start`` (publicación de la versión) ·
``realtime_end`` (**exclusivo**: primer día en que la versión ya no rige; ``NaT`` = vigente).

Casos difíciles incluidos a propósito (spec 004, revisión B3 e I5):

- revisiones a +1 y +2 meses de cada periodo;
- una revisión de **año base** que reescala toda la historia en una fecha;
- una versión de **un solo día** (en ALFRED, inicio = fin inclusivo);
- una **primera publicación tardía** de un periodo anterior, publicada después que el
  periodo siguiente.

Las funciones ``first_release``, ``view`` y ``to_alfred`` son implementaciones de
referencia, deliberadamente simples, contra las que se comparan las del paquete.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["CASES", "first_release", "synthetic_vintages", "to_alfred", "view"]

# Fechas de los casos especiales, para que las pruebas los recorran explícitamente.
CASES: dict[str, pd.Timestamp] = {}


def synthetic_vintages(n_periods: int = 60, seed: int = 3) -> pd.DataFrame:
    """Serie mensual con versiones; ver el docstring del módulo."""
    rng = np.random.default_rng(seed)
    periods = pd.date_range("2015-01-31", periods=n_periods, freq="ME")
    true = 100 * np.exp(np.cumsum(rng.normal(0.002, 0.004, n_periods)))
    late = periods[n_periods // 2]  # su primera publicación llega tarde
    rebase_at = periods[2 * n_periods // 3] + pd.offsets.BDay(5)
    events: list[tuple[pd.Timestamp, pd.Timestamp, float]] = []  # (date, start, value)
    for i, p in enumerate(periods):
        first = p + pd.offsets.BDay(12)
        if p == late:
            first = periods[i + 1] + pd.offsets.BDay(20)  # después del periodo siguiente
        noise = rng.normal(0, 0.3, 3)
        events.append((p, first, true[i] + noise[0]))
        events.append((p, first + pd.DateOffset(months=1), true[i] + noise[1]))
        events.append((p, first + pd.DateOffset(months=2), true[i] + noise[2]))
    df = pd.DataFrame(events, columns=["date", "realtime_start", "value"])
    # Revisión de año base: todos los periodos ya publicados se reescalan en rebase_at.
    known = df[df["realtime_start"] <= rebase_at]
    latest = known.sort_values("realtime_start").groupby("date").tail(1)
    rebased = latest.assign(realtime_start=rebase_at, value=latest["value"] * 1.1)
    df = pd.concat([df, rebased], ignore_index=True)
    # Las revisiones regulares posteriores al rebase quedan en la nueva base.
    after = (df["realtime_start"] > rebase_at) & df["date"].isin(latest["date"])
    df.loc[after, "value"] *= 1.1
    # Versión de un solo día: una corrección que se anula al día siguiente.
    one_day_period = periods[n_periods // 4]
    od_start = one_day_period + pd.offsets.BDay(30)
    base = df[(df["date"] == one_day_period) & (df["realtime_start"] < od_start)]
    od_value = float(base.sort_values("realtime_start")["value"].iloc[-1])
    df = pd.concat(
        [
            df,
            pd.DataFrame(
                {
                    "date": [one_day_period, one_day_period],
                    "realtime_start": [od_start, od_start + pd.Timedelta(days=1)],
                    "value": [od_value + 5.0, od_value],
                }
            ),
        ],
        ignore_index=True,
    )
    df = (
        df.drop_duplicates(["date", "realtime_start"], keep="last")
        .sort_values(["date", "realtime_start"])
        .reset_index(drop=True)
    )
    df["realtime_end"] = df.groupby("date")["realtime_start"].shift(-1)
    CASES.update(
        late_period=late,
        late_first_release=df.loc[df["date"] == late, "realtime_start"].min(),
        rebase=rebase_at,
        one_day_period=one_day_period,
        one_day_start=od_start,
    )
    return df[["date", "value", "realtime_start", "realtime_end"]]


def first_release(v: pd.DataFrame) -> pd.DataFrame:
    """Primera publicación de cada periodo (una fila por ``date``; ``realtime_end`` vacío)."""
    out = v.sort_values("realtime_start").groupby("date", as_index=False).first()
    return out.assign(realtime_end=pd.NaT)[["date", "value", "realtime_start", "realtime_end"]]


def view(v: pd.DataFrame, d: pd.Timestamp) -> pd.Series:
    """Valores vigentes en ``d``: ``realtime_start ≤ d < realtime_end`` (fin exclusivo)."""
    end = v["realtime_end"].fillna(pd.Timestamp.max)
    live = v[(v["realtime_start"] <= d) & (d < end)]
    return live.set_index("date")["value"].sort_index()


def to_alfred(v: pd.DataFrame) -> list[dict[str, str]]:
    """Filas como las devuelve ALFRED (``output_type=1``): fin **inclusivo**, ``9999-12-31``."""
    rows = []
    for r in v.itertuples(index=False):
        end = (
            "9999-12-31"
            if pd.isna(r.realtime_end)
            else str((r.realtime_end - pd.Timedelta(days=1)).date())
        )
        rows.append(
            {
                "realtime_start": str(r.realtime_start.date()),
                "realtime_end": end,
                "date": str(r.date.replace(day=1).date()),  # FRED fecha los meses el día 1
                "value": f"{r.value:.4f}",
            }
        )
    return rows
