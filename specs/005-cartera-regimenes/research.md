# Research: Ideas de cartera y regímenes del ciclo

## R1. Una idea de cartera como prueba sobre un "activo universo"

**Decisión.** Cada configuración de cartera se convierte en un `Trial` cuyo `asset` es la
**identidad del universo**: `U:` seguido de los identificadores ordenados
alfabéticamente y unidos con `+` (p. ej. `U:XLB+XLE+…+XLY`). Así se reutilizan sin
cambios la selección, el Sharpe deflactado, la SPA de Hansen, Holm entre "activos" y la
memoria de la bitácora: todas las pruebas sobre el mismo universo se acumulan, de
cualquier experimento (FR-005, SC-006).

- **Orden.** La identidad usa el conjunto ordenado, así que reordenar el universo no crea
  una identidad nueva. El orden declarado sólo desempata el ranking (determinista).
- **Benchmark (FR-004).** La cartera **igual ponderada de los activos disponibles en cada
  fecha**, ejecutada con el mismo motor, costos y rebalanceo mensual. La medida de
  habilidad es el retorno activo `estrategia − exposición × igual ponderado`, con la
  exposición bruta media medida (≈ 1 para carteras siempre invertidas). Es el mismo
  criterio de "exposición constante" de las ideas por activo.
- **Kind en la bitácora.** `portfolio`, con los mismos campos que `signal` (`n_obs`,
  `eval_start`, `eval_end`, `timing_ir_per_period`, `sharpe_se_hac`). El cálculo de las
  pruebas previas acepta `signal`, `econometric` y `portfolio`. Nunca cruza universos con
  activos: la memoria es por identidad.

**Alternativas descartadas.**
- Contar la cartera en la memoria de cada constituyente: mezcla hipótesis distintas
  (timing de un activo frente a selección entre activos) e inflaría N de forma arbitraria.
- Benchmark SPY: no es el mismo universo, así que mezclaría la selección de sectores con
  el sesgo de composición. Se reporta como información.

## R2. Señales de cartera incluidas

| Nombre | Parámetros | Regla (causal; decisión con datos hasta t) |
|---|---|---|
| `cross_sectional_momentum` | `lookback_m` (meses), `skip_m` (meses, por defecto 1), `top_k` | En cada fecha, ranking por `P(t−21·skip)/P(t−21·(skip+lookback)) − 1` entre los activos con historia suficiente; peso `1/top_k` a los `top_k` mejores (empates por orden declarado); sin suficientes activos ⇒ efectivo |
| `inverse_volatility` | `lookback` (días) | Pesos ∝ 1/σ (desviación de los retornos diarios de los `lookback` días previos), normalizados a 1 entre los disponibles |

Las señales propias se registran con `register_portfolio_signal(nombre, fn)`, con
`fn(prices: DataFrame, **params) -> DataFrame` de pesos. La prueba de anticipación corre
sobre el universo completo con los cortes vigentes (FR-003).

## R3. Dos fases

Las ideas de cartera siguen exactamente la spec 004:
- **Calibración** sobre `Bundle.as_of(train_end)`. `frozen` gana la sección `portfolios`:
  parámetros, exposición de la calibración y universo.
- **Validación**: una evaluación después del corte. La comparación usa la exposición de
  la calibración y entra en la familia de Holm (`cartera:<nombre>`).
- **Periodo ya visto (FR-006).** El resultado es exploratorio si cualquier línea previa
  cubrió fechas posteriores al corte para el **universo** o para **cualquier
  constituyente**. Es conservador: haber visto el desempeño posterior de un sector ya
  informa la elección de una rotación.

## R4. Estados de régimen punto en el tiempo

**Definiciones (FR-008):**

| `type` | Campos | Estado en la fecha de decisión d |
|---|---|---|
| `threshold` | `variable`, `op` (`>`/`<`), `value` | último valor publicado ≤ d de la variable (con su transformación) frente al umbral |
| `spread` | `variables = [a, b]`, `op`, `value` | (a − b), cada una con su último valor publicado ≤ d: la disponibilidad efectiva es la más tardía |
| `trend` | `asset`, `months` | precio del activo en d bajo su media de los `months` cierres de mes previos (incluido d) |

- Las variables pueden ser exógenas o la tasa libre de riesgo, en su nivel, con el rezago
  declarado. Se alinean con `align_point_in_time` en las fechas de decisión mensuales del
  activo analizado.
- **Resultado (FR-009).** Para el activo i: `y_{t+1}` = exceso de retorno del mes
  siguiente a la decisión t. Regresión `y_{t+1} = a + b·S_t + e` con errores HAC
  (Newey-West, 3 rezagos). Se reportan b·12 (diferencia anualizada), t, p, las medias en
  cada estado y los meses en cada uno.
- **Mínimo (FR-010):** `min_months` (por defecto 12) en el estado y fuera de él. Si no se
  alcanza: "no concluyente", fuera de la familia.
- **Familia (FR-009):** todas las combinaciones válidas del experimento, con Holm. En la
  validación, la familia única pre-registrada (ideas, modelos, carteras y regímenes).
- **Bitácora (FR-011):** kind `regime`, con `asset`, `regime`, `eval_start`, `eval_end`,
  `n_obs`, `p`. Las pruebas de régimen **no** entran en el DSR de ideas: son otra
  hipótesis.

**Por qué HAC y no t simple.** Los estados son persistentes (la curva invertida dura
meses) y la volatilidad cambia con el régimen; HAC corrige ambos.

**Limitación declarada.** Una diferencia significativa entre estados **no** es una
estrategia: no incluye costos ni dice cuánto invertir. Se reporta como evidencia
descriptiva-inferencial sobre el ciclo.

## R5. Calibración estadística (Monte Carlo)

- **SC-001 (tamaño de cartera).** 11 activos con retornos iid sin persistencia relativa,
  malla de 4 configuraciones, 500 réplicas: fracción de significativas.
- **SC-002 (potencia).** Retornos relativos con persistencia AR(1) de la media
  (φ = 0,95), señal-ruido calibrada para un IR anual ≈ 0,8.
- **SC-004.** 11 activos × 3 estados independientes del retorno, 300 meses, 500
  réplicas: probabilidad de ≥ 1 falso positivo tras Holm. Potencia con +1 % mensual en un
  estado activo el 20 % del tiempo.

Los criterios de 5 % + 2,5 errores de Monte Carlo se toman de la spec 004 (I11).

---

## R6. Correcciones tras la revisión econométrica (2026-11-17)

| # | Hallazgo | Decisión |
|---|---|---|
| B1 | Regímenes sin memoria entre experimentos; umbrales elegidos ex post (VIX 25, 10 meses) | **Clave de memoria** = (activo, tipo, variables o activo de referencia). Cada variante (umbral u op distinto) es una hipótesis. El Holm de la calibración usa m = hipótesis actuales + variantes previas distintas con la misma clave. Se admiten mallas (`value = [20, 25, 30]`, `months = [8, 10, 12]`) y todas cuentan. Cada régimen declara `justification` (referencia o razón previa); si falta, el resultado es exploratorio |
| B2 | Lo probado fuera de la bitácora (4 rotaciones y 33 regímenes del script exploratorio) no se contabiliza | Bloque `[[declared_prior_tests]]` → línea `declared_prior` (idempotente por clave) con kind declarado, universo o activos, número de pruebas, periodo y hash del script. Suma en N (carteras por Jaccard, regímenes por clave) y cuenta en la detección de periodo visto |
| B3 | La memoria por universo exacto permite reiniciar N cambiando un constituyente | El DSR cuenta toda prueba de cartera previa (incluidas las declaradas) cuyo universo tenga **Jaccard ≥ 0,5** con el actual. La varianza del umbral sólo usa las de la misma frecuencia con `eval_end` ≤ corte. La SPA sigue sobre el universo exacto. Una cartera no entra en la memoria de sus constituyentes (otra nula) |
| B4 | El benchmark por defecto del motor es igual ponderado diario y sin costos; `every_bar` daría rotación diaria | Las carteras **siempre** con `rebalance = "M"` (en la identidad). El benchmark es `run_backtest(precios, pesos_igual_ponderados, cfg_M)` con los mismos costos. El **conjunto elegible es por bloque**: activo con ≥ `min_history_m` meses de precios (por defecto, el máximo de `lookback_m + skip_m` de la malla, o 12). La misma elegibilidad aplica a estrategia y benchmark. Ventana común: el fin de calentamiento más tardío de la malla |
| I1 | Una sola familia de Holm en la validación mezcla preguntas y quita potencia | **Dos familias** con α repartido y pre-declarado: estrategias (ideas, modelos y carteras) α·0,8 y regímenes α·0,2. FWER global ≤ α. A la validación sólo pasan las hipótesis de régimen **seleccionadas** en la calibración (p Holm < α_régimen), probadas **unilateralmente** en el signo calibrado |
| I2 | La detección de periodo visto no mira carteras, regímenes ni pruebas declaradas | Se agregan `portfolio` (expandiendo el universo a sus constituyentes), `regime` y `declared_prior`, de forma simétrica (una validación por activo también las ve). Se reporta la fracción de constituyentes vistos |
| I3 | SC-001 con medias distintas hace ganar al momentum sin habilidad; SC-004 inviable con σ sectorial (potencia ≈ 6 %) | SC-001: medias **iguales**, factor común (ρ ≈ 0,6), inicios distintos y costos. SC-002: T = 240 meses, 9 activos, top_k = 3, 4 configuraciones, IR 0,8 y 0,4 reportados. SC-004: efecto en unidades de σ (0,6σ mensual, 20 % de meses en el estado, T = 300, 9 activos × 3 estados, efecto en 1 activo); se reporta que con datos reales la potencia es baja |
| I4 | La justificación del HAC es inexacta; pocos meses en el estado | Errores **HC3** (heterocedasticidad por régimen; y mensual sin solapamiento). `min_months` por defecto 24. Horizonte fijo de 1 mes. El Monte Carlo incluye un estado endógeno (tendencia sobre retornos GARCH-t) |
| I5 | Definición de las señales | `cross_sectional_momentum` con **cierres de fin de mes**. Fuera de la ventana común no hay posiciones. Se rechaza `top_k ≥ |U|`. Empates por **id ordenado** (coherente con la identidad). `inverse_volatility` con piso de σ (1e-4 diario), ventana de `lookback` días hasta t incluido, al menos `lookback` observaciones, y pesos que sólo cambian a fin de mes (rebalanceo M) |
| I6 | Tiempos de los regímenes | **Convención declarada (descriptiva, no es estrategia):** estado al cierre de d, resultado = exceso de retorno del mes calendario siguiente desde ese cierre, sin rezago de ejecución. `spread`: si la última observación de cualquiera de las dos variables tiene más de 5 días hábiles de antigüedad en d, el estado es faltante |
| M1-M4 | `spa_p_holm` = `spa_p` con un solo universo (se documenta); IV-bis y `docs/methodology/` en el plan; exclusión por `min_months` válida porque sólo depende de S; SPY sólo informativo | Aceptados |
