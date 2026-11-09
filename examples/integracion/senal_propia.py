"""Registra una señal propia y ejecuta un experimento que la usa, desde Python.

La señal debe ser **causal**: el peso de la fecha t sólo puede usar precios hasta t.
El paquete lo comprueba (prueba de anticipación) y rechaza la idea si no lo es.

Uso (desde esta carpeta, después de generar ``data/``)::

    python senal_propia.py
"""

from __future__ import annotations

import json

import pandas as pd

from tsinsurance.experiments import register_signal, run_experiment


def ruptura(precios: pd.DataFrame, ventana: int = 120) -> pd.DataFrame:
    """Largo (peso 1) si el precio supera el máximo de las ``ventana`` sesiones previas."""
    maximo = precios.rolling(ventana).max().shift(1)  # shift(1): sólo información pasada
    return (precios > maximo).astype(float).where(precios.notna())


# El nombre registrado es el que se usa en `signal = "ruptura"` del experimento.
register_signal("ruptura", ruptura)

res = run_experiment("experiment_senal_propia.toml")
idea = res.result["ideas"]["ruptura"]
print("Estado de la idea:", idea["status"])  # "evaluada" o "rechazada_por_anticipacion"
print(json.dumps(res.result["status"], ensure_ascii=False, indent=2))
