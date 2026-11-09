# Tasks: Flujo de experimentos registrados, insumo base y entrega a agentes

**Tests**: obligatorios (Principio VI).

## Phase 1: US1 — Paquete de insumos (P1)

- [X] T001 [P] [US1] Pruebas de equivalencia paquete manual vs generado (SC-001) en tests/experiments/test_bundle.py
- [X] T002 [P] [US1] Catálogo de inconsistencias de manifiesto y datos (SC-002) en tests/experiments/test_bundle.py
- [X] T003 [US1] Implementar `SeriesSpec`, `Bundle`, `validate_bundle`, `write_bundle_template`, `fetch_recipe` en src/tsinsurance/data/bundle.py
- [X] T004 [US1] CLI `tsinsurance bundle template|validate|fetch|show` en src/tsinsurance/cli.py

## Phase 2: US2 — Experimentos registrados (P1)

- [X] T005 [P] [US2] Pruebas del ejecutor, bitácora y deduplicación (SC-003) en tests/experiments/test_runner.py
- [X] T006 [US2] Registro de señales en src/tsinsurance/experiments/signals.py
- [X] T007 [US2] Lectura de experiment.toml en src/tsinsurance/experiments/spec.py
- [X] T008 [US2] Bitácora JSONL en src/tsinsurance/experiments/registry.py
- [X] T009 [US2] `prior_information_ratios` en sweep y ejecutor en src/tsinsurance/experiments/runner.py
- [X] T010 [US2] CLI `tsinsurance experiment run|list|signals`
- [X] T011 [US2] Experimento real experiments/inverse_treasury/ (TBT, TBX, TBF, TLT) y prueba de reproducibilidad (SC-004)

## Phase 3: US3-US4 — Agentes, proceso y publicación (P2)

- [X] T012 [P] [US3] AGENTS.md y .claude/skills/tsinsurance-experiment/SKILL.md
- [X] T013 [P] [US4] docs/propuesta-proceso.md (incluye el acercamiento al flujo de información)
- [X] T014 [P] [US4] docs/politica-datos-y-publicacion.md y LICENSE
- [ ] T015 [US4] Retirar datos no redistribuibles de examples/data antes de publicar (decisión del dueño)
- [ ] T016 [US4] PR a main y cambio de visibilidad (acción del dueño)
- [X] T017 Revisión `econometrics-reviewer` de la spec 003
