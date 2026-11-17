# Feature Specification: Ideas de cartera y análisis por regímenes del ciclo

**Feature Branch**: `005-cartera-regimenes`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "Spec pequeña para ideas de cartera (rotación) y análisis
por regímenes. Hallazgos C1 y C2 del experimento exploratorio con ETFs sectoriales GICS:
`experiment.toml` sólo evalúa activo por activo, así que una rotación sectorial tuvo que
hacerse fuera de la bitácora y sus pruebas no cuentan para el ajuste por pruebas
múltiples; y el análisis por estados del ciclo (curva invertida, VIX alto, mercado
bajista) no existe en el paquete."

## Contexto

En el experimento `sectores-gics-ciclo` (2026-11-17) se probaron dos cosas fuera del
procedimiento registrado:

1. **Rotación sectorial**: invertir cada mes en los k sectores con mejor momentum. Es una
   **cartera** sobre un universo, no una regla sobre un activo. Las 4 configuraciones
   probadas no quedaron en la bitácora: una próxima prueba de rotación no "sabrá" que ya
   se intentó.
2. **Regímenes del ciclo**: retorno del mes siguiente de cada sector según un estado
   observable al cierre de mes. Se hizo con código ad hoc (33 pruebas con Holm), sin
   registro ni las salvaguardas del paquete.

Esta spec incorpora ambas al flujo declarativo con las mismas salvaguardas: anticipación,
punto en el tiempo, costos, doble benchmark, pruebas múltiples con memoria, y calibración
y validación en dos fases (spec 004).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ideas de cartera declarativas y registradas (Priority: P1)

El analista declara en el experimento una idea que asigna pesos **entre** los activos de
un universo (por ejemplo, los k sectores con mejor momentum o pesos inversos a la
volatilidad). El sistema la evalúa con los mismos supuestos de ejecución y la compara
con la cartera igual ponderada del mismo universo. Cada configuración queda en la
bitácora y cuenta para el ajuste por pruebas múltiples de futuras ideas sobre el mismo
universo. La validación fuera de muestra se abre una vez.

**Why this priority**: Sin esto, las estrategias de cartera, que son las naturales para
una aseguradora con un portafolio diversificado, quedan fuera del procedimiento
auditable.

**Independent Test**: Declarar una rotación con 4 configuraciones sobre un universo
sintético sin habilidad. Comprobar:
- la prueba de anticipación;
- las 4 líneas en la bitácora;
- un Sharpe deflactado no significativo;
- que una segunda idea de cartera sobre el mismo universo cuente las 4 previas;
- la validación única en dos fases.

**Acceptance Scenarios**:

1. **Given** un bloque de cartera con universo, señal y malla, **When** se calibra,
   **Then** cada configuración pasa la prueba de anticipación sobre el universo completo
   y se registra con la identidad del universo.
2. **Given** las configuraciones evaluadas, **When** se selecciona, **Then** la mejor se
   deflacta con todas las pruebas registradas sobre ese universo (de cualquier
   experimento) y se compara con la cartera igual ponderada del universo con los mismos
   costos y rebalanceo.
3. **Given** una calibración con ideas de cartera, **When** se valida, **Then** la
   configuración fijada se evalúa una vez después del corte, entra en la familia de Holm,
   y un periodo ya visto para ese universo marca el resultado como exploratorio.
4. **Given** una señal de cartera que usa precios futuros, **When** se calibra, **Then**
   la idea se rechaza por anticipación y no se evalúa.
5. **Given** un universo con activos que empiezan en fechas distintas, **When** se evalúa,
   **Then** cada activo entra a la cartera recién cuando tiene historia suficiente para la
   señal, y el benchmark igual ponderado usa el mismo conjunto disponible en cada fecha.

---

### User Story 2 - Análisis por regímenes del ciclo (Priority: P2)

El analista declara estados del ciclo **observables al cierre de cada mes** (una variable
sobre o bajo un umbral, la diferencia entre dos tasas, un activo bajo su media móvil) y
obtiene, para cada activo, el exceso de retorno del mes siguiente en cada estado. Recibe
las diferencias con errores robustos a autocorrelación y heterocedasticidad, ajustadas por
pruebas múltiples, con el número de meses en cada estado. Lo calcula en la calibración y
lo valida una vez después del corte.

**Why this priority**: Responde la pregunta "¿el ciclo cambia qué sector rinde mejor?"
con las salvaguardas del paquete en lugar de código ad hoc.

**Independent Test**:
- Con un proceso simulado donde el retorno del mes siguiente depende de un estado
  conocido, detectar la diferencia.
- Con un proceso sin dependencia, mantener la tasa de falsos positivos en el nivel
  nominal tras Holm.
- Comprobar que ningún estado usa información posterior a la fecha de decisión.

**Acceptance Scenarios**:

1. **Given** una definición de estado sobre una variable con rezago de publicación,
   **When** se construye en cada fin de mes, **Then** sólo usa valores publicados hasta
   esa fecha.
2. **Given** los estados y los activos, **When** se analiza, **Then** cada combinación
   (estado, activo) reporta: meses en el estado y fuera de él, exceso anualizado en cada
   caso, diferencia, t HAC, valor p y valor p de Holm sobre toda la familia.
3. **Given** un estado con menos meses que el mínimo declarado, **When** se analiza,
   **Then** se reporta como "no concluyente" y no entra en la familia de Holm.
4. **Given** una calibración con regímenes, **When** se valida, **Then** el análisis se
   repite sólo con meses posteriores al corte, y las hipótesis de régimen entran en la
   familia de Holm de la validación.
5. **Given** un estado definido con la diferencia entre dos series (p. ej. tasa a 10 años
   menos tasa a 3 meses), **When** las series tienen rezagos distintos, **Then** el estado
   usa la disponibilidad más tardía de las dos.

---

### User Story 3 - Demostración con ETFs sectoriales (Priority: P3)

El dueño del proyecto vuelve a correr la rotación sectorial y los regímenes con el flujo
registrado sobre los ETFs GICS. El sistema marca solo que el periodo 2015-2026 ya se miró
(en el análisis exploratorio anterior y en las validaciones de los sectores).

**Why this priority**: Cierra los hallazgos C1 y C2 con el caso real que los originó.

**Independent Test**: Ejecutar las dos fases; la bitácora queda íntegra; aparecen las
razones de exploratorio esperadas.

**Acceptance Scenarios**:

1. **Given** el experimento sectorial con un bloque de rotación y uno de regímenes,
   **When** se calibra y se valida, **Then** las pruebas de cartera y de régimen quedan en
   la bitácora y la validación sale exploratoria por periodo ya visto.

### Edge Cases

- Universo de un solo activo: no es una idea de cartera; se rechaza con un mensaje que
  remite a `[[ideas]]`.
- Señal de cartera que devuelve pesos negativos con `allow_short = false`, o una suma
  mayor que el bruto máximo: se acotan como en el motor actual y se informa.
- Empates en el ranking de momentum: regla determinista (orden del universo declarado).
- Estado siempre activo o siempre inactivo en la ventana: no concluyente.
- Variable de régimen no punto-en-el-tiempo: el análisis queda exploratorio.
- Ventana de validación sin meses en un estado: no concluyente para ese estado.

## Requirements *(mandatory)*

### Functional Requirements

**Ideas de cartera (US1)**

- **FR-001**: El experimento MUST admitir bloques de cartera con nombre, universo (≥ 2
  activos del paquete), señal de cartera registrada y malla de parámetros.
- **FR-002**: Una señal de cartera MUST ser una función causal que recibe los precios del
  universo y devuelve pesos objetivo por fecha y activo. El paquete MUST incluir al menos:
  - momentum relativo (los k mejores con retorno pasado de L meses, saltando el último mes);
  - pesos inversos a la volatilidad.

  Las señales propias MUST poder registrarse.
- **FR-003**: Cada configuración MUST pasar la prueba de anticipación sobre el universo
  completo antes de evaluarse.
- **FR-004**: El benchmark MUST ser la cartera igual ponderada de los activos
  **elegibles del bloque** (≥ `min_history_m` meses de historia), ejecutada con el mismo
  motor, costos y rebalanceo mensual. Estrategia y benchmark usan la misma elegibilidad y
  la misma ventana común. El retorno activo frente a ella es la medida de habilidad.
- **FR-005**: La identidad de una prueba de cartera MUST incluir la identidad del
  universo (conjunto ordenado de activos), la señal, sus parámetros, la ejecución, la
  ventana y los datos. El Sharpe deflactado MUST contar todas las pruebas de cartera
  previas, registradas o declaradas, cuyo universo comparta al menos el 50 % de los
  constituyentes (Jaccard ≥ 0,5). La SPA usa el universo exacto.
- **FR-005a**: El experimento MUST poder declarar pruebas hechas fuera de la bitácora
  (`[[declared_prior_tests]]`: tipo, universo o activos, número, periodo, hash del
  script). Cuentan en N y en la detección de periodo visto.
- **FR-006**: Las ideas de cartera MUST seguir las dos fases de la spec 004:
  - calibración con datos truncados en el corte;
  - configuración fijada;
  - validación única con detección de periodo ya visto (por universo, y por cualquier
    constituyente);
  - entrada en la familia de Holm de la validación.

**Regímenes (US2)**

- **FR-007**: El experimento MUST admitir bloques de régimen con nombre, definición del
  estado, activos a analizar y mínimo de meses por estado.
- **FR-008**: Las definiciones de estado MUST incluir:
  - (a) una variable del paquete frente a un umbral;
  - (b) la diferencia entre dos variables frente a un umbral;
  - (c) un activo bajo su media móvil de n meses.

  Cada estado MUST construirse en la fecha de decisión mensual sólo con valores
  disponibles en esa fecha (rezago de publicación; la disponibilidad más tardía de los
  insumos).
- **FR-009**: Para cada (estado, activo) MUST reportarse:
  - meses en el estado y fuera de él;
  - exceso anualizado del mes siguiente en cada caso;
  - la diferencia con su t y valor p robustos a heterocedasticidad (HC3);
  - el valor p de Holm con m = hipótesis actuales + variantes previas con la misma clave
    de memoria (activo, tipo, variables).
- **FR-009a**: Los regímenes MUST admitir mallas de umbrales, todas contadas, y declarar
  `justification`; sin ella el resultado es exploratorio.
- **FR-009b**: En la validación, las estrategias (ideas, modelos y carteras) y los
  regímenes MUST ser familias separadas con α pre-declarado (0,8α y 0,2α). Sólo se
  validan las hipótesis de régimen seleccionadas en la calibración, unilaterales en el
  signo calibrado.
- **FR-010**: Las combinaciones con menos meses que el mínimo MUST marcarse "no
  concluyente" y quedar fuera de la familia.
- **FR-011**: Cada combinación evaluada MUST registrarse en la bitácora. En la
  validación, el análisis se repite sólo con meses posteriores al corte y entra en la
  familia de Holm.
- **FR-012**: Un régimen sobre variables no punto-en-el-tiempo MUST marcar el resultado
  como exploratorio.

**Compatibilidad y documentación**

- **FR-013**: Los resultados MUST seguir siendo compatibles en forma aditiva (versión 1.x)
  y la bitácora existente MUST seguir verificándose.
- **FR-014**: El manual de integración, la guía para agentes y la habilidad de
  experimentos MUST describir los bloques nuevos.

### Key Entities

- **Universo**: conjunto ordenado de activos sobre el que una idea de cartera asigna
  pesos; su identidad es la lista ordenada de identificadores.
- **Idea de cartera**: universo + señal de cartera + malla.
- **Estado de régimen**: serie booleana mensual construida punto en el tiempo.
- **Hipótesis de régimen**: (estado, activo) con su diferencia de exceso de retorno.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Con universos sintéticos sin habilidad (medias iguales, factor común
  ρ ≈ 0,6, inicios distintos, costos; ≥ 500 réplicas), la fracción de ideas de cartera
  declaradas significativas es ≤ 5 % + 2,5 errores de Monte Carlo.
- **SC-002**: Con un universo sintético con momentum relativo real (persistencia de
  retornos relativos), la rotación supera al igual ponderado con potencia ≥ 80 % en el
  diseño declarado en el plan.
- **SC-003**: El 100 % de las señales de cartera con información futura (incluido el
  ranking con precios futuros) se rechazan por anticipación.
- **SC-004**: Con estados sin efecto (≥ 500 réplicas, 9 activos × 3 estados, uno de ellos
  endógeno), la probabilidad de al menos un falso positivo tras Holm es ≤ 5 % + 2,5
  errores de Monte Carlo. Con un efecto de 0,6σ mensual en un activo, en un estado activo
  el 20 % del tiempo y T = 300, la potencia para ese activo es ≥ 80 %. El informe declara
  que, con la volatilidad sectorial real, la potencia para efectos de ~1 % mensual es
  baja.
- **SC-005**: Alterar las observaciones posteriores a cada fecha de decisión no cambia
  ningún estado de esa fecha (100 % de los casos de prueba).
- **SC-006**: Una segunda idea de cartera sobre el mismo universo cuenta todas las
  configuraciones registradas antes (100 % de los casos).
- **SC-007**: La demostración sectorial corre ambas fases en menos de 3 minutos y la
  bitácora queda íntegra.

## Assumptions

- La frecuencia de decisión de carteras y regímenes es mensual (fin de mes), como en los
  modelos econométricos.
- La cartera igual ponderada es el benchmark por defecto. Otros benchmarks (por ejemplo
  SPY) se reportan como información, sin inferencia.
- Las pruebas de régimen forman su propia familia de Holm en la calibración. En la
  validación entran en la familia única pre-registrada junto con ideas y modelos.
- Las variables de régimen pueden ser exógenas o la tasa libre de riesgo (con su rezago
  declarado).

## Clarifications

### Session 2026-11-17

- Revisión econométrica del diseño: 4 bloqueantes (memoria de regímenes y umbrales,
  pruebas fuera de la bitácora, memoria por universo, benchmark del motor) e importantes
  I1-I6, resueltos en FR-004, FR-005, FR-005a, FR-009, FR-009a, FR-009b, SC-001, SC-004
  y research R6.

- Q: ¿Spec pequeña o dentro de la 004? → A: Spec aparte y pequeña (hallazgos C1 y C2),
  sobre el flujo de dos fases de la spec 004.
