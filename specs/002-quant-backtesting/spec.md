# Feature Specification: Backtesting responsable de estrategias cuantitativas y modelos econométricos

**Feature Branch**: `002-quant-backtesting`

**Created**: 2026-11-08

**Status**: Clarified (decisiones por defecto pendientes de confirmación, ver Clarifications)

**Input**: User description: "Agregar una parte de backtesting basada en modelos
econométricos de series de tiempo y enfocada en estrategias cuantitativas: ingresar una
idea y testearla; señales de tendencia y de volatilidad (comunes en otros paquetes) y,
además, backtesting de modelos econométricos con variables explicativas macroeconómicas
para ver si las señales que dan se cumplen. Debe seguir dando la validación general del
modelo y además testearlo con un backtesting responsable. Reutilizar paquetes de Python
existentes si funcionan; debe ser escalable. Probar con diferentes ETFs, en especial un
ETF de renta fija (TLT)."

## User Scenarios & Testing *(mandatory)*

Actores:

- **Analista cuantitativo**: formula ideas de inversión y quiere saber, con rigor, si
  funcionan.
- **Comité de inversiones / riesgos**: decide si una señal pasa a uso real; necesita
  evidencia estadística y económica, no sólo una curva de capital atractiva.
- **Validador de modelos**: verifica que el backtest no tenga sesgos (anticipación,
  supervivencia, sobreajuste) y que el modelo econométrico subyacente sea válido.

### User Story 1 - Probar una idea con señales de tendencia y volatilidad (Priority: P1)

El analista elige uno o varios activos (p. ej. ETFs de renta fija y renta variable),
define una idea con señales predefinidas (cruce de medias, momentum de serie de tiempo,
objetivo de volatilidad) o con su propia función de señal, y obtiene el backtest con
costos y retraso de ejecución explícitos, comparado contra comprar y mantener.

**Why this priority**: es el uso más frecuente y la base sobre la que se montan las
señales econométricas; por sí solo ya es un MVP utilizable.

**Independent Test**: con precios simulados y una señal conocida, el resultado coincide
con un cálculo independiente (otra librería de backtesting) y una señal que mira al
futuro es detectada por la prueba de anticipación.

**Acceptance Scenarios**:

1. **Given** precios diarios de TLT y una regla de cruce de medias, **When** el analista
   ejecuta el backtest con costo de 5 pb y ejecución en la barra siguiente, **Then**
   recibe la curva de capital, posiciones, rotación, métricas de desempeño de la
   estrategia y del benchmark, y los supuestos usados.
2. **Given** una función de señal escrita por el usuario que usa información futura,
   **When** se ejecuta la prueba de anticipación, **Then** el sistema la detecta, indica
   las fechas afectadas y marca el backtest como inválido.
3. **Given** varios ETFs, **When** se aplica una señal de objetivo de volatilidad,
   **Then** cada activo y el portafolio combinado se evalúan con la misma metodología.

---

### User Story 2 - Backtesting de modelos econométricos con variables macroeconómicas (Priority: P1)

El analista especifica un modelo econométrico de pronóstico (regresión predictiva con
variables macroeconómicas rezagadas, con o sin componentes autorregresivos) para el
retorno de un activo, una regla que convierte el pronóstico en posición y obtiene: (a) la
validación estadística del modelo (estacionariedad de regresores, coeficientes con
errores robustos, diagnósticos de residuos, precisión fuera de muestra frente a la media
histórica) y (b) el backtest económico de la señal, re-estimando el modelo sólo con
información disponible en cada fecha y respetando el rezago de publicación de cada
variable macro.

**Why this priority**: es el diferencial pedido: verificar si las señales de los modelos
econométricos "se cumplen", con doble validación (Principio VIII).

**Independent Test**: con datos simulados donde un regresor sí predice el retorno, el
modelo muestra R² fuera de muestra positivo y significativo y la estrategia supera al
benchmark; con un regresor irrelevante, ambas validaciones lo rechazan.

**Acceptance Scenarios**:

1. **Given** retornos mensuales de TLT y variables de FRED (pendiente de la curva,
   inflación, diferencial de crédito), **When** se ejecuta el backtest walk-forward,
   **Then** cada pronóstico usa sólo datos publicados antes de la fecha de decisión.
2. **Given** el resultado, **When** el analista consulta la validación del modelo,
   **Then** ve el diagnóstico de estacionariedad de cada regresor, advertencias de
   regresores muy persistentes, coeficientes con errores HAC, diagnósticos de residuos,
   R² fuera de muestra con la prueba de Clark-West y precisión direccional con la prueba
   de Pesaran-Timmermann.
3. **Given** el resultado, **When** consulta el veredicto, **Then** el sistema reporta por
   separado si hay evidencia estadística y si hay valor económico, y el cuadrante en que
   cae la señal.

---

### User Story 3 - Validación estadística del desempeño y control de sobreajuste (Priority: P2)

Para cualquier backtest el sistema reporta la significancia del desempeño (Sharpe con
error estándar robusto, intervalo por bootstrap, Sharpe probabilístico) y, cuando se
probaron varias configuraciones, ajusta por pruebas múltiples (Sharpe deflactado y prueba
SPA frente al benchmark). Permite separar un periodo de calibración y un periodo de
validación final que se evalúa una sola vez.

**Why this priority**: sin esto un backtest no es "responsable"; depende de US1/US2.

**Independent Test**: sobre estrategias sin capacidad predictiva (señales aleatorias) el
mejor resultado de un barrido de 100 configuraciones no resulta significativo tras el
ajuste por pruebas múltiples.

**Acceptance Scenarios**:

1. **Given** un barrido de parámetros, **When** se pide el reporte, **Then** incluye el
   número de configuraciones probadas, el Sharpe deflactado del mejor y el valor p de la
   prueba SPA.
2. **Given** una división calibración/validación, **When** se elige el mejor parámetro
   en calibración, **Then** su desempeño en validación se reporta sin re-optimizar.

---

### User Story 4 - Ejercicios replicables con ETFs reales (Priority: P2)

El paquete incluye ejercicios con datos reales (Yahoo Finance para ETFs, FRED para
macro y tasa libre de riesgo) guardados como instantáneas, que comparan señales de
tendencia, volatilidad y econométricas sobre TLT y otros ETFs (IEF, SHY, TIP, LQD, HYG,
AGG, SPY).

**Why this priority**: demuestra el uso real y permite replicar los resultados.

**Independent Test**: los ejercicios se re-ejecutan sin red desde las instantáneas y
reproducen exactamente los resultados.

**Acceptance Scenarios**:

1. **Given** las instantáneas versionadas, **When** se ejecuta el ejercicio de TLT,
   **Then** produce el mismo reporte en cada corrida, con los supuestos explícitos.

---

### User Story 5 - Escalar a muchos activos y configuraciones (Priority: P3)

El analista evalúa una idea sobre un universo de activos y una malla de parámetros sin
reescribir código, y obtiene una tabla comparable de resultados con el ajuste por
pruebas múltiples incluido.

**Why this priority**: necesario para uso cotidiano, pero se apoya en US1-US3.

**Independent Test**: un barrido de 8 activos × 20 configuraciones con datos diarios de
10 años termina en menos de 60 segundos en un portátil.

**Acceptance Scenarios**:

1. **Given** un universo y una malla de parámetros, **When** se ejecuta el barrido,
   **Then** se obtiene una tabla por configuración con métricas, y el registro de
   configuraciones probadas alimenta el ajuste por pruebas múltiples.

### Edge Cases

- Activos con historia de distinta longitud: se usa el periodo común o se excluye el
  activo antes de su primer dato, y se informa.
- Señales con faltantes al inicio (ventanas de cálculo): posición en efectivo hasta que
  la señal exista; se reporta el periodo de calentamiento.
- Variables macro con frecuencia menor que la de trading: se alinean "hacia atrás" con
  el último dato publicado (nunca interpolando hacia adelante).
- Ventana de estimación insuficiente para el modelo econométrico: no se opera hasta
  alcanzar el mínimo y se informa.
- Rotación extrema o apalancamiento por encima del límite declarado: se recorta y se
  informa.
- Periodo de validación demasiado corto para inferencia: se marca como no concluyente.
- Datos de un activo con precios ajustados por dividendos vs. sin ajustar: se declara
  qué precio se usa (retorno total por defecto).

## Requirements *(mandatory)*

### Functional Requirements

**Estrategias y señales**

- **FR-001**: El sistema MUST permitir definir una estrategia como (datos de entrada,
  señal, regla de posición, frecuencia de rebalanceo, costos, retraso de ejecución,
  límites de exposición) y ejecutarla sobre uno o varios activos.
- **FR-002**: El sistema MUST incluir señales de tendencia (cruce de medias móviles y
  momentum de serie de tiempo) y de volatilidad (objetivo de volatilidad con volatilidad
  realizada y con pronóstico GARCH re-estimado walk-forward).
- **FR-003**: El sistema MUST aceptar funciones de señal definidas por el usuario y
  MUST ofrecer una prueba automática de sesgo de anticipación que compare la señal
  calculada con todos los datos frente a la calculada con datos truncados en fechas de
  corte.
- **FR-004**: El sistema MUST incluir señales econométricas: regresión predictiva con
  variables exógenas rezagadas (con componentes autorregresivos opcionales), re-estimada
  con ventana expansiva o móvil y frecuencia de re-estimación configurable.
- **FR-005**: Cada variable exógena MUST declarar su rezago de publicación; el sistema
  MUST alinear los datos para que en cada fecha de decisión sólo se use lo publicado.

**Motor**

- **FR-006**: El motor MUST aplicar las posiciones decididas en `t` a partir de
  `t + retraso` (por defecto una barra), cobrar costos proporcionales a la rotación y
  calcular retornos en exceso sobre una tasa libre de riesgo opcional.
- **FR-007**: El motor MUST ser verificable contra una librería de backtesting
  independiente; los resultados MUST coincidir dentro de una tolerancia documentada.
- **FR-008**: El sistema MUST ejecutar barridos de parámetros sobre un universo de
  activos y registrar todas las configuraciones probadas.

**Validación**

- **FR-009**: El sistema MUST reportar métricas de desempeño (retorno anualizado,
  volatilidad, Sharpe, Sortino, máxima caída, Calmar, rotación, porcentaje de aciertos)
  para estrategia y benchmark.
- **FR-010**: El sistema MUST reportar la significancia del Sharpe (error estándar
  robusto a autocorrelación, intervalo por bootstrap estacionario, Sharpe probabilístico)
  y la significancia del exceso sobre el benchmark.
- **FR-011**: El sistema MUST ajustar por pruebas múltiples (Sharpe deflactado con el
  número de configuraciones probadas y prueba SPA de Hansen frente al benchmark).
- **FR-012**: El sistema MUST permitir una división calibración/validación en la que la
  selección de parámetros sólo usa la calibración.
- **FR-013**: Para señales econométricas el sistema MUST reportar la validación del
  modelo: estacionariedad de cada regresor (reutilizando el diagnóstico de la spec 001),
  persistencia de regresores, coeficientes con errores HAC, diagnósticos de residuos,
  R² fuera de muestra con prueba de Clark-West frente a la media histórica, prueba de
  Diebold-Mariano y precisión direccional con prueba de Pesaran-Timmermann.
- **FR-014**: El sistema MUST emitir un veredicto doble —evidencia estadística sí/no y
  valor económico sí/no— con la regla de decisión explícita.

**Datos y reproducibilidad**

- **FR-015**: Los ejercicios MUST usar instantáneas versionadas de datos reales (ETFs
  vía Yahoo, macro y tasa libre de riesgo vía FRED) y re-ejecutarse sin red.
- **FR-016**: Todo resultado de backtest MUST ser exportable con supuestos, parámetros,
  configuraciones probadas, versión del paquete y huella de los datos.

### Key Entities

- **Estrategia**: señal + regla de posición + configuración de ejecución.
- **Señal**: serie (o tabla por activo) de valores decididos en cada fecha con
  información disponible hasta esa fecha.
- **Configuración de ejecución**: retraso, costos, deslizamiento, frecuencia de
  rebalanceo, límites de exposición, tasa libre de riesgo.
- **Variable exógena**: serie macro con rezago de publicación y transformación.
- **Modelo de pronóstico walk-forward**: especificación, esquema de ventana, frecuencia
  de re-estimación, pronósticos fuera de muestra y diagnósticos.
- **Resultado de backtest**: curva de capital, posiciones, rotación, métricas,
  significancia, benchmark y supuestos.
- **Registro de pruebas**: configuraciones probadas y sus resultados (para el ajuste por
  pruebas múltiples).
- **Veredicto**: evidencia estadística y valor económico con su regla.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El motor reproduce el retorno total de una librería de backtesting
  independiente con diferencia absoluta menor a 1e-6 en estrategias de referencia.
- **SC-002**: La prueba de anticipación detecta el 100 % de las señales sintéticas con
  fuga de información (desplazamiento de −1 barra o uso de estadísticas de muestra
  completa) y no marca señales causales.
- **SC-003**: Sobre 100 configuraciones de señales aleatorias, el mejor Sharpe ajustado
  por pruebas múltiples no es significativo al 5 % en al menos el 90 % de 200 réplicas.
- **SC-004**: Con un proceso generador en el que un regresor explica al menos el 5 % de
  la varianza del retorno, la prueba de Clark-West detecta la capacidad predictiva en al
  menos el 80 % de las réplicas (n = 300 meses); con un regresor irrelevante su tamaño
  empírico es como máximo 8 %.
- **SC-005**: Las pruebas estadísticas implementadas reproducen ejemplos publicados o
  equivalencias analíticas: Sharpe deflactado del ejemplo de Bailey y López de Prado
  (2014) con diferencia absoluta menor a 1e-4; Pesaran-Timmermann equivalente
  asintóticamente a la prueba chi-cuadrado de independencia 2×2 (diferencia relativa del
  estadístico al cuadrado menor a 2 % con n ≥ 2000); Clark-West y R² fuera de muestra
  idénticos (1e-10) a su cálculo directo por definición.
- **SC-006**: Un barrido de 8 activos × 20 configuraciones con 10 años de datos diarios
  termina en menos de 60 segundos.
- **SC-007**: Cada ejercicio con ETFs reales se re-ejecuta desde sus instantáneas y
  reproduce exactamente su reporte.

## Clarifications

### Session 2026-11-08

- Q: ¿Qué ETF es "TFT"? → A: El ticker TFT no existe en Yahoo Finance; se asume **TLT**
  (iShares 20+ Year Treasury Bond ETF, renta fija larga). *Decisión por defecto, confirmar.*
- Q: ¿Reutilizar una librería de backtesting? → A: Se evaluaron bt, vectorbt y
  backtesting.py con pandas 3.1. Se adopta **bt** (MIT, multi-activo, compatible) como
  motor de referencia opcional y un motor vectorizado propio, validado contra bt, para
  barridos y bootstrap. vectorbt se descarta por licencia (Commons Clause) y fallas con
  pandas 3; backtesting.py por licencia AGPL y ser mono-activo. Las pruebas estadísticas
  de remuestreo reutilizan `arch.bootstrap`.
- Q: ¿Paquete separado? → A: Se implementa como subpaquete `tsinsurance.backtest`
  desacoplado (sólo depende de `data` y `diagnostics`), extraíble a un paquete propio
  si se decide más adelante. *Decisión por defecto, confirmar.*
- Q: ¿Precios? → A: Precios ajustados por dividendos (retorno total) de Yahoo; tasa
  libre de riesgo: letra del Tesoro a 3 meses de FRED (DTB3).

## Assumptions

- Estrategias sólo con posiciones largas, cortas o efectivo sobre activos líquidos; sin
  modelado de libro de órdenes, márgenes ni impuestos en v1.
- Frecuencias de decisión: diaria, semanal o mensual.
- El universo de ETFs se toma tal como existe hoy (sesgo de supervivencia declarado en
  los reportes; los ETFs elegidos siguen vigentes).
- Los datos macro de FRED se toman en su versión actual (no en *vintages*), con rezago
  de publicación declarado; el uso de *vintages* (ALFRED) queda para una versión futura
  y se señala como limitación.
- Los modelos ARIMA/GARCH completos de la spec 001 (US2) se reutilizarán cuando estén
  disponibles; en esta spec el pronóstico GARCH usa `arch` directamente.
