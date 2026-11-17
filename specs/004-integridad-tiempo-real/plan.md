# Implementation Plan: Integridad del procedimiento y datos en tiempo real

**Branch**: `ccr-d4f6f6a0-bg0992` (rama de trabajo; la carpeta de la spec es `004-integridad-tiempo-real`) | **Date**: 2026-11-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-integridad-tiempo-real/spec.md`

## Summary

La spec cierra cinco vías por las que un resultado puede parecer válido sin serlo y
afina la inferencia:

- **Bitácora a prueba de recortes**: el estado de la bitácora se guarda en cada
  resultado, la integración continua sólo acepta líneas agregadas al final y hay un solo
  escritor con bloqueo.
- **Validación única en dos fases**: `experiment run` calibra con un paquete truncado en
  `train_end`; `experiment validate` abre la validación una vez. Aplica también a los
  modelos econométricos.
- **Huella del código** de las señales propias en la identidad de cada prueba.
- **Variables macro en tiempo real** desde ALFRED, en dos modos: primera publicación y
  todas las versiones. Se apoya en un contrato de datos 1.1 compatible.
- **Inferencia**: IVX para regresores persistentes y preblanqueo del EE HAC del Sharpe,
  ambos verificados contra R.
- **Varianza del DSR estandarizada por √T**, adoptada sólo si el Monte Carlo la respalda.
  El research corrige la idea original de "restar el ruido", que sería permisiva bajo la
  hipótesis nula.

La prueba de aceptación es un experimento registrado con TLT, TBX y TBF.

## Technical Context

**Language/Version**: Python ≥ 3.11 (CI en 3.11, 3.12 y 3.13)

**Primary Dependencies**: numpy, pandas, scipy, statsmodels, arch, pandera (existentes);
`ast`, `inspect`, `os` de la biblioteca estándar. No hay dependencias nuevas.

**Storage**: archivos (`registry.jsonl` + `.lock`, `result.json`, paquete de insumos
CSV + TOML)

**Testing**: pytest + hypothesis; referencias en R (`ivx` 1.1.1 y `sandwich`, instalados);
Monte Carlo con la marca `slow`; ALFRED con respuestas grabadas (sin red) y una prueba
`network` opcional.

**Target Platform**: Linux, macOS y Windows (el bloqueo usa creación exclusiva de archivo,
no `fcntl`)

**Project Type**: biblioteca Python con CLI

**Performance Goals**:
- experimento de aceptación < 5 min de punta a punta (SC-010);
- la vista `all_vintages` mensual para 30 años debe agregar < 10 s por regresor;
- la verificación con `--results` de 100 resultados debe tardar < 2 s.

**Constraints**:
- compatibilidad aditiva de `result.json` (1.2) y del contrato de datos (1.1);
- las bitácoras existentes siguen verificando;
- la clave de FRED se lee sólo del entorno.

**Scale/Scope**:
- bitácoras de hasta ~10⁵ líneas;
- series con hasta ~500 versiones por periodo (IPC, empleo).

## Constitution Check

| Principio | Cómo lo cumple el diseño | Estado |
|-----------|--------------------------|--------|
| I. Rigor econométrico | IVX para regresores persistentes (R5); estandarización del DSR justificada bajo H0 (R7) | ✔ |
| II. Validación sin fuga | `Bundle.as_of` en calibración (R3); tiempo real con fecha de publicación y `realtime_end` reabierto (R4) | ✔ (núcleo de la spec) |
| III. Incertidumbre | preblanqueo del EE del Sharpe (R6); tamaño y potencia por Monte Carlo | ✔ |
| IV. Agnóstico de jurisdicción | el tiempo real vive en el contrato (cualquier fuente puede traer `realtime_start`); ALFRED es sólo un conector | ✔ |
| IV-bis. Datos con contrato | contrato 1.1 opcional y validado; licencias por serie sin cambios | ✔ |
| V. Biblioteca tipada | API en `contracts/python-api.md`, mypy estricto | ✔ |
| VI. Pruebas primero | cada SC tiene una prueba: DGP conocido, referencia en R o mutación de datos | ✔ |
| VII. Simplicidad | dos modos de tiempo real y dos fases agregan superficie; ver Complexity Tracking | ⚠ justificado |
| VIII. Backtesting responsable | fuera de muestra intocable de verdad (dos fases), bitácora completa para pruebas múltiples, anticipación por fecha de publicación | ✔ (núcleo de la spec) |

**Gate**: pasa. No hay violaciones sin justificar. Re-evaluado después del diseño de la
Fase 1: sin cambios.

## Project Structure

### Documentation (this feature)

```text
specs/004-integridad-tiempo-real/
├── spec.md
├── plan.md              # este archivo
├── research.md          # R1-R9
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   └── python-api.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/tsinsurance/
├── experiments/
│   ├── registry.py        # RegistryHead, registry_lock, unlock, verify(base, results)   [US1]
│   ├── fingerprint.py     # NUEVO: SignalFingerprint                                     [US3]
│   ├── runner.py          # fase de calibración con Bundle.as_of; evento calibration     [US2]
│   ├── validate.py        # NUEVO: validate_experiment y precondiciones                  [US2]
│   └── spec.py            # vintage_mode en recetas                                     [US4]
├── data/
│   ├── schemas.py         # contrato market 1.1 (realtime_start, realtime_end)           [US4]
│   ├── bundle.py          # vintage_mode, Bundle.as_of, construcción de RealTimeExogenous [US2, US4]
│   └── sources/fred.py    # modos first_release / all_vintages (ALFRED, paginado)        [US4]
├── backtest/
│   ├── pit.py             # RealTimeExogenous, alineación por fecha de publicación       [US4]
│   ├── lookahead.py       # truncado por realtime_start; reabrir realtime_end            [US4]
│   ├── econometric.py     # ivx_test; walk_forward con X_at(d); ventana de calibración   [US2, US4, US5]
│   ├── inference.py       # hac="prewhitened"; variance_rule="standardized"              [US5, US6]
│   └── sweep.py           # n_obs de pruebas previas hacia el DSR                        [US6]
└── cli.py                 # experiment validate | verify --base --results | unlock

.github/workflows/ci.yml   # paso de prefijo de bitácora en pull_request                  [US1]

tests/
├── experiments/  test_registry_head.py, test_lock.py, test_two_phase.py, test_fingerprint.py
├── data/         test_contract_1_1.py, test_alfred_recorded.py (respuestas grabadas)
├── backtest/     test_realtime_exogenous.py, test_lookahead_vintages.py
├── reference/    test_ivx_against_r.py, test_prewhitening_against_r.py (+ r/*.R)
├── simulation/   test_ivx_size.py, test_prewhitening_bias.py, test_dsr_variance_rule.py  (slow)
└── network/      test_alfred_live.py

experiments/tlt_treasury/  recipe.toml, experiment.toml, README.md                        [US7]
docs/  methodology/backtesting.md (R6, R7), methodology/realtime.md (NUEVO, R4),
       integracion/manual-de-uso.md, AGENTS.md, SKILL.md (dos fases, campos nuevos)
```

**Structure Decision**: biblioteca única con layout `src/`, igual que las specs 001-003.
Dos módulos nuevos:
- `fingerprint.py`, porque es una responsabilidad aislada;
- `validate.py`, para que la fase de validación tenga sus precondiciones en un solo lugar
  y no se mezcle con la calibración.

### Orden de implementación (dependencias)

```text
US1 bitácora ──┐
US3 huella ────┼──▶ US2 dos fases ──▶ US7 aceptación
US4 tiempo real┘         ▲
US5 IVX / preblanqueo ───┤ (independientes; se integran en result.json)
US6 varianza DSR ────────┘ (Monte Carlo decide el valor por defecto)
```

- US1 y US3 van primero porque son pequeñas y cambian la identidad y el registro que usa
  US2.
- US4 puede avanzar en paralelo (datos) y se integra con US2 en `Bundle.as_of`.
- US5 y US6 son independientes.
- US7 cierra.

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Cobertura de ALFRED: la primera versión archivada es de los años noventa | modo estricto por defecto; `bundle show` informa la cobertura; el experimento de aceptación empieza donde hay cobertura |
| La API real de ALFRED difiere de lo documentado (nombres, límites) | grabar respuestas reales en la primera ejecución con clave; pruebas sin red sobre esas grabaciones |
| `experiment run` deja de validar (cambio de comportamiento) | versión 0.2.0, nota en el registro de cambios, manual y AGENTS actualizados, mensaje con el comando de validación |
| El preblanqueo o la estandarización no pasan el Monte Carlo | se mantiene la regla vigente (FR-023) y se documenta; la opción queda disponible y explícita |
| Huella por AST sensible a refactorizaciones sin cambio de comportamiento | conservador por diseño: cuenta una prueba de más, nunca de menos |

## Complexity Tracking

| Agregado | Por qué se necesita | Alternativa más simple descartada porque |
|----------|---------------------|------------------------------------------|
| Dos modos de tiempo real | El usuario pidió ambos. Comparar los dos modos mide cuánto depende la conclusión de las correcciones ya conocidas | Uno solo no permite esa comparación |
| Dos comandos (run / validate) | Es la única forma lógica de impedir ver el periodo de validación mientras se itera | La validación automática con advertencia es lo actual y no lo impide |
| `walk_forward` con `X_at(d)` | En el modo todas las versiones, la historia de regresores cambia en cada fecha | Una matriz fija mezclaría versiones de fechas distintas |
