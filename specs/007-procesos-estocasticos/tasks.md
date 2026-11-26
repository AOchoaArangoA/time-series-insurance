---
description: "Tareas de la spec 007: procesos estocásticos (MVP)"
---

# Tasks: Procesos estocásticos, simulación y sensibilidades (MVP)

**Input**: spec.md, plan.md, research.md (R1-R9, incluida la revisión),
contracts/python-api.md. **Tests**: primero.

## Phase 1: stochastics (US1, US3)

- [X] T001 `Curve` (Protocol) y `NodeCurve` (lineal en cero continuo, plana fuera de
  rango, forward continuo por la derecha); conversiones de tasa (descuento act/360, par
  semestral, cero continuo) en `src/tsinsurance/stochastics/curves.py`
- [X] T002 [US1] Vasicek y CIR bajo ℙ en `short_rate.py`:
  - MV exacta;
  - simulación exacta (Vasicek gaussiana; CIR con χ² no central);
  - bootstrap paramétrico y *jackknife* (B2);
  - φ̂ ≥ 1 manejado;
  - tasas ≤ 0 en CIR con error claro;
  - Feller con IC (M1).
- [X] T003 [US1] Diagnósticos FR-001b en `short_rate.py`:
  - ADF/PP+KPSS y ZA;
  - residuos (Ljung-Box, ARCH-LM, Jarque-Bera, CUSUM);
  - walk-forward frente a paseo aleatorio con DM.
- [X] T004 [US3] Fórmulas cerradas de cupón cero (Vasicek, CIR) y Hull-White con
  r = x + α(t) en `affine.py`.
- [X] T005 [US3] `calibrate_q`:
  - valora cada dato según su convención (par semestral, descuento);
  - parámetros comunes en una ventana;
  - σ_ℚ = σ_ℙ;
  - λ con su ee (I2).

## Phase 2: regímenes (US2)

- [X] T006 [US2] `MarkovShortRate` en `regimes.py`:
  - `MarkovRegression` con r_{t−1} exógeno, `switching_exog` y `switching_variance`;
  - `search_reps`;
  - regímenes ordenados por σ;
  - AIC y BIC frente a 1 régimen;
  - probabilidades filtradas y suavizadas con `params_estimation_end` (pseudo-filtrada);
  - simulación con la misma recursión (B4, I1).

## Phase 3: simulation (US4)

- [X] T007 [US4] `fit_factors`: PCA de cambios en pb y Diebold-Li con λ fija y residuo por
  nodo (M3), en `simulation/factors.py`.
- [X] T008 [US4] Escenarios en `simulation/scenarios.py`:
  - histórica con bootstrap por bloques;
  - histórica filtrada (EWMA o GARCH, punto en el tiempo);
  - Monte Carlo de factores;
  - Monte Carlo de la tasa corta;
  - `Scenarios` con `state_measure`, `pricing_measure` y el mapeo (I8).
- [X] T009 [US4] Reducción de varianza en `simulation/variance.py`: antitéticas y variable
  de control con (r_T, ∫r) exacta (B1) y β en una muestra piloto.

## Phase 4: sensitivities (US5)

- [X] T010 [US5] `FixedBond`, `BondPortfolio`; `measures` (PV, DV01, KRD analítica,
  duración efectiva, convexidad) en `sensitivities/`.
- [X] T011 [US5] `factor_greeks` (Γ cruzado con 4 puntos), `approximate` (Δ, ΔΓ y
  revaluación completa) y `attribute_pnl`.

## Phase 5: portfolio_risk (US6)

- [X] T012 [US6] `var_es` con IC (bootstrap o por bloques; Monte Carlo sólo como error de
  simulación).
- [X] T013 [US6] `backtest_var`: Kupiec, Christoffersen, duraciones (Christoffersen y
  Pelletier 2004) y Z2 con distribución predictiva guardada; menos de 250 observaciones ⇒
  no concluyente.
- [X] T014 [US6] `stress` (paralelo, pendiente, curvatura y condicionado a régimen con
  re-estimación walk-forward) e `immunize` (factible o residual mínimo).

## Phase 6: contratos, demostración y documentación

- [X] T015 Extensión aditiva de `rate_nodes` (`rate_type`, `compounding`) y campos
  `tenor_years`, `rate_type` y `compounding` en el manifiesto (I7).
- [X] T016 [US7] `experiments/tesoro_riesgo/`:
  - receta Yahoo (^IRX, ^FVX, ^TNX, ^TYX), verificando ^TYX en 2002-2006 (M2);
  - script de demostración con re-estimación mensual;
  - README.
- [ ] T017 [P] Monte Carlo en `tests/simulation/test_stochastic_calibration.py` (`slow`):
  SC-001 a SC-007.
- [ ] T018 `docs/methodology/procesos-estocasticos.md`, más AGENTS, manual y CHANGELOG;
  revisión de implementación con `econometrics-reviewer` y suite completa.
