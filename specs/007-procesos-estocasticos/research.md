# Research: Procesos estocásticos, simulación y sensibilidades (spec 007)

## R1. Tasa corta bajo ℙ

| Modelo | dr | Transición exacta | Estimación |
|---|---|---|---|
| Vasicek | κ(θ − r)dt + σ dW | Gaussiana: media θ + (r₀−θ)e^{−κΔ}; var σ²(1−e^{−2κΔ})/(2κ) | MV exacta = AR(1) gaussiano; parámetros por transformación; errores por método delta |
| CIR | κ(θ − r)dt + σ√r dW | χ² no central escalada (`scipy.stats.ncx2`) | MV exacta con `ncx2.logpdf`; inicio con OLS de la discretización de Euler; errores por la hessiana numérica |

**Simulación exacta.** Vasicek con normales; CIR con `ncx2.rvs` o, si 4κθ/σ² es pequeño,
con la mezcla de Poisson y gamma. Así se evita el sesgo de Euler y los valores negativos.

**Datos.** ^IRX (Yahoo) o DTB3 (FRED). Son tasas de descuento en porcentaje: se convierten
a tasa continua equivalente. La conversión se documenta.

**Tasas ≤ 0** (2020-2021 con ^IRX): CIR no es aplicable. Se advierte y se ofrece Vasicek
o un desplazamiento declarado (*shifted* CIR).

## R2. Regímenes de Markov

**Decisión.** `statsmodels.tsa.regime_switching.MarkovAutoregression` sobre r_t con AR(1)
y parámetros por régimen. Es equivalente a Vasicek discreto con régimen en θ (constante),
en κ (coeficiente AR) y en σ (`switching_variance`). Reporta:
- probabilidades filtradas (`filtered_marginal_probabilities`), punto en el tiempo;
- probabilidades suavizadas, descriptivas;
- la matriz de transición y las duraciones esperadas.

**Simulación.** Primero la cadena de Markov y después el AR(1) del régimen vigente, con
semilla explícita.

**Punto en el tiempo.** Las probabilidades filtradas en t cambian sólo si cambian los
**parámetros**. Al usar el modelo para decidir, se estima con datos hasta la fecha de
decisión: re-estimación walk-forward o parámetros fijados en la calibración. La prueba
verifica que la probabilidad filtrada en t, con parámetros fijos, no depende de datos
posteriores a t.

## R3. Valoración ℚ (afines)

P(t, T) = A(τ)·exp(−B(τ)·r_t), con las fórmulas estándar:
- **Vasicek**: B = (1 − e^{−aτ})/a; ln A = (θ − σ²/(2a²))(B − τ) − σ²B²/(4a).
- **CIR**: Cox, Ingersoll y Ross (1985), con γ = √(a² + 2σ²).
- **Hull-White** (Brigo y Mercurio 2006): θ(t) se elige para reproducir la curva inicial.
  P(t, T) = (P^M(0,T)/P^M(0,t))·exp(B(t,T)·f^M(0,t) − (σ²/(4a))(1 − e^{−2at})·B² − B·r_t).

**Calibración ℚ.** Mínimos cuadrados en rendimientos en los nodos (scipy `least_squares`
con límites), por fecha o con parámetros comunes en una ventana. Se reportan el ajuste por
nodo y la prima de riesgo implícita: diferencia entre θ_ℚ y θ_ℙ, o λ en Vasicek.

**Interfaz de curva (frontera estricta).** El `Protocol` `Curve` expone
`discount(t)`, `zero_rate(t)` y `forward(t)`. El paquete trae sólo `NodeCurve`: lineal en
tasas cero continuas y plana fuera de rango. **No es apta para producción**; el forward de
`NodeCurve` es discontinuo en los nodos. Las curvas de producción vienen del paquete
hermano con la misma interfaz.

**Rendimientos de Yahoo.** ^IRX es tasa de descuento; ^FVX, ^TNX y ^TYX son rendimientos
par (semestrales). Se convierten a tasa cero continua de forma **aproximada**
(par ≈ cero, que es sesgada en plazos largos con pendiente). Queda documentado.

## R4. Factores de curva y simulación

- **PCA sobre cambios** (no niveles) de rendimientos en nodos, con la covarianza de la
  ventana. Las cargas de los primeros componentes se rotulan (nivel, pendiente, curvatura)
  según su patrón de signos.
- **Diebold-Li con λ fija** (0,0609 con plazos en meses): regresión MCO en cada fecha
  sobre las cargas de Nelson-Siegel. **No** se optimiza λ, para respetar la frontera. Con
  4 nodos, 3 factores dejan 1 grado de libertad, y se advierte.
- **Motores de escenarios**:
  - **histórica**: cambios a h días con ventana móvil;
  - **histórica filtrada** (Barone-Adesi 1999): innovaciones estandarizadas con EWMA
    (λ = 0,94) o GARCH(1,1) de `arch`, reescaladas a la volatilidad del día de análisis,
    sólo con datos hasta ese día;
  - **Monte Carlo de factores**: normal multivariada o t de Student con la covarianza de
    los factores;
  - **Monte Carlo de la tasa corta**: con o sin regímenes.
- **Reducción de varianza**:
  - **antitéticas**: pares Z y −Z;
  - **variable de control**: el precio cerrado del cupón cero o de una cartera lineal,
    con β óptima estimada en una muestra piloto independiente para no sesgar.

  El factor de reducción es var(MC simple)/var(MC reducido), con igual número de
  evaluaciones.

## R5. Instrumentos y sensibilidades

- **Instrumento**: bono de flujos fijos con fechas en años y cupones. La cartera es una
  lista de (instrumento, cantidad).
- **Valoración**: PV = Σ c_k·D(t_k) con la curva (interfaz) o con P(t, T) de un modelo
  afín.
- **Sensibilidades**:
  - **duración modificada y convexidad** analíticas en rendimiento; DV01 = −∂PV/∂y·0,0001;
  - **KRD por nodo**: diferencias finitas centrales con choque triangular en el nodo
    (Ho 1992), paso de 1 pb declarado; Σ KRD = duración bajo choque paralelo (SC-006);
  - **por factor**: Δ_f = ∂PV/∂f y Γ_fg por diferencias finitas centrales sobre la curva
    reconstruida con las cargas del PCA;
  - **aproximaciones**: ΔPV ≈ Δ·Δf (+ ½ Δfᵀ Γ Δf), con el error frente a la revaluación
    completa en cada escenario;
  - **atribución de P&L**: Δ_f·Δf por factor, más el término cuadrático y el residuo
    contra la revaluación completa.
- **Por qué diferencias finitas y no diferenciación automática**: no agrega dependencias.
  El paso y el esquema se declaran y se verifican contra las fórmulas analíticas.

## R6. Riesgo, backtesting y cobertura

- **VaR y ES** empíricos sobre los escenarios (cuantil con interpolación declarada), con
  IC por bootstrap de los escenarios.
- **Backtesting** con pronóstico rodante a 1 día, con información hasta t−1:
  - Kupiec POF (razón de verosimilitud);
  - Christoffersen (independencia y cobertura condicional);
  - Acerbi-Székely Z2, con valor p por simulación bajo H0 usando la distribución
    pronosticada.

  Con menos de 250 observaciones, no concluyente.
- **Estrés**:
  - choques en unidades de factor (k desviaciones) o en puntos básicos sobre los nodos;
  - empinamiento y aplanamiento con un pivote declarado;
  - condicionados a régimen: choques muestreados de los días con probabilidad filtrada del
    régimen > 0,8.
- **Cobertura**: mínimos cuadrados con restricciones (scipy `lsq_linear`), sobre la matriz
  de exposiciones de los instrumentos de cobertura × factores. Se reportan los residuos.

## R7. Cautela causal (FR-017)

Este módulo **mide** riesgo. Toda regla de asignación que use sus salidas (*tilt* de
sensibilidades, valor relativo) es una idea y entra por `[[ideas]]` o `[[portfolios]]`,
con dos fases, costos y pruebas múltiples. La documentación lo exige.

## R8. Calibración Monte Carlo

| Criterio | Diseño |
|---|---|
| SC-001 | 500 trayectorias por modelo, T = 2 500, Δ = 1/252; cobertura de los IC |
| SC-003 | 2 regímenes con p₁₁ = 0,98 y p₂₂ = 0,95, distintas σ y θ; T = 2 000; 200 réplicas (estimación lenta) |
| SC-004 | Cupón cero a 10 años bajo Vasicek ℚ; 10 000 trayectorias; variable de control = el mismo bono con la integral exacta de r (esquema de Euler pareado) |
| SC-007 | Retornos t de Student con GARCH; VaR al 99 %; modelo correcto frente a σ × 0,7; T = 1 000; 500 réplicas |

## R9. Correcciones tras la revisión econométrica del diseño (2026-11-26)

### Bloqueantes

**B1 — variable de control (SC-004).**
- Se simula (r_T, Y = ∫₀ᵀ r dt) de forma **exacta**: en Vasicek son conjuntamente
  gaussianos, con media y covarianza cerradas.
- El estimador es el factor de descuento exp(−Y). La variable de control es **Y**, cuya
  media cerrada es E[Y] = θτ + (r₀ − θ)·B(τ). Un precio cerrado es una constante y no sirve
  como control.
- β se estima en una muestra piloto independiente.
- Las antitéticas sólo se ofrecen en motores gaussianos o t simétricos. En CIR se usan
  uniformes U y 1 − U en la inversa o no se ofrecen (se declara).
- SC-004 exige que el precio estimado esté dentro de 3 ee del cerrado (sin sesgo de
  discretización, porque la simulación es exacta) y una reducción de varianza ≥ 5×.

**B2 — SC-001 y el sesgo de κ.**
- El estimador de MV de κ tiene un sesgo de orden ≈ 4/T_años (Tang y Chen 2009; Phillips y
  Yu 2009).
- Los intervalos de κ y θ se calculan con un **bootstrap paramétrico** (B = 499), y se
  ofrece la corrección de sesgo por *jackknife* (Phillips y Yu 2009).
- φ̂ ≥ 1 (sin reversión a la media) se maneja de forma explícita: κ no identificado,
  advertencia y alternativa de paseo aleatorio.
- **SC-001 rehecho:**
  - cobertura del IC de **σ** entre 92 % y 98 %;
  - para κ y θ se reportan el sesgo y la cobertura con un proceso generador fijado
    (κ = 0,5, θ = 0,04, σ = 0,01, Δ = 1/252);
  - la cobertura de 92-98 % para κ sólo se exige con κT ≥ 50.

**B3 — diagnósticos y validación fuera de muestra** (FR-001b nuevo).
- **Sobre r_t:** ADF/PP + KPSS y Zivot-Andrews, con la regla jerárquica existente.
- **Sobre los residuos estandarizados:** Ljung-Box, ARCH-LM, Jarque-Bera y CUSUM.
- **Validación walk-forward** del pronóstico a 1 mes frente al paseo aleatorio, con
  Diebold-Mariano HLN.
- **Número de regímenes** (1 o 2) por AIC y BIC.
- Diagnósticos no superados ⇒ marca en el resultado. Vasicek con σ constante fallará
  ARCH: se espera y se reporta.

**B4 — regímenes coherentes entre estimación y simulación.**
- Se usa `MarkovRegression` con r_{t−1} como regresor exógeno, `switching_exog=True` y
  `switching_variance=True`: r_t = c_s + φ_s·r_{t−1} + σ_s·ε. Se interpreta como
  θ_s = c_s/(1 − φ_s) y κ_s = −ln(φ_s)/Δ.
- La simulación usa **exactamente** esa recursión: es la discretización exacta de Vasicek
  en cada régimen con paso Δ.
- **Identificación:** varias inicializaciones (`search_reps`) y los regímenes se ordenan
  por σ_s para evitar la permutación de etiquetas entre estimaciones walk-forward.

### Importantes

**I1 — probabilidades filtradas sin fuga.**
- Todo resultado de regímenes declara `params_estimation_end`. Una probabilidad filtrada
  en t con parámetros estimados con datos posteriores a t se rotula
  **pseudo-filtrada (descriptiva)**.
- El estrés por régimen y el backtesting re-estiman walk-forward con frecuencia mensual
  declarada.
- La prueba de anticipación reutiliza `backtest/lookahead.py` sobre la función "datos →
  probabilidad filtrada en t con re-estimación hasta t".

**I2 — calibración ℚ correcta con los datos disponibles.**
- **Convenciones de los datos:**
  - **^IRX** (descuento a 13 semanas): precio = 1 − d·n/360 con n = 91; tasa continua
    r = −ln(precio)·365/n;
  - **^FVX, ^TNX, ^TYX** son rendimientos par semestrales. El modelo **valora el bono
    par**: y_par = 2(1 − P(T))/Σ P(t_i), con t_i semestrales. Así se calibra al dato
    observado y **no** se trata el par como cero.
- **Identificación:** parámetros ℚ comunes en una ventana (p. ej. 12 meses de datos
  diarios), con r_t de cada fecha fijado en la tasa corta observada (^IRX).
- **Girsanov:**
  - σ_ℚ = σ_ℙ por construcción, y se reporta si la calibración libre los separa
    (diagnóstico);
  - **Vasicek:** κ_ℚ = κ_ℙ y θ_ℚ = θ_ℙ − λσ/κ, con λ el precio de mercado del riesgo;
  - **CIR:** κ_ℚ = κ_ℙ + λσ y θ_ℚ = κ_ℙθ_ℙ/κ_ℚ.

  Se reportan λ y su error estándar por el jacobiano.

**I3 — Hull-White sin θ(t).**
- Se simula r(t) = x(t) + α(t), con dx = −a·x dt + σ dW y
  α(t) = f^M(0, t) + σ²/(2a²)·(1 − e^{−at})². No se necesita ∂f/∂t.
- El forward de `NodeCurve` se define continuo por la derecha.
- SC-005 rehecho: el precio Monte Carlo de cupones cero reproduce P^M(0, T) dentro de
  3 ee. La fórmula cerrada en t = 0 es una identidad y no se usa como criterio.

**I4 — KRD y duración.**
- **KRD analítica:** KRD_i = Σ_k c_k·t_k·w_i(t_k)·e^{−z(t_k)·t_k}/PV, con funciones
  triangulares w_i que suman 1. En los extremos (13 semanas y 30 años) se extienden
  planas.
- La comparación es contra la **duración efectiva (Fisher-Weil)** ante un choque paralelo
  de las tasas cero, no contra la duración modificada en rendimiento.
- La tolerancia es **relativa** 1e-10 (analítico frente a analítico). Frente a diferencias
  finitas centrales con 1 pb, la tolerancia relativa es 1e-6, con el mismo esquema en
  ambos lados.

**I5 — histórica filtrada y horizonte.**
- La varianza inicial del EWMA y los parámetros GARCH se estiman **sólo** con datos
  anteriores a la fecha de análisis.
- Los cambios solapados a h días usan bootstrap **por bloques** para el IC.
- El IC sobre escenarios de Monte Carlo mide **sólo** el error de simulación (se declara).
- El horizonte h > 1 día se obtiene simulando la trayectoria. El escalado por √h queda
  como opción explícita, con su supuesto de iid declarado.

**I6 — backtesting.**
- Z2 guarda la distribución predictiva completa en cada t (los escenarios) y simula su
  valor p bajo esa distribución. Es unilateral e ignora el error de estimación; se
  documenta.
- **SC-007:**
  - el modelo correcto es el **oráculo**: los mismos parámetros del proceso generador;
  - las alternativas son σ × 0,7 y σ × 0,9 (potencia reportada);
  - se agrega la prueba por duraciones de Christoffersen y Pelletier (2004).

**I7 — contrato de nodos.**
- Extensión aditiva y versionada de `rate_nodes`: columnas opcionales `rate_type`
  (`zero`, `par`, `discount`) y `compounding` (`continuous`, `semiannual`, `annual`,
  `discount_act360`).
- Se coordina con el paquete hermano mediante el JSON Schema publicado. Las series del
  paquete de insumos pueden declarar `tenor_years`, `rate_type` y `compounding` en el
  manifiesto.

**I8 — dos medidas en los escenarios.**
- `Scenarios` declara `state_measure` (con qué medida se simuló el estado) y
  `pricing_measure` (con qué fórmula se revalúa), junto con el mapeo explícito del estado
  (r_t o factores) a los nodos.
- **Caso típico:** estado bajo ℙ y revaluación con la fórmula ℚ con λ calibrada.

**I9 — rendimiento.**
- Re-estimación **mensual** de Markov y GARCH en el backtesting; los parámetros se
  mantienen durante el mes.
- SC-008 se evalúa así y la frecuencia se declara en el resultado.

### Menores

- **M1 — CIR con tasas casi nulas.** Prueba con valores cero (`ncx2.logpdf` se degenera):
  se usa un piso numérico declarado o la advertencia de inaplicabilidad. La condición de
  Feller se reporta con su IC. Las dos simulaciones de CIR (χ² no central y mezcla de
  Poisson y gamma) son **exactas**. Las fechas irregulares usan Δ real en días hábiles y
  se declara.
- **M2 — datos de ^TYX.** Se verifica la serie en 2002-2006 (el bono a 30 años no se
  emitió), la alineación de feriados y las unidades. Los huecos se tratan como faltantes y
  se informan.
- **M3 — PCA.** Covarianza en puntos básicos. Γ cruzado con un esquema de 4 puntos.
  Diebold-Li con 4 nodos y 3 factores deja 1 grado de libertad: se reporta el residuo por
  nodo.
- **M4 — parámetros explícitos.** λ_EWMA, el umbral de régimen (0,8) y el mínimo de
  observaciones (250).
- **M5 — cobertura.** El objetivo de 1e-8 sólo se exige si las restricciones son
  factibles; si no, se reporta la exposición residual mínima.
- **M6 — prueba por duraciones** de Christoffersen y Pelletier, por la baja potencia de
  Christoffersen con pocas excepciones.

### Constitution Check corregido

El plan agrega:
- I (diagnósticos: B3);
- II (fuga: I1, I5);
- IV-bis (contrato de nodos: I7);
- V (API tipada con resultados inmutables con `summary()`);
- el benchmark de pronóstico (paseo aleatorio con DM).

`contracts/python-api.md` se agrega en esta corrección.
