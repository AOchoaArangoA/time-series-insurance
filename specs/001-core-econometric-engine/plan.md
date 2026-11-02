# Implementation Plan: Motor econométrico núcleo para inversiones de una aseguradora

**Branch**: `001-core-econometric-engine` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-core-econometric-engine/spec.md`

## Summary

Biblioteca Python `tsinsurance` que, a partir de datos locales o públicos validados
contra un contrato de datos publicado, diagnostica estacionariedad, ajusta modelos de
media (ARIMA/SARIMA) y volatilidad (GARCH y variantes), produce pronósticos con
incertidumbre evaluados fuera de muestra sin fuga de información, y calcula VaR/ES de
activos y portafolios con backtesting formal. Todo resultado es un objeto inmutable con
`summary()` y exportable a un reporte reproducible. El paquete es agnóstico de país y
moneda (perfiles de jurisdicción) y consume nodos de tasas con un esquema compatible con
el futuro paquete de curvas. Detalle de decisiones en [research.md](./research.md).

## Technical Context

**Language/Version**: Python >= 3.11

**Primary Dependencies**: numpy, pandas, scipy, statsmodels (>=0.14), arch (>=7),
pandera (contrato de datos), httpx (FRED). Extras: `[yahoo]` yfinance, `[excel]` openpyxl,
`[parquet]` pyarrow, `[viz]` matplotlib.

**Storage**: Archivos: snapshots Parquet + metadatos JSON en `examples/data/`; sin base de datos.

**Testing**: pytest, pytest-cov (>= 90 %), hypothesis; marcas `slow` (Monte Carlo) y
`network` (descargas reales, excluidas de CI por defecto).

**Target Platform**: Linux/macOS/Windows, CPython 3.11-3.13; uso en scripts y notebooks.

**Project Type**: library (con CLI mínimo opcional para plantillas y validación de insumos).

**Performance Goals**: Diagnóstico completo de una serie de 5.000 observaciones < 2 s;
selección ARIMA en malla por defecto < 30 s; backtesting de VaR de 2.500 días < 5 s.

**Constraints**: Sin red en pruebas de CI; resultados deterministas con semilla; tipado
`mypy --strict` en API pública.

**Scale/Scope**: Series diarias/semanales/mensuales de hasta ~20 años; portafolios de
hasta ~200 activos en v1.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Cómo se cumple | Estado |
|-----------|----------------|--------|
| I. Rigor econométrico | `diagnostics.stationarity` con ADF/PP + KPSS + ZA y regla confirmatoria; `diagnostics.residuals` obligatorio tras cada ajuste; bandera `is_adequate` | PASS |
| II. Validación sin fuga | `validation.rolling_origin` sólo entrega datos `<= origen`; prueba con modelo espía; DM vs benchmarks; Kupiec/Christoffersen/AS | PASS |
| III. Incertidumbre | `Forecast` siempre con intervalos; SE robustos; `numpy.random.Generator` con semilla en toda simulación | PASS |
| IV. Pertinencia actuarial, agnóstica | VaR/ES configurables vía `JurisdictionProfile` (perfil `generic` 99,5 %/1 año); nodos de tasas vía `RateNodesSchema` (interfaz con paquete hermano de curvas) | PASS |
| IV-bis. Datos con contrato | `pandera` + plantillas + `Snapshot` con hash; CI sin red | PASS |
| V. Biblioteca primero, tipada | layout `src/`, dataclasses congeladas, docstrings NumPy con `References`, reuso de statsmodels/arch | PASS |
| VI. Pruebas primero | Cada tarea de implementación precedida por prueba con DGP conocido y/o valor de referencia | PASS |
| VII. Simplicidad | Sin ML en v1; malla acotada; backtesting propio sólo donde no hay librería | PASS (ver Complexity Tracking) |

**Re-check post-diseño (Fase 1)**: sin violaciones. La constitución se enmendó a v1.1.0
(curvas en paquete hermano, agnosticismo de jurisdicción y principio IV-bis).

## Project Structure

### Documentation (this feature)

```text
specs/001-core-econometric-engine/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── public-api.md
│   └── input-schemas.md
├── checklists/requirements.md
└── tasks.md            # /speckit-tasks
```

### Source Code (repository root)

```text
src/tsinsurance/
├── __init__.py
├── _types.py               # alias de tipos, Frequency, etc.
├── config.py               # JurisdictionProfile, carga TOML, perfil "generic"
├── results.py              # TestResult y base de resultados con summary()/to_dict()
├── data/
│   ├── schemas.py          # MarketSeriesSchema, PortfolioSchema, RateNodesSchema
│   ├── templates.py        # generación de plantillas CSV/Excel, export JSON Schema
│   ├── prepare.py          # validación de índice, faltantes, retornos/diferencias
│   ├── snapshot.py         # Snapshot (Parquet + metadatos + hash)
│   └── sources/
│       ├── base.py         # Protocolo DataSource + registro por entry points
│       ├── files.py        # CSVSource, ExcelSource
│       ├── fred.py         # FredSource
│       └── yahoo.py        # YahooSource (extra)
├── diagnostics/
│   ├── stationarity.py     # adf, pp, kpss, zivot_andrews, integration_order
│   ├── descriptive.py      # momentos, ACF/PACF, JB, ARCH-LM
│   └── residuals.py        # ResidualDiagnostics
├── models/
│   ├── arima.py            # fit_arima, select_arima
│   └── volatility.py       # fit_garch, select_garch
├── forecast/
│   └── forecast.py         # Forecast (media + intervalos)
├── validation/
│   ├── rolling.py          # rolling_origin
│   ├── metrics.py          # rmse, mae, mase
│   └── comparison.py       # diebold_mariano, benchmarks
├── risk/
│   ├── measures.py         # var, expected_shortfall (hist/param/garch), portafolio
│   ├── horizon.py          # escalado sqrt-time / simulación
│   └── backtest.py         # kupiec, christoffersen, traffic_light, acerbi_szekely
├── reporting/
│   └── report.py           # AnalysisReport -> JSON/Markdown
└── cli.py                  # `tsinsurance template|validate`

tests/
├── unit/                   # por módulo
├── reference/              # valores publicados / R / statsmodels
├── simulation/             # DGP conocidos (marca slow)
├── integration/            # flujo de punta a punta con snapshots
└── conftest.py             # generadores con semilla

examples/
├── data/                   # snapshots versionados (Parquet + JSON)
├── 01_diagnostico_tasas_fred.py
├── 02_garch_indice_accionario.py
└── 03_var_portafolio_backtesting.py

docs/methodology/           # una nota por método con referencias
```

**Structure Decision**: proyecto único tipo biblioteca con layout `src/`, subpaquetes por
etapa del ciclo econométrico (datos → diagnóstico → modelos → pronóstico → validación →
riesgo → reporte). Ejercicios con datos reales en `examples/` usando snapshots.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Implementación propia de backtesting (Kupiec, Christoffersen, Acerbi-Szekely, DM) | No hay librería Python consolidada y mantenida que las cubra | Dependencias sueltas sin mantenimiento ni tipos; se valida contra ejemplos publicados |
| Dependencia `pandera` | Contrato de datos con reporte de errores fila/columna (FR-019b, SC-008) | Validación manual: frágil y sin export de esquema |
