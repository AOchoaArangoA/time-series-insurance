---
description: "Tareas de la spec 005: ideas de cartera y regímenes del ciclo"
---

# Tasks: Ideas de cartera y regímenes del ciclo

**Input**: `specs/005-cartera-regimenes/`
- spec.md;
- plan.md;
- research.md (R1-R6, incluidas las correcciones de la revisión);
- data-model.md;
- contracts/experiment-toml.md.

**Tests**: obligatorios (Principio VI): se escriben primero.

## Phase 1: Setup / Foundational

- [X] T001 [P] Registro de señales de cartera con `cross_sectional_momentum`, `inverse_volatility` y `equal_weight` en `src/tsinsurance/experiments/portfolio_signals.py`, con pruebas en `tests/experiments/test_portfolio_signals.py`
- [X] T002 [P] `Bundle.variable(id)` (exógena o tasa libre de riesgo con su rezago) en `src/tsinsurance/data/bundle.py`
- [ ] T003 Ajustar las señales a la revisión (I5) en `src/tsinsurance/experiments/portfolio_signals.py`:
  - momentum con cierres de fin de mes;
  - empates por id ordenado;
  - rechazar `top_k ≥ |U|`;
  - piso de σ en `inverse_volatility`.
- [ ] T004 `PortfolioSpec`, `RegimeSpec` y `DeclaredPriorSpec` en `src/tsinsurance/experiments/spec.py`, con validación:
  - universo con ≥ 2 activos;
  - tipos de régimen válidos;
  - `justification`;
  - mallas de umbral.
- [ ] T005 Memoria en `src/tsinsurance/experiments/registry.py`:
  - kinds `portfolio`, `regime` y `declared_prior`;
  - `prior_portfolio_trials(rows, universe, cut)` con Jaccard ≥ 0,5 (N) y varianza sólo con `eval_end` ≤ corte (B3);
  - `prior_regime_variants(rows, key)` (B1).

## Phase 2: User Story 1 — Ideas de cartera (P1) 🎯 MVP

- [ ] T006 [US1] Pruebas en `tests/experiments/test_portfolios.py`:
  - anticipación sobre el universo;
  - líneas `portfolio` con la identidad del universo;
  - benchmark igual ponderado con costos y rebalanceo M (B4);
  - elegibilidad por bloque y ventana común;
  - memoria por Jaccard: 9 → 11 sectores no reinicia N (B3);
  - pruebas declaradas suman en N (B2);
  - dos fases con exposición de la calibración y periodo visto por universo o constituyente (I2).
- [ ] T007 [US1] Evaluación de carteras en la calibración en `src/tsinsurance/experiments/runner.py`:
  - `rebalance = "M"`;
  - benchmark con `run_backtest` (pesos igual ponderados y los mismos costos);
  - `Trial` por configuración y `select`;
  - líneas `portfolio`;
  - `frozen.portfolios`.
- [ ] T008 [US1] Validación de carteras en `src/tsinsurance/experiments/validate.py`:
  - evaluación única con la exposición de la calibración;
  - familia "estrategias" con α·0,8 (I1);
  - periodo visto por universo, constituyentes y pruebas declaradas (I2).
- [ ] T009 [US1] Registrar `[[declared_prior_tests]]` como líneas `declared_prior` idempotentes en `src/tsinsurance/experiments/runner.py`

## Phase 3: User Story 2 — Regímenes (P2)

- [ ] T010 [US2] Pruebas en `tests/experiments/test_regimes.py`:
  - estados punto en el tiempo (SC-005), incluido `spread` con desfase máximo de 5 días hábiles;
  - `trend` con cierres de mes;
  - HC3;
  - `min_months` ⇒ no concluyente;
  - Holm con variantes previas (B1);
  - malla de umbrales;
  - sin `justification` ⇒ exploratorio;
  - validación sólo de las seleccionadas, unilateral, en la familia de regímenes con α·0,2.
- [ ] T011 [US2] Implementar `src/tsinsurance/experiments/regimes.py`:
  - construcción de estados;
  - análisis HC3;
  - Holm con m extendido.
- [ ] T012 [US2] Integrar los regímenes en `runner.py` (calibración, líneas `regime`, `frozen.regimes` con los seleccionados) y en `validate.py` (pruebas unilaterales en la familia de regímenes)

## Phase 4: Calibración estadística

- [ ] T013 [P] Monte Carlo en `tests/simulation/test_portfolio_regime_size.py` (marca `slow`):
  - SC-001: tamaño de la rotación con medias iguales, factor común, inicios distintos y costos;
  - SC-004: tamaño con un estado endógeno de tendencia, y potencia con un efecto de 0,6σ.

## Phase 5: User Story 3 — Demostración sectorial (P3)

- [ ] T014 [US3] Crear `experiments/sectores_gics/rotacion_regimenes.toml` con:
  - rotación sobre 9 sectores;
  - regímenes (curva invertida, VIX con malla y justificación, tendencia de SPY);
  - pruebas declaradas del script exploratorio.
- [ ] T015 [US3] Ejecutar la calibración, confirmar en git, validar y verificar la bitácora. Documentar en `experiments/sectores_gics/README.md`

## Phase 6: Polish

- [ ] T016 [P] Agregar `docs/methodology/carteras-y-regimenes.md` (R1-R6) y los bloques nuevos en `docs/integracion/manual-de-uso.md`, `AGENTS.md` y el SKILL
- [ ] T017 Ejecutar `ruff`, `mypy` y `pytest` completo, y la revisión de implementación con `econometrics-reviewer`
