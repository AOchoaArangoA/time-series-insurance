# Backtesting responsable

Módulo: `tsinsurance.backtest` · Especificación: `specs/002-quant-backtesting` ·
Constitución: Principio VIII.

Un backtest es un experimento estadístico. El paquete obliga a declarar cada supuesto,
compara siempre con un benchmark, cuantifica la incertidumbre y ajusta por el número de
ideas probadas. Para señales econométricas exige **validación doble**: estadística (el
pronóstico es mejor que la media histórica) y económica (la señal agrega valor neto de
costos).

## 1. Motor y convención de ejecución

- `target_weights[t]` es una decisión con información hasta el **cierre de t**.
- Se ejecuta al cierre de `t + lag` (`lag = 1` por defecto). `lag = 0` se marca como
  optimista (órdenes al cierre).
- Entre ejecuciones los pesos **derivan** con los precios; con `rebalance = "M"` sólo se
  re-ajustan el último día de cada mes.
- Costo = `(cost_bps + slippage_bps) × Σ|w_objetivo − w_derivado|`, por activo si se
  entrega un `Mapping`.
- La porción en efectivo rinde la tasa libre de riesgo **conocida el día anterior**; el
  efectivo negativo y los cortos pagan `rf + financing_spread_bps`.
- El calentamiento termina en el primer periodo cuyo retorno refleja una decisión
  (aunque sea quedarse en efectivo).
- Un precio faltante dentro de la historia se rellena hacia adelante (nota en el
  resultado); antes del primer precio el peso se fija en 0.
- Para señales econométricas mensuales el rebalanceo por defecto es mensual: la posición
  se mantiene hasta la próxima decisión.

**Validación contra bt 1.4.1** (`run_with_bt`, posiciones fraccionarias, comisión
proporcional): sin costos, diferencia máxima por periodo 3e-16; con 5 pb, 2,4e-6 por
periodo. La diferencia es de segundo orden: bt cobra la comisión después de fijar
posiciones y el motor la descuenta antes y mantiene pesos exactos.

### Por qué un motor propio

Se evaluaron tres librerías con pandas 3.1 (ver `specs/002-quant-backtesting/research.md`,
R1). bt y vectorbt coinciden exactamente entre sí; vectorbt se descartó por licencia
(Commons Clause) y fallas con pandas 3, backtesting.py por licencia AGPL y ser
mono-activo. bt se usa como referencia independiente.

## 2. Punto en el tiempo

- `Exogenous(series, frequency, release_lag)`: una observación del periodo `p` está
  disponible en `fin_de_periodo(p) + release_lag` (FRED fecha los meses el día 1; el dato
  de enero del IPC no existe hasta ~mediados de febrero).
- `align_point_in_time` alinea hacia atrás (`merge_asof`): nunca usa un dato antes de su
  publicación.
- Decisiones mensuales: último día hábil con precio del mes (`monthly_decision_dates`);
  retornos de cierre de fin de mes a cierre de fin de mes (`monthly_returns`).
- Tasa libre de riesgo: DTB3 (descuento) → retorno al vencimiento `R = d·91/(360 − d·91)`
  → efectiva anual `(1+R)^{365/91} − 1` → por día hábil `(1+e)^{1/252} − 1`; disponible un
  día hábil después y aplicada con la tasa conocida el día anterior (el periodo `t` usa la
  DTB3 de `t − 2`: conservador).
- Transformaciones de variables (`diff`, `pct_change`, `yoy`) por **fecha** sobre el
  calendario de su frecuencia: un dato faltante (p. ej. el IPC de octubre de 2025 en FRED)
  deja NaN en vez de comparar contra el mes equivocado.
- Un último mes incompleto no genera fecha de decisión ni retorno mensual.
- Revisiones: sólo se usan series de mercado (no revisadas) e IPC **sin
  desestacionalizar** (CPIAUCNS). Una variable revisable se declara
  `point_in_time=False` y el veredicto queda "exploratorio".

## 3. Prueba de anticipación

`check_lookahead(fn, data)` calcula la señal con todos los datos y con datos truncados en
cortes deterministas (fin del calentamiento de la señal y +1, +5, +20; posiciones 5, 20,
60, 250, n/4, n/2, n−3, n−2) y aleatorios dentro del tramo con señal. Si la señal falla
con datos truncados en tantos cortes que quedan menos de 5 evaluables, el resultado es
**no concluyente** y `raise_if_biased()` lo rechaza. Las
`Exogenous` se truncan por **fecha de disponibilidad**. Detecta (pruebas
automatizadas): desplazamiento −1, estandarización con estadísticas de muestra completa,
`bfill` del calentamiento, fuga puntual al final y rezago de publicación omitido. No
marca las señales incluidas ni el flujo econométrico completo.

## 4. Inferencia sobre el desempeño

| Medida | Método |
|--------|--------|
| EE del Sharpe | iid con asimetría y curtosis (Mertens 2002) y HAC por método delta (Newey-West) |
| IC del Sharpe | bootstrap estacionario (Politis-Romano), bloque de Politis-White |
| PSR | Bailey y López de Prado (2012), curtosis no-exceso |
| DSR | Bailey y López de Prado (2014); varianza de Sharpes **por periodo**; N bruto |
| Diferencia de Sharpe | bootstrap estacionario pareado, unilateral (versión no estudentizada de Ledoit-Wolf 2008) y ganancia CER γ = 3 |
| SPA | Hansen (2005) vía `arch.bootstrap.SPA`, pérdidas −(r_estrategia − r_benchmark), valor p consistente |

**Barridos.** La significancia se mide sobre el **retorno activo** frente a comprar y
mantener (nula común: sin habilidad de timing): DSR del ratio de información del mejor,
deflactado con todas las pruebas del activo en un `TrialRegistry` **compartido** entre
barridos e ideas, y SPA sobre los retornos activos de todas ellas. Así la prima de riesgo
del activo (p. ej. SPY) no se confunde con habilidad.

**N efectivo.** El número efectivo de pruebas por autovalores `(Σλ)²/Σλ²` dio ≈ 4 para
100 estrategias de timing sobre el mismo activo, porque todas comparten el factor del
activo. Usarlo en el DSR con la varianza de todas las pruebas infló el tamaño a 22 %
(medido). El DSR usa N bruto (tamaño 1,6 %, potencia 88 %; SC-003) y el N efectivo se
reporta sólo como diagnóstico.

## 5. Señales econométricas y validación doble

`PredictiveRegression` estima `y_{t+1} = a + b'X_t (+ AR) + e` con todos los pares
`(X_s, y_{s+1})` observables en `t` (ventana expansiva o móvil, re-estimación cada
`refit_every`). Guarda la trayectoria de β y el error estándar de la media pronosticada
(sólo incertidumbre de parámetros, covarianza OLS homocedástica: no es un intervalo de
predicción).

**(a) Validación estadística**

- Fuera de muestra: R² de Campbell-Thompson, **Clark-West** (modelos anidados, h = 1,
  unilateral), Diebold-Mariano (reportada con la nota de que no es válida para modelos
  anidados), Pesaran-Timmermann (dirección; "no aplicable" si hay un solo signo).
- Muestra completa (descriptiva ex post, **no** para elegir la especificación):
  coeficientes HAC; estacionariedad de cada regresor con la regla de la spec 001; un
  regresor I(1) ⇒ regresión desbalanceada; persistencia ρ, correlación de innovaciones δ
  y sesgo aproximado de Stambaugh `−(σ_uv/σ_v²)(1+3ρ)/T`; Ljung-Box (con `model_df`),
  ARCH-LM, Jarque-Bera y CUSUM.

**(b) Valor económico**: la misma regla de posición aplicada al pronóstico del modelo
frente a la aplicada a la **media histórica**, neto de costos y en exceso de rf, con la
prueba de diferencia de Sharpe.

**Veredicto**: estadística = Clark-West (regla `proportional`) o Pesaran-Timmermann
(reglas de signo); económica = diferencia de Sharpe significativa. Cuadrantes:
estadística y económica / sólo estadística / sólo económica / sin evidencia. Se agregan
las marcas *no concluyente* (< 60 pronósticos), *exploratorio* (más de una
especificación o variables no punto-en-el-tiempo) y *diagnósticos no superados*.

Precisión medida (SC-004, n = 300 meses, 1000 réplicas): Clark-West detecta un regresor
con R² = 5 % en el 94 % de los casos; tamaño 3,5 %; con un regresor persistente
irrelevante (ρ = 0,98, δ = −0,9) el tamaño es 2,6 %.

## 6. Resultados con datos reales (instantáneas 2003-2025)

- **Ejercicio 01** (`examples/backtest_01_tendencia_volatilidad_etfs.py`): en TLT, ni la
  tendencia 50/200, ni el momentum 12-1, ni el momentum con objetivo de volatilidad superan
  a comprar y mantener en Sharpe; reducen la máxima caída (−29 % / −38 % / −26 % vs −51 %).
  En el barrido sobre 8 ETFs (registro acumulado de 159 pruebas; 18 sobre TLT) ninguna
  configuración muestra habilidad de timing significativa tras el ajuste por pruebas
  múltiples (DSR del ratio de información y SPA).
- **Ejercicio 02** (`examples/backtest_02_macro_tlt.py`): el modelo macro (pendiente de la
  curva, diferencial de crédito, inflación anual, cambio de la tasa a 10 años) acierta la
  dirección del retorno de TLT (Pesaran-Timmermann p ≈ 0,04), pero su R² fuera de muestra
  es negativo y la mejora de Sharpe frente a la regla con la media histórica no es
  significativa (p ≈ 0,1). La pendiente es I(1) y muy persistente: la inferencia de
  muestra completa no es confiable. Veredicto: "sólo estadística" (Pesaran-Timmermann sí,
  Clark-West no; el reporte señala la contradicción), exploratorio y con diagnósticos no
  superados.

## 7. Limitaciones conocidas

- Sin *vintages* de ALFRED (T046); inferencia IVX para regresores persistentes pendiente
  (T045); referencias externas de R no disponibles en el entorno (T044).
- Universo elegido ex post (sesgo de supervivencia, nota automática en cada resultado).
- Sin impuestos, márgenes ni impacto de mercado no lineal.

## Referencias

- Bailey, D. & López de Prado, M. (2012, 2014). The Sharpe ratio efficient frontier; The deflated Sharpe ratio.
- Brock, W., Lakonishok, J. & LeBaron, B. (1992). Simple technical trading rules. *Journal of Finance*.
- Campbell, J. & Thompson, S. (2008). Predicting excess stock returns out of sample. *RFS*.
- Clark, T. & West, K. (2007). Approximately normal tests for equal predictive accuracy in nested models. *J. Econometrics*.
- Diebold, F. & Mariano, R. (1995); Harvey, D., Leybourne, S. & Newbold, P. (1997).
- Hansen, P. R. (2005). A test for superior predictive ability. *JBES*.
- Ledoit, O. & Wolf, M. (2008). Robust performance hypothesis testing with the Sharpe ratio. *J. Empirical Finance*.
- Lo, A. (2002). The statistics of Sharpe ratios. *FAJ*. Mertens, E. (2002).
- Moreira, A. & Muir, T. (2017). Volatility-managed portfolios. *Journal of Finance*.
- Moskowitz, T., Ooi, Y. H. & Pedersen, L. H. (2012). Time series momentum. *JFE*.
- Pesaran, M. H. & Timmermann, A. (1992). A simple nonparametric test of predictive performance. *JBES*.
- Politis, D. & Romano, J. (1994). The stationary bootstrap. *JASA*; Politis, D. & White, H. (2004).
- Stambaugh, R. (1999). Predictive regressions. *JFE*.
- Welch, I. & Goyal, A. (2008). A comprehensive look at the empirical performance of equity premium prediction. *RFS*.
