# Procesos estocásticos, simulación y sensibilidades de tasas

Spec 007 (MVP). Módulos:

- `tsinsurance.stochastics`: tasa corta bajo ℙ, regímenes, valoración afín ℚ y curvas;
- `tsinsurance.simulation`: factores, escenarios y reducción de varianza;
- `tsinsurance.sensitivities`: instrumentos, KRD, Δ/Γ y atribución;
- `tsinsurance.portfolio_risk`: VaR/ES, backtesting, estrés y cobertura.

Estas capas **miden** riesgo. Una regla de asignación construida sobre sus salidas
(*tilt* de duración, valor relativo, cobertura dinámica) es una **idea** y pasa por
`tsinsurance experiment` con dos fases, costos y pruebas múltiples (FR-017). La
demostración está en `experiments/tesoro_riesgo/`.

## 1. Dos medidas: ℙ y ℚ

| Medida | Para qué | En el paquete |
|---|---|---|
| ℙ (física) | dinámica real de las tasas: escenarios, VaR, estrés | `VasicekP`, `CIRP`, `MarkovShortRate`, motores de `simulation` |
| ℚ (neutral al riesgo) | precios: valorar bonos en cada escenario | `zero_coupon`, `HullWhite`, `calibrate_q` |

El puente es el **precio de mercado del riesgo** λ (Girsanov, con σ_ℚ = σ_ℙ):

- en Vasicek, κ_ℚ = κ_ℙ y θ_ℚ = θ_ℙ − λσ/κ;
- en CIR, κ_ℚ = κ_ℙ + λσ y θ_ℚ = κ_ℙθ_ℙ/κ_ℚ.

Todo `Scenarios` declara con qué medida se simuló el estado (`state_measure`), con qué
fórmula se revalúa (`pricing_measure`) y el mapeo del estado a los nodos. El caso típico
es estado bajo ℙ y revaluación con la fórmula ℚ con λ calibrado.

## 2. Tasa corta bajo ℙ

| Modelo | dr | Transición exacta (paso Δ) |
|---|---|---|
| Vasicek | κ(θ − r)dt + σ dW | N(θ + (r − θ)φ, σ²(1 − φ²)/(2κ)), φ = e^{−κΔ} |
| CIR | κ(θ − r)dt + σ√r dW | 2c·r' ~ χ²'(4κθ/σ², 2c·r·φ), c = 2κ/(σ²(1 − φ)) |

- **Estimación por MV exacta.** En Vasicek es el MCO del AR(1). En CIR se maximiza la
  densidad χ² no central, partiendo del MCO de la discretización de Euler.
- **Simulación exacta.** Vasicek con normales; CIR con la mezcla de Poisson y gamma, que
  vale también si no se cumple Feller. No hay sesgo de Euler ni tasas negativas en CIR.
- **Sesgo de κ.** El MV de κ está sesgado hacia arriba, ≈ 4/T_años (Tang y Chen 2009).
  Con κ = 0,5 y 10 años de datos diarios, el sesgo medio es +0,51: κ̂ duplica al verdadero.
  - **IC por bootstrap paramétrico** con intervalos **básicos** (Hall 1992). El
    percentil hereda el sesgo: con él, la cobertura de κ era 49 %; con el básico, 93 %.
  - θ se re-simula con κ corregido por el sesgo del bootstrap, κ̃ = 2κ̂ − media(κ*),
    porque su dispersión depende de κ. Cobertura de θ: 74 % → 87 %.
  - Corrección por *jackknife* de Phillips y Yu (2009) con dos subbloques.
- **φ̂ ≥ 1**: κ no está identificado. Se advierte, no se simula y los diagnósticos se
  rechazan con un mensaje claro.
- **CIR con tasas ≤ 0** (^IRX en 2009-2015 y 2020-2021): error claro, salvo que se declare
  un piso numérico. Se reporta Feller (2κθ/σ²) con su IC.
- **Diagnósticos (FR-001b)**:
  - ADF/PP + KPSS y Zivot-Andrews sobre r_t;
  - Ljung-Box, ARCH-LM, Jarque-Bera y CUSUM sobre los residuos estandarizados;
  - pronóstico *walk-forward* a 1 mes frente al paseo aleatorio, con Diebold-Mariano HLN.

  Vasicek con σ constante falla ARCH en datos reales: es esperado y se reporta.

**Lectura con datos reales (Tesoro, 2026-10-30).**

- Desde 2009, φ̂ = 1,00009: κ no está identificado.
- Con 1998-2026, κ ≈ 0,07, con un IC de [0,04; 0,73], y r_t resulta I(1).
- La reversión a la media es un **supuesto** del modelo, no un hecho de los datos, y el
  pronóstico no supera al paseo aleatorio. Para escenarios de riesgo a corto plazo
  conviene un motor que no dependa de κ: histórica filtrada o factores.

## 3. Regímenes de Markov

r_t = c_s + φ_s·r_{t−1} + σ_s·ε, la discretización exacta de un Vasicek por régimen.

- Se estima con `statsmodels` (`MarkovRegression` con r_{t−1} exógeno y parámetros por
  régimen) y se **simula con la misma recursión**.
- Los regímenes se ordenan por σ_s, para que las etiquetas no se permuten entre
  estimaciones. Se comparan AIC y BIC contra el modelo de un régimen.
- **Sin fuga (I1):**
  - `params_estimation_end` acompaña a todo resultado;
  - una probabilidad filtrada en t con parámetros estimados con datos posteriores es
    **pseudo-filtrada** (descriptiva);
  - `RegimeFit.filter(r)` aplica el filtro de Hamilton con los parámetros fijos: la fila t
    no depende de datos posteriores a t;
  - el estrés por régimen (`regime_conditional_scenarios`) exige probabilidades filtradas
    punto en el tiempo, re-estimadas *walk-forward*.

## 4. Valoración afín ℚ y curvas

- **Fórmulas cerradas** de cupón cero para Vasicek y CIR (Brigo y Mercurio 2006).
- **Hull-White** como r = x + α(t), con α(t) = f^M(0, t) + σ²/(2a²)(1 − e^{−at})². No
  necesita ∂f/∂t. E[exp(−∫r)] = P^M(0, T) se verifica por Monte Carlo exacto (SC-005).
- **Frontera estricta con el paquete de curvas.** Aquí sólo están:
  - el `Protocol` `Curve` (`discount`, `zero_rate`, `forward`);
  - una `NodeCurve` **mínima**: lineal en ceros continuos, plana fuera de rango, forward
    continuo por la derecha. **No es de producción.**

  El ajuste paramétrico y el *bootstrapping* vienen del paquete hermano con la misma
  interfaz.
- **Calibración ℚ (`calibrate_q`)**: valora cada dato **según su convención**:
  - **^IRX**, tasa de descuento: precio = 1 − d·91/360;
  - **^FVX, ^TNX, ^TYX**, par semestral: y = 2(1 − P(T))/Σ P(t_i).

  Usa parámetros comunes en una ventana, con r_t observado en cada fecha. El modo
  `lambda` estima sólo λ, con su ee por el jacobiano; el modo `free` deja κ_ℚ y θ_ℚ libres
  como diagnóstico. Si el óptimo queda en la cota, se advierte que la curva no los
  identifica por separado.

## 5. Factores y escenarios

- **PCA de cambios en pb**, con las componentes rotuladas por su patrón de signos (nivel,
  pendiente, curvatura).
- **Diebold-Li con λ fija** = 0,0609 por mes. λ no se optimiza: hacerlo sería ajustar la
  curva, que es tarea del paquete hermano. Las cargas no son ortogonales, así que las
  varianzas por factor no son aditivas: se reporta el R² conjunto. Con 4 nodos y 3 factores
  queda 1 grado de libertad, y se advierte.
- **Motores de escenarios**:
  - **histórica**: cambios observados a h días en una ventana. Si se solapan, el IC usa
    bootstrap por bloques;
  - **histórica filtrada** (Barone-Adesi et al. 1999): innovaciones estandarizadas por
    EWMA (λ = 0,94) o GARCH(1,1), estimados **sólo con datos hasta** `asof` y reescalados a
    la volatilidad pronosticada. Con h > 1 se simula la trayectoria con la recursión de
    volatilidad (√h sólo como opción explícita con supuesto iid);
  - **Monte Carlo de factores**: normal o t de Student;
  - **Monte Carlo de la tasa corta**: un factor, que mueve la curva de forma rígida y
    **subestima** el riesgo de pendiente.
- **Reducción de varianza**:
  - antitéticas, sólo en motores simétricos (no en CIR);
  - variable de control en Vasicek con (r_T, ∫r) exacto. Control Y = ∫r con
    E[Y] = θT + (r₀ − θ)(1 − e^{−κT})/κ y β estimada en una muestra piloto independiente.
    SC-004: reducción de 159× y sin sesgo (3 ee).

## 6. Sensibilidades

Con la `NodeCurve`, z(t) = Σ w_i(t) z_i, con pesos triangulares w_i.

- **KRD analítica** (Ho 1992): KRD_i = Σ c_k t_k w_i(t_k) e^{−z_k t_k} / PV.
- **Σ KRD = duración efectiva de Fisher-Weil** (choque paralelo de los ceros continuos;
  no es la duración modificada en rendimiento). La diferencia relativa es menor que 1e-10
  y, frente a diferencias finitas de 1 pb, menor que 1e-6 (SC-006).
- **Convexidad** y **hessiana por nodos** analíticas; DV01 = PV·D·1 pb.
- **Δ y Γ por factor** con diferencias finitas centrales (Γ cruzado de 4 puntos).
- **Aproximación Δ y ΔΓ** frente a la **revaluación completa** en cada escenario. Ante
  10 pb, el error de ΔΓ es menor que el 1 % del de Δ.
- **Atribución de P&L**: proyección del cambio en los factores; P&L = Σ Δ_f·f + ½f'Γf +
  residuo.

## 7. Riesgo de cartera

- **VaR y ES empíricos** con IC por bootstrap iid o por bloques. Con Monte Carlo, el IC
  mide sólo el error de simulación, y se declara.
- **Backtesting** con pronósticos punto en el tiempo (información hasta t−1):
  - Kupiec POF;
  - Christoffersen (independencia y cobertura condicional);
  - duraciones de Christoffersen y Pelletier (Weibull con censura), más potente con
    pocas excepciones;
  - Z2 de Acerbi y Székely para el ES, con valor p simulado bajo la distribución
    predictiva **guardada** de cada día (unilateral; ignora el error de estimación).

  Con menos de 250 observaciones, **no concluyente**. SC-007 (oráculo, T = 1 000, VaR
  99 %): tamaño de Kupiec 6,4 %, potencia 100 % contra σ × 0,7 y 64 % contra σ × 0,9.
- **Estrés**: paralelo, empinamiento y aplanamiento con pivote, curvatura, ±kσ de cada
  factor, y condicionado a régimen.
- **Inmunización** por mínimos cuadrados con cotas sobre las KRD en dólares. Si las
  restricciones no son factibles, se reporta la exposición residual mínima.

## 8. Contrato de datos (aditivo)

- `rate_nodes` admite `rate_type` (`zero`, `par`, `discount`) y `compounding =
  discount_act360`.
- El manifiesto del paquete de insumos admite `tenor_years`, `rate_type` y `compounding`
  por serie.
- Los campos sin declarar no se serializan, así que la huella de los paquetes existentes
  no cambia.

## Referencias

- Acerbi, C. y Székely, B. (2014). Backtesting expected shortfall. *Risk*.
- Ang, A. y Bekaert, G. (2002). Short rate nonlinearities and regime switches. *Journal of
  Economic Dynamics and Control*, 26, 1243-1274.
- Barone-Adesi, G., Giannopoulos, K. y Vosper, L. (1999). VaR without correlations for
  portfolios of derivative securities. *Journal of Futures Markets*, 19(5), 583-602.
- Brigo, D. y Mercurio, F. (2006). *Interest Rate Models — Theory and Practice*, 2.ª ed.
- Christoffersen, P. (1998). Evaluating interval forecasts. *International Economic Review*,
  39(4), 841-862.
- Christoffersen, P. y Pelletier, D. (2004). Backtesting value-at-risk: a duration-based
  approach. *Journal of Financial Econometrics*, 2(1), 84-108.
- Cox, J., Ingersoll, J. y Ross, S. (1985). A theory of the term structure of interest
  rates. *Econometrica*, 53(2), 385-407.
- Diebold, F. y Li, C. (2006). Forecasting the term structure of government bond yields.
  *Journal of Econometrics*, 130(2), 337-364.
- Glasserman, P. (2003). *Monte Carlo Methods in Financial Engineering*. Springer.
- Hall, P. (1992). *The Bootstrap and Edgeworth Expansion*. Springer.
- Hamilton, J. (1989). A new approach to the economic analysis of nonstationary time
  series. *Econometrica*, 57(2), 357-384.
- Ho, T. (1992). Key rate durations. *Journal of Fixed Income*, 2(2), 29-44.
- Kupiec, P. (1995). Techniques for verifying the accuracy of risk measurement models.
  *Journal of Derivatives*, 3(2), 73-84.
- Litterman, R. y Scheinkman, J. (1991). Common factors affecting bond returns. *Journal
  of Fixed Income*, 1(1), 54-61.
- Phillips, P. C. B. y Yu, J. (2009). Simulation-based estimation of contingent-claims
  prices. *Review of Financial Studies*, 22(9), 3669-3705.
- Tang, C. Y. y Chen, S. X. (2009). Parameter estimation and bias correction for
  diffusion processes. *Journal of Econometrics*, 149(1), 65-81.
- Vasicek, O. (1977). An equilibrium characterization of the term structure. *Journal of
  Financial Economics*, 5(2), 177-188.
