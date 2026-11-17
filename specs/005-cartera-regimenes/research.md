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
