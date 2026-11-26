# Implementation Plan: Datos de panel con efectos fijos y aleatorios

**Branch**: `ccr-d4f6f6a0-bg0992` (carpeta: `006-panel-datos`) | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

## Summary

Se agrega un subpaquete `tsinsurance.panel` con:
- estimadores de panel sobre `linearmodels`;
- errores robustos para paneles financieros (Driscoll-Kraay y wild cluster bootstrap con
  pocas unidades);
- la comparación de efectos fijos y aleatorios con la prueba Mundlak/CRE robusta;
- diagnósticos (Wooldridge, CD de Pesaran);
- supuestos causales explícitos (Facure, capítulo 14);
- diferencias en diferencias con estudio de evento (capítulo 13).

Después se integra al flujo de experimentos con `[[panels]]` y las dos fases de la spec
004, y se demuestra con los sectores GICS.

## Technical Context

- **Language**: Python ≥ 3.11.
- **Dependencias**: `linearmodels>=7.0`, nueva (justificada en research R1); `statsmodels`;
  `numpy`; `pandas`. R `plm` sólo para generar las referencias guardadas.
- **Testing**: pytest; Monte Carlo con la marca `slow`; referencias de R en
  `tests/data/reference/`.
- **Constraints**:
  - `result.json` aditivo (1.2);
  - mypy estricto (`linearmodels` se tipa con `ignore_missing_imports`).

## Constitution Check

| Principio | Cumplimiento |
|---|---|
| I. Rigor | FE/RE con Hausman robusto; errores adecuados a la dependencia transversal; Nickell advertido |
| II. Sin fuga | Panel punto en el tiempo; calibración sobre `as_of`; validación sólo con datos posteriores al corte |
| III. Incertidumbre | Errores DK y wild bootstrap; tamaño medido (SC-004) |
| VI. Pruebas primero | DGP conocidos, Monte Carlo y referencias de R |
| VII. Simplicidad | Se reutiliza `linearmodels`; lo propio es sólo lo que falta |
| VIII. Backtesting responsable | Memoria de especificaciones, Holm y periodo visto |

**Gate**: pasa. La dependencia nueva es `linearmodels`, del autor de `arch`, y está
justificada.

## Project Structure

```text
src/tsinsurance/panel/
├── __init__.py
├── data.py          # PanelData: validación (unidad, periodo), balance, absorbidos, interacciones
├── estimators.py    # fit_panel(estimator, effects, cov): PanelResult (+ supuestos causales)
├── inference.py     # driscoll_kraay, wild_cluster_bootstrap, mundlak_test, hausman_test
├── diagnostics.py   # wooldridge_serial, pesaran_cd, within_variation
└── did.py           # diff_in_diff, event_study, pretrend_test
src/tsinsurance/experiments/
├── spec.py          # PanelSpec ([[panels]])
├── panels.py        # NUEVO: panel PIT desde el paquete; calibración/validación
├── runner.py        # integración (líneas `panel`, frozen)
└── validate.py      # validación unilateral de hipótesis; familia "paneles"
tests/panel/         # unidades, DGP, referencias R, Monte Carlo (slow)
experiments/sectores_gics/panel_sectores.toml
docs/methodology/panel.md
```

## Orden de implementación

1. `data` + `estimators`: US1 núcleo, con pruebas DGP y `linearmodels`.
2. `inference` + `diagnostics`: US1 y US2 (DK, wild bootstrap, Mundlak, Hausman, CD,
   Wooldridge).
3. `did`: US4.
4. Experimentos `[[panels]]`: US3.
5. Demostración sectorial: US5.
6. Monte Carlo, documentación y revisión.
