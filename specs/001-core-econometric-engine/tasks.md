# Tasks: Motor econométrico núcleo para inversiones de una aseguradora

**Input**: Design documents from `/specs/001-core-econometric-engine/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: OBLIGATORIOS (constitución, Principio VI — TDD). Cada prueba se escribe antes
de su implementación y debe fallar primero.

**Organization**: por historia de usuario (US1-US5 de spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizable (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia de usuario (US1…US5)

---

## Phase 1: Setup

- [ ] T001 Actualizar dependencias en pyproject.toml: núcleo `pandera>=0.20`, `httpx>=0.27`; extras `yahoo` (yfinance), `excel` (openpyxl), `parquet` (pyarrow), `viz` (matplotlib); script `tsinsurance = "tsinsurance.cli:main"`; marcas pytest `slow` y `network` con `-m "not network"` por defecto
- [ ] T002 [P] Crear estructura de subpaquetes vacíos según plan.md en src/tsinsurance/{data,data/sources,diagnostics,models,forecast,validation,risk,reporting}/__init__.py
- [ ] T003 [P] Crear tests/conftest.py con fixtures de `numpy.random.Generator(seed)` y simuladores de DGP: random walk, AR(1), ARMA(1,1), ARMA(1,1)-GARCH(1,1) con innovaciones t
- [ ] T004 [P] Crear estructura de tests: tests/{unit,reference,simulation,integration,fixtures}/

---

## Phase 2: Foundational (bloquea todas las historias)

- [ ] T005 [P] Prueba de jerarquía de errores y warnings en tests/unit/test_errors.py
- [ ] T006 [P] Implementar `TSInsuranceError`, `DataValidationError`, `InsufficientDataError`, `ConvergenceError`, `InadequateModelWarning` en src/tsinsurance/errors.py
- [ ] T007 [P] Prueba de `TestResult` (`summary()`, `to_dict()` JSON canónico, `reject_at`) en tests/unit/test_results.py
- [ ] T008 Implementar `TestResult` y base `ResultMixin` (frozen dataclass, `summary`, `to_dict`) en src/tsinsurance/results.py
- [ ] T009 [P] Prueba de `JurisdictionProfile`: perfil `generic` = `confidence_level 0.995`, `horizon_days 252`; carga desde TOML; inmutabilidad, en tests/unit/test_config.py
- [ ] T010 Implementar `JurisdictionProfile` y `load_profile` en src/tsinsurance/config.py y perfil por defecto src/tsinsurance/profiles/generic.toml
- [ ] T011 [P] Implementar alias de tipos (`Frequency = Literal["D","B","W","M"]`, `SeriesLike`) en src/tsinsurance/_types.py

**Checkpoint**: fundación lista.

---

## Phase 3: User Story 1 — Preparar y diagnosticar series de mercado (P1) 🎯 MVP

**Goal**: datos validados contra contrato, conectores replicables y diagnóstico de estacionariedad.
**Independent Test**: random walk → `I(1)`; AR(1) φ=0.5 → `I(0)`; plantilla generada y validada; snapshot recargable con hash idéntico.

### Tests (escribir primero)

- [ ] T012 [P] [US1] Pruebas de esquemas en tests/unit/test_schemas.py: `MarketSeries` (`date` única por `series_id` y monótona; `series_id` `^[A-Za-z0-9_.:-]+$`; `kind` ∈ {price, return, rate, index}; `unit` ∈ {level, percent, decimal, bps}; `currency` ISO 4217; `frequency` ∈ {D,B,W,M}; `price` > 0), `Portfolio` (`sum(weight) == 1 ± 1e-8`; `amount` requerido si no hay `weight`; `asset_class` ∈ {fixed_income, equity, real_estate, cash, other}), `RateNodes` (`tenor_years` > 0; `compounding` ∈ {continuous, annual, semiannual, simple})
- [ ] T013 [P] [US1] Prueba de validación lazy: archivo con 3 errores reporta 3 filas con `row`, `column`, `check`, `failure_case` en tests/unit/test_validate.py y fixture tests/fixtures/market_bad.csv
- [ ] T014 [P] [US1] Pruebas de plantillas CSV/XLSX y export JSON Schema / Frictionless en tests/unit/test_templates.py
- [ ] T015 [P] [US1] Pruebas de `Snapshot` (round-trip Parquet+JSON, SHA-256 estable, `schema_version`) en tests/unit/test_snapshot.py
- [ ] T016 [P] [US1] Pruebas de fuentes con respuestas HTTP simuladas (sin red) para FRED y Yahoo, y CSV/Excel locales en tests/unit/test_sources.py
- [ ] T017 [P] [US1] Pruebas de `prepare`: índice no monótono/duplicado → error; log de precio ≤ 0 → error; registro de imputaciones en tests/unit/test_prepare.py
- [ ] T018 [P] [US1] Pruebas de referencia ADF/KPSS/PP/ZA contra statsmodels/arch y valores publicados (Nelson-Plosser) en tests/reference/test_unit_roots.py
- [ ] T019 [P] [US1] Prueba de regla confirmatoria (I(0), I(1), inconcluso) y quiebre detectado en serie con cambio de nivel en tests/unit/test_stationarity.py
- [ ] T020 [P] [US1] Simulación SC-001 (500 réplicas, n=500, acierto ≥ 90 %) en tests/simulation/test_integration_order_power.py (marca `slow`)

### Implementation

- [ ] T021 [P] [US1] Implementar `MarketSeriesSchema`, `PortfolioSchema`, `RateNodesSchema` y `SCHEMA_VERSION = "1.0"` en src/tsinsurance/data/schemas.py
- [ ] T022 [US1] Implementar `validate`, `ValidationReport` y `load` en src/tsinsurance/data/validate.py (depende de T021)
- [ ] T023 [P] [US1] Implementar `write_template` y `export_schema` en src/tsinsurance/data/templates.py
- [ ] T024 [P] [US1] Implementar `Snapshot` (save/load, hash) en src/tsinsurance/data/snapshot.py
- [ ] T025 [US1] Implementar protocolo `DataSource` y registro por entry points `tsinsurance.sources` en src/tsinsurance/data/sources/base.py
- [ ] T026 [P] [US1] Implementar `CSVSource` y `ExcelSource` en src/tsinsurance/data/sources/files.py
- [ ] T027 [P] [US1] Implementar `FredSource` (API REST, clave en `FRED_API_KEY`) en src/tsinsurance/data/sources/fred.py
- [ ] T028 [P] [US1] Implementar `YahooSource` (extra `yahoo`) en src/tsinsurance/data/sources/yahoo.py
- [ ] T029 [US1] Implementar `prepare` y `PreparedSeries` en src/tsinsurance/data/prepare.py
- [ ] T030 [P] [US1] Implementar `adf`, `pp`, `kpss`, `zivot_andrews` envolviendo statsmodels/arch en src/tsinsurance/diagnostics/stationarity.py
- [ ] T031 [US1] Implementar `stationarity` (regla confirmatoria, recursión hasta `max_d`, `StationarityReport`) en src/tsinsurance/diagnostics/stationarity.py
- [ ] T032 [P] [US1] Implementar `describe` (momentos, ACF/PACF, JB, ARCH-LM) en src/tsinsurance/diagnostics/descriptive.py
- [ ] T033 [US1] Implementar CLI `template`, `validate`, `schema` en src/tsinsurance/cli.py
- [ ] T034 [US1] Crear snapshot FRED DGS10 en examples/data/fred_dgs10/ y ejercicio examples/01_diagnostico_tasas_fred.py
- [ ] T035 [P] [US1] Nota metodológica docs/methodology/stationarity.md (referencias: Dickey-Fuller 1979, Phillips-Perron 1988, KPSS 1992, Zivot-Andrews 1992, MacKinnon 1996)

**Checkpoint**: US1 funcional y demostrable sola.

---

## Phase 4: User Story 2 — Ajustar y validar modelos de media y volatilidad (P1)

**Goal**: ARIMA/SARIMA y GARCH/EGARCH/GJR con selección y diagnósticos.
**Independent Test**: DGP ARMA(1,1)-GARCH(1,1)-t recupera parámetros; residuos aptos.

### Tests

- [ ] T036 [P] [US2] Pruebas de `residual_diagnostics` (Ljung-Box con `model_df`, ARCH-LM, JB, CUSUM, `is_adequate`) en tests/unit/test_residuals.py
- [ ] T037 [P] [US2] Pruebas de `fit_arima` / `select_arima` (recupera orden de ARMA(1,1); tabla de candidatos con AIC/BIC/HQIC) en tests/unit/test_arima.py
- [ ] T038 [P] [US2] Pruebas de `fit_garch` / `select_garch` (convergencia, reintentos, SE robustos, `skewt`) en tests/unit/test_garch.py
- [ ] T039 [P] [US2] Prueba de advertencia `InadequateModelWarning` al pronosticar modelo no apto y error con `converged=False` en tests/unit/test_model_states.py
- [ ] T040 [P] [US2] Simulación SC-002 (cobertura ±2 SE ≥ 95 %) en tests/simulation/test_parameter_recovery.py (marca `slow`)
- [ ] T041 [P] [US2] Referencia GARCH contra valores publicados (Bollerslev-Ghysels DM/GBP) en tests/reference/test_garch_reference.py

### Implementation

- [ ] T042 [US2] Implementar `ResidualDiagnostics` y `residual_diagnostics` en src/tsinsurance/diagnostics/residuals.py
- [ ] T043 [US2] Implementar base `FittedModel` y `SelectionResult` en src/tsinsurance/models/base.py
- [ ] T044 [P] [US2] Implementar `fit_arima`, `select_arima`, `ArimaResult` en src/tsinsurance/models/arima.py
- [ ] T045 [P] [US2] Implementar `fit_garch`, `select_garch`, `GarchResult` en src/tsinsurance/models/volatility.py
- [ ] T046 [P] [US2] Notas metodológicas docs/methodology/arima.md y docs/methodology/garch.md

**Checkpoint**: US1 + US2 funcionales.

---

## Phase 5: User Story 3 — Pronóstico con incertidumbre y validación fuera de muestra (P2)

**Goal**: `Forecast` con intervalos y `rolling_origin` sin fuga, con DM vs benchmarks.
**Independent Test**: modelo espía nunca recibe datos > origen; cobertura 95 % en [93 %, 97 %].

### Tests

- [ ] T047 [P] [US3] Pruebas de `Forecast` (intervalos 80/95 % por defecto; métodos analytic/simulation reproducibles con semilla) en tests/unit/test_forecast.py
- [ ] T048 [P] [US3] Prueba anti-fuga con modelo espía en tests/unit/test_rolling_no_leakage.py
- [ ] T049 [P] [US3] Pruebas de métricas RMSE/MAE/MASE en tests/unit/test_metrics.py
- [ ] T050 [P] [US3] Referencia Diebold-Mariano con corrección HLN en tests/reference/test_diebold_mariano.py
- [ ] T051 [P] [US3] Simulación SC-004 de cobertura de intervalos en tests/simulation/test_interval_coverage.py (marca `slow`)

### Implementation

- [ ] T052 [US3] Implementar `Forecast` y `FittedModel.forecast` en src/tsinsurance/forecast/forecast.py
- [ ] T053 [P] [US3] Implementar `rmse`, `mae`, `mase` en src/tsinsurance/validation/metrics.py
- [ ] T054 [P] [US3] Implementar `diebold_mariano` y benchmarks `random_walk`, `mean` en src/tsinsurance/validation/comparison.py
- [ ] T055 [US3] Implementar `rolling_origin` y `BacktestResult` en src/tsinsurance/validation/rolling.py
- [ ] T056 [US3] Crear snapshot Yahoo índice accionario en examples/data/ y ejercicio examples/02_garch_indice_accionario.py
- [ ] T057 [P] [US3] Nota metodológica docs/methodology/forecast-evaluation.md

---

## Phase 6: User Story 4 — Riesgo de mercado del portafolio y backtesting (P2)

**Goal**: VaR/ES histórico, paramétrico y GARCH, por activo y portafolio, con backtesting.
**Independent Test**: SC-005 — rechaza VaR mal especificado y no rechaza el correcto en ≥ 90 % de réplicas.

### Tests

- [ ] T058 [P] [US4] Pruebas de `value_at_risk` / `expected_shortfall` (tres métodos; pesos; nivel/horizonte desde perfil cuando son `None`) en tests/unit/test_risk_measures.py
- [ ] T059 [P] [US4] Pruebas de escalado `sqrt_time` (incluye advertencia de supuesto i.i.d.) y `simulation` reproducible en tests/unit/test_horizon.py
- [ ] T060 [P] [US4] Referencia Kupiec/Christoffersen contra ejemplos publicados (Jorion; Christoffersen 1998) y zonas semáforo de Basilea en tests/reference/test_var_backtests.py
- [ ] T061 [P] [US4] Pruebas de Acerbi-Szekely Z2 en tests/unit/test_es_backtest.py
- [ ] T062 [P] [US4] Simulación SC-005 en tests/simulation/test_var_backtest_power.py (marca `slow`)

### Implementation

- [ ] T063 [US4] Implementar `RiskMeasure`, `value_at_risk`, `expected_shortfall` en src/tsinsurance/risk/measures.py
- [ ] T064 [P] [US4] Implementar escalado de horizonte en src/tsinsurance/risk/horizon.py
- [ ] T065 [P] [US4] Implementar `kupiec`, `christoffersen`, `traffic_light`, `acerbi_szekely`, `backtest_var`, `backtest_es` en src/tsinsurance/risk/backtest.py
- [ ] T066 [US4] Ejercicio examples/03_var_portafolio_backtesting.py con portafolio de ejemplo examples/data/portfolio_example.csv
- [ ] T067 [P] [US4] Nota metodológica docs/methodology/var-es-backtesting.md

---

## Phase 7: User Story 5 — Reporte reproducible (P3)

**Goal**: `AnalysisReport` JSON/Markdown con huella de datos, versiones, semilla y perfil.
**Independent Test**: dos ejecuciones con la misma semilla → JSON idéntico (excluyendo `created_at`).

- [ ] T068 [P] [US5] Pruebas de serialización canónica y reproducibilidad en tests/unit/test_report.py
- [ ] T069 [US5] Implementar `AnalysisReport` (`to_json`, `to_markdown`, `save`) en src/tsinsurance/reporting/report.py
- [ ] T070 [US5] Añadir opción `--report` a los ejercicios en examples/ y prueba de integración tests/integration/test_examples_reproducible.py (SC-007, SC-009)

---

## Phase 8: Polish & Cross-Cutting

- [ ] T071 [P] Exportar API pública en src/tsinsurance/__init__.py y subpaquetes según contracts/public-api.md
- [ ] T072 [P] Prueba de contrato de API (nombres y firmas exportadas) en tests/integration/test_public_api.py
- [ ] T073 Ejecutar subagente `econometrics-reviewer` y resolver hallazgos bloqueantes
- [ ] T074 [P] Tutorial de punta a punta (SC-006) en docs/tutorial.md
- [ ] T075 Verificar cobertura ≥ 90 %, `mypy --strict` y `ruff` limpios; validar quickstart.md

---

## Dependencies & Execution Order

- Setup (T001-T004) → Foundational (T005-T011) → historias.
- US1 (P1) es el MVP y no depende de otras historias.
- US2 depende de US1 (datos preparados y diagnóstico de estacionariedad para `d`).
- US3 depende de US2 (modelos ajustados).
- US4 depende de US2 (GARCH) y de US1 (portafolio); puede avanzar en paralelo a US3 con métodos histórico/paramétrico.
- US5 depende de que existan resultados (US1-US4) pero su núcleo (T068-T069) puede iniciarse tras Foundational.
- Dentro de cada historia: pruebas → implementación; esquemas antes que validación; base de modelos antes que modelos concretos.

## Parallel Examples

```text
# US1 — todas las pruebas en paralelo:
T012, T013, T014, T015, T016, T017, T018, T019, T020
# US1 — implementación paralela tras T021:
T023, T024, T026, T027, T028, T030, T032
# US2:
T036-T041 en paralelo; luego T044 y T045 en paralelo tras T043
# US4:
T064 y T065 en paralelo con T063
```

## Implementation Strategy

1. **MVP**: Setup + Foundational + US1 → paquete que valida insumos, descarga datos
   reales replicables y diagnostica estacionariedad. Validar y demostrar.
2. **Incremento 2**: US2 (modelos) → **Incremento 3**: US3 (pronóstico y validación)
   → **Incremento 4**: US4 (riesgo) → **Incremento 5**: US5 (reportes).
3. Tras cada incremento: `uv run pytest`, `econometrics-reviewer`, PR con referencia a
   esta spec.
