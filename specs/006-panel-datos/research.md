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
