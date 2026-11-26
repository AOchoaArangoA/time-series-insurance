# Datos de panel: efectos fijos, efectos aleatorios y diferencias en diferencias

Spec 006. Módulo `tsinsurance.panel` (extra opcional: `pip install "tsinsurance[panel]"`,
que instala `linearmodels`) y bloques `[[panels]]` de los experimentos.

Referencia principal: M. Facure, *Causal Inference for the Brave and True*, cap. 13
(diferencias en diferencias) y cap. 14 (panel y efectos fijos). Para efectos aleatorios,
Hausman y Mundlak, el libro no tiene capítulo: se sigue a Wooldridge (2010, cap. 10) y a
Mundlak (1978).

## 1. Qué estima cada modelo

Modelo: y_it = x_it'β + α_i + λ_t + e_it.

| Estimador | `estimator` | Supuesto clave sobre α_i | Qué elimina |
|---|---|---|---|
| MCO agrupado | `pooled` | α_i no correlacionado con x | nada |
| Efectos fijos (*within*) | `fe` | ninguno | confusores constantes en el tiempo |
| Dos vías | `twfe` | ninguno | lo constante por unidad y lo común por periodo |
| Primeras diferencias | `fd` | ninguno | lo constante por unidad |
| Efectos aleatorios (GLS) | `re` | α_i no correlacionado con x | nada (es más eficiente si el supuesto vale) |

**Lo que los efectos fijos NO resuelven** (Facure, cap. 14):

- confusores que **cambian** en el tiempo;
- causalidad inversa (el resultado de hoy cambia el regresor de mañana);
- efectos heterogéneos: β es un promedio ponderado por la varianza *within*.

Con efectos de tiempo, un regresor común a todas las unidades (x_t: tasas, VIX) queda
**absorbido**. Sólo se identifican las interacciones x_t × D_i: el efecto **diferencial**
de las unidades con la característica D frente a las demás, no el efecto total. El
paquete detecta los regresores absorbidos y los que tienen poca variación *within*.

## 2. Inferencia con pocas unidades y un factor común

Un panel sectorial típico tiene N = 11 unidades, T de 36 a 300 meses y un factor de
mercado que correlaciona a todas las unidades.

- **Principal: Driscoll-Kraay (1998).** Suma los *scores* por periodo, S_t = Σ_i x̃_it·ẽ_it,
  y aplica un HAC de Bartlett con L = ⌊4(T/100)^(2/9)⌋. Es robusto a dependencia
  transversal arbitraria y a autocorrelación. Coincide con `plm::vcovSCC(type = "HC0")` con
  error relativo menor a 1e-8 (`tests/reference/`).
- **Corrección de muestra finita** (hallazgos del Monte Carlo, R9 y R10). El diseño
  preveía valores críticos t(T−1). La simulación de SC-004 mostró que sobre-rechazan:
  ~9 % unilateral al 5 % con T = 36. El paquete aplica dos correcciones:
  1. **grados de libertad**: los efectos fijos absorben N + (T − 1) parámetros. El error
     se multiplica por √c, con c = n / (n − N − (T−1)·[efectos de tiempo] − k);
  2. **valor p**:
     - en los experimentos se usa un **wild bootstrap restringido por bloques de
       periodos** (`dk_wild_bootstrap`). Impone H0, multiplica los residuos por signos
       comunes a todas las unidades en bloques de L + 1 periodos (conserva la dependencia
       transversal y la autocorrelación de corto plazo) y recalcula el mismo t,
       condicionado a los X observados;
     - `fit_panel` reporta el valor p analítico con la referencia **fixed-b** (Kiefer y
       Vogelsang 2005), simulada con el mismo T y L. Es correcta con scores
       homogéneos, pero con un regresor persistente y errores autocorrelacionados
       sobre-rechaza (hasta 9,5 %).

  Resultado: el tamaño unilateral del bootstrap queda en 3-7 % en todas las celdas de
  SC-004, incluida una de reserva con errores AR(1) y t₅, regresor correlacionado con el
  factor y panel desbalanceado. El error de `plm` sin corregir queda en
  `diagnostics["driscoll_kraay_plm_hc0"]`.
- **Estabilidad de cada coeficiente**: Nyblom-Hansen sobre los scores DK acumulados
  (`score_stability`). Vale con efectos de tiempo, donde el CUSUM de la media de los
  residuos sólo vería el factor absorbido.
- **Sensibilidad: wild cluster bootstrap restringido** por unidad (WCR; Cameron, Gelbach
  y Miller 2008). Con G ≤ 12 enumera las 2^G combinaciones de Rademacher; en otro caso usa
  pesos de Webb con semilla. Supone clústeres **independientes**, lo que el factor común
  viola: sólo se reporta, nunca decide.
- **G₁**: número de unidades con D_i = 1 en una interacción. Con G₁ < 2 el coeficiente es
  **no concluyente** (Conley y Taber 2011): con una sola unidad tratada ni los errores
  agrupados ni el bootstrap son válidos.
- Con `cov = "clustered_entity"` y menos de 30 unidades, se advierte y se reporta DK como
  alternativa.

## 3. ¿Efectos fijos o aleatorios?

- **Mundlak / efectos aleatorios correlacionados** (`mundlak_test`). Se agregan a un
  modelo RE o agrupado las medias por unidad de los regresores (y, con dos vías o paneles
  desbalanceados, las medias de las dummies de tiempo; Wooldridge 2021). H0: sus
  coeficientes son cero, y entonces RE es consistente. Es un Wald con error agrupado,
  F(q, G−1) con pocos grupos. **La recomendación se basa en esta prueba.**
- **Hausman clásico** (`hausman_test`): sólo es válido con errores homocedásticos y RE
  eficiente. Usa la escala `sigmamore` para evitar estadísticos negativos.
- Con N pequeño y T grande, θ ≈ 1 (RE ≈ FE) y la varianza de unidad es poco confiable: se
  advierte.
- En un experimento, Mundlak se calcula sólo con los regresores que varían entre
  unidades. Las medias por unidad de un x_t común son casi constantes.

## 4. Diagnósticos del Principio I (`panel_diagnostics`)

| Diagnóstico | Qué detecta | Consecuencia |
|---|---|---|
| Wooldridge (2010, §10.6.3) | AR(1) de e_it: en FD, corr(Δe_t, Δe_{t−1}) = −0,5 bajo H0; F(1, G−1) | usar DK |
| CD de Pesaran (2004) | dependencia transversal (residuos **sin** efectos de tiempo; Juodis y Reese 2022) | usar DK |
| ADF + KPSS de cada regresor | regresor I(1) ⇒ regresión desbalanceada | exploratorio |
| ADF + KPSS de y por unidad | variable dependiente no estacionaria | exploratorio |
| ARCH-LM por unidad (residuos del modelo, de dos vías si hay efectos de tiempo) | heterocedasticidad condicional en la mayoría | exploratorio |
| CUSUM (sin efectos de tiempo) o Nyblom-Hansen por coeficiente | inestabilidad de los parámetros | exploratorio |
| AR(1) del regresor y correlación de su innovación con el residuo (con el choque diferencial tratadas − controles en una interacción) | ρ > 0,9 y \|corr\| > 0,3 ⇒ sesgo tipo Stambaugh en panel (Hjalmarsson 2008) | exploratorio |

## 5. Diferencias en diferencias (`diff_in_diff`)

- ATET por TWFE con D_it = tratado_i × post_t (Facure, cap. 13).
- Estudio de evento con *leads* y *lags* (el periodo −1 es la referencia; los extremos se
  agrupan) y una prueba de Wald conjunta de los *leads* = 0.
- **No rechazar la prueba de tendencias previas NO prueba tendencias paralelas**: puede
  ser falta de potencia, y condicionar el análisis a su resultado sesga la inferencia
  (Roth 2022). SC-005 reporta su tamaño y su potencia contra una violación que sesga el
  ATET en ~1 ee.
- **No anticipación**: la fecha del evento debe ser la del anuncio.
- **Una sola unidad tratada**: inferencia por permutación con placebos sobre cada
  control, **estudentizados** por la desviación estándar previa de cada unidad (Ferman y
  Pinto 2019): p = (1 + #{|placebo| ≥ |ATET|}) / (1 + n_controles). El p mínimo
  alcanzable es 1/(1 + n_controles): si supera α, la prueba no puede rechazar y se
  advierte. La prueba de tendencias previas también es por permutación.
- **Pocas tratadas (2 a 29)**: la prueba previa agrupada se reporta como F(q, G−1).
- **Adopción escalonada**: el TWFE está sesgado con efectos heterogéneos
  (Goodman-Bacon 2021). Se advierte; los estimadores robustos (Callaway-Sant'Anna,
  HonestDiD) están en la hoja de ruta.

## 6. Paneles en experimentos (`[[panels]]`)

```toml
[[panels]]
name = "tasas_vix"
units = ["XLB", "XLE", "XLF", "XLP", "XLU", "XLV"]
regressors = ["^TNX", "^VIX"]                 # series del paquete, punto en el tiempo
transforms = { "^TNX" = "diff", "^VIX" = "diff" }   # level | diff (cambio mensual)
characteristics = { tasas = ["XLF", "XLU"], defensivo = ["XLP", "XLU", "XLV"] }
interactions = [["^TNX", "tasas"], ["^VIX", "defensivo"]]
estimator = "twfe"                            # pooled | fe | twfe | fd | re
cov = "driscoll_kraay"
bootstrap_draws = 9999                        # WCR (sensibilidad)
min_months = 36
hypotheses = [{ coef = "^TNX:tasas", sign = "-" }, { coef = "^VIX:defensivo", sign = "+" }]
justification = "razón económica fijada antes de estimar"
```

- **Variable dependiente**: exceso de retorno del mes siguiente a la decisión. Es la misma
  convención descriptiva que los regímenes, sin rezago de ejecución ni costos: no es una
  estrategia.
- **Punto en el tiempo**: los regresores toman el último valor publicado al cierre de mes.
  Las series diarias con más de 5 días hábiles de antigüedad quedan faltantes. Las
  unidades sin datos hasta el corte se omiten y se advierte.
- **Dos fases**:
  - la calibración (`experiment run`) estima con `Bundle.as_of(train_end)`. Las hipótesis
    están **pre-registradas con su signo**: no se seleccionan, y todas las concluyentes
    pasan a la validación;
  - la validación (`experiment validate`) re-estima **sólo con los meses posteriores al
    corte**, con el estimador, el error, el ancho de banda declarado (o su regla), B y la
    semilla congelados. Cada hipótesis se prueba unilateralmente;
  - se reporta el **efecto mínimo detectable** ex ante: (z_{1−α_p/m} + z_{0,8}) × el ee
    de la calibración reescalado al T de la validación, con α_p el α de la familia y m sus
    hipótesis. Si el efecto de la calibración es menor, se marca `low_power`; si el MDE no
    es finito, `low_power = None`;
  - los diagnósticos se recalculan en la validación.
- **Memoria**:
  - clave: (variable dependiente, universo con Jaccard ≥ 0,5);
  - variante: (regresores, transformaciones, interacciones con su composición,
    estimador, error, ancho de banda, hipótesis con signo), más el universo y la ventana.
    Sólo una re-ejecución idéntica no cuenta; cualquier otra combinación ya registrada
    entra en la m del Holm de la calibración **y de la validación**;
  - las líneas `panel` cuentan en la detección de "periodo ya visto" para cada unidad.
- **Reparto de α** (revisión B1): estrategias 0,7α, regímenes 0,15α y paneles 0,15α,
  renormalizado entre las familias presentes (si sólo hay paneles, reciben α). Se congela
  en `frozen.alpha_split` y la validación lee ese valor. Las calibraciones previas a esta
  versión guardaron 0,8α / 0,2α y se respetan.

## Referencias

- Conley, T. y Taber, C. (2011). Inference with "difference in differences" with a small
  number of policy changes. *Review of Economics and Statistics*, 93(1), 113-125.
- Cameron, A. C., Gelbach, J. y Miller, D. (2008). Bootstrap-based improvements for
  inference with clustered errors. *Review of Economics and Statistics*, 90(3), 414-427.
- Driscoll, J. y Kraay, A. (1998). Consistent covariance matrix estimation with spatially
  dependent panel data. *Review of Economics and Statistics*, 80(4), 549-560.
- Facure, M. (2022). *Causal Inference for the Brave and True*, cap. 13-14.
- Goodman-Bacon, A. (2021). Difference-in-differences with variation in treatment
  timing. *Journal of Econometrics*, 225(2), 254-277.
- Hjalmarsson, E. (2008). The Stambaugh bias in panel predictive regressions. *Finance
  Research Letters*, 5(1), 47-58.
- Juodis, A. y Reese, S. (2022). The incidental parameters problem in testing for
  remaining cross-section correlation. *Journal of Business & Economic Statistics*,
  40(3), 1191-1203.
- Ferman, B. y Pinto, C. (2019). Inference in differences-in-differences with few
  treated groups and heteroskedasticity. *Review of Economics and Statistics*, 101(3),
  452-467.
- Hansen, B. (1992). Testing for parameter instability in linear models. *Journal of
  Policy Modeling*, 14(4), 517-533.
- Kiefer, N. y Vogelsang, T. (2005). A new asymptotic theory for
  heteroskedasticity-autocorrelation robust tests. *Econometric Theory*, 21(6), 1130-1164.
- Kline, P. y Santos, A. (2012). A score based approach to wild bootstrap inference.
  *Journal of Econometric Methods*, 1(1), 23-41.
- MacKinnon, J. y Webb, M. (2017). Wild bootstrap inference for wildly different cluster
  sizes. *Journal of Applied Econometrics*, 32(2), 233-254.
- Mundlak, Y. (1978). On the pooling of time series and cross section data.
  *Econometrica*, 46(1), 69-85.
- Pesaran, M. H. (2004). General diagnostic tests for cross section dependence in panels.
  CESifo WP 1229.
- Nyblom, J. (1989). Testing for the constancy of parameters over time. *Journal of the
  American Statistical Association*, 84(405), 223-230.
- Roth, J. (2022). Pretest with caution: event-study estimates after testing for parallel
  trends. *American Economic Review: Insights*, 4(3), 305-322.
- Shao, X. (2010). The dependent wild bootstrap. *Journal of the American Statistical
  Association*, 105(489), 218-235.
- Vogelsang, T. (2012). Heteroskedasticity, autocorrelation, and spatial correlation
  robust inference in linear panel models with fixed-effects. *Journal of Econometrics*,
  166(2), 303-319.
- Wooldridge, J. (2010). *Econometric Analysis of Cross Section and Panel Data*, 2.ª ed.,
  MIT Press, cap. 10.
- Wooldridge, J. (2021). Two-way fixed effects, the two-way Mundlak regression, and
  difference-in-differences estimators. SSRN 3906345.
