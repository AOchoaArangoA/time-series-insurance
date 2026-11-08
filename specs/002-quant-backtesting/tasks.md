# Tasks: Backtesting responsable de estrategias cuantitativas y modelos econométricos

**Input**: `/specs/002-quant-backtesting/` (plan.md, spec.md, research.md, data-model.md, contracts/)

**Tests**: OBLIGATORIOS (Principio VI, TDD).

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Agregar extra `backtest = ["bt>=1.1"]` en pyproject.toml y `bt.*`, `ffn.*` a overrides de mypy
- [X] T002 [P] Crear subpaquete src/tsinsurance/backtest/__init__.py y tests/backtest/__init__.py
- [X] T003 [P] Agregar `LookaheadBiasError(TSInsuranceError)` en src/tsinsurance/errors.py

## Phase 2: Foundational

- [X] T004 [P] Pruebas de `ExecutionConfig` (`lag ≥ 0`, `cost_bps ≥ 0`, `rebalance ∈ {every_bar, W, M}`, `max_gross > 0`, nota optimista si `lag = 0`) en tests/backtest/test_config.py
- [X] T005 Implementar `ExecutionConfig` y `periods_per_year` (B/D=252, W=52, M=12) en src/tsinsurance/backtest/config.py
- [X] T006 [P] Pruebas de métricas (retorno anualizado, volatilidad, Sharpe, Sortino, máxima caída, Calmar, aciertos) con valores calculados a mano en tests/backtest/test_metrics.py
- [X] T007 Implementar `PerformanceMetrics` y `performance_metrics` en src/tsinsurance/backtest/metrics.py

## Phase 3: US1 — Señales de tendencia y volatilidad (P1) 🎯 MVP

**Independent Test**: equivalencia con bt (SC-001) y detección de anticipación (SC-002).

- [X] T008 [P] [US1] Pruebas del motor: retraso de ejecución, costos por rotación, deriva entre rebalanceos, tasa libre de riesgo en efectivo, recorte de `max_gross`, pesos negativos sin `allow_short` → error, calentamiento en efectivo, en tests/backtest/test_engine.py
- [X] T009 [P] [US1] Prueba de equivalencia con bt (sin costos < 1e-9; con costos dentro de la tolerancia documentada) en tests/backtest/test_reference_bt.py
- [X] T010 [P] [US1] Pruebas de señales `sma_crossover`, `tsmom`, `ewma_volatility`, `garch_volatility_forecast`, `vol_target` (causalidad, rangos, límites) en tests/backtest/test_signals.py
- [X] T011 [P] [US1] Pruebas de `check_lookahead` (detecta `shift(-1)` y estandarización con media de muestra completa; no marca señales causales) en tests/backtest/test_lookahead.py
- [X] T012 [US1] Implementar `run_backtest` y `BacktestResult` en src/tsinsurance/backtest/engine.py
- [X] T013 [P] [US1] Implementar `run_with_bt` en src/tsinsurance/backtest/reference.py
- [X] T014 [P] [US1] Implementar señales en src/tsinsurance/backtest/signals.py
- [X] T015 [P] [US1] Implementar `check_lookahead` y `LookaheadReport` en src/tsinsurance/backtest/lookahead.py

## Phase 4: US2 — Modelos econométricos con variables macro (P1)

**Independent Test**: DGP con regresor predictivo → Clark-West detecta y la estrategia supera al benchmark; regresor irrelevante → no.

- [X] T016 [P] [US2] Pruebas de `Exogenous` / `align_point_in_time` (disponibilidad = fin de periodo + `release_lag`; nunca usa valores no publicados; mensual vs diario) en tests/backtest/test_pit.py
- [X] T017 [P] [US2] Pruebas de `PredictiveRegression.walk_forward` (sólo pares observables en `t`; `min_train`; `refit_every`; ventana móvil; invariancia al truncamiento) en tests/backtest/test_econometric.py
- [X] T018 [P] [US2] Pruebas de `validate` (HAC, estacionariedad de regresores, persistencia > 0,95 → advertencia de Stambaugh, residuos) en tests/backtest/test_econometric.py
- [X] T019 [P] [US2] Pruebas de `pesaran_timmermann`, `clark_west`, `oos_r2`, `diebold_mariano` (definición directa y equivalencia PT ↔ chi-cuadrado 2×2) en tests/backtest/test_forecast_tests.py
- [X] T020 [P] [US2] Simulación SC-004 (potencia de Clark-West ≥ 80 % con R² = 5 %, n = 300; tamaño ≤ 8 %) en tests/backtest/test_sim_clark_west.py (marca `slow`)
- [X] T021 [US2] Implementar `Exogenous` y `align_point_in_time` en src/tsinsurance/backtest/pit.py
- [X] T022 [US2] Implementar `diebold_mariano` (HLN) en src/tsinsurance/validation/comparison.py
- [X] T023 [US2] Implementar pruebas de pronóstico y `evaluate_forecasts` en src/tsinsurance/backtest/inference.py
- [X] T024 [US2] Implementar `PredictiveRegression`, `ModelValidation`, `WalkForwardForecast` en src/tsinsurance/backtest/econometric.py
- [X] T025 [US2] Implementar `backtest_econometric`, `EconometricBacktest` y `Verdict` en src/tsinsurance/backtest/econometric.py y verdict.py

## Phase 5: US3 — Inferencia y control de sobreajuste (P2)

- [X] T026 [P] [US3] Pruebas de `sharpe_inference`, `probabilistic_sharpe`, `deflated_sharpe` (ejemplo publicado DSR = 0,9004) en tests/backtest/test_inference.py
- [X] T027 [P] [US3] Pruebas de `spa_test` (reproducible con semilla; estrategia idéntica al benchmark → p alto) en tests/backtest/test_inference.py
- [X] T028 [P] [US3] Simulación SC-003 (100 señales aleatorias, mejor DSR/SPA no significativo en ≥ 90 % de 200 réplicas) en tests/backtest/test_sim_multiple_testing.py (marca `slow`)
- [X] T029 [US3] Implementar inferencia de Sharpe, PSR, DSR y SPA en src/tsinsurance/backtest/inference.py
- [X] T030 [P] [US3] Pruebas de `TrialRegistry`, `sweep`, `calibrate_validate` (selección sólo con calibración) en tests/backtest/test_sweep.py
- [X] T031 [US3] Implementar `Trial`, `TrialRegistry`, `sweep`, `SweepResult`, `calibrate_validate` en src/tsinsurance/backtest/sweep.py

## Phase 6: US4 — Ejercicios con ETFs reales (P2)

- [X] T032 [US4] Instantáneas: Yahoo (TLT, IEF, SHY, TIP, LQD, HYG, AGG, SPY) en examples/data/yahoo_etfs/; FRED diarias (DTB3, DGS10, T10Y2Y, BAA10Y) en examples/data/fred_daily/; FRED mensuales (CPIAUCSL, UNRATE) en examples/data/fred_monthly/
- [X] T033 [US4] Ejercicio examples/backtest_01_tendencia_volatilidad_etfs.py
- [X] T034 [US4] Ejercicio examples/backtest_02_macro_tlt.py
- [X] T035 [P] [US4] Pruebas de integración sin red y reproducibles de ambos ejercicios en tests/integration/test_backtest_examples.py (SC-007)

## Phase 7: US5 — Escalado (P3)

- [X] T041 [P] [US2] Pruebas de `monthly_decision_dates`, `dtb3_to_daily` y proyección mensual→diaria en tests/backtest/test_pit.py
- [X] T042 [P] [US3] Pruebas de `sharpe_difference` y SE HAC del Sharpe en tests/backtest/test_inference.py
- [X] T043 [P] [US2] Simulación SC-004 (c) con regresor persistente: medir y documentar tamaño
- [ ] T044 Referencias externas de R (rugarch::DACTest, forecast::dm.test, Rapach-Zhou) cuando R esté disponible
- [ ] T045 Inferencia IVX (Kostakis-Magdalinos-Stamatogiannis 2015) para regresores persistentes
- [ ] T046 Soporte de vintages ALFRED en FredSource para variables revisables
- [X] T036 [P] [US5] Prueba de rendimiento SC-006 (8 activos × 20 configuraciones × 10 años diarios < 60 s) en tests/backtest/test_performance.py (marca `slow`)

## Phase 8: Polish

- [X] T037 [P] Nota metodológica docs/methodology/backtesting.md con referencias
- [X] T038 [P] Exportar API pública en src/tsinsurance/backtest/__init__.py según contracts/public-api.md
- [ ] T039 Ejecutar `econometrics-reviewer` sobre la implementación y resolver bloqueantes
- [X] T040 Actualizar README, roadmap y CI (`--all-extras`); verificar cobertura ≥ 90 %, mypy y ruff

## Dependencies & Execution Order

- Setup → Foundational (config, métricas) → US1 (motor, señales, anticipación).
- US2 depende de US1 (motor) y de `diagnostics.stationarity` (spec 001).
- US3 depende de US1; `backtest_econometric` (T025) usa SPA de US3 (T029) → implementar T029 antes de T025.
- US4 depende de US1-US3. US5 depende de T031.

## Parallel Examples

```text
US1 pruebas: T008, T009, T010, T011 · implementación: T013, T014, T015 tras T012
US2 pruebas: T016-T020 en paralelo
```

## Implementation Strategy

MVP = Setup + Foundational + US1 (motor validado contra bt + señales + anticipación);
luego US3 (inferencia) → US2 (econométrico) → US4 (ETFs reales) → US5.
