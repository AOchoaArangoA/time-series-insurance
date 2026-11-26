# Feature Specification: Datos de panel con efectos fijos y aleatorios

**Feature Branch**: `006-panel-datos`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "Agregar un proceso econométrico completo con datos de panel,
efectos fijos y efectos aleatorios, tomando como referencia *Causal Inference for the
Brave and True* (Facure), capítulo 14 (Panel Data and Fixed Effects) y capítulo 13
(Difference-in-Differences). Caso de uso principal: sectores × meses."

## Contexto

Hasta ahora el paquete modela cada activo por separado (series de tiempo) o una cartera
sobre un universo. Un **panel** observa las mismas unidades (sectores, emisores, ETFs) en
muchos periodos. Eso permite controlar lo que no se observa:

- **Efectos fijos de unidad.** Absorben todo lo constante en el tiempo de cada sector
  (su beta estructural, su composición). Es la transformación *within*: restar la media de
  cada unidad.
- **Efectos fijos de tiempo.** Absorben todo lo común a todas las unidades en cada mes (el
  mercado, la inflación, la política monetaria).

**Referencia principal: Facure, capítulo 14.**
- Los efectos fijos eliminan el sesgo de confusores **constantes en el tiempo**.
- **No** eliminan:
  - confusores que **cambian en el tiempo**;
  - **causalidad inversa**.
- Suponen un **efecto constante** entre unidades.
- No admiten regresores constantes por unidad, porque se anulan.
- Los errores estándar deben ser **agrupados** (*clustered*).

**Lo que el libro no trata.** El libro **no** cubre efectos aleatorios ni la prueba de
Hausman. Para eso se usan las referencias estándar: Wooldridge (2010), *Econometric
Analysis of Cross Section and Panel Data*, y Mundlak (1978).

**Lo propio de un panel financiero.** Hay dos rasgos que el ejemplo del libro (salarios
de individuos) no tiene:
- **Dependencia transversal fuerte.** Todos los sectores se mueven con el mercado, así
  que los errores agrupados por unidad no bastan. Hacen falta errores robustos a esa
  dependencia (Driscoll y Kraay 1998) o efectos de tiempo.
- **Pocas unidades.** Con 11 sectores, los errores agrupados por unidad son poco
  confiables (Cameron, Gelbach y Miller 2008). El paquete debe advertirlo y ofrecer
  alternativas.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Estimación de panel con diagnóstico y advertencias causales (Priority: P1)

El analista entrega un panel (unidad × periodo) y elige un estimador:
- MCO agrupado;
- efectos fijos de unidad;
- efectos fijos de unidad y tiempo;
- primeras diferencias;
- efectos aleatorios.

Recibe los coeficientes con el tipo de error estándar elegido, los diagnósticos del panel
y una sección explícita de **supuestos causales**: qué sesgo controla el estimador y qué
sesgo no.

**Why this priority**: Es el núcleo; las demás historias lo usan.

**Independent Test**: Con un proceso generador conocido en el que un confusor constante
por unidad sesga el MCO agrupado, comprobar:
- los efectos fijos recuperan el coeficiente verdadero y el MCO agrupado no;
- el estimador *within* coincide con la regresión con variables dummy;
- los resultados coinciden con `linearmodels` (y con `plm` de R).

**Acceptance Scenarios**:

1. **Given** un panel balanceado o desbalanceado, **When** se estima con efectos fijos de
   unidad, **Then** los coeficientes coinciden con el *within* manual y con la regresión
   con dummies (diferencia ≤ 1e-8).
2. **Given** un regresor constante dentro de cada unidad, **When** se pide efectos fijos de
   unidad, **Then** el sistema lo informa como "absorbido por los efectos fijos" y lo
   excluye, en lugar de fallar en silencio. Si la variación *within* es mínima, también se
   advierte.
3. **Given** un regresor común a todas las unidades (p. ej. el VIX), **When** se piden
   efectos de tiempo, **Then** el sistema informa que queda absorbido. Para estimar su
   efecto heterogéneo se ofrece la interacción con una característica de la unidad.
4. **Given** pocas unidades (menos de 30), **When** se piden errores agrupados por unidad,
   **Then** el resultado advierte que no son confiables y reporta también errores
   Driscoll-Kraay y un **wild cluster bootstrap**.
5. **Given** cualquier estimación, **When** se lee el resultado, **Then** incluye:
   - la sección de supuestos (qué controla y qué no: confusores que cambian en el tiempo,
     causalidad inversa, efecto homogéneo);
   - los diagnósticos: correlación serial de Wooldridge, dependencia transversal de
     Pesaran (CD), número de unidades y periodos, y balance.

---

### User Story 2 - Efectos fijos frente a efectos aleatorios (Priority: P1)

El analista decide entre efectos fijos y aleatorios con una prueba que siga siendo válida
con errores robustos.

**Why this priority**: Los efectos aleatorios son más eficientes, pero sólo son
consistentes si los efectos de unidad no están correlacionados con los regresores. Elegir
mal sesga todo.

**Independent Test**:
- Con un proceso donde los efectos de unidad sí están correlacionados con X, la prueba
  rechaza y recomienda efectos fijos.
- Con un proceso donde no lo están, rechaza con su tamaño nominal y los efectos
  aleatorios coinciden con `linearmodels` y `plm`.

**Acceptance Scenarios**:

1. **Given** un panel, **When** se comparan efectos fijos y aleatorios, **Then** se
   reportan dos pruebas:
   - el **Hausman clásico**, sólo con errores homocedásticos;
   - la prueba **Mundlak / efectos aleatorios correlacionados**, robusta a errores
     agrupados.

   La recomendación se basa en la robusta.
2. **Given** efectos aleatorios, **When** se estima, **Then** se reportan las varianzas de
   los componentes (unidad e idiosincrático) y θ, el parámetro de cuasi-diferencia.

---

### User Story 3 - Panel declarativo en el flujo de experimentos (Priority: P2)

El analista declara en `experiment.toml` un bloque de panel: unidades, variable
dependiente, regresores, efectos, tipo de error y las hipótesis que quiere probar (signo
esperado). El sistema lo estima en la calibración con los datos truncados en el corte y
lo valida una vez después del corte. Lo registra en la bitácora con memoria de
especificaciones, igual que los modelos y regímenes.

**Why this priority**: Lleva el panel al procedimiento auditable (dos fases, pruebas
múltiples, periodos ya vistos).

**Independent Test**: Un panel declarado:
- usa sólo datos punto-en-el-tiempo;
- queda registrado;
- la validación prueba de forma unilateral los coeficientes pre-registrados con datos
  posteriores al corte;
- una segunda especificación sobre el mismo panel cuenta en el ajuste por pruebas
  múltiples.

**Acceptance Scenarios**:

1. **Given** un bloque de panel con regresores macro y su interacción con una
   característica de la unidad, **When** se calibra, **Then** los regresores se alinean
   punto en el tiempo y la variable dependiente es el exceso de retorno del mes
   siguiente.
2. **Given** las hipótesis pre-registradas (coeficiente y signo), **When** se valida,
   **Then** se prueban unilateralmente sólo con datos posteriores al corte, en la familia
   de Holm de estrategias o en una familia propia con α declarado.
3. **Given** una especificación previa con otros regresores sobre el mismo panel, **When**
   se calibra, **Then** cuenta en la memoria (clave: unidades, variable dependiente,
   efectos) y el resultado declara las especificaciones probadas.

---

### User Story 4 - Diferencias en diferencias con chequeo de tendencias previas (Priority: P3)

El analista evalúa un evento que afecta a un grupo de unidades y no a otras (p. ej. un
cambio regulatorio que afecta a Financials). Usa diferencias en diferencias con efectos
fijos de unidad y tiempo, siguiendo el capítulo 13 de Facure.

**Why this priority**: Es la extensión causal natural del panel.

**Independent Test**:
- Con un proceso con efecto conocido y tendencias paralelas, se recupera el efecto.
- Con tendencias no paralelas, el chequeo de tendencias previas lo detecta.

**Acceptance Scenarios**:

1. **Given** unidades tratadas y no tratadas y una fecha de evento, **When** se estima,
   **Then** se reporta el efecto (ATET), su error agrupado y un **estudio de evento** con
   coeficientes por periodo relativo.
2. **Given** tendencias previas distintas entre grupos, **When** se estima, **Then** la
   prueba conjunta de coeficientes previos nulos rechaza y el resultado advierte que el
   supuesto de tendencias paralelas no se sostiene.
3. **Given** adopción escalonada (distintas fechas de tratamiento), **When** se usa el
   estimador clásico de dos vías, **Then** se advierte el sesgo conocido de TWFE con
   efectos heterogéneos (Goodman-Bacon 2021). Los estimadores robustos quedan fuera de
   alcance.

---

### User Story 5 - Demostración con sectores GICS (Priority: P3)

Panel de 11 sectores × meses:
- variable dependiente: exceso de retorno del mes siguiente;
- regresores: cambio de la tasa a 10 años y VIX, **interactuados** con características
  del sector (financiero, defensivo, sensible a tasas);
- efectos fijos de sector y de tiempo.

Comparación de efectos fijos y aleatorios, y advertencias por pocas unidades.

**Independent Test**: El experimento corre en dos fases y documenta resultados y
limitaciones.

**Acceptance Scenarios**:

1. **Given** el paquete sectorial, **When** se calibra y se valida, **Then** queda
   registrado. La validación sale exploratoria si el periodo ya se vio (2015-2026 ya fue
   visto).

### Edge Cases

- Panel desbalanceado (XLC desde 2018, XLRE desde 2015): soporte completo, con el balance
  reportado.
- Unidad con un solo periodo: se excluye en efectos fijos y se informa.
- Colinealidad perfecta tras la transformación *within*: se informa qué regresor se
  eliminó.
- Efectos aleatorios con varianza de unidad estimada ≤ 0: θ = 0 (equivale al MCO
  agrupado) y se informa.
- Diferencias en diferencias sin periodos previos suficientes: no concluyente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El paquete MUST estimar sobre paneles balanceados y desbalanceados:
  - MCO agrupado;
  - efectos fijos de unidad;
  - efectos fijos de unidad y tiempo;
  - primeras diferencias;
  - efectos aleatorios (GLS factible, Swamy-Arora).
- **FR-002**: Los tipos de error MUST incluir:
  - homocedástico y robusto;
  - agrupado por unidad, por tiempo y en dos vías;
  - Driscoll-Kraay (ancho de banda declarado);
  - wild cluster bootstrap (Rademacher; con menos de 12 grupos, Webb).
- **FR-003**: Con menos de 30 grupos, el resultado MUST advertir que los errores
  agrupados no son confiables y reportar también Driscoll-Kraay y el wild cluster
  bootstrap.
- **FR-004**: Los regresores constantes por unidad (con efectos de unidad) o comunes a
  todas las unidades (con efectos de tiempo) MUST informarse como absorbidos y excluirse.
  Si la variación *within* es baja, MUST advertirse.
- **FR-005**: Todo resultado MUST incluir:
  - una sección de supuestos causales (qué sesgo controla el estimador y cuál no);
  - diagnósticos: correlación serial de Wooldridge, dependencia transversal CD de
    Pesaran, número de unidades y periodos, y balance.
- **FR-006**: La comparación de efectos fijos y aleatorios MUST reportar el Hausman clásico
  y la prueba Mundlak/CRE robusta, y basar la recomendación en la robusta.
- **FR-007**: Efectos aleatorios MUST reportar las varianzas de los componentes y θ.
- **FR-008**: El experimento MUST admitir bloques `[[panels]]` con unidades, variable
  dependiente (exceso de retorno del mes siguiente), regresores punto-en-el-tiempo,
  interacciones con características de la unidad, efectos, tipo de error e hipótesis
  pre-registradas (coeficiente y signo).
- **FR-009**: Los paneles MUST seguir las dos fases:
  - calibración con datos truncados en el corte;
  - validación única unilateral de las hipótesis pre-registradas;
  - registro en la bitácora con clave de memoria (unidades, variable dependiente,
    efectos);
  - detección de periodo ya visto para cada unidad.
- **FR-010**: Diferencias en diferencias MUST estimar el ATET con efectos fijos de unidad
  y tiempo, un estudio de evento con periodos relativos y una prueba conjunta de
  tendencias previas. Con adopción escalonada MUST advertir el sesgo de TWFE.
- **FR-011**: Las estimaciones MUST coincidir con `linearmodels` (efectos fijos y
  aleatorios, errores agrupados) y, donde aplique, con `plm` de R. Las diferencias se
  reportan en las pruebas de referencia.

### Key Entities

- **Panel**: tabla indexada por (unidad, periodo) con la variable dependiente, los
  regresores y las características de la unidad.
- **Estimación de panel**: estimador, efectos, coeficientes, tipo de error, regresores
  absorbidos, diagnósticos y supuestos.
- **Comparación FE/RE**: Hausman clásico, Mundlak/CRE y recomendación.
- **Estudio de evento**: coeficientes por periodo relativo y prueba de tendencias previas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Con un proceso generador con confusor constante por unidad (500 réplicas),
  el sesgo medio de los efectos fijos es ≤ 0,02·|β| y el del MCO agrupado ≥ 0,2·|β|.
- **SC-002**: Los coeficientes y errores coinciden con `linearmodels` con diferencia
  relativa ≤ 1e-6 (efectos fijos, de dos vías, aleatorios y errores agrupados).
- **SC-003**: La prueba Mundlak/CRE tiene un tamaño de 3 % a 7 % al 5 % sin correlación, y
  una potencia ≥ 80 % con correlación moderada (N = 50, T = 20; ≥ 500 réplicas).
- **SC-004**: Con 11 unidades, T = 300 y un factor común, el tamaño al 5 % de la prueba de
  un coeficiente nulo es:
  - ≤ 8 % con Driscoll-Kraay y con el wild cluster bootstrap;
  - el de los errores agrupados por unidad se **reporta** (se espera que sea mayor).
- **SC-005**: Diferencias en diferencias recupera el efecto con sesgo ≤ 5 % bajo
  tendencias paralelas. La prueba de tendencias previas rechaza con potencia ≥ 80 % cuando
  la pendiente diferencial es de 0,5σ por periodo.

## Assumptions

- Se usa `linearmodels` (K. Sheppard, autor de `arch`, ya dependencia del paquete) como
  motor de referencia. Lo que no ofrece se implementa con pruebas de referencia:
  Driscoll-Kraay con el ancho de banda declarado, wild cluster bootstrap, Mundlak/CRE y
  CD de Pesaran.
- Las características de las unidades (p. ej. "defensivo", "financiero") se declaran en
  el experimento, no se infieren de los datos.
- Estimadores robustos de diferencias en diferencias escalonadas (Callaway y Sant'Anna,
  Sun y Abraham, control sintético) quedan fuera de alcance; la hoja de ruta los menciona.

## Clarifications

### Session 2026-11-26

- Q: ¿Caso de uso principal? → A: sectores × meses (11 ETFs GICS), con datos ya
  disponibles.
- Q: ¿Cubre el libro efectos aleatorios y Hausman? → A: No (verificado al leer los
  capítulos 13 y 14). Se usa Wooldridge (2010) y Mundlak (1978) para esa parte.
