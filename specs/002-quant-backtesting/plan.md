# Implementation Plan: Backtesting responsable de estrategias cuantitativas y modelos econométricos

**Branch**: `002-quant-backtesting` | **Date**: 2026-11-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-quant-backtesting/spec.md`

## Summary

Subpaquete `tsinsurance.backtest` que convierte ideas de inversión en experimentos
estadísticos verificables: señales (tendencia, volatilidad, econométricas con variables
macro rezagadas por publicación) → pesos objetivo decididos con información en `t` →
motor vectorizado con retraso de ejecución, costos, deriva y tasa libre de riesgo
explícitos (validado contra **bt**) → métricas con inferencia (Sharpe con error
estándar robusto, bootstrap estacionario, PSR/DSR, SPA de Hansen) → para modelos
econométricos, validación estadística del pronóstico (Clark-West, R² fuera de muestra,
Diebold-Mariano, Pesaran-Timmermann, diagnósticos de residuos y estacionariedad de
regresores) y un veredicto doble estadístico/económico. Detalle en
[research.md](./research.md).

## Technical Context

**Language/Version**: Python >= 3.11

**Primary Dependencies**: núcleo existente (numpy, pandas, scipy, statsmodels, arch,
pandera, pyarrow). Nuevo extra opcional `[backtest]` = `bt>=1.1` (motor de referencia).
Remuestreo y SPA con `arch.bootstrap`.

**Storage**: instantáneas Parquet + JSON en `examples/data/` (ETFs y macro).

**Testing**: pytest + hypothesis; `slow` para Monte Carlo (SC-003, SC-004) y rendimiento
(SC-006); `network` para descargas. La prueba contra bt se omite si el extra no está
instalado (CI instala `--all-extras`).

**Target Platform**: Linux/macOS/Windows, CPython 3.11-3.13.

**Project Type**: library.

**Performance Goals**: barrido 8 activos × 20 configuraciones × 10 años diarios < 60 s
(SC-006); backtest individual diario de 20 años < 0,5 s.

**Constraints**: sin red en CI; determinismo con semilla; `mypy --strict`.

**Scale/Scope**: universos de decenas de activos; barridos de cientos de configuraciones.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Cómo se cumple | Estado |
|-----------|----------------|--------|
| I. Rigor econométrico | Regresores con diagnóstico de estacionariedad (spec 001) y advertencia de persistencia; residuos con LB/ARCH-LM/JB | PASS |
| II. Validación sin fuga | Walk-forward con pares observables en `t`; rezagos de publicación; prueba de anticipación; Clark-West/DM vs media histórica | PASS |
| III. Incertidumbre | Sharpe con SE robusto e IC bootstrap; semillas explícitas en bootstrap y SPA | PASS |
| IV. Agnóstico de jurisdicción | Sin supuestos de mercado; tasa libre de riesgo y costos como parámetros | PASS |
| IV-bis. Datos con contrato | ETFs y macro por conectores existentes y `Snapshot` | PASS |
| V. Biblioteca primero | Subpaquete tipado; reutiliza `arch.bootstrap`, statsmodels OLS/HAC; motor propio validado contra bt | PASS (ver Complexity Tracking) |
| VI. Pruebas primero | DGP conocidos (SC-003/004), referencia publicada (DSR), equivalencia con bt | PASS |
| VII. Simplicidad | Señales clásicas, OLS; sin ML | PASS |
| VIII. Backtesting responsable | Ejecución explícita, benchmark, pruebas múltiples (DSR/SPA), calibración/validación, veredicto doble | PASS |

**Re-check post-diseño (Fase 1)**: sin violaciones.

## Project Structure

### Documentation (this feature)

```text
specs/002-quant-backtesting/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/public-api.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/tsinsurance/
├── backtest/
│   ├── __init__.py
│   ├── config.py          # ExecutionConfig, periods_per_year
│   ├── engine.py          # run_backtest (motor vectorizado), BacktestResult
│   ├── reference.py       # run_with_bt (motor de referencia, extra [backtest])
│   ├── metrics.py         # métricas de desempeño
│   ├── inference.py       # sharpe_se, PSR, DSR, bootstrap, SPA, PT, Clark-West, R²_OS
│   ├── signals.py         # sma_crossover, tsmom, vol_target, garch_vol_forecast, ewma_vol
│   ├── pit.py             # Exogenous, align_point_in_time
│   ├── econometric.py     # PredictiveRegression walk-forward + ModelValidation
│   ├── lookahead.py       # check_lookahead
│   ├── sweep.py           # Strategy, TrialRegistry, sweep, calibrate_validate
│   └── verdict.py         # Verdict (cuadrantes)
└── validation/
    └── comparison.py      # diebold_mariano (compartido con spec 001)

tests/backtest/            # unit + reference + simulation por módulo
examples/
├── backtest_01_tendencia_volatilidad_etfs.py
├── backtest_02_macro_tlt.py
└── data/{yahoo_etfs,fred_daily,fred_monthly}/
docs/methodology/backtesting.md
```

**Structure Decision**: subpaquete desacoplado (`backtest` sólo importa `data`,
`diagnostics`, `validation` y `results`), extraíble a un paquete propio si se decide.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Motor de backtesting propio | Control de convención de ejecución, deriva, rf y costos; velocidad en barridos/bootstrap | bt como único motor: lento en barridos y supuestos implícitos; se usa como referencia (SC-001) |
| PSR/DSR, Pesaran-Timmermann, Clark-West propios | No existen en librerías mantenidas | Se validan contra ejemplo publicado y equivalencias analíticas (SC-005) |
