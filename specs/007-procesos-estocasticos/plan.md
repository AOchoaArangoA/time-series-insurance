# Implementation Plan: Procesos estocásticos, simulación y sensibilidades (MVP)

**Branch**: `ccr-d4f6f6a0-bg0992` (carpeta: `007-procesos-estocasticos`) | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

## Summary

Hay cuatro capas desacopladas, siguiendo la base metodológica del usuario:

- **`stochastics/`**:
  - Vasicek y CIR bajo ℙ (MV exacta, simulación exacta);
  - regímenes de Markov (`statsmodels`);
  - valoración afín ℚ (Vasicek, CIR, Hull-White) y calibración a nodos;
  - interfaz `Curve` con `NodeCurve` mínima.
- **`simulation/`**:
  - escenarios histórico, histórico filtrado, Monte Carlo de factores y Monte Carlo de la
    tasa corta;
  - PCA y Diebold-Li con λ fija;
  - antitéticas y variable de control.
- **`sensitivities/`**:
  - bonos de flujos fijos;
  - PV, DV01, KRD, duración y convexidad;
  - Δ y Γ por factor;
  - Δ/ΔΓ frente a la revaluación completa;
  - atribución de P&L.
- **`portfolio_risk/`**:
  - VaR y ES con IC;
  - backtesting (Kupiec, Christoffersen, Z2);
  - estrés (factores y régimen);
  - cobertura e inmunización.

La demostración usa el Tesoro de EE. UU. (Yahoo, 4 nodos).

## Technical Context

- **Dependencias**: existentes (`numpy`, `scipy`, `statsmodels`, `arch`, `pandas`). No se
  agregan dependencias nuevas.
- **Testing**: pytest con DGP conocidos; Monte Carlo con la marca `slow`; referencias
  analíticas (fórmulas cerradas) y de R cuando aplique (`sde`/`YieldCurve` no son
  necesarios).
- **Performance**:
  - 10 000 trayectorias × 2 520 pasos de Vasicek en < 2 s (vectorizado);
  - demostración en < 5 min.

## Constitution Check

| Principio | Cumplimiento |
|---|---|
| I. Rigor | Transición exacta (sin sesgo de Euler); MV exacta; Feller; ℙ/ℚ separados y declarados |
| II. Sin fuga | Probabilidades filtradas (no suavizadas) para decidir; FHS y backtesting de VaR punto en el tiempo |
| III. Incertidumbre | Errores de parámetros; IC de VaR y ES; error de Monte Carlo reportado |
| IV. Agnóstico de jurisdicción | Curvas por interfaz; nodos de cualquier mercado |
| VI. Pruebas primero | Momentos teóricos, fórmulas cerradas, cobertura de IC, tamaño y potencia del backtesting |
| VII. Simplicidad | Diferencias finitas en lugar de diferenciación automática; reutiliza `statsmodels` y `arch` |
| VIII. Backtesting responsable | FR-017: las asignaciones pasan por el flujo de experimentos |

**Gate**: pasa.

## Project Structure

```text
src/tsinsurance/stochastics/
├── __init__.py
├── short_rate.py     # Vasicek, CIR: fit (P), simulate (exact), transition moments
├── regimes.py        # MarkovShortRate: fit, filtered/smoothed, simulate
├── affine.py         # zero-coupon closed forms (Vasicek, CIR, Hull-White) + calibrate_q
└── curves.py         # Curve Protocol, NodeCurve (minimal), conversiones de tasa
src/tsinsurance/simulation/
├── __init__.py
├── factors.py        # PCA de cambios, Diebold-Li λ fija
├── scenarios.py      # historical, filtered_historical, factor_mc, short_rate_mc → Scenarios
└── variance.py       # antithetic, control_variate, reduction factor
src/tsinsurance/sensitivities/
├── __init__.py
├── instruments.py    # FixedBond, Portfolio (flujos)
├── measures.py       # pv, dv01, krd, duration, convexity, factor deltas/gammas
└── approx.py         # delta / delta_gamma vs full revaluation, pnl_attribution
src/tsinsurance/portfolio_risk/
├── __init__.py
├── var_es.py         # var/es + bootstrap CI
├── backtest.py       # kupiec, christoffersen, acerbi_szekely_z2, rolling forecasts
├── stress.py         # parallel/steepener/flattener/curvature/regime-conditional
└── hedge.py          # immunize (constrained least squares)
tests/stochastics, tests/simulation_engine, tests/sensitivities, tests/portfolio_risk
experiments/tesoro_riesgo/ (receta, script de demostración, README)
docs/methodology/procesos-estocasticos.md
```

**Nota sobre módulos existentes.** Las carpetas vacías `models/`, `forecast/` y `risk/` de
la spec 001 no se reutilizan, para no mezclar capas. `risk/` queda para VaR de series
individuales (spec 001 US4). La documentación explica la relación.

## Orden de implementación

1. `stochastics.curves` + `affine` + `short_rate`: US1 y US3 base.
2. `stochastics.regimes`: US2.
3. `simulation`: US4.
4. `sensitivities`: US5.
5. `portfolio_risk`: US6.
6. Demostración con el Tesoro: US7. Monte Carlo y documentación.
