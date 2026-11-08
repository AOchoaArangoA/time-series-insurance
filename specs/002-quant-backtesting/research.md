# Research: Backtesting responsable (002)

Formato: **Decision / Rationale / Alternatives considered**.

## R1. Librería de backtesting

- **Decision**: Motor vectorizado propio (`tsinsurance.backtest.engine`, ~150 líneas,
  bucle NumPy por barra con deriva de pesos) como motor principal, y **bt 1.4.1**
  (extra opcional `[backtest]`) como motor de referencia independiente para la prueba de
  equivalencia (SC-001).
- **Rationale**: Evaluación del 2026-11-08 con pandas 3.1 / Python 3.13 sobre la misma
  estrategia (cruce de medias 20/100, costo 5 pb):

  | Librería | Retorno | Compatible | Licencia | Observación |
  |----------|---------|------------|----------|-------------|
  | bt 1.4.1 | 2,5497 % | sí | MIT | multi-activo, árbol de algoritmos, 0,19 s |
  | vectorbt 1.2.0 | 2,5497 % | parcial (barrido de indicadores falla al alinear índices) | Apache-2.0 + Commons Clause | 10 s de compilación JIT en la primera llamada |
  | backtesting.py 0.6.6 | 1,51 % | sí | AGPL-3.0 | mono-activo, convención de órdenes por unidades |

  bt y vectorbt coinciden exactamente (ejecución en la barra siguiente). Un motor propio
  delgado da control total sobre la convención de ejecución, costos, tasa libre de riesgo
  y deriva, y es rápido para barridos y remuestreo; su exactitud se garantiza
  comparándolo con bt (Principio V: implementación propia validada contra referencia).
- **Alternatives considered**: usar bt como único motor (más lento en barridos grandes y
  menos control de supuestos); vectorbt (licencia restrictiva para uso comercial y
  fallas con pandas 3); backtesting.py (AGPL, mono-activo); zipline-reloaded
  (infraestructura de *bundles* pesada, orientado a acciones de EE. UU.).

## R2. Convención de ejecución y costos

- **Decision**: la decisión en el cierre de `t` se ejecuta al cierre de `t + lag`
  (`lag = 1` por defecto; `lag = 0` permitido pero marcado "optimista: requiere órdenes
  al cierre"). Costo = `(cost_bps + slippage_bps) / 1e4 × rotación`, donde rotación =
  Σ|w_objetivo − w_derivado|. Entre rebalanceos los pesos derivan con los precios. La
  porción no invertida rinde la tasa libre de riesgo (opcional).
- **Rationale**: la evaluación de librerías mostró que la convención de ejecución
  cambia el resultado (3,14 % vs 2,55 %); debe ser explícita (Principio VIII).

## R3. Inferencia sobre el desempeño

- **Decision**:
  - Error estándar del Sharpe: Mertens (2002) / Opdyke (2007) con asimetría y curtosis.
  - Intervalo de confianza: bootstrap estacionario (`arch.bootstrap.StationaryBootstrap`,
    bloque óptimo de Politis-White vía `optimal_block_length`).
  - Sharpe probabilístico (PSR) y deflactado (DSR): Bailey & López de Prado (2012, 2014).
    Verificado: el ejemplo publicado (SR anual 2,5; T = 1250; asimetría −3; curtosis 10;
    N = 100; V[SR] = 0,5) da DSR = 0,9004.
  - Pruebas múltiples frente al benchmark: `arch.bootstrap.SPA` (Hansen 2005) con
    pérdidas = −retornos en exceso.
- **Rationale**: reutiliza `arch` para remuestreo; las fórmulas cerradas (PSR/DSR) no
  existen en una librería mantenida y se validan contra el ejemplo publicado.

## R4. Validación de pronósticos econométricos

- **Decision**: R² fuera de muestra (Campbell & Thompson 2008) frente a la media
  histórica expansiva; prueba de Clark & West (2007) para modelos anidados (regresión
  de `f_t` sobre constante con errores Newey-West, unilateral); Diebold-Mariano con
  corrección de Harvey-Leybourne-Newbold (compartido con la spec 001, T054);
  Pesaran & Timmermann (1992) para la precisión direccional.
- **Rationale**: Diebold-Mariano no es válida para modelos anidados (la media histórica
  está anidada en la regresión predictiva); Clark-West corrige ese sesgo.

## R5. Regresión predictiva walk-forward

- **Decision**: OLS de `y_{s+1}` sobre `[1, X_s, y_s…y_{s-p+1}]` estimada en cada fecha
  de re-estimación con todos los pares cuyo resultado `y_{s+1}` es observable en `t`
  (ventana expansiva o móvil, `min_train`, `refit_every`). Errores HAC Newey-West
  (rezagos `floor(4(n/100)^{2/9})`) en el reporte de muestra completa. Diagnósticos:
  estacionariedad de cada regresor (`tsinsurance.diagnostics.stationarity`),
  persistencia AR(1) con advertencia de sesgo de Stambaugh (1999) si ρ > 0,95, y
  Ljung-Box / ARCH-LM / Jarque-Bera sobre residuos.
- **Rationale**: estándar en la literatura de predictibilidad de retornos (Welch &
  Goyal 2008; Campbell & Thompson 2008).

## R6. Rezago de publicación (punto en el tiempo)

- **Decision**: cada variable exógena declara `release_lag` (un `DateOffset` contado
  desde el **fin del periodo** de la observación) y su frecuencia. La fecha de
  disponibilidad es `fin_de_periodo + release_lag`; la alineación a fechas de decisión
  usa `merge_asof` hacia atrás. Valores por defecto en los ejercicios: series diarias de
  mercado de FRED 1 día hábil; IPC y desempleo 1 mes + 15 días.
- **Rationale**: evita usar datos no publicados; los *vintages* (ALFRED) quedan como
  limitación declarada.

## R7. Prueba de anticipación (look-ahead)

- **Decision**: `check_lookahead(signal_fn, data, n_cuts, seed)`: calcula la señal con
  todos los datos y con datos truncados en `n_cuts` fechas aleatorias; cualquier
  diferencia en fechas ≤ corte (tolerancia 1e-10) indica fuga. Detecta desplazamientos
  negativos y estadísticas de muestra completa (p. ej. estandarizar con la media total).
- **Rationale**: implementación simple y general para funciones arbitrarias del usuario.

## R8. Señales incluidas

- Tendencia: cruce de medias (Brock, Lakonishok & LeBaron 1992); momentum de serie de
  tiempo (Moskowitz, Ooi & Pedersen 2012).
- Volatilidad: objetivo de volatilidad (Moreira & Muir 2017) con volatilidad EWMA
  (RiskMetrics, λ = 0,94) o pronóstico GARCH(1,1) re-estimado walk-forward con `arch`.
- Econométrica: regresión predictiva macro (R5) con regla de posición `sign` (largo /
  efectivo o largo / corto) o proporcional al pronóstico estandarizado, con límite.

## R9. Veredicto doble

- **Decision**: *evidencia estadística* = Clark-West rechaza al nivel α (o
  Pesaran-Timmermann para señales sin pronóstico numérico); *valor económico* = la
  prueba SPA frente al benchmark rechaza al nivel α con costos incluidos. Cuatro
  cuadrantes: ambos, solo estadística ("ajuste sin valor económico"), solo económica
  ("posible suerte o no linealidad"), ninguno.

## R10. Datos de los ejercicios

- ETFs (Yahoo, precio ajustado): TLT, IEF, SHY, TIP, LQD, HYG, AGG, SPY, 2007-05-01 a
  2025-12-31 (HYG inicia en abril de 2007). El ticker "TFT" no existe; se usa TLT.
- FRED diarias: DTB3 (tasa libre de riesgo), DGS10, T10Y2Y, BAA10Y.
- FRED mensuales: CPIAUCSL, UNRATE.
- Instantáneas separadas por frecuencia (el contrato exige una frecuencia por `to_wide`).
