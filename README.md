# time-series-insurance (`tsinsurance`)

Paquete Python de series de tiempo para asistir decisiones cuantitativas de inversión
—con foco en el portafolio de una aseguradora—, con metodología econométrica y
estadística robusta: estacionariedad, modelos de media y volatilidad, pronóstico con
incertidumbre, validación fuera de muestra, **backtesting responsable de estrategias
cuantitativas y de modelos econométricos**, VaR/ES y ALM.

## Metodología de desarrollo: Spec-Driven Development con agentes de IA

El proyecto usa [GitHub Spec Kit](https://github.com/github/spec-kit) con Claude Code.
Spec Kit separa el **qué** (especificación) del **cómo** (plan) y hace que el agente
implemente por tareas verificables.

| Artefacto | Ubicación |
|-----------|-----------|
| Constitución (principios no negociables) | `.specify/memory/constitution.md` |
| Especificaciones por funcionalidad | `specs/NNN-*/spec.md` |
| Hoja de ruta | `docs/roadmap.md` |
| Comandos de Spec Kit para Claude Code | `.claude/skills/speckit-*` |
| Subagente revisor econométrico | `.claude/agents/econometrics-reviewer.md` |
| Guía para agentes | `CLAUDE.md` |

Flujo por funcionalidad, dentro de Claude Code:

```text
/speckit-specify   describe la funcionalidad
/speckit-clarify   resuelve ambigüedades
/speckit-plan      plan técnico (stack, contratos, modelo de datos)
/speckit-tasks     lista de tareas ordenadas por dependencias
/speckit-analyze   consistencia spec ↔ plan ↔ tareas
/speckit-implement implementación con TDD
```

## Uso rápido (v0.1 — preparación y diagnóstico)

```bash
uv sync --all-extras          # incluye bt (motor de referencia) y yfinance
uv run tsinsurance template market --format xlsx -o mis_series.xlsx   # plantilla de insumos
uv run tsinsurance validate market mis_series.csv                     # valida contra el contrato
uv run tsinsurance schema market --format json-schema                 # contrato publicado
uv run python examples/01_diagnostico_tasas_fred.py                   # ejercicio con datos reales
```

```python
from tsinsurance.data import Snapshot, prepare, to_wide
from tsinsurance.data.sources import get_source
from tsinsurance.diagnostics import describe, stationarity

snap = get_source("fred").fetch(["GS10"], "1990-01-01", "2025-12-31")  # requiere FRED_API_KEY
snap.save("data/gs10")                       # instantánea replicable (Parquet + metadatos + hash)
serie = prepare(to_wide(snap.data)["GS10"], freq="M").data
print(stationarity(serie).summary())         # ADF + PP + KPSS + Zivot-Andrews, regla confirmatoria
```

## Backtesting responsable (spec 002)

```bash
uv run python examples/backtest_01_tendencia_volatilidad_etfs.py   # tendencia/volatilidad, 8 ETFs
uv run python examples/backtest_02_macro_tlt.py                    # modelo macro para TLT
```

```python
from tsinsurance.backtest import (
    ExecutionConfig, run_backtest, sma_crossover, check_lookahead, sweep,
    Exogenous, align_point_in_time, PredictiveRegression, backtest_econometric,
)

# 1) Una idea de tendencia, con supuestos explícitos y prueba de anticipación
idea = lambda p: sma_crossover(p, 50, 200, normalize=False)
check_lookahead(idea, precios).raise_if_biased()
res = run_backtest(precios, idea(precios), ExecutionConfig(lag=1, cost_bps=5), risk_free=rf)
print(res.summary())

# 2) Barrido con ajuste por pruebas múltiples (Sharpe deflactado + SPA de Hansen)
print(sweep(precios, lambda p, fast, slow: sma_crossover(p, fast, slow, normalize=False),
            {"fast": [20, 50], "slow": [150, 200]}, risk_free=rf).summary())

# 3) Modelo econométrico con variables macro: validación estadística + económica
x = align_point_in_time([Exogenous("inflacion", cpi, "M", release_lag="20D", transform="yoy")],
                        fechas_decision)
print(backtest_econometric(tlt, y_exceso, x, PredictiveRegression(min_train=60)).summary())
```

Cada resultado reporta supuestos, benchmark, incertidumbre (EE HAC, bootstrap) y, para
modelos econométricos, un **veredicto doble** (evidencia estadística / valor económico).
Metodología: `docs/methodology/backtesting.md`.

Las claves de API (p. ej. `FRED_API_KEY`) se leen de variables de entorno y nunca se versionan.

## Resumen de procesos y resultados

Ver [`docs/resumen-procesos-y-resultados.md`](docs/resumen-procesos-y-resultados.md).

## Desarrollo

```bash
uv sync --all-extras
uv run pytest                 # rápido + simulaciones; sin red
uv run pytest -m network      # descargas reales (requiere FRED_API_KEY)
uv run ruff check src tests && uv run mypy
```

Requiere Python >= 3.11 y [uv](https://docs.astral.sh/uv/).
