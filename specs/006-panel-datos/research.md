# Research: Datos de panel (spec 006)

## R1. Motor y referencias

**Decisión.** Usar `linearmodels` 7.x (PanelOLS, RandomEffects, FirstDifferenceOLS,
PooledOLS; K. Sheppard). Facure lo usa en el capítulo 14, y el autor es el mismo de
`arch`, que ya es dependencia. Lo que `linearmodels` no cubre (o cubre distinto) se
implementa y se verifica:

| Elemento | Origen | Verificación |
|---|---|---|
| FE (unidad, dos vías), FD, RE, MCO agrupado | `linearmodels` | `plm` de R (si está instalado) y *within* manual / dummies |
| Errores agrupados (1 y 2 vías) | `linearmodels` | `sandwich::vcovCL` / `plm::vcovHC` |
| Driscoll-Kraay | `linearmodels` (`kernel`), con ancho de banda declarado | `plm::vcovSCC` |
| Wild cluster bootstrap (restringido, Rademacher; Webb con < 12 grupos) | propio | Monte Carlo de tamaño (SC-004); comparación con `fwildclusterboot` si está disponible |
| Mundlak / CRE | propio (regresión con medias por unidad y prueba de Wald con error agrupado) | igual al Hausman clásico bajo homocedasticidad (prueba) |
| Hausman clásico | `linearmodels.compare` o propio | `plm::phtest` |
| CD de Pesaran | propio | valor de referencia de `plm::pcdtest` |
| Correlación serial de Wooldridge | propio (regresión de los residuos en primeras diferencias) | `plm::pwartest` / `pwfdtest` |

**R disponible.** El contenedor ya tiene R 4.3.3. Se instala `plm` (CRAN) para las
referencias guardadas en `tests/data/reference/plm_*.json`, como se hizo con `ivx`.

## R2. Pocas unidades y dependencia transversal

Con 11 sectores, los errores agrupados por unidad tienen un tamaño muy superior al
nominal (Cameron, Gelbach y Miller 2008; MacKinnon y Webb 2017). Además, todos los
sectores comparten el factor de mercado, así que la dependencia transversal es fuerte.

**Decisión.**
- El tipo de error por defecto para paneles financieros es **Driscoll-Kraay**, robusto a
  dependencia transversal y temporal, con ancho de banda floor(4·(T/100)^(2/9)) declarado.
- Siempre se reporta el wild cluster bootstrap por unidad cuando G < 30.
- SC-004 mide el tamaño de los tres tipos de error con 11 unidades y un factor común.

## R3. Regresores comunes y efectos de tiempo

Con efectos fijos de tiempo, un regresor común a todas las unidades (Δ tasa a 10 años, el
VIX) queda absorbido. El diseño útil es la **interacción** con una característica de la
unidad: `x_t × D_i`, por ejemplo Δtasa × financiero. Esa interacción estima el efecto
**diferencial**, no el efecto total.

El sistema:
- detecta el regresor absorbido y lo explica;
- documenta que la interpretación es diferencial.

## R4. Panel predictivo y punto en el tiempo

Variable dependiente: y_{i,t+1}, el exceso de retorno del sector en el mes siguiente a la
decisión t (la misma convención de los regímenes). Los regresores se alinean con
`align_point_in_time` en la fecha de decisión.

Con efectos fijos de unidad y T grande, el sesgo de Nickell no aplica (no hay variable
dependiente rezagada). Si el usuario incluye un rezago de y, se advierte el sesgo de
Nickell con T pequeño.

## R5. Dos fases y memoria

- **Calibración** sobre `Bundle.as_of(train_end)`.
- **`frozen`**: la especificación y las hipótesis pre-registradas (coeficiente y signo
  esperado).
- **Validación**: se re-estima **sólo con los meses posteriores al corte**. Cada hipótesis
  se prueba unilateralmente en el signo pre-registrado. Las hipótesis forman la familia
  "paneles", con α declarado; por defecto, la misma regla que los regímenes (0,2α si
  conviven con estrategias).
- **Memoria**: clave = (unidades ordenadas, variable dependiente, efectos). Las variantes
  son los conjuntos de regresores. El Holm de la calibración suma las variantes previas,
  y las líneas `panel` cuentan en la detección de periodo visto para cada unidad.

## R6. Diferencias en diferencias

- **Estimación**: ATET con TWFE y un estudio de evento con *leads* y *lags* (el periodo −1
  es la referencia).
- **Tendencias previas**: prueba de Wald conjunta de los *leads* = 0. Se reporta que no
  rechazar no prueba tendencias paralelas, porque puede ser falta de potencia (Roth 2022).
- **Adopción escalonada**: se advierte el sesgo de TWFE (Goodman-Bacon 2021). Los
  estimadores robustos quedan fuera de alcance.

## R7. Calibración Monte Carlo

| Criterio | Diseño |
|---|---|
| SC-001 | N = 50, T = 20, α_i correlacionado con x (ρ = 0,5), β = 1, 500 réplicas |
| SC-003 | Mundlak con N = 50, T = 20: tamaño sin correlación y potencia con ρ = 0,3 |
| SC-004 | N = 11, T = 300, factor común f_t con cargas heterogéneas, x_it con componente común, β = 0, 1 000 réplicas, tres tipos de error |
| SC-005 | Diferencias en diferencias con N = 20 (10 tratadas), T = 40, evento en T/2; tendencias paralelas y no paralelas (0,5σ por periodo) |

## R8. Correcciones tras la revisión econométrica del diseño (2026-11-26)

### Bloqueantes

**B1 — reparto de α.**
- Se declara un reparto que **suma α**, se congela en `frozen.alpha_split` y la validación
  **lee el valor congelado** (hoy está fijo en el código: también se corrige para los
  regímenes).
- Reparto por defecto cuando hay familias presentes: estrategias 0,7α, regímenes 0,15α y
  paneles 0,15α. Si una familia está ausente, su α se reparte de forma proporcional entre
  las presentes.

**B2 — inferencia con dependencia transversal.**
- **Inferencia principal:** Driscoll-Kraay con valores críticos t(T−1), lo que da tamaño
  conservador con T moderado. El wild cluster bootstrap restringido (WCR) por unidad se
  reporta **sólo como sensibilidad**: no es válido si los clústeres comparten un factor
  común.
- **Clústeres tratados:** en cada interacción con una característica de la unidad se
  reporta G₁, el número de unidades con D_i = 1. Con G₁ < 2, ese coeficiente es **no
  concluyente** (Conley y Taber 2011; MacKinnon y Webb 2017). La demostración usa
  características con G₁ ≥ 2: "financiero o sensible a tasas" (XLF, XLRE, XLU) y
  "defensivo" (XLP, XLU, XLV). No usa "sólo Financials".
- **SC-004 rehecho:**
  - tamaño **unilateral** al 5 %, con banda 3 % a 7 % para DK con t(T−1);
  - escenarios G₁ ∈ {1, 2, 5}, T ∈ {36, 300} y un regresor persistente (φ = 0,95);
  - el tamaño de los errores agrupados y del WCR se reporta sin aserción;
  - con G₁ = 1 se exige que el resultado diga "no concluyente".

**B3 — diagnósticos del Principio I** (FR-005 ampliado):
- **estacionariedad:**
  - de cada regresor macro, con ADF + KPSS y la regla jerárquica existente;
  - de y, por unidad;
- **ARCH-LM** por unidad sobre los residuos;
- **estabilidad:** Chow en la fecha de corte para la calibración completa, o CUSUM sobre la
  serie apilada por periodo;
- **persistencia de los regresores:** AR(1) y correlación de sus innovaciones con los
  residuos (ver I2).

Regresor I(1) (p. ej. el VIX en nivel, si así resulta) ⇒ regresión desbalanceada:
advertencia y diagnósticos no superados ⇒ resultado exploratorio, igual que en los
modelos econométricos de series.

### Importantes

- **I1 — Mundlak/CRE con dos vías y desbalanceado.** Se incluyen las medias por unidad de
  los regresores, las medias por periodo y las medias por unidad de las dummies de tiempo
  (Wooldridge 2021).
  - La igualdad exacta con Hausman se prueba sólo con RE-GLS no robusto en panel
    balanceado; en otro caso la equivalencia es asintótica.
  - Con pocos grupos, el Wald agrupado se reporta como F(q, G−1).
  - Con N = 11 y T grande se advierte que θ ≈ 1 (RE ≈ FE) y que la varianza de unidad es
    poco confiable.
  - SC-003 agrega el caso N = 11.
- **I2 — sesgo tipo Stambaugh en panel** (Hjalmarsson 2008). R4 se corrige: con un
  regresor predeterminado y persistente, el estimador *within* tiene un sesgo O(1/T),
  grave con T ≈ 36 en la validación. Se reportan el AR(1) de cada regresor y la
  correlación de sus innovaciones con los residuos.
  - Si ρ > 0,9 y |corr| > 0,3: advertencia y resultado exploratorio.
  - El Monte Carlo lo incluye.
  - IVX en panel queda para la spec 004 US5 (hoy el paquete tiene sólo las referencias
    de `ivx`).
- **I3 — memoria.**
  - **Clave:** (variable dependiente, universo); la memoria se comparte con universos de
    Jaccard ≥ 0,5, como en las carteras.
  - **Variante:** (regresores, efectos, estimador, tipo de error, hipótesis con signo).
    Cambiar cualquiera de ellos cuenta como una especificación más.
- **I4 — validación.**
  - Valor p unilateral con t(T−1) en DK y con el t **con signo** en el WCR.
  - Se congelan el tipo de error, el ancho de banda, B y la semilla.
  - Se reporta el efecto mínimo detectable ex ante: 2,8·ee de la calibración reescalado
    al T de la validación.
  - `_seen_after` acepta `kind == "panel"` con `universe`.
- **I5 — CD con efectos de tiempo.** Tras quitar las medias por periodo, la CD clásica no
  es válida (Juodis y Reese 2022). Se reporta la CD de los residuos **sin** efectos de
  tiempo y se advierte. CD* (Pesaran y Xie 2021) queda en la hoja de ruta.
- **I6 — diferencias en diferencias.**
  - SC-005 se calibra con una violación de tendencias que sesga el ATET en 1 ee, y se
    reporta también el tamaño de la prueba previa.
  - Se advierte el sesgo de condicionar al resultado de la prueba previa (Roth 2022).
  - Con una sola unidad tratada: inferencia por permutación (placebo sobre las unidades de
    control).
  - Se declara el supuesto de **no anticipación** (fecha de evento = anuncio).
  - HonestDiD (Rambachan y Roth 2023) va a la hoja de ruta.
- **I7 — dependencia.** `linearmodels` pasa a un extra `[panel]` (import diferido con un
  mensaje claro). Se agrega la tabla Complexity Tracking al plan.

### Menores

- **M1 — referencias guardadas obligatorias** de lo propio (DK frente a `plm::vcovSCC`,
  con la corrección de muestra pequeña fijada; CD; Mundlak; Wooldridge). El WCR con
  G = 11 tiene una referencia determinista por **enumeración completa** de las
  2¹¹ = 2 048 combinaciones Rademacher.
- **M2 — SC-003** con ≥ 2 000 réplicas. "Correlación moderada" = corr(α_i, x̄_i) = 0,3.
- **M3 — FR-002** dice "restringido (WCR)": Webb con G < 12, B ≥ 9 999 o enumeración
  completa, con semilla explícita.
- **M4 — interpretación.**
  - Con efectos de tiempo se mide predictibilidad **diferencial** (rotación), no el
    retorno total. El resultado se rotula descriptivo-inferencial y no es una estrategia:
    una regla basada en él entra por `[[portfolios]]` (validación doble).
  - Caso límite: la reclasificación GICS de 2018 (XLC, XLK, XLY) rompe la invariancia del
    efecto fijo. Se advierte y la demostración permite cortar en 2018-10 o marcarlo.
- **M5 — RE Swamy-Arora** en panel desbalanceado: la comparación con `plm` usa una
  tolerancia de 1e-4 y se documenta la diferencia de implementación.
