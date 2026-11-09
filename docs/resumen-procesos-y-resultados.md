# Resumen de procesos y resultados

Proyecto `tsinsurance` — corte al 2026-11-09 (rama `ccr-d4f6f6a0-bg0992`).

Paquete Python de series de tiempo para asistir decisiones cuantitativas de inversión
—con foco en el portafolio de una aseguradora— con metodología econométrica robusta,
desarrollado con *Spec-Driven Development* (GitHub Spec Kit) y agentes de IA.

---

## 1. Proceso seguido

| Fase | Qué se hizo | Artefactos |
|------|-------------|------------|
| Preparación | Spec Kit con Claude Code; esqueleto del paquete (uv, ruff, mypy estricto, pytest, CI) | `.specify/`, `.claude/`, `pyproject.toml` |
| Constitución | 8 principios no negociables: rigor econométrico, validación sin fuga, incertidumbre, agnóstico de jurisdicción, datos con contrato, biblioteca tipada, pruebas primero, simplicidad, **backtesting responsable** | `.specify/memory/constitution.md` (v1.2.0) |
| Spec 001 — motor econométrico | Especificación, aclaraciones (mercado genérico, datos locales + públicos, curvas en paquete aparte), plan, 85 tareas | `specs/001-core-econometric-engine/` |
| Implementación US1 | Contrato de datos, conectores, instantáneas, preparación, estacionariedad, descriptivos | `src/tsinsurance/data`, `diagnostics` |
| Spec 002 — backtesting | Evaluación de librerías, especificación, plan, 47 tareas, implementación completa v0.1 | `specs/002-quant-backtesting/`, `src/tsinsurance/backtest` |
| Revisiones independientes | `/speckit-analyze` de la spec 001 y 3 revisiones con el subagente `econometrics-reviewer` (MVP 001, diseño 002, implementación 002); corrección de todos los hallazgos bloqueantes e importantes | `research.md` R11-R12, `tasks.md` fase 9 |
| Referencias externas | Instalación de R 4.3.3 (urca, tseries, forecast, FinTS, rugarch, sandwich, lmtest) y prueba automatizada contra R | `tests/reference/test_against_r.py` |

### Hallazgos de las revisiones independientes (todos corregidos salvo los listados como pendientes)

| Revisión | Bloqueantes | Importantes | Ejemplos de lo corregido |
|----------|-------------|-------------|--------------------------|
| MVP spec 001 | 4 | 10 | valor p acotado de KPSS rompía la regla con α = 1 %; fechas mensuales al día 1 (fuga); ARCH-LM con falsos positivos; interpolación con información futura sin marcar |
| Diseño spec 002 | 3 | 12 | "valor económico" contra el benchmark equivocado; prueba de anticipación sin cubrir el flujo econométrico; series macro revisadas (vintages) |
| Implementación spec 002 | 1 | 7 | prueba de anticipación que certificaba con todos los cortes omitidos; variación anual del IPC contra el mes equivocado por un dato faltante; huecos de precio con operaciones espurias; significancia de barridos sesgada por la prima de riesgo |

---

## 2. Qué hace el paquete hoy

**Datos** (`tsinsurance.data`)
- Contrato de insumos v1.0 (series de mercado, portafolio, nodos de tasas), plantillas
  CSV/Excel, JSON Schema, validación con fila, columna y regla de cada error; CLI
  `tsinsurance template|validate|schema`.
- Conectores: CSV, Excel, FRED, Yahoo Finance y registro extensible.
- Instantáneas replicables (Parquet + metadatos + SHA-256).

**Diagnóstico** (`tsinsurance.diagnostics`)
- ADF, Phillips-Perron, KPSS, Zivot-Andrews con regla jerárquica de decisión del orden
  de integración; descriptivos, ACF/PACF, Jarque-Bera, Ljung-Box, ARCH-LM sobre residuos.

**Backtesting responsable** (`tsinsurance.backtest`)
- Motor con retraso de ejecución, costos por activo, deriva de pesos, tasa libre de
  riesgo y financiación explícitos; validado contra la librería **bt**.
- Señales de tendencia (cruce de medias, momentum) y volatilidad (EWMA, GARCH
  walk-forward, objetivo de volatilidad); funciones propias del usuario.
- Datos macro punto-en-el-tiempo con rezago de publicación.
- Prueba automática de anticipación (*look-ahead*).
- Inferencia: Sharpe con EE iid y HAC, IC por bootstrap, PSR, **Sharpe deflactado**,
  **SPA de Hansen**, diferencia de Sharpe y ganancia de equivalente cierto.
- Modelos econométricos: regresión predictiva walk-forward con variables macro y
  **validación doble** (estadística: Clark-West, R² fuera de muestra, Pesaran-Timmermann,
  estacionariedad y persistencia de regresores, residuos; económica: Sharpe neto frente
  a la misma regla con la media histórica) y veredicto en cuatro cuadrantes.
- Barridos con registro de pruebas compartido y calibración/validación fuera de muestra.

---

## 3. Resultados registrados

### 3.1 Verificación del software

| Verificación | Resultado |
|--------------|-----------|
| Suite de pruebas | 176 pruebas aprobadas (unitarias, referencia, Monte Carlo, integración, R); cobertura 98 % |
| Tipos y estilo | `mypy --strict` y `ruff` sin errores |
| Conectores en vivo | FRED y Yahoo Finance verificados |
| Motor vs bt | sin costos: 3e-16 por periodo; con 5 pb: 2,4e-6 por periodo |
| Sharpe deflactado | reproduce el ejemplo publicado (Bailey y López de Prado 2014): 0,9004 |

**Comparación con R** (datos reales GS10):

| Prueba | tsinsurance | R | Diferencia relativa |
|--------|-------------|---|---------------------|
| ADF (constante, 3 rezagos) — urca | −2,480170 | −2,480170 | 5e-14 |
| Phillips-Perron Z-tau — urca | −2,104666 | −2,105817 | 5e-4 (convención de varianza) |
| KPSS nivel (5 rezagos) — tseries | 5,550429 | 5,550429 | 2e-14 |
| Ljung-Box(10) — stats | 40,007631 | 40,007631 | 2e-15 |
| Jarque-Bera — tseries | 35,358867 | 35,358867 | 7e-15 |
| ARCH-LM(5) — FinTS | 4,146900 | 4,146900 | 8e-14 |
| Diebold-Mariano HLN — forecast | 5,041692 | 5,041692 | 8e-14 |

### 3.2 Calibración estadística (Monte Carlo)

| Criterio | Resultado | Meta |
|----------|-----------|------|
| Orden de integración, I(0) (AR(1), n = 500) | ≈ 100 % | ≥ 90 % |
| Orden de integración, I(1) (paseo aleatorio) | ≈ 89 % | ≥ 85 % (redefinido: el 90 % es inalcanzable con α = 5 %) |
| Sharpe deflactado, tamaño (mejor de 100 sin habilidad) | 1,6 % | ≤ 6,9 % |
| Sharpe deflactado, potencia (Sharpe real 1,5) | 88,2 % | ≥ 80 % |
| Clark-West, potencia (R² = 5 %, 300 meses) | 94,3 % | ≥ 80 % |
| Clark-West, tamaño | 3,5 % | ≤ 6,4 % |
| Clark-West, regresor persistente (ρ = 0,98, δ = −0,9) | 2,6 % | ≤ 10 % |
| Barrido 8 activos × 20 configuraciones × 10 años | 7,5 s | < 60 s |

Hallazgo metodológico: el número efectivo de pruebas por autovalores dio ≈ 4 de 100
estrategias sobre el mismo activo y llevó el tamaño del Sharpe deflactado a 22 %; por eso
el paquete usa el número bruto de pruebas.

### 3.3 Resultados con datos reales (instantáneas 2003-2025)

**Tasa del Tesoro a 10 años (GS10 mensual, 1990-2025)**: I(1); la diferencia es
estacionaria. El estadístico de Zivot-Andrews se minimiza en 2020-08, sin ser
significativo.

**TLT: tendencia y volatilidad** (costo 5 pb, ejecución al cierre siguiente, en exceso de rf)

| Estrategia | Sharpe | IC 95 % | Máx. caída | vs comprar y mantener (p) |
|------------|--------|---------|------------|---------------------------|
| Comprar y mantener | 0,18-0,19 | — | −51 % | — |
| Cruce de medias 50/200 | 0,16 | [−0,24; 0,52] | −29 % | 0,59 |
| Momentum 12-1 | 0,08 | [−0,30; 0,46] | −38 % | 0,81 |
| Momentum + objetivo de volatilidad 8 % | 0,07 | [−0,32; 0,44] | −26 % | 0,80 |

Las reglas reducen la peor caída, pero no mejoran el Sharpe.

**8 ETFs** (TLT, IEF, SHY, TIP, LQD, HYG, AGG, SPY; 159 pruebas registradas, 18 sobre TLT):
ninguna configuración muestra habilidad de *timing* significativa tras el ajuste por
pruebas múltiples (Sharpe deflactado del ratio de información y SPA). La más cercana es
SHY con tendencia (DSR 0,85; SPA p = 0,054).

**Calibración 2003-2016 / validación 2017-2025** (tendencia): en TLT el Sharpe fuera de
muestra fue ≈ 0,00 frente a −0,13 de comprar y mantener (p = 0,32, no significativo).

**Modelo macro para TLT** (pendiente de la curva, diferencial de crédito, inflación anual
del IPC sin desestacionalizar, cambio de la tasa a 10 años; walk-forward expansivo):

| Medida | Resultado |
|--------|-----------|
| Pronósticos fuera de muestra | 214 meses (2008-2025) |
| R² fuera de muestra | −14,1 % (peor que la media histórica) |
| Clark-West | p = 0,70 |
| Acierto de dirección (Pesaran-Timmermann) | 56,1 %, p = 0,039 |
| Sharpe regla largo/efectivo vs la misma regla con media histórica | 0,37 vs 0,16; p = 0,10 |
| Diagnósticos | pendiente de la curva I(1) y muy persistente; ARCH en residuos |
| Veredicto | **sólo estadística**, exploratorio, diagnósticos no superados |

Conclusión: las señales macro aciertan la dirección algo más que el azar, pero no
mejoran el pronóstico en error cuadrático ni generan valor económico significativo neto
de costos.

---

### 3.4 Experimento registrado: ETFs inversos del Tesoro (spec 003)

TBT, TBX y TBF ("TFT" no existe; se asumió TBT), 2008-2025, selección 2008-2018 y
validación única 2019-2025, ejecución confirmatoria registrada en la bitácora. Frente a
comprar y mantener las reglas parecen ganar (ratio +0,16 a +0,52) sólo porque están
invertidas ~1/3 del tiempo en activos que decaen; frente a la misma exposición constante
**no hay habilidad de timing** (DSR máximo 0,35; ninguna significativa) y los modelos
macro tienen R² fuera de muestra negativo. Detalle: `experiments/inverse_treasury/README.md`.

## 4. Decisiones pendientes de confirmar

1. "TFT" no existe en Yahoo Finance: en la spec 002 se usó **TLT** y en la 003 **TBT**
   (familia de inversos con TBX y TBF).
2. El backtesting es el subpaquete `tsinsurance.backtest` (extraíble si se prefiere un
   paquete aparte).
3. Criterio SC-001 redefinido (I(0) ≥ 90 %, I(1) ≥ 85 %, incorrectas ≤ 7 %).

## 5. Pendientes principales

- Spec 001: ARIMA/GARCH completos, pronóstico, VaR/ES y reportes (US2-US5); mejoras de
  la revisión (T077-T085).
- Spec 002: inferencia IVX para regresores persistentes (T045), *vintages* ALFRED (T046),
  EE HAC del Sharpe con preblanqueo (T047).
- Ampliar la comparación con R a Zivot-Andrews, GARCH (rugarch) y Pesaran-Timmermann.

## 6. Cómo reproducir

```bash
uv sync --all-extras
uv run pytest                                              # suite completa (~3,5 min)
uv run python examples/01_diagnostico_tasas_fred.py
uv run python examples/backtest_01_tendencia_volatilidad_etfs.py
uv run python examples/backtest_02_macro_tlt.py
```

Metodología: `docs/methodology/stationarity.md` y `docs/methodology/backtesting.md`.
