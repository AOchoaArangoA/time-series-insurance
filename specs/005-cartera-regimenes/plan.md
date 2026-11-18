# Implementation Plan: Ideas de cartera y regímenes del ciclo

**Branch**: `ccr-d4f6f6a0-bg0992` (carpeta de la spec: `005-cartera-regimenes`) | **Date**: 2026-11-17 | **Spec**: [spec.md](spec.md)

## Summary

Lleva dos análisis del experimento sectorial al flujo declarativo y registrado:

1. **Ideas de cartera** (`[[portfolios]]`): una señal asigna pesos entre los activos de
   un universo. La prueba se registra con la identidad del universo, de modo que la
   selección, el Sharpe deflactado, la SPA y la memoria de la bitácora funcionan igual que
   para un activo. El benchmark es la cartera igual ponderada del mismo universo.
2. **Regímenes del ciclo** (`[[regimes]]`): estados mensuales punto en el tiempo
   (umbral, diferencia de tasas o tendencia). Para cada activo, exceso del mes siguiente
   por estado, con HAC y Holm.

Ambos siguen las dos fases de la spec 004.

## Technical Context

- **Language/Version**: Python ≥ 3.11
- **Primary Dependencies**: existentes (pandas, numpy, statsmodels para OLS-HAC, arch
  para SPA)
- **Storage**: bitácora JSONL, `result.json`
- **Testing**: pytest; Monte Carlo con la marca `slow`
- **Project Type**: biblioteca + CLI
- **Performance Goals**: demostración sectorial (2 fases) < 3 min
- **Constraints**: `result.json` aditivo (1.2); bitácora compatible
- **Scale/Scope**: universos de hasta ~50 activos; ≤ 20 estados

## Constitution Check

| Principio | Cumplimiento |
|---|---|
| I. Rigor | Benchmark del mismo universo; regresión HAC por persistencia de estados |
| II. Sin fuga | Calibración sobre `as_of`; estados con `align_point_in_time`; anticipación sobre el universo |
| III. Incertidumbre | DSR, SPA y Holm; t HAC; meses por estado reportados |
| VI. Pruebas primero | Monte Carlo de tamaño y potencia (SC-001, 002 y 004); mutación de datos futuros (SC-005) |
| VII. Simplicidad | Reutiliza `Trial`/`select`/validación; dos bloques nuevos, sin motor nuevo |
| VIII. Backtesting responsable | Memoria por universo; periodo visto por universo y constituyentes; Holm en la validación |

**Gate**: pasa.

## Project Structure

```text
src/tsinsurance/
├── experiments/
│   ├── portfolio_signals.py   # NUEVO: registro + cross_sectional_momentum, inverse_volatility
│   ├── regimes.py             # NUEVO: RegimeSpec → estados PIT; análisis HAC + Holm
│   ├── spec.py                # PortfolioSpec, RegimeSpec en ExperimentSpec
│   ├── runner.py              # evaluación de carteras y regímenes en calibración; frozen
│   ├── validate.py            # validación de carteras y regímenes; periodo visto por universo
│   └── registry.py            # kind "portfolio" en las pruebas previas
├── data/bundle.py             # Bundle.variable(id): exógena o tasa libre de riesgo como Exogenous
└── cli.py                     # signals lista también las de cartera

tests/experiments/test_portfolios.py, test_regimes.py
tests/simulation/test_portfolio_regime_size.py (slow)
experiments/sectores_gics/rotacion_regimenes.toml (demostración)
```

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Holm sobre 33+ hipótesis de régimen deja poca potencia | Se reporta la potencia del diseño (SC-004) y los meses por estado |
| Los estados raros (curva invertida ≈ 14 % de los meses) dan pocas observaciones | `min_months` y "no concluyente" |
| La rotación con universos que empiezan en distintas fechas | Ranking sólo entre activos con historia; benchmark con los mismos disponibles |
