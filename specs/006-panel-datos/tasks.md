---
description: "Tareas de la spec 006: datos de panel"
---

# Tasks: Datos de panel con efectos fijos y aleatorios

**Input**: spec.md, plan.md, research.md (R1-R8, incluida la revisión). **Tests**:
primero (Principio VI).

## Phase 1: US1 núcleo (P1) 🎯

- [X] T001 [US1] `fit_panel` en `src/tsinsurance/panel/estimators.py`:
  - MCO agrupado, FE, TWFE, FD y RE;
  - detección de regresores absorbidos y con poca variación *within*;
  - advertencia con pocas unidades;
  - supuestos causales;
  - pruebas DGP y *within* manual en `tests/panel/test_estimators.py`.
- [ ] T002 [US1] Diagnósticos del Principio I en `src/tsinsurance/panel/diagnostics.py` (B3):
  - correlación serial de Wooldridge;
  - CD de Pesaran sin efectos de tiempo (con efectos de tiempo se advierte; I5);
  - ADF+KPSS de los regresores y de y por unidad;
  - ARCH-LM por unidad;
  - Chow en el corte o CUSUM;
  - AR(1) de los regresores y correlación de sus innovaciones con los residuos (I2).

  Con pruebas en `tests/panel/test_diagnostics.py`.
- [ ] T003 [US1] Inferencia en `src/tsinsurance/panel/inference.py`:
  - Driscoll-Kraay con t(T−1);
  - WCR (Rademacher o Webb, enumeración completa con G ≤ 12, B ≥ 9 999 en otro caso,
    semilla);
  - G₁ por interacción, con G₁ < 2 ⇒ no concluyente (B2).

  Con pruebas en `tests/panel/test_inference.py`.
- [ ] T004 [US1] Referencias de R guardadas (M1): `tests/reference/r/plm_reference.R` y
  `tests/data/reference/plm_*.json`, con:
  - FE, TWFE, RE (desbalanceado con tolerancia 1e-4);
  - `vcovSCC`;
  - `pcdtest`;
  - `pwartest`;
  - `phtest`.

## Phase 2: US2 FE frente a RE (P1)

- [ ] T005 [US2] `mundlak_test` (CRE con medias por unidad y por periodo; F(q, G−1) con
  pocos grupos) y `hausman_test` (clásico) en `src/tsinsurance/panel/inference.py`, con su
  recomendación y la advertencia θ ≈ 1 (I1)

## Phase 3: US4 diferencias en diferencias (P3)

- [ ] T006 [US4] `diff_in_diff` y `event_study` en `src/tsinsurance/panel/did.py`:
  - ATET con TWFE;
  - *leads* y *lags* con −1 como referencia;
  - prueba conjunta de tendencias previas (advertencia de Roth 2022);
  - permutación con una sola unidad tratada;
  - advertencia de Goodman-Bacon con adopción escalonada;
  - supuesto de no anticipación (I6).

## Phase 4: US3 experimentos (P2)

- [ ] T007 [US3] `PanelSpec` (`[[panels]]`) en `spec.py`.
- [ ] T008 [US3] Construcción del panel punto en el tiempo en
  `src/tsinsurance/experiments/panels.py`.
- [ ] T009 [US3] Integración en `runner.py`:
  - líneas `panel`;
  - memoria por (variable dependiente, universo con Jaccard), con las variantes de I3;
  - frozen: especificación, hipótesis, tipo de error, ancho de banda, B y semilla.
- [ ] T010 [US3] Integración en `validate.py`:
  - re-estimación posterior al corte;
  - valor p unilateral con t(T−1);
  - efecto mínimo detectable (I4);
  - `_seen_after` con `kind == "panel"`.
- [ ] T011 [US3] Reparto de α congelado (estrategias 0,7α, regímenes 0,15α y paneles
  0,15α, renormalizado según las familias presentes) en `runner.py` y `validate.py`, que
  lee `frozen.alpha_split` (B1).

## Phase 5: Monte Carlo y demostración

- [ ] T012 [P] Monte Carlo en `tests/simulation/test_panel_size.py` (`slow`): SC-001,
  SC-003 (≥ 2 000 réplicas), SC-004 (G₁ ∈ {1, 2, 5}, T ∈ {36, 300}, regresor persistente)
  y SC-005.
- [ ] T013 [US5] `experiments/sectores_gics/panel_sectores.toml`, con características
  "financiero o sensible a tasas" y "defensivo" (G₁ ≥ 2); advertencia por la
  reclasificación GICS de 2018 (M4).
- [ ] T014 `docs/methodology/panel.md`, más AGENTS, manual, SKILL y CHANGELOG.
- [ ] T015 Revisión de implementación con `econometrics-reviewer` y suite completa.
