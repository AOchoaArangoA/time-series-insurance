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
