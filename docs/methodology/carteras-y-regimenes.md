# Carteras entre activos y regímenes del ciclo

Metodología de la spec 005. Complementa `backtesting.md` (ideas por activo y modelos
econométricos) y `metodologia-general.md`.

## 1. Ideas de cartera

Una idea de cartera asigna pesos **entre** los activos de un universo; la rotación
sectorial es el ejemplo típico. La pregunta es si la **selección** entre activos agrega
valor, no si conviene estar invertido.

**Benchmark.** La cartera igual ponderada de los activos elegibles del bloque. Se ejecuta
con el mismo motor, los mismos costos y el mismo rebalanceo mensual. Un activo es elegible
cuando tiene al menos `min_history_m` cierres de mes de historia (por defecto, el mayor
`lookback_m + skip_m` de la malla). La estrategia y el benchmark usan la misma
elegibilidad y la misma ventana: desde la primera fecha en que todas las configuraciones
y el benchmark están invertidos. Comparar contra SPY mezclaría la selección con la
composición del universo, así que SPY sólo se reporta como información.

**Habilidad.** Se mide con el retorno activo:

```text
estrategia − exposición media × igual ponderado
```

Es el mismo criterio de "exposición constante" de las ideas por activo.

**Pruebas múltiples.** Cada configuración es una prueba sobre la identidad del universo
(ids ordenados).
- El Sharpe deflactado cuenta **todas** las pruebas de cartera previas sobre universos
  parecidos (Jaccard ≥ 0,5). Así, cambiar un sector del universo no reinicia la cuenta.
- La SPA compara sólo las configuraciones sobre el universo exacto.
- Una cartera no entra en la memoria de sus constituyentes: es otra hipótesis nula.

**Señales incluidas.**
- `cross_sectional_momentum`: decide en los cierres de mes de calendario, salta el último
  mes, desempata por id ordenado y rechaza `top_k ≥ |universo|`.
- `inverse_volatility`: σ de los `lookback` días hasta t, con piso de 1e-4.

**Calibración (Monte Carlo, SC-001).** Con universos sin habilidad (medias iguales,
factor común ρ ≈ 0,6, inicios distintos, costos y 500 réplicas), la fracción declarada
significativa fue **1,4 %**.

Con medias distintas entre activos, el momentum "gana" por la dispersión transversal de
las medias aunque no haya persistencia (Lo y MacKinlay 1990; Conrad y Kaul 1998). Por
eso la nula usa medias iguales.

## 2. Regímenes del ciclo

**Estado.** Una serie mensual construida al cierre de cada mes sólo con información
publicada hasta ese cierre:

| Tipo | Definición |
|---|---|
| `threshold` | Una variable frente a un umbral |
| `spread` | Diferencia entre dos variables frente a un umbral. Faltante si alguna serie diaria tiene más de 5 días hábiles sin dato |
| `trend` | Cierre de mes de un activo bajo su media de n cierres |

**Convención (descriptiva, no es una estrategia).** El resultado es el exceso de retorno
del mes calendario siguiente al cierre del estado, sin rezago de ejecución ni costos. Se
estima `y_{t+1} = a + b·S_t + e` con errores **HC3**. La volatilidad cambia con el
régimen y puede haber pocos meses en el estado. Con datos mensuales sin solapamiento, la
persistencia del estado no autocorrelaciona los residuos.

**Pruebas múltiples entre experimentos.**
- **Memoria y Holm.** La clave de memoria es (activo, tipo, variables). Cada umbral es
  una variante. El Holm de la calibración usa m = hipótesis actuales + variantes previas
  con la misma clave + pruebas declaradas fuera de la bitácora.
- **Umbrales.** Se admiten mallas de umbrales; todas cuentan. Cada régimen declara su
  justificación (literatura o razón previa); sin ella, el resultado es exploratorio.
- **Mínimo de meses.** Si el estado tiene menos de `min_months` (24 por defecto) meses
  activo o inactivo, la combinación es no concluyente y no entra en la familia.

**Validación.**
- Sólo pasan las hipótesis **seleccionadas** en la calibración (p de Holm < 0,2α), y se
  prueban unilateralmente en el signo calibrado.
- La familia de regímenes usa 0,2α y la de estrategias (ideas, modelos y carteras) 0,8α:
  la FWER global queda ≤ α.

**Calibración (Monte Carlo, SC-004).** 9 activos × 3 estados (uno endógeno: la
tendencia del propio mercado), σ mensual ≈ 4,8 % y T = 300.
- Sin efecto: P(≥ 1 falso positivo tras Holm) = **4,4 %**.
- Potencia condicional a que el estado tenga al menos 24 meses, con Holm al 5 %:
  **79 %** con un efecto de 0,6σ y **92 %** con 0,75σ. Con el α de la familia de
  regímenes (1 %) baja a 68 % y 85 %.
- Un efecto de ~1 % mensual en un sector (≈ 0,2σ) es prácticamente indetectable con 25
  años de datos. "No significativo" no quiere decir "no existe".

## 3. Pruebas hechas fuera de la bitácora

`[[declared_prior_tests]]` registra una vez (idempotente) las pruebas de un análisis
exploratorio: tipo, universo o activos, número, periodo y huella del script. Cuentan en el
número de pruebas y en la detección de periodo ya visto. Es la forma honesta de
"regularizar" un análisis exploratorio antes de llevarlo al flujo registrado.

## Referencias

- Conrad, J. y Kaul, G. (1998). An anatomy of trading strategies. *Review of Financial
  Studies*.
- Estrella, A. y Mishkin, F. (1998). Predicting U.S. recessions: financial variables as
  leading indicators. *Review of Economics and Statistics*.
- Faber, M. (2007). A quantitative approach to tactical asset allocation. *Journal of
  Wealth Management*.
- Holm, S. (1979). A simple sequentially rejective multiple test procedure.
- Lo, A. y MacKinlay, C. (1990). When are contrarian profits due to stock market
  overreaction? *Review of Financial Studies*.
- MacKinnon, J. y White, H. (1985). Some heteroskedasticity-consistent covariance matrix
  estimators (HC3).
