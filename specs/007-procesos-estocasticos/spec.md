# Feature Specification: Procesos estocásticos, simulación y sensibilidades en renta fija (MVP)

**Feature Branch**: `007-procesos-estocasticos`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: base metodológica entregada por el usuario (2026-11-26):
1. arquitectura de procesos estocásticos y regímenes en renta fija (tasa corta con
   reversión a la media, regímenes de Markov, modelos afines, crédito, medidas ℙ y ℚ);
2. motor de simulación y reducción de dimensionalidad (factores de curva, PCA, simulación
   histórica, histórica dinámica y Monte Carlo, reducción de varianza);
3. gestión de sensibilidades (operador de pérdidas, Δ y ΔΓ, duración y convexidad,
   sensibilidades por factor y por régimen, revaluación completa, inmunización, cautela
   causal);
4. estructura `stochastics/`, `simulation/`, `sensitivities/` y `portfolio_risk/`.

Decisiones del usuario (2026-11-26):
- **Frontera estricta con el paquete hermano de curvas.**
- **MVP primero.**
- **Calibración ℚ a rendimientos del Tesoro.**

## Contexto

El paquete ya sabe decir si una señal tiene habilidad. Le falta modelar el **riesgo** de
una cartera de renta fija: cómo se mueven las tasas, qué pasa con el valor de la cartera
en escenarios y cuánto se puede perder. La base metodológica separa cuatro capas que **no
deben mezclarse**:

| Capa | Pregunta | Medida |
|---|---|---|
| `stochastics/` | ¿Cómo evolucionan los factores de estado (tasa corta, régimen)? | ℙ para proyectar, ℚ para valorar |
| `simulation/` | ¿Qué trayectorias o escenarios son posibles? | ℙ (riesgo) o ℚ (precios) |
| `sensitivities/` | ¿Cómo responde el valor a cada factor? | — (derivadas del mapeo de valoración) |
| `portfolio_risk/` | ¿Cuánto se puede perder y cómo se cubre? | ℙ |

**Frontera con el paquete hermano de curvas.**
- **Aquí** van las curvas cero **implícitas** de los modelos (Vasicek, CIR, afines), la
  dinámica de factores, el PCA sobre nodos y los factores tipo Nelson-Siegel con λ fija
  estimados por regresión en cada fecha (Diebold y Li 2006), sin optimizar la forma de
  la curva.
- **En el paquete hermano** quedan el ajuste paramétrico, el bootstrapping y la
  interpolación o extrapolación de producción. Sus curvas entran como nodos (contrato
  `rate_nodes`) o como un objeto con la interfaz de curva.
- **Fuera de alcance de este MVP** (spec siguiente):
  - crédito (intensidad, migraciones, estructural);
  - afines con saltos;
  - filtraje de estados latentes (Kalman);
  - importance sampling.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tasa corta con reversión a la media bajo ℙ (Priority: P1)

El analista estima un modelo de tasa corta (Vasicek o CIR) sobre la serie de la letra del
Tesoro. Obtiene los parámetros con su incertidumbre y la verificación de la condición de
Feller. Simula trayectorias con su discretización **exacta**.

**Why this priority**: Es el proceso de estado base de todo lo demás.

**Independent Test**: Con trayectorias simuladas con parámetros conocidos, la estimación
recupera los parámetros dentro de su intervalo. La simulación exacta reproduce los
momentos teóricos de la distribución de transición.

**Acceptance Scenarios**:

1. **Given** una serie de tasa corta, **When** se estima Vasicek, **Then** se obtienen κ,
   θ y σ por máxima verosimilitud exacta (AR(1) gaussiano), con errores estándar e
   intervalos.
2. **Given** CIR, **When** se estima, **Then** se usa la verosimilitud exacta (chi-cuadrado
   no central) o una aproximación declarada, y se informa si se cumple la condición de
   Feller (2κθ ≥ σ²).
3. **Given** parámetros, **When** se simula, **Then** la media y la varianza a cada
   horizonte coinciden con las teóricas dentro del error de Monte Carlo.
4. **Given** tasas negativas o nulas en la serie (2020-2021), **When** se estima CIR,
   **Then** se advierte que CIR no admite tasas negativas y se sugiere Vasicek o un
   desplazamiento declarado.

---

### User Story 2 - Regímenes de Markov en la tasa corta (Priority: P1)

El analista estima un modelo con **cambio de régimen**: el nivel de reversión y/o la
volatilidad dependen de una cadena de Markov oculta. Obtiene las probabilidades de
régimen **filtradas** (lo que se sabía en cada fecha) y las **suavizadas** (con toda la
muestra), y simula trayectorias con regímenes.

**Why this priority**: Los parámetros constantes no capturan los ciclos; la base
metodológica lo exige.

**Independent Test**:
- Con un proceso simulado de dos regímenes, se recuperan la matriz de transición y los
  parámetros por régimen.
- Las probabilidades filtradas en t no cambian al agregar datos posteriores (sólo las
  suavizadas cambian).

**Acceptance Scenarios**:

1. **Given** la serie de tasa corta, **When** se estima un modelo de 2 regímenes, **Then**
   se reportan, por régimen:
   - los parámetros;
   - la matriz de transición;
   - la duración esperada;
   - las probabilidades filtradas y suavizadas.
2. **Given** una decisión o estado en la fecha t, **When** se usa la probabilidad de
   régimen, **Then** sólo se usa la **filtrada**. La suavizada usa el futuro y queda
   marcada como descriptiva.
3. **Given** parámetros de régimen, **When** se simula, **Then** las trayectorias
   alternan regímenes con las frecuencias de la cadena.

---

### User Story 3 - Valoración libre de arbitraje y calibración ℚ (Priority: P1)

El analista obtiene precios de bonos cupón cero en forma cerrada (exponencial-afín) para
Vasicek, CIR y Hull-White. Calibra los parámetros ℚ a los rendimientos del Tesoro en los
nodos disponibles. Hull-White ajusta exactamente la curva inicial que entrega una
**curva externa** (interfaz). La separación ℙ/ℚ queda explícita en todo resultado.

**Why this priority**: Sin ℚ no hay valoración consistente ni coberturas.

**Independent Test**:
- Los precios cerrados coinciden con la simulación Monte Carlo bajo ℚ (con variable de
  control) dentro del error.
- Hull-White reproduce la curva inicial con un error ≤ 1e-8.
- La calibración recupera parámetros conocidos a partir de curvas sintéticas.

**Acceptance Scenarios**:

1. **Given** parámetros ℚ, **When** se valora un bono cupón cero, **Then** se usa
   P(t,T) = A(τ)·exp(−B(τ)·r_t), con las fórmulas cerradas de cada modelo.
2. **Given** rendimientos del Tesoro en los nodos de una fecha, **When** se calibra,
   **Then** se minimiza el error de precio o rendimiento en los nodos y se reportan el
   ajuste por nodo y los parámetros ℚ.
3. **Given** una curva inicial externa (interfaz de curva), **When** se usa Hull-White,
   **Then** θ(t) se deduce de la curva y el modelo la reproduce exactamente.
4. **Given** cualquier resultado, **When** se lee, **Then** declara la medida (ℙ o ℚ) y,
   cuando ambas se usan, la prima de riesgo de mercado implícita.

---

### User Story 4 - Motor de simulación y reducción de dimensión (Priority: P1)

El analista genera escenarios de factores de riesgo para una cartera de renta fija. Tiene
cuatro opciones:
- **simulación histórica**: cambios observados;
- **histórica filtrada**: innovaciones estandarizadas con EWMA o GARCH y reescaladas a la
  volatilidad actual;
- **Monte Carlo de factores**: PCA de los cambios en los nodos, o nivel, pendiente y
  curvatura tipo Diebold-Li;
- **Monte Carlo de la tasa corta**, con o sin regímenes.

Puede aplicar **reducción de varianza**: variables antitéticas y variables de control.

**Why this priority**: Es el motor que alimenta riesgo y estrés.

**Independent Test**:
- El PCA reproduce la varianza explicada conocida en datos sintéticos.
- La reducción de varianza baja el error estándar del estimador frente a Monte Carlo
  simple con el mismo número de trayectorias, por un factor medido y reportado.
- La misma semilla da los mismos escenarios.

**Acceptance Scenarios**:

1. **Given** rendimientos en nodos (contrato `rate_nodes` o series del paquete con su
   plazo), **When** se ajusta el PCA de los cambios, **Then** se reportan los componentes
   (cargas), la varianza explicada y la interpretación nivel/pendiente/curvatura.
2. **Given** un método de simulación, **When** se generan escenarios a un horizonte,
   **Then** el resultado incluye la medida, el método, la semilla, la ventana de datos y
   el número de escenarios.
3. **Given** antitéticas o variable de control, **When** se estima un valor esperado,
   **Then** se reporta el factor de reducción de varianza frente a Monte Carlo simple.
4. **Given** la simulación histórica filtrada, **When** se reescala, **Then** sólo se usa la
   volatilidad conocida en la fecha de análisis (punto en el tiempo).

---

### User Story 5 - Sensibilidades: Δ, ΔΓ, duración, convexidad y por factor (Priority: P1)

El analista valora una cartera de bonos (flujos fijos) y obtiene, con una interfaz
uniforme:
- valor presente;
- DV01 y duraciones por nodo (*key-rate*);
- duración modificada y convexidad;
- deltas y gammas por factor (PCA o nivel, pendiente y curvatura);
- aproximaciones Δ y ΔΓ del cambio de valor.

Las aproximaciones se validan contra la **revaluación completa**, con el error de
truncamiento reportado.

**Why this priority**: Sin sensibilidades, la simulación es ruido que no se puede operar
ni cubrir.

**Independent Test**:
- La duración y la convexidad analíticas coinciden con las de diferencias finitas.
- Ante choques pequeños, ΔΓ tiene un error de orden 3; ante choques grandes, se reporta
  cuánto se aleja de la revaluación completa.
- La suma de las *key-rate* durations iguala la duración bajo un movimiento paralelo.

**Acceptance Scenarios**:

1. **Given** un bono o una cartera y una curva, **When** se calculan sensibilidades,
   **Then** se obtienen PV, DV01 total y por nodo, duración modificada, convexidad y
   deltas y gammas por factor, cada una con su método (analítico o diferencias finitas)
   declarado.
2. **Given** un escenario de factores, **When** se aproxima el cambio de valor, **Then**
   se reportan Δ, ΔΓ y la revaluación completa, con el error de cada aproximación.
3. **Given** una cartera y escenarios, **When** se atribuye el P&L, **Then** se separa por
   factor (nivel, pendiente, curvatura) y queda un residuo explícito.

---

### User Story 6 - Riesgo de cartera: VaR/ES, estrés, backtesting e inmunización (Priority: P2)

El analista mide VaR y ES de la cartera con cada motor de escenarios y cada método de
revaluación (Δ, ΔΓ, completa). Además:
- hace **backtesting** del VaR con pruebas formales;
- aplica **escenarios de estrés**: paralelos, de pendiente, de curvatura y condicionados
  a régimen;
- calcula una **cobertura** que neutraliza exposiciones no deseadas (duración o factor)
  con instrumentos declarados.

**Why this priority**: Es lo que pide la gestión de inversiones de una aseguradora.

**Independent Test**:
- Con pérdidas simuladas de una distribución conocida, VaR y ES coinciden con los
  teóricos.
- Las pruebas de backtesting tienen el tamaño nominal bajo un modelo correcto y rechazan
  un modelo mal calibrado.
- La cobertura deja la exposición objetivo en cero (≤ 1e-8).

**Acceptance Scenarios**:

1. **Given** escenarios y una cartera, **When** se calcula el riesgo, **Then** se reportan
   VaR y ES a los niveles declarados, con un intervalo por bootstrap y el método de
   revaluación.
2. **Given** una historia de pronósticos de VaR, **When** se hace backtesting, **Then** se
   reportan:
   - Kupiec (POF);
   - Christoffersen (independencia y cobertura condicional);
   - una prueba de ES (Acerbi-Székely Z2).

   Los pronósticos se calculan **sólo con información hasta cada fecha**.
3. **Given** exposiciones a neutralizar y los instrumentos de cobertura, **When** se
   calcula la cobertura, **Then** se obtienen las cantidades por mínimos cuadrados con
   restricciones declaradas y la exposición residual.
4. **Given** un escenario de estrés condicionado a régimen, **When** se aplica, **Then**
   los choques salen de la distribución del régimen declarado y se reporta su
   probabilidad filtrada actual.

---

### User Story 7 - Demostración con el Tesoro de EE. UU. (Priority: P3)

Rendimientos del Tesoro a 13 semanas, 5, 10 y 30 años (Yahoo, sin clave), 2000-2026:
1. estimación ℙ de Vasicek o CIR con regímenes sobre la tasa corta;
2. calibración ℚ;
3. PCA de los cambios de la curva;
4. una cartera tipo aseguradora (bonos a 2, 5, 10 y 20 años);
5. sensibilidades, VaR/ES con backtesting 2010-2026, estrés e inmunización de duración.

**Independent Test**: El ejercicio corre desde su receta y documenta resultados y
limitaciones.

**Acceptance Scenarios**:

1. **Given** la receta y el análisis, **When** se ejecutan, **Then** se obtienen todos los
   resultados con su procedencia (huella de datos, semilla, medida, método), sin usar
   información futura en los pronósticos de VaR.

### Edge Cases

- **Curva con muy pocos nodos** (4): PCA con a lo sumo 4 componentes. Las *key-rate*
  durations son por nodo; entre nodos se usa la interfaz de curva externa, o la curva
  mínima de nodos lineal documentada como no apta para producción.
- **Tasas negativas en CIR**: advertencia y alternativa (US1).
- **Calibración ℚ que no converge**: se informa con el mejor punto y el motivo; no se
  devuelve un resultado silencioso.
- **Régimen degenerado** (probabilidad de un régimen ≈ 0): se reporta y se sugiere un solo
  régimen.
- **Muestra corta para el backtesting de VaR**: con menos de 250 observaciones el
  resultado es no concluyente.

## Requirements *(mandatory)*

### Functional Requirements

**Procesos (stochastics/)**

- **FR-001**: El paquete MUST ofrecer Vasicek y CIR bajo ℙ con estimación por máxima
  verosimilitud exacta, errores estándar, condición de Feller y simulación exacta.
- **FR-002**: El paquete MUST ofrecer un modelo de 2 o más regímenes de Markov para la
  tasa corta (nivel y/o volatilidad por régimen) con:
  - matriz de transición;
  - probabilidades filtradas (punto en el tiempo) y suavizadas (descriptivas);
  - simulación con regímenes.
- **FR-003**: Vasicek, CIR y Hull-White MUST valorar bonos cupón cero en forma cerrada
  exponencial-afín bajo ℚ.
- **FR-004**: La calibración ℚ MUST ajustarse a rendimientos en nodos (contrato
  `rate_nodes` o series con plazo declarado) y reportar el ajuste por nodo.
- **FR-004a**: Hull-White MUST reproducir una curva inicial entregada por una **interfaz
  de curva** (descuento y forward instantáneo). El paquete MUST incluir sólo una curva
  mínima de nodos (lineal en tasas cero, plana fuera de rango), documentada como no apta
  para producción.
- **FR-005**: Todo objeto de proceso y todo resultado MUST declarar su medida (ℙ o ℚ).

**Simulación (simulation/)**

- **FR-006**: El paquete MUST generar escenarios por:
  - simulación histórica;
  - histórica filtrada (EWMA o GARCH, punto en el tiempo);
  - Monte Carlo de factores (PCA o Diebold-Li con λ fija);
  - Monte Carlo de la tasa corta (con o sin regímenes).
- **FR-007**: El paquete MUST ofrecer variables antitéticas y variables de control, y
  reportar el factor de reducción de varianza.
- **FR-008**: Los escenarios MUST ser reproducibles (generador con semilla explícita) y
  llevar procedencia: medida, método, ventana, semilla y número de escenarios.
- **FR-009**: El PCA MUST reportar las cargas, la varianza explicada y la interpretación
  nivel/pendiente/curvatura, sobre **cambios** de tasas (no niveles).

**Sensibilidades (sensitivities/)**

- **FR-010**: Una interfaz uniforme MUST entregar, para instrumentos y carteras:
  - PV;
  - DV01 total y por nodo;
  - duración modificada y convexidad;
  - deltas y gammas por factor y términos cruzados.

  Cada una con su método declarado (analítico o diferencias finitas centrales, con el paso
  declarado).
- **FR-011**: Las aproximaciones Δ y ΔΓ MUST validarse contra la revaluación completa y
  reportar el error de truncamiento por escenario y agregado.
- **FR-012**: La atribución de P&L MUST separar el resultado por factor y dejar un residuo
  explícito.

**Riesgo de cartera (portfolio_risk/)**

- **FR-013**: VaR y ES MUST calcularse para cualquier motor de escenarios y método de
  revaluación, con un intervalo por bootstrap.
- **FR-014**: El backtesting de VaR MUST incluir Kupiec, Christoffersen y Acerbi-Székely Z2,
  con pronósticos punto en el tiempo. Con menos de 250 observaciones el resultado es no
  concluyente.
- **FR-015**: Los escenarios de estrés MUST incluir choques paralelos, de pendiente y de
  curvatura (en unidades de factor o de puntos básicos) y escenarios condicionados a
  régimen.
- **FR-016**: La cobertura e inmunización MUST neutralizar las exposiciones declaradas con
  instrumentos declarados (mínimos cuadrados con restricciones) y reportar la exposición
  residual.
- **FR-017**: Toda regla que convierta sensibilidades o desvíos en asignaciones MUST pasar
  por el flujo de experimentos (hipótesis, dos fases, costos y pruebas múltiples). Este
  módulo mide riesgo; no declara señales rentables.

### Key Entities

- **Proceso estocástico**: parámetros, medida, discretización exacta, verosimilitud.
- **Modelo de regímenes**: parámetros por régimen, matriz de transición, probabilidades
  filtradas y suavizadas.
- **Curva**: interfaz de descuento y forward (externa o mínima de nodos).
- **Escenarios**: matriz de choques de factores con procedencia.
- **Instrumento / Cartera**: flujos fijos y cantidades.
- **Sensibilidades**: PV, DV01, KRD, duración, convexidad, deltas y gammas por factor.
- **Resultado de riesgo**: VaR, ES, IC, método, backtesting.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: La estimación de Vasicek y CIR sobre 500 trayectorias simuladas (T = 2 500
  días) tiene una cobertura de los intervalos al 95 % de entre 92 % y 98 % para κ, θ y σ.
- **SC-002**: La simulación exacta reproduce media y varianza teóricas a 1 año dentro de
  3 errores de Monte Carlo.
- **SC-003**: El modelo de regímenes recupera la matriz de transición de un proceso
  simulado de 2 regímenes con un error absoluto medio ≤ 0,05 (T = 2 000).
- **SC-004**: Los precios cerrados de cupón cero coinciden con Monte Carlo bajo ℚ dentro
  de 3 errores estándar. La variable de control reduce la varianza al menos 5 veces.
- **SC-005**: Hull-White reproduce la curva inicial con un error ≤ 1e-8 en precio.
- **SC-006**:
  - Duración y convexidad analíticas frente a diferencias finitas: diferencia relativa
    ≤ 1e-6.
  - Error de ΔΓ ante un choque de 10 pb: ≤ 1 % del error de Δ.
  - Suma de las *key-rate* durations: igual a la duración con diferencia ≤ 1e-6 bajo
    choque paralelo.
- **SC-007**: El backtesting de VaR tiene un tamaño de 3 % a 7 % (Kupiec, al 5 %) con un
  modelo correcto, y una potencia ≥ 80 % contra un modelo que subestima la volatilidad un
  30 % (T = 1 000, VaR 99 %).
- **SC-008**: La demostración con el Tesoro corre de punta a punta en menos de 5 minutos.

## Assumptions

- Las tasas del Tesoro de Yahoo (^IRX, ^FVX, ^TNX, ^TYX) son rendimientos de mercado, no
  curvas cero. La calibración ℚ con ellas es **aproximada** (rendimientos par usados como
  cero, documentado). La curva cero de producción viene del paquete hermano.
- Los bonos de la cartera de demostración son sintéticos (flujos fijos sin riesgo de
  crédito). El crédito queda para la spec siguiente.
- Se reutilizan `statsmodels` (regímenes de Markov), `arch` (GARCH) y `scipy` (no central
  χ², optimización). Las implementaciones propias se justifican y se verifican contra
  referencias.

## Clarifications

### Session 2026-11-26

- Q: ¿Frontera con el paquete hermano de curvas? → A: Estricta. Aquí van las curvas
  implícitas de los modelos, la dinámica de factores, el PCA y Diebold-Li con λ fija; el
  ajuste paramétrico y el bootstrapping quedan fuera.
- Q: ¿Alcance? → A: MVP. Crédito, afines con saltos, filtraje latente e importance
  sampling van a la spec siguiente.
- Q: ¿Datos ℚ? → A: Rendimientos del Tesoro en nodos (aproximación documentada).
