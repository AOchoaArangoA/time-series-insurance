# time-series-insurance (`tsinsurance`)

[![CI](https://github.com/AOchoaArangoA/time-series-insurance/actions/workflows/ci.yml/badge.svg)](https://github.com/AOchoaArangoA/time-series-insurance/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Paquete Python de series de tiempo para **asistir decisiones cuantitativas de
inversión** —con foco en el portafolio de una aseguradora— con metodología econométrica
y estadística robusta: contrato de datos, estacionariedad, **backtesting responsable** de
estrategias cuantitativas y de modelos econométricos con variables macro, y
**experimentos registrados** que humanos y agentes de IA pueden ejecutar y auditar.

## Instalación

```bash
pip install "tsinsurance[yahoo,excel,backtest] @ git+https://github.com/AOchoaArangoA/time-series-insurance"
# o, para desarrollar:
git clone https://github.com/AOchoaArangoA/time-series-insurance && cd time-series-insurance
uv sync --all-extras
```

Requiere Python ≥ 3.11. La clave de FRED (`FRED_API_KEY`) sólo se necesita para
descargar datos de FRED; se lee del entorno y nunca se versiona.

## Mapa del proceso

```text
 1. Hipótesis ─▶ 2. Receta de datos ─▶ 3. Paquete de insumos ─▶ 4. experiment.toml ─▶ 5. Ejecución
   (humano o      (Yahoo, FRED, CSV,     (formato base,           (ideas, modelos,       │ anticipación
    agente)        proveedor interno)     independiente de        supuestos,             │ punto en el tiempo
                                          la fuente)              validación)            │ pruebas múltiples
                                                                                         ▼ validación única
 8. Decisión ◀── 7. report.md / result.json ◀── 6. Bitácora permanente (registry.jsonl, encadenada por hash)
```

| Necesito… | Dónde |
|-----------|-------|
| Entender el proceso completo y el flujo de la información | [`docs/propuesta-proceso.md`](docs/propuesta-proceso.md) |
| Usar el paquete desde **otro agente o herramienta** | [`AGENTS.md`](AGENTS.md) · habilidad [`.claude/skills/tsinsurance-experiment`](.claude/skills/tsinsurance-experiment/SKILL.md) |
| Ver un experimento real registrado (TBT, TBX, TBF) | [`experiments/inverse_treasury/`](experiments/inverse_treasury/README.md) |
| Resultados y validaciones realizadas hasta hoy | [`docs/resumen-procesos-y-resultados.md`](docs/resumen-procesos-y-resultados.md) |
| Metodología (pruebas, supuestos, referencias) | [`docs/methodology/`](docs/methodology/) |
| Principios no negociables | [`.specify/memory/constitution.md`](.specify/memory/constitution.md) |
| Especificaciones, planes y tareas | [`specs/`](specs/) · hoja de ruta [`docs/roadmap.md`](docs/roadmap.md) |
| Datos de terceros y publicación | [`docs/politica-datos-y-publicacion.md`](docs/politica-datos-y-publicacion.md) |

## Uso rápido: un experimento en 4 comandos

```bash
uv run tsinsurance bundle template mi_exp/data            # 1. paquete de insumos para llenar (o:)
uv run tsinsurance bundle fetch recipe.toml mi_exp/data    #    descargarlo con una receta
uv run tsinsurance bundle validate mi_exp/data             # 2. contrato, manifiesto y huella
uv run tsinsurance experiment run mi_exp/experiment.toml   # 3. ejecutar y registrar
uv run tsinsurance experiment verify experiments/registry.jsonl   # 4. integridad de la bitácora
```

Ver el formato de `experiment.toml` y de `result.json` en [`AGENTS.md`](AGENTS.md).

## Qué incluye

| Módulo | Capacidades |
|--------|-------------|
| `tsinsurance.data` | contrato de insumos v1.0 (plantillas, JSON Schema, validación fila/columna/regla), conectores CSV/Excel/FRED/Yahoo, instantáneas con huella, **paquete de insumos** independiente de la fuente |
| `tsinsurance.diagnostics` | ADF, Phillips-Perron, KPSS, Zivot-Andrews con regla de decisión explícita; descriptivos, Ljung-Box, Jarque-Bera, ARCH-LM (verificados contra R) |
| `tsinsurance.backtest` | motor con ejecución, costos y tasa libre de riesgo explícitos (validado contra `bt`); señales de tendencia y volatilidad; datos punto-en-el-tiempo; prueba de anticipación; Sharpe con EE HAC y bootstrap, PSR, Sharpe deflactado, SPA de Hansen; regresión predictiva walk-forward con **validación doble** (Clark-West, Pesaran-Timmermann, diagnósticos / valor económico) |
| `tsinsurance.experiments` | `experiment.toml` declarativo, registro de señales, bitácora con pre-registro y validación registrada, ajuste por pruebas múltiples acumulado entre experimentos |

### Desde Python

```python
from tsinsurance.data.bundle import Bundle
from tsinsurance.backtest import ExecutionConfig, check_lookahead, run_backtest, sma_crossover
from tsinsurance.experiments import run_experiment

bundle = Bundle.load("mi_exp/data")
precios, rf = bundle.assets(), bundle.risk_free()
idea = lambda p: sma_crossover(p, 50, 200, normalize=False)
check_lookahead(idea, precios[["TLT"]].dropna()).raise_if_biased()
print(run_backtest(precios["TLT"].dropna(), idea(precios[["TLT"]].dropna()),
                   ExecutionConfig(lag=1, cost_bps=5), risk_free=rf).summary())

print(run_experiment("mi_exp/experiment.toml").summary())
```

## Ejemplos

```bash
uv run python examples/01_diagnostico_tasas_fred.py               # estacionariedad de GS10 (datos incluidos)
uv run python examples/fetch_data.py                              # descarga los datos de terceros (FRED_API_KEY)
uv run python examples/backtest_01_tendencia_volatilidad_etfs.py  # tendencia/volatilidad en 8 ETFs
uv run python examples/backtest_02_macro_tlt.py                   # modelo macro para TLT
```

Los precios de Yahoo Finance y la serie BAA10Y (Moody's) **no se redistribuyen**: se
regeneran localmente con su receta o script, y cada resultado registra la huella exacta
de los datos usados.

## Cómo se desarrolla

*Spec-Driven Development* con [GitHub Spec Kit](https://github.com/github/spec-kit) y
Claude Code (`/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
`/speckit-implement`), pruebas primero y revisión independiente con el subagente
[`econometrics-reviewer`](.claude/agents/econometrics-reviewer.md) antes de integrar.
Guía para agentes que desarrollan: [`CLAUDE.md`](CLAUDE.md).

```bash
uv sync --all-extras
uv run pytest                 # unitarias, referencia, Monte Carlo, integración (sin red)
uv run pytest -m network      # descargas reales (requiere FRED_API_KEY)
uv run ruff check src tests && uv run mypy
```

## Licencia

Código bajo [MIT](LICENSE). Los datos de terceros se rigen por los términos de sus
proveedores.
