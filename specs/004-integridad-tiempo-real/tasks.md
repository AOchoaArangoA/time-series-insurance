---
description: "Tareas de la spec 004: integridad del procedimiento y datos en tiempo real"
---

# Tasks: Integridad del procedimiento y datos en tiempo real

**Input**: `specs/004-integridad-tiempo-real/`
- plan.md;
- spec.md (US1-US7);
- research.md (R1-R10, incluidas las correcciones B1-B6 e I1-I14 de la revisión);
- data-model.md;
- contracts/cli.md y contracts/python-api.md;
- quickstart.md.

**Tests**: obligatorios (Principio VI, pruebas primero). En cada historia, las pruebas se
escriben primero y deben **fallar** antes de implementar.

**Organization**: por historia de usuario. Los identificadores de la revisión (B1…, I1…,
M1…) remiten a `research.md` R10.

## Format: `[ID] [P?] [Story] Descripción`

- **[P]**: paralelizable (archivo distinto, sin dependencias pendientes)
- **[USn]**: historia de `spec.md`
- Rutas desde la raíz del repositorio (layout `src/`)

---

## Phase 1: Setup

**Purpose**: versión, datos de prueba compartidos y referencias en R.

- [ ] T001 Subir la versión a `0.2.0` en `pyproject.toml` y en `src/tsinsurance/__init__.py`; crear `CHANGELOG.md` con la sección 0.2.0, incluido el cambio incompatible "`experiment run` ya no abre la validación"
- [ ] T002 [P] Crear el generador de paquetes sintéticos reutilizable en `tests/fixtures/synthetic_bundle.py`: precios, exógena de mercado con rezago, tasa libre de riesgo, parámetro `train_end` y una función `mutate_after(cut, kind)` para las categorías de mutación de SC-003
- [ ] T003 [P] Crear el generador de series con versiones conocidas en `tests/fixtures/synthetic_vintages.py`, con:
  - versiones de un solo día;
  - una primera publicación tardía de un periodo anterior;
  - una revisión que cambia el año base;
  - la derivación de `first_release` desde el conjunto de todas las versiones (I5).
- [ ] T004 [P] Guardar como datos de prueba versionados las salidas de R en `tests/data/reference/` (`ivx_*.json`, `prewhite_*.json`) junto con los scripts que las generan en `tests/reference/r/ivx_reference.R` y `tests/reference/r/prewhite_reference.R`, para que CI verifique sin R (I10)

---

## Phase 2: Foundational (bloquea todas las historias)

**Purpose**: campos de la bitácora y del resultado que usan varias historias.

- [ ] T005 Escribir pruebas en `tests/experiments/test_registry_fields.py`: toda línea `signal`/`econometric` nueva trae:
  - `n_obs`, igual al largo de la ventana del ratio en sus mismas unidades (días también en las econométricas; nunca `n_forecasts`, B6);
  - `eval_start`, `eval_end` y `sharpe_se_hac`.
- [ ] T006 Registrar `n_obs`, `eval_start`, `eval_end` y `sharpe_se_hac` en las líneas `signal` y `econometric` de `src/tsinsurance/experiments/runner.py`; en las econométricas, `n_obs = len(bt.evaluation_window())`
- [ ] T007 [P] Agregar las excepciones `ValidationPreconditionError`, `RegistryLockedError` y `RegistryTruncatedError` (subclases de `TSInsuranceError`) en `src/tsinsurance/errors.py`
- [ ] T008 [P] Subir `RESULT_VERSION` a `"1.2"` y agregar `phase` y `status.out_of_sample` (`pendiente` | `abierta` | `ninguna`) en `src/tsinsurance/experiments/runner.py`; probar en `tests/experiments/test_result_v1_2.py` que las claves 1.1 se conservan

**Checkpoint**: la suite actual sigue verde y los campos nuevos aparecen en la bitácora.

---

## Phase 3: User Story 1 — Bitácora a prueba de recortes (P1) 🎯 MVP

**Goal**: detectar recortes al final, aceptar en CI sólo líneas agregadas y permitir un
solo escritor a la vez.

**Independent Test**:
- borrar de 1 a N líneas del final ⇒ `verify --results` falla y nombra el resultado;
- editar, reordenar o borrar líneas ⇒ `verify --base` falla;
- dos ejecuciones a la vez ⇒ la segunda sale con código 2.

### Tests (escribir primero)

- [ ] T009 [P] [US1] Pruebas de `registry_head` y de `verify_registry(results=...)` en `tests/experiments/test_registry_head.py`: recortes de 1..N líneas detectados al 100 % (SC-001); resultados de otra bitácora ignorados al filtrar por `provenance.registry` (I14); bitácoras antiguas sin `registry_head` siguen verificando
- [ ] T010 [P] [US1] Pruebas de `verify_registry(base=...)` en `tests/experiments/test_registry_prefix.py`: agregar líneas ⇒ acepta; editar, reordenar o borrar ⇒ rechaza con la primera línea distinta (SC-002); base vacía ⇒ acepta cualquier bitácora íntegra
- [ ] T011 [P] [US1] Pruebas del bloqueo en `tests/experiments/test_lock.py`:
  - creación exclusiva;
  - una segunda ejecución recibe `RegistryLockedError`;
  - el bloqueo cubre la ejecución **entera**: una ejecución concurrente simulada no puede leer la bitácora entre la lectura y la escritura de otra (I1);
  - un bloqueo vencido sólo se borra con `unlock`;
  - en la misma máquina con el PID vivo, sólo con `--force` (M2);
  - recuperación de una última línea JSON truncada (I1).

### Implementation

- [ ] T012 [US1] Implementar `RegistryHead` y `registry_head(path)` en `src/tsinsurance/experiments/registry.py` ("`n_lines` int ≥ 0; `last_hash` = `line_hash` de la línea `n_lines`; `GENESIS` si `n_lines = 0`")
- [ ] T013 [US1] Extender `verify_registry(path, *, base=None, results=None)` en `src/tsinsurance/experiments/registry.py`: `base` exige prefijo byte a byte; `results` recorre `result.json` con `provenance.registry` igual a `path` y exige `len ≥ n_lines` y hash coincidente
- [ ] T014 [US1] Implementar `registry_lock(path, run_id)` (gestor de contexto con `O_CREAT | O_EXCL`; JSON con `pid`, `host`, `run_id`, `created_at`; escritura con `flush` + `fsync`) y `unlock_registry(path, *, force=False)` en `src/tsinsurance/experiments/registry.py`. El PID vivo se comprueba con `os.kill(pid, 0)` en POSIX y con `OpenProcess` por ctypes en Windows (M1)
- [ ] T015 [US1] En `src/tsinsurance/experiments/runner.py`: tomar el bloqueo **antes** de `verify_registry`/`read_registry` y liberarlo después de la última escritura (I1); guardar `registry_head_before` y `registry_head` en `result.json`
- [ ] T016 [US1] En `src/tsinsurance/cli.py`:
  - `experiment verify REGISTRY [--base BASE] [--results DIR]`;
  - `experiment unlock REGISTRY [--force]`;
  - código de salida 2 cuando la bitácora está bloqueada (contracts/cli.md).
- [ ] T017 [US1] Agregar a `.github/workflows/ci.yml` la verificación de prefijo:
  - en `pull_request`, contra `origin/$GITHUB_BASE_REF`;
  - en `push` a `main`, contra `github.event.before`;
  - distinguir con `git cat-file -e` entre "no existe en la base" y un error (I14).
- [ ] T018 [US1] Escribir la prueba de punta a punta del quickstart §1 en `tests/integration/test_registry_tamper.py`, usando `examples/integracion/`

**Checkpoint**: US1 se puede demostrar sola; el MVP de integridad de la bitácora está completo.

---

## Phase 4: User Story 2 — Validación única con separación lógica (P1)

**Goal**: `experiment run` calibra sin ver nada posterior a `train_end`;
`experiment validate` abre la validación una vez, con precondiciones, detección de
periodos ya vistos, ajuste de Holm y modelos econométricos incluidos.

**Independent Test**:
- SC-003: mutaciones posteriores al corte ⇒ calibración idéntica;
- SC-004: cada precondición violada ⇒ rechazo;
- cada intento de eludir la reapertura ⇒ exploratorio.

### Tests (escribir primero)

- [ ] T019 [P] [US2] Pruebas de `Bundle.as_of(cut)` en `tests/data/test_bundle_as_of.py`:
  - activos y tasa libre de riesgo con `date ≤ cut`;
  - exógenas con disponibilidad ≤ `cut`;
  - `sha256` del completo y `as_of_sha256` del truncado;
  - el objeto truncado no expone el original.
- [ ] T020 [P] [US2] Prueba SC-003 en `tests/experiments/test_two_phase_isolation.py`. Con una copia fija de la bitácora y para cada categoría de `mutate_after` (observaciones posteriores al corte; versiones posteriores al corte de periodos anteriores; `realtime_end > cut`; primeras publicaciones tardías de periodos anteriores), la calibración es idéntica número a número, salvo los campos de procedencia del paquete completo (I6)
- [ ] T021 [P] [US2] Pruebas de precondiciones en `tests/experiments/test_validate_preconditions.py`. Cada uno de estos casos lanza `ValidationPreconditionError` con su causa (SC-004, B5):
  - sin evento `calibration`;
  - otra huella del experimento;
  - otra huella de `as_of(train_end)`;
  - otra bitácora;
  - cambios sin confirmar;
  - archivo no rastreado en el directorio del experimento.

  Sin git, el resultado queda exploratorio.
- [ ] T022 [P] [US2] Pruebas de reapertura en `tests/experiments/test_validate_reopen.py`. Quedan exploratorias, con la ejecución y el experimento que vieron el periodo (FR-009, FR-009a, B1):
  - validar dos veces;
  - renombrar `experiment.id`;
  - volver a descargar el paquete (otra huella completa, mismo `as_of`);
  - extender `end`;
  - una línea `full_sample` previa sobre el activo;
  - una validación de otro experimento.
- [ ] T023 [P] [US2] Pruebas econométricas por fase en `tests/experiments/test_econometric_phases.py`:
  - en calibración, el walk-forward termina en `train_end`;
  - en validación, el veredicto usa sólo pronósticos con fecha **objetivo** > `train_end` y `n_specifications` congelado (M6);
  - la validación escribe `kind = "validation"` y nunca `econometric` (I3).
- [ ] T024 [P] [US2] Pruebas de inferencia de la validación en `tests/experiments/test_validation_inference.py`:
  - Holm sobre la familia pre-registrada;
  - p frente a efectivo con EE HAC o bootstrap estacionario;
  - exposición constante tomada de la calibración, no de la media fuera de muestra (I7, FR-009b).
- [ ] T025 [P] [US2] Prueba de FR-022a en `tests/backtest/test_prior_window.py`: en calibración, la varianza del umbral del DSR excluye las líneas con `eval_end > cut`; N las incluye; las líneas `validation` nunca entran en `prior_information_ratios` (I3)

### Implementation

- [ ] T026 [US2] Implementar `Bundle.as_of(cut)` en `src/tsinsurance/data/bundle.py` (vista en memoria; `as_of_date`; `as_of_sha256` = huella de datos truncados + declaraciones + `cut`)
- [ ] T027 [US2] Reorganizar `run_experiment` en `src/tsinsurance/experiments/runner.py`:
  - con `train_end`, fase `calibration` sobre `bundle.as_of(train_end)`, aplicado antes de cualquier otro uso;
  - `quality_warnings`, `window` y `asset_start` sobre `as_of` (M8);
  - claves de prueba con `as_of_sha256` (I6);
  - eliminar la validación de esta ejecución;
  - escribir el evento `calibration` con `frozen`: parámetros, especificaciones, familia de hipótesis, `package_version` y `bundle_as_of_sha256`;
  - imprimir el comando de validación;
  - sin `train_end`, fase `full_sample`.
- [ ] T028 [US2] Exigir que `train_end` sea una fecha de decisión mensual (o aplicar un embargo del mes que la cruza) en `src/tsinsurance/experiments/spec.py` (M6)
- [ ] T029 [US2] Separar `prior_information_ratios` en dos conjuntos en `src/tsinsurance/experiments/registry.py`: "para N" (todas) y "para V" (`eval_end ≤ cut`). Excluir `kind = "validation"`. Usar ambos en `src/tsinsurance/backtest/sweep.py` (FR-022a)
- [ ] T030 [US2] Implementar en `src/tsinsurance/experiments/validate.py`:
  - `validate_experiment(path, calibration_run_id, *, registry=None, output_root=None)`;
  - las precondiciones de contracts/cli.md (sólo la bitácora declarada; `git status --porcelain` con archivos no rastreados);
  - la detección de periodos ya vistos por `(asset, oos_start, oos_end)` en toda la bitácora;
  - la evaluación de las configuraciones fijadas, con Holm, valores p robustos y la exposición de la calibración;
  - eventos `validation` con `calibration_run_id`, `frozen_sha256`, `model`, `oos_start` y `oos_end`.
- [ ] T031 [US2] Calibración y validación econométricas en `src/tsinsurance/experiments/runner.py` y `src/tsinsurance/experiments/validate.py`: walk-forward hasta `train_end` en calibración; en validación, continuación con la especificación fijada y veredicto sólo sobre pronósticos con fecha objetivo > `train_end`
- [ ] T032 [US2] Agregar `experiment validate EXP --calibration RUN_ID [--output DIR]` en `src/tsinsurance/cli.py`; exportar `validate_experiment` en `src/tsinsurance/experiments/__init__.py`
- [ ] T033 [US2] Deprecar `calibrate_validate` en `src/tsinsurance/backtest/sweep.py` (`DeprecationWarning`; resultado marcado exploratorio) (I12)
- [ ] T034 [US2] Actualizar `tests/integration/test_integracion_ejemplo.py` y `tests/integration/test_inverse_treasury_experiment.py` al flujo de dos fases

**Checkpoint**: US1 y US2 funcionan juntas; ningún resultado de calibración puede ver el periodo de validación.

---

## Phase 5: User Story 3 — Identidad del código de las señales (P2)

**Goal**: que la identidad de una prueba refleje lo que la señal hace.

**Independent Test**: SC-005. Mismo nombre y distinto código ⇒ identidades distintas; el
mismo código ⇒ la misma identidad, en procesos distintos.

### Tests (escribir primero)

- [ ] T035 [P] [US3] Pruebas en `tests/experiments/test_fingerprint.py`. Cambian la huella: el cuerpo; un valor por defecto; una constante global del módulo (`VENTANA = 120`); una función auxiliar de otro módulo del usuario llamada como `mi_lib.f`; un `functools.partial`; un arreglo de numpy cerrado por la función (hash de bytes). No la cambian: comentarios, docstrings ni espacios. Además (I2):
  - la huella es determinista entre procesos (sin direcciones `0x…`);
  - una lambda sin fuente usa `coverage = "bytecode"`;
  - lo no hasheable da `coverage = "partial"` con su lista;
  - las señales incluidas se cubren por AST.

### Implementation

- [ ] T036 [US3] Implementar `SignalFingerprint` y `fingerprint(fn)` en `src/tsinsurance/experiments/fingerprint.py`:
  - AST sin docstrings;
  - recorrido transitivo de `Name`/`Attribute` y `co_names` hacia llamables del usuario, fuera de site-packages y de la biblioteca estándar, entre módulos;
  - valores no llamables por hash canónico (arreglos y DataFrames por sus bytes);
  - respaldo por bytecode;
  - campo `coverage` en `builtin`, `source`, `bytecode`, `partial` o `none`.
- [ ] T037 [US3] Incluir `signal_fingerprint` en `trial_key` de las señales en `src/tsinsurance/experiments/runner.py`; registrar la huella en `result.json` (`ideas.<n>.fingerprint`); agregar una razón de exploratorio si `coverage ∈ {partial, none}`; conservar las líneas antiguas (FR-013)
- [ ] T038 [US3] Agregar la precondición de US2 en `src/tsinsurance/experiments/validate.py`: las huellas recalculadas deben coincidir con las de `frozen` (B5); el chequeo de no rastreados cubre los módulos de las huellas. Probarlo en `tests/experiments/test_validate_preconditions.py`

**Checkpoint**: US3 completa y conectada con la validación.

---

## Phase 6: User Story 4 — Variables macro en tiempo real (P2)

**Goal**: contrato 1.1, conector ALFRED en dos modos, vista por fecha, disponibilidad
correcta de los valores transformados y prueba de anticipación sobre el flujo completo.

**Independent Test**:
- SC-006: mutar revisiones o versiones posteriores no cambia nada;
- SC-006b: la vista coincide con ALFRED en fechas al azar y en todos los bordes.

### Tests (escribir primero)

- [ ] T039 [P] [US4] Pruebas del contrato 1.1 en `tests/data/test_contract_1_1.py`. Se aceptan: paquetes 1.0 sin cambios; `schema_version` ∈ {1.0, 1.1} (M3). Se rechazan:
  - `realtime_start` anterior al fin del periodo;
  - solapes;
  - `realtime_end ≤ realtime_start` (fin **exclusivo**);
  - `first_release` con más de una fila por `date`;
  - una serie con `vintage_mode` y filas sin `realtime_start`;
  - `vintage_mode` en `risk_free` (M4).
- [ ] T040 [P] [US4] Pruebas del conector con respuestas grabadas en `tests/data/test_alfred_recorded.py` (`tests/data/alfred_*.json`):
  - `output_type=4` y `output_type=1`;
  - paginación con `offset`;
  - conversión de `realtime_end` inclusivo a exclusivo (+1 día);
  - `9999-12-31` → vacío;
  - "." → faltante explícito (M7);
  - versiones de un solo día (B3).
- [ ] T041 [P] [US4] Pruebas de `RealTimeExogenous` en `tests/backtest/test_realtime_exogenous.py`:
  - `first_release`: disponibilidad de un valor transformado = **máximo** de los `realtime_start` de sus insumos (I5);
  - `all_vintages`: `view(d)` con transformaciones dentro de la vista (FR-019a);
  - alineación dentro de la vista: a cada `t` le corresponde el último periodo con primera publicación ≤ `t` (I4);
  - SC-006 sobre `tests/fixtures/synthetic_vintages.py`;
  - SC-006b en fechas al azar, en cada `realtime_start` y en cada último día de vigencia.
- [ ] T042 [P] [US4] Pruebas de anticipación en `tests/backtest/test_lookahead_vintages.py`:
  - `truncate_available(cut)` reabre `realtime_end > cut`;
  - el flujo econométrico probado parte de objetos truncables;
  - mutaciones detectadas: una señal que omite el rezago, una que usa `realtime_end` y una derivada calculada después de alinear (B4).

### Implementation

- [ ] T043 [US4] Contrato 1.1 en `src/tsinsurance/data/schemas.py` y `src/tsinsurance/data/bundle.py`:
  - columnas opcionales `realtime_start` y `realtime_end` (exclusivo);
  - unicidad `(date, series_id, realtime_start)`;
  - campo `vintage_mode` en `SeriesSpec`; con `vintage_mode`, `point_in_time = true` y `release_lag` ignorado con aviso;
  - aceptar `schema_version` 1.0 y 1.1;
  - desfase de publicación opcional por serie (M5).
- [ ] T044 [US4] Implementar `RealTimeExogenous` en `src/tsinsurance/backtest/pit.py`:
  - `available_series()` con la regla del máximo;
  - `view(d)`;
  - `truncate_available(cut)` con la reapertura;
  - compatible con `align_point_in_time`.
- [ ] T045 [US4] Construir `RealTimeExogenous` desde el manifiesto en `src/tsinsurance/data/bundle.py` (`Bundle.exogenous()`) y extender `Bundle.as_of` para que trunque por `realtime_start` y reabra `realtime_end`
- [ ] T046 [US4] Modos `first_release` y `all_vintages` en `src/tsinsurance/data/sources/fred.py`:
  - `realtime_start=1776-07-04`, `realtime_end=9999-12-31`;
  - `output_type` 4 y 1;
  - paginación;
  - conversión del fin a exclusivo;
  - "." como faltante;
  - la clave sólo desde `FRED_API_KEY`.
- [ ] T047 [US4] Aceptar `vintage_mode` por serie en las recetas, en `src/tsinsurance/experiments/spec.py` y en `fetch_recipe` (`src/tsinsurance/data/bundle.py`). `bundle show` debe informar el número de versiones y el inicio de la cobertura de ALFRED, con las observaciones afectadas (`src/tsinsurance/cli.py`)
- [ ] T048 [US4] Reconstruir el flujo econométrico en `src/tsinsurance/experiments/runner.py` y `src/tsinsurance/backtest/econometric.py`:
  - la función probada por `check_lookahead` recibe precios y objetos `Exogenous`/`RealTimeExogenous`;
  - hace dentro la alineación, las derivadas por vista y el walk-forward;
  - `PredictiveRegression.walk_forward` acepta una matriz por fecha construida dentro del flujo, nunca una función externa;
  - diagnósticos sobre la vista en `train_end` (calibración) y la vista final (validación) (B4, I4).
- [ ] T049 [US4] Registrar `vintage_mode` por regresor en `result.json` (`econometric.<n>.vintage_modes`) y en `trial_key` (FR-019b); soportar el bloque de sensibilidad declarado (`role = "sensitivity"` en `[[econometric]]`), que no cuenta como selección (I8), en `src/tsinsurance/experiments/spec.py` y `src/tsinsurance/backtest/verdict.py`
- [ ] T050 [P] [US4] Prueba de red opcional en `tests/network/test_alfred_live.py` (marca `network`) que, con `FRED_API_KEY`, descarga CPIAUCSL en ambos modos y graba las respuestas para T040

**Checkpoint**: modelos macro con datos de tiempo real; la prueba de anticipación detecta las fugas de tiempo real.

---

## Phase 7: User Story 5 — IVX y preblanqueo (P3)

**Goal**: inferencia robusta a regresores persistentes y menos sesgo en el EE del Sharpe.

**Independent Test**: SC-007 y SC-008 contra los valores de R guardados, más los Monte
Carlo.

### Tests (escribir primero)

- [ ] T051 [P] [US5] Pruebas de referencia IVX en `tests/reference/test_ivx_against_r.py` sobre `tests/data/reference/ivx_*.json`: datos simulados y GS10/T10Y2Y guardados; diferencia relativa ≤ 1e-6; convención `Rz = 1 − 1/(n−1)^0.95` con n efectivo (I10)
- [ ] T052 [P] [US5] Monte Carlo IVX en `tests/simulation/test_ivx_size.py` (marca `slow`): tamaño al 5 % entre 3 % y 7 % para ρ ∈ {0,9, 0,99, 1} × δ ∈ {0, −0,5, −0,95}, con n = 300; potencia y recuperación del coeficiente con β ≠ 0
- [ ] T053 [P] [US5] Prueba de referencia del preblanqueo en `tests/reference/test_prewhitening_against_r.py`: HAC sobre la influencia escalar ψ_t frente a `kernHAC(prewhite=1, kernel="Quadratic Spectral", bw=bwAndrews, adjust=FALSE, ar.method="ols")`, con diferencia ≤ 1e-6 (I9)
- [ ] T054 [P] [US5] Monte Carlo del preblanqueo en `tests/simulation/test_prewhitening_bias.py` (marca `slow`): AR(1) con φ ∈ {0, 0,1, 0,3}, n ∈ {250, 2 520} e innovaciones t de Student; reporta sesgo relativo, ECM y cobertura del IC al 95 % frente a Newey-West (SC-008)

### Implementation

- [ ] T055 [US5] Leer la fuente C++ de `ivx` 1.1.1 (CRAN) y documentar en `docs/methodology/backtesting.md` la convención de n y si aplica la corrección de muestra finita de Kostakis-Magdalinos-Stamatogiannis (2015)
- [ ] T056 [US5] Implementar `ivx_test(y, X, *, c_z=1.0, beta=0.95) -> IvxResult` en `src/tsinsurance/backtest/econometric.py` (Wald por regresor y conjunto; rezagos AR de y excluidos o documentados); agregar el campo `ivx` a `ModelValidation`; la advertencia de persistencia remite a la IVX; `result.json` → `econometric.<n>.ivx`
- [ ] T057 [US5] Implementar `hac="prewhitened"` en `sharpe_inference` en `src/tsinsurance/backtest/inference.py` (VAR(1), kernel espectral cuadrático, ancho de banda de Andrews y recoloreado; declarar si se ajustan los autovalores); `assumptions.sharpe_hac` en `result.json`. El valor por defecto sólo cambia si T054 lo respalda

---

## Phase 8: User Story 6 — Varianza del DSR estandarizada y documentada (P3)

**Goal**: combinar pruebas de distinto largo de forma comparable; adoptar la regla sólo
con evidencia y documentarla.

**Independent Test**: SC-009 con su Monte Carlo.

### Tests (escribir primero)

- [ ] T058 [P] [US6] Pruebas unitarias en `tests/backtest/test_dsr_variance_rule.py`:
  - con T iguales, `standardized` = `raw`;
  - `z_i = SR_i·√T_i` y umbral reescalado por `√T_actual`;
  - las líneas antiguas sin `n_obs` imputan T desde `eval_start`/`eval_end`, o usan T actual, y lo declaran (B6);
  - la variante estandarizada por `sharpe_se_hac`.
- [ ] T059 [US6] Monte Carlo en `tests/simulation/test_dsr_variance_rule.py` (marca `slow`; ≥ 2 000 réplicas por escenario):
  - familias de mallas SMA/TSMOM sobre precios simulados, con ventanas solapadas y T heterogéneo;
  - correlación entre pruebas ∈ {0, 0,5, 0,9, 0,97}, con y sin autocorrelación;
  - selección por "mejor de la ejecución" y por "mejor global";
  - reporta tamaño y potencia de `raw`, `standardized` y `standardized_hac`;
  - criterio: tamaño ≤ 5 % + 2,5 EE de Monte Carlo y potencia ≥ la de `raw` (SC-009, I11).

### Implementation

- [ ] T060 [US6] Implementar `variance_rule` y `trials_n_obs` en `deflated_sharpe` en `src/tsinsurance/backtest/inference.py`; pasar `n_obs`/`sharpe_se_hac` de las pruebas previas desde `src/tsinsurance/experiments/registry.py` y `src/tsinsurance/backtest/sweep.py`; `assumptions.dsr_variance_rule` en `result.json`
- [ ] T061 [US6] Fijar el valor por defecto según T059 y documentar en `docs/methodology/backtesting.md`: la regla vigente, la tabla de tamaño y potencia por escenario, la fecha, y el efecto en la conservaduría. Actualizar la nota de gobernanza en `docs/propuesta-proceso.md` (FR-023, FR-024)

---

## Phase 9: User Story 7 — Demostración con TLT, TBX y TBF (P3)

**Goal**: el flujo completo con las salvaguardas nuevas; el sistema marca solo el
periodo 2019-2025 como ya visto.

**Independent Test**: las dos fases registradas, la bitácora íntegra y razones de
exploratorio automáticas y explicadas (US7, SC-010).

- [ ] T062 [US7] Crear `experiments/tlt_treasury/recipe.toml`:
  - TLT, TBX y TBF de Yahoo;
  - T10Y2Y y DGS10 con rezago 1B;
  - CPIAUCSL en `first_release` y en `all_vintages`;
  - licencias y `redistributable` declarados.
- [ ] T063 [US7] Crear `experiments/tlt_treasury/experiment.toml`:
  - hipótesis;
  - `train_end = 2018-12-31`;
  - ideas de tendencia y momentum;
  - modelo macro principal en `first_release` y sensibilidad en `all_vintages` (I8);
  - familia de hipótesis declarada para Holm.
- [ ] T064 [US7] Ejecutar (con `FRED_API_KEY` y red), en este orden:
  1. `bundle fetch`;
  2. `experiment run`;
  3. confirmar en git;
  4. `experiment validate`;
  5. `experiment verify --results`.

  Verificar que aparece "periodo posterior a train_end ya visto en inverse-treasury-etfs" para TBX y TBF, y medir el tiempo de punta a punta (< 5 min, SC-010)
- [ ] T065 [US7] Escribir `experiments/tlt_treasury/README.md` con:
  - las dos fases;
  - la comparación entre los modos de tiempo real;
  - las razones de exploratorio;
  - las limitaciones, empezando por que es una demostración y no un resultado confirmatorio.

---

## Phase 10: Polish & Cross-Cutting

- [ ] T066 [P] Crear `docs/methodology/realtime.md`:
  - primera publicación frente a todas las versiones (diagonal frente a vista);
  - fin exclusivo y su conversión desde ALFRED;
  - cobertura de ALFRED;
  - regla del máximo para los transformados;
  - advertencia de Koenig-Dolmas-Piger (2003);
  - referencias a Croushore-Stark (2001).
- [ ] T067 [P] Actualizar `docs/integracion/manual-de-uso.md`, `docs/integracion/prompt-agente.md`, `AGENTS.md` y `.claude/skills/tsinsurance-experiment/SKILL.md` con:
  - las dos fases;
  - `validate`, `verify --base/--results` y `unlock`;
  - `result.json` 1.2;
  - el contrato 1.1 y `vintage_mode`;
  - el código de salida 2.
- [ ] T068 [P] Actualizar `examples/integracion/` y su prueba al flujo de dos fases; reemplazar `head -n -3` en `specs/004-integridad-tiempo-real/quickstart.md` (M9, hecho en el diseño; verificar)
- [ ] T069 [P] Declarar en `docs/politica-datos-y-publicacion.md` y en `docs/propuesta-proceso.md`:
  - los límites de la separación lógica (M10);
  - el riesgo residual de la bitácora: resultados no confirmados y ramas abandonadas (I14).
- [ ] T070 Marcar como hechas las tareas absorbidas en `specs/001-core-econometric-engine/tasks.md` (T083), `specs/002-quant-backtesting/tasks.md` (T045-T047) y `specs/003-experiment-workflow/tasks.md` (T018-T021)
- [ ] T071 Ejecutar `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run mypy` y `uv run pytest` (incluido `-m slow` para los Monte Carlo de la spec), y el quickstart completo
- [ ] T072 Revisión de implementación con el subagente `econometrics-reviewer` antes del PR (CLAUDE.md), y corrección de sus hallazgos bloqueantes

---

## Dependencies & Execution Order

```text
Setup (T001-T004) ─▶ Foundational (T005-T008)
                        │
                        ├─▶ US1 (T009-T018)  ─┐
                        │                     ├─▶ US2 (T019-T034) ─▶ US3 (T035-T038)* ─┐
                        ├─▶ US4 (T039-T050) ──┘  (T045 extiende as_of de T026)          ├─▶ US7 (T062-T065) ─▶ Polish
                        ├─▶ US5 (T051-T057) ───────────────────────────────────────────┤
                        └─▶ US6 (T058-T061) ───────────────────────────────────────────┘
```

\* T038 (precondición de huellas) depende de T030 (validate) y de T036 (fingerprint).

- **US1** sólo depende de Foundational.
- **US2** depende de US1, porque el bloqueo cubre toda la ejecución (T015).
- **US3**: T035-T037 pueden hacerse en paralelo con US2; T038 cierra la conexión.
- **US4** puede avanzar en paralelo con US1 y US2. T045 y T048 tocan `bundle.py` y
  `runner.py` después de T026 y T027.
- **US5** y **US6** son independientes del resto. T061 depende del resultado de T059.
- **US7** necesita todas las anteriores.

## Parallel Opportunities

- Setup: T002, T003 y T004 en paralelo.
- US1: pruebas T009, T010 y T011 en paralelo.
- US2: pruebas T019 a T025 en paralelo, en archivos distintos.
- US4: pruebas T039 a T042 en paralelo; T050 cuando haya clave.
- US5: T051 a T054 en paralelo; luego T056 y T057 en paralelo, en módulos distintos.
- US5, US6 y US4 pueden asignarse a la vez a personas o agentes distintos, porque tocan
  `econometric.py`/`inference.py` y `pit.py`/`fred.py` respectivamente. La excepción es
  `runner.py`, que se coordina en serie: T006, T008, T015, T027, T031, T037, T048 y T049.

## Implementation Strategy

1. **MVP = Setup + Foundational + US1**: la bitácora deja de poder recortarse sin rastro.
   Se puede integrar sola.
2. **+ US2 y US3**: el procedimiento queda íntegro (fuera de muestra intocable y
   huellas). Es el corte de la versión **0.2.0**.
3. **+ US4**: modelos macro de tiempo real.
4. **+ US5 y US6**: inferencia afinada, con las reglas por defecto decididas por Monte
   Carlo.
5. **US7 + Polish**: demostración, documentación y revisión econométrica de la
   implementación antes del PR.

**Totales**: 72 tareas.

| Fase | Tareas |
|------|--------|
| Setup | 4 |
| Foundational | 4 |
| US1 | 10 |
| US2 | 16 |
| US3 | 4 |
| US4 | 12 |
| US5 | 7 |
| US6 | 4 |
| US7 | 4 |
| Polish | 7 |
