# Quickstart / guía de validación (002)

## Prerrequisitos

```bash
uv sync --all-extras          # incluye bt (motor de referencia) y yfinance
export FRED_API_KEY=...       # sólo para refrescar instantáneas
```

## Escenario 1 — Tendencia y volatilidad sobre ETFs (US1, US3, US5)

```bash
uv run python examples/backtest_01_tendencia_volatilidad_etfs.py
```
Esperado: para TLT y 7 ETFs más (IEF, SHY, TIP, LQD, HYG, AGG, SPY), backtests de cruce
de medias, momentum de serie de tiempo y objetivo de volatilidad con costo 5 pb y
ejecución en la barra siguiente; tabla de métricas vs comprar y mantener; barrido de
parámetros con número de configuraciones, Sharpe deflactado y valor p SPA; prueba de
anticipación superada por todas las señales incluidas.

## Escenario 2 — Modelo macro para TLT (US2, US3)

```bash
uv run python examples/backtest_02_macro_tlt.py
```
Esperado: retornos mensuales en exceso de TLT pronosticados con pendiente de la curva,
cambio de la tasa a 10 años, diferencial de crédito e inflación (rezagos de publicación
declarados), walk-forward expansivo; reporte de validación del modelo (estacionariedad
de regresores, HAC, residuos), evaluación del pronóstico (R² fuera de muestra,
Clark-West, Diebold-Mariano, Pesaran-Timmermann), backtest económico y veredicto doble.

## Escenario 3 — Equivalencia con bt (SC-001) y anticipación (SC-002)

```bash
uv run pytest tests/backtest -k "bt or lookahead"
```

## Suite completa

```bash
uv run pytest                       # incluye Monte Carlo SC-003/SC-004 (marca slow)
```
