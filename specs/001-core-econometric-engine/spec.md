# Feature Specification: Motor econométrico núcleo para inversiones de una aseguradora

**Feature Branch**: `001-core-econometric-engine`

**Created**: 2026-11-02

**Status**: Clarified

**Input**: User description: "Paquete en Python sobre la aplicación de modelos de series de
tiempo centrado en el manejo de las inversiones de una aseguradora, con toda la lógica
empaquetada y una metodología econométrica y estadística robusta."

## User Scenarios & Testing *(mandatory)*

Actores principales:

- **Analista de inversiones / riesgos**: prepara datos de mercado, ajusta modelos y produce
  pronósticos y métricas de riesgo para el comité de inversiones.
- **Actuario / responsable ALM**: usa pronósticos de tasas y retornos para el calce
  activo-pasivo y el cálculo de capital.
- **Validador de modelos / auditor**: revisa que cada modelo cumpla diagnósticos y
  backtesting antes de ser aprobado.

### User Story 1 - Preparar y diagnosticar series de mercado (Priority: P1)

El analista carga series de precios, retornos o tasas de los activos del portafolio
(bonos, acciones, índices, tasas de interés) y obtiene un diagnóstico estadístico
completo: frecuencia validada, datos faltantes tratados, transformación a retornos o
diferencias, pruebas de estacionariedad con conclusión del orden de integración,
detección de quiebres estructurales y estadísticos descriptivos (asimetría, curtosis,
autocorrelación).

**Why this priority**: Sin datos limpios y un diagnóstico de estacionariedad correcto
ningún modelo posterior es válido (Principio I). Es el cimiento de todo el paquete y por
sí solo ya entrega valor como herramienta de análisis exploratorio auditable.

**Independent Test**: Con una serie simulada de paseo aleatorio y otra AR(1) estacionaria,
el diagnóstico concluye I(1) e I(0) respectivamente y entrega un reporte legible.

**Acceptance Scenarios**:

1. **Given** una serie de precios diarios con huecos por feriados, **When** el analista
   solicita su preparación, **Then** recibe la serie alineada a la frecuencia declarada,
   con un registro de los valores imputados o eliminados y el método usado.
2. **Given** una serie de tasas de interés, **When** solicita el diagnóstico de
   estacionariedad, **Then** obtiene el resultado de al menos dos pruebas con hipótesis
   nulas opuestas, sus estadísticos, valores p, especificación (constante/tendencia,
   rezagos) y una conclusión explícita sobre el orden de integración.
3. **Given** una serie con un cambio de régimen evidente, **When** solicita el
   diagnóstico, **Then** el reporte señala la fecha candidata de quiebre estructural.

---

### User Story 2 - Ajustar y validar modelos de media y volatilidad (Priority: P1)

El analista ajusta modelos univariados para el retorno esperado (familia ARIMA/SARIMA) y
para la volatilidad condicional (familia GARCH, incluidas variantes asimétricas y
distribuciones de colas pesadas), con selección automática de orden por criterio de
información y un reporte de diagnósticos de residuos que indica si el modelo es apto.

**Why this priority**: La volatilidad y la media condicional son los insumos directos de
las métricas de riesgo y de las proyecciones del portafolio.

**Independent Test**: Con datos simulados de un ARMA(1,1)-GARCH(1,1) con parámetros
conocidos, el modelo recupera los parámetros dentro de la tolerancia y los diagnósticos
de residuos no rechazan ruido blanco.

**Acceptance Scenarios**:

1. **Given** una serie de retornos estacionaria, **When** el analista pide selección
   automática de modelo, **Then** recibe el modelo elegido, la tabla de candidatos con
   sus criterios de información y la justificación de la elección.
2. **Given** un modelo ajustado, **When** consulta su resumen, **Then** ve parámetros con
   errores estándar (robustos si aplica), criterios de información y los resultados de
   las pruebas de autocorrelación, heterocedasticidad condicional, normalidad y
   estabilidad de los residuos, con un indicador global "apto / no apto".
3. **Given** un modelo que no pasa los diagnósticos, **When** se intenta usar para
   pronosticar, **Then** el sistema emite una advertencia explícita que queda registrada
   en el resultado.

---

### User Story 3 - Pronosticar con incertidumbre y evaluar fuera de muestra (Priority: P2)

El analista genera pronósticos a varios horizontes con intervalos de confianza o
distribución predictiva, y los evalúa con validación temporal (ventana móvil o
expansiva) frente a un benchmark ingenuo, con prueba formal de igualdad de precisión.

**Why this priority**: El comité de inversiones necesita saber no sólo qué se espera,
sino cuán confiable es y si supera a una alternativa trivial.

**Independent Test**: Sobre una serie simulada, la evaluación fuera de muestra reporta
métricas de error por horizonte, cobertura empírica de los intervalos y la prueba
Diebold-Mariano contra el paseo aleatorio, sin usar información futura.

**Acceptance Scenarios**:

1. **Given** un modelo apto, **When** se pide un pronóstico a 12 períodos, **Then** se
   entregan media e intervalos a los niveles solicitados (por defecto 80 % y 95 %).
2. **Given** una serie histórica, **When** se ejecuta la validación temporal, **Then** cada
   pronóstico usa sólo información disponible en su fecha de origen y el reporte incluye
   error por horizonte, cobertura de intervalos y la comparación formal con el
   benchmark.

---

### User Story 4 - Medir el riesgo de mercado del portafolio y hacer backtesting (Priority: P2)

El analista de riesgos calcula VaR y Expected Shortfall del portafolio de inversiones
(por activo y agregado con sus ponderaciones) usando los modelos de volatilidad, a los
niveles y horizontes regulatorios, y valida esas métricas con backtesting formal.

**Why this priority**: Es la salida que conecta el paquete con el capital regulatorio y
el apetito de riesgo de la aseguradora.

**Independent Test**: Con retornos simulados de distribución conocida, el VaR al 99 %
produce una tasa de excepciones consistente con el nivel y las pruebas de Kupiec y
Christoffersen no rechazan el modelo correcto pero sí uno deliberadamente mal
especificado.

**Acceptance Scenarios**:

1. **Given** retornos de los activos y pesos del portafolio, **When** se calcula el riesgo,
   **Then** se obtienen VaR y ES por método histórico, paramétrico y basado en el modelo
   de volatilidad, al nivel y horizonte solicitados (por defecto 99,5 % a un año).
2. **Given** una serie de VaR diarios y pérdidas realizadas, **When** se ejecuta el
   backtesting, **Then** el reporte incluye número de excepciones, pruebas de cobertura
   incondicional e independencia, y la zona semáforo (verde/amarillo/rojo).

---

### User Story 5 - Reporte reproducible para comité y auditoría (Priority: P3)

El validador de modelos obtiene, para cualquier análisis, un reporte reproducible que
documenta datos de entrada (con huella), supuestos, versión del paquete, semilla,
parámetros, diagnósticos y resultados, exportable para el comité.

**Why this priority**: Facilita la gobernanza de modelos exigida por los supervisores,
pero depende de las historias anteriores.

**Independent Test**: Ejecutar el mismo análisis dos veces con la misma semilla produce
reportes idénticos, y el reporte contiene todas las secciones requeridas.

**Acceptance Scenarios**:

1. **Given** un análisis completo, **When** se exporta el reporte, **Then** contiene
   huella de datos, versión, semilla, supuestos, diagnósticos y resultados.

---

### Edge Cases

- Series demasiado cortas para la prueba o el modelo solicitado: el sistema rechaza con
  un mensaje que indica el mínimo requerido.
- Frecuencia irregular o índice temporal no monótono / duplicado: error explícito antes
  de cualquier cálculo.
- Precios no positivos al calcular retornos logarítmicos: error explícito.
- Pruebas de estacionariedad con conclusiones contradictorias: el reporte lo indica como
  "inconcluso" y explica la regla de decisión aplicada.
- No convergencia del optimizador en GARCH: se informa, se reintenta con valores
  iniciales alternativos y, si persiste, se marca el modelo como no apto.
- Activos con historia de distinta longitud en el portafolio: se informa el período común
  usado o el método de tratamiento.
- Horizontes de riesgo largos (un año) a partir de datos diarios: el método de escalado o
  simulación se declara explícitamente.

## Requirements *(mandatory)*

### Functional Requirements

**Datos y preparación**

- **FR-001**: El sistema MUST aceptar series univariadas y multivariadas indexadas por
  fecha y validar que el índice sea monótono, sin duplicados y con frecuencia declarada.
- **FR-002**: El sistema MUST transformar precios en retornos simples o logarítmicos y
  tasas en diferencias, registrando la transformación aplicada.
- **FR-003**: El sistema MUST tratar datos faltantes con un método explícito elegido por
  el usuario y registrar cuántos valores se modificaron.

**Diagnóstico**

- **FR-004**: El sistema MUST ejecutar pruebas de raíz unitaria y estacionariedad con
  hipótesis nulas opuestas y emitir una conclusión del orden de integración con su regla
  de decisión.
- **FR-005**: El sistema MUST ofrecer al menos una prueba de raíz unitaria con quiebre
  estructural endógeno.
- **FR-006**: El sistema MUST calcular estadísticos descriptivos, funciones de
  autocorrelación simple y parcial y pruebas de normalidad y de efectos ARCH.

**Modelado**

- **FR-007**: El sistema MUST ajustar modelos ARIMA/SARIMA con selección de orden por
  criterio de información (AIC, BIC, HQIC a elección).
- **FR-008**: El sistema MUST ajustar modelos de volatilidad condicional GARCH, EGARCH y
  GJR-GARCH con distribuciones normal, t de Student y t asimétrica.
- **FR-009**: Todo modelo ajustado MUST reportar parámetros con errores estándar,
  criterios de información y diagnósticos de residuos (Ljung-Box, ARCH-LM, Jarque-Bera,
  estabilidad) con un indicador global de aptitud.

**Pronóstico y validación**

- **FR-010**: El sistema MUST producir pronósticos puntuales e intervalos a niveles
  configurables para horizontes múltiples.
- **FR-011**: El sistema MUST ejecutar validación temporal con ventana móvil o expansiva,
  garantizando que no se use información posterior al origen del pronóstico.
- **FR-012**: El sistema MUST comparar cada modelo con un benchmark ingenuo mediante
  métricas de error (RMSE, MAE, MASE) y la prueba Diebold-Mariano.

**Riesgo**

- **FR-013**: El sistema MUST calcular VaR y Expected Shortfall por método histórico,
  paramétrico y condicional al modelo de volatilidad, para activos individuales y para un
  portafolio con pesos dados.
- **FR-014**: El sistema MUST ejecutar backtesting de VaR con pruebas de Kupiec y
  Christoffersen y clasificación por zonas semáforo.
- **FR-015**: El sistema MUST permitir escalar el riesgo a horizontes largos mediante un
  método declarado (regla de raíz del tiempo o simulación del modelo), con advertencia
  sobre sus supuestos.

**Reproducibilidad**

- **FR-016**: Toda simulación MUST aceptar una semilla y producir resultados idénticos con
  la misma semilla.
- **FR-017**: Todo resultado MUST poder exportarse como reporte con huella de datos,
  versión del paquete, supuestos, parámetros, diagnósticos y conclusiones.
**Alcance, datos e interoperabilidad**

- **FR-018**: El paquete MUST ser agnóstico de mercado, país y moneda en la v1: ningún
  supuesto regulatorio, calendario, moneda o convención queda fijo en el código. Los
  parámetros dependientes de jurisdicción (nivel y horizonte de capital, choques de
  estrés, calendario de días hábiles, moneda base) MUST configurarse mediante un
  "perfil" explícito; la v1 incluye un perfil genérico por defecto (99,5 % a un año).
- **FR-019**: El sistema MUST leer datos desde archivos locales (CSV y Excel) y desde
  fuentes públicas mediante conectores (al menos FRED y Yahoo Finance; otros bancos
  centrales vía un mecanismo de conector extensible). Toda descarga MUST registrar
  fuente, identificador de serie, fecha de consulta y rango para poder replicarla.
- **FR-019a**: El paquete MUST incluir ejercicios con datos reales públicos que puedan
  re-ejecutarse de punta a punta, guardando una instantánea de los datos usados para que
  el resultado sea replicable aun si la fuente cambia.
- **FR-019b**: El paquete MUST publicar el esquema de los insumos (contrato de datos):
  columnas, tipos, unidades, frecuencia y reglas de validación para series de mercado y
  portafolios, y MUST poder generar plantillas vacías (CSV/Excel) y validar archivos del
  usuario contra ese esquema con mensajes de error claros.
- **FR-020**: La v1 MUST centrarse en retornos de activos y tasas individuales. La
  construcción, interpolación y extrapolación de curvas de rendimiento queda fuera del
  paquete (será un paquete separado). El paquete MUST aceptar como entrada series de
  tasas por plazo (p. ej. nodos de una curva ya construida) usando el mismo contrato de
  datos, para permitir la comunicación futura entre ambos paquetes.

### Key Entities *(include if feature involves data)*

- **Serie de mercado**: observaciones de un activo o factor (precio, retorno, tasa) con
  fecha, frecuencia, moneda, unidad y transformación aplicada.
- **Portafolio**: conjunto de activos con pesos o montos, moneda base y fecha de corte.
- **Reporte de diagnóstico**: resultado de pruebas estadísticas (estadístico, valor p,
  especificación, conclusión) asociado a una serie.
- **Modelo ajustado**: especificación, parámetros con errores estándar, criterios de
  información, diagnósticos de residuos e indicador de aptitud.
- **Pronóstico**: horizonte, media, intervalos/distribución predictiva, origen y modelo
  que lo generó.
- **Medida de riesgo**: VaR/ES con nivel, horizonte, método y resultados de backtesting.
- **Reporte reproducible**: agrupa los anteriores con huella de datos, versión y semilla.
- **Contrato de datos (esquema de insumos)**: definición versionada de columnas, tipos,
  unidades, frecuencia y reglas de validación de cada insumo; genera plantillas.
- **Perfil de jurisdicción**: conjunto de parámetros regulatorios y de mercado (nivel,
  horizonte, choques, calendario, moneda) que se inyecta en los cálculos.
- **Fuente de datos**: origen (archivo, FRED, Yahoo, otro conector) con metadatos de
  consulta para replicar la descarga.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En simulaciones con procesos generadores conocidos (al menos 500
  réplicas, muestras de 500 observaciones, α = 5 %), el diagnóstico identifica el orden
  de integración correcto en al menos el 90 % de las series I(0) y el 85 % de las series
  I(1), y concluye un orden *incorrecto* en no más del 7 % de los casos (el resto se
  reporta como inconcluso). El límite para I(1) refleja el tamaño α de las pruebas de
  raíz unitaria combinado con la potencia de KPSS (≈ 0,95 × 0,94).
- **SC-002**: Los parámetros estimados de modelos ARMA-GARCH sobre datos simulados caen
  dentro de 2 errores estándar del valor verdadero en al menos el 95 % de las réplicas.
- **SC-003**: Los resultados de las pruebas estadísticas coinciden con implementaciones
  de referencia (statsmodels, arch o R) con una diferencia relativa menor a 1e-6 sobre
  conjuntos de referencia publicados.
- **SC-004**: La cobertura empírica de los intervalos de pronóstico al 95 % en datos
  simulados bajo el modelo correcto está entre 93 % y 97 %.
- **SC-005**: El backtesting rechaza un modelo de VaR deliberadamente mal especificado y
  no rechaza el correctamente especificado en al menos el 90 % de las réplicas.
- **SC-006**: Un analista puede pasar de un archivo de precios a un reporte completo de
  diagnóstico, modelo, pronóstico y riesgo en menos de 15 minutos siguiendo el tutorial.
- **SC-007**: Ejecutar dos veces el mismo análisis con la misma semilla produce reportes
  idénticos en el 100 % de los casos.
- **SC-008**: Un usuario puede generar la plantilla de insumos, llenarla con sus datos y
  validarla; el 100 % de los errores de formato se reportan con fila, columna y regla
  incumplida.
- **SC-009**: Cada ejercicio con datos reales se re-ejecuta desde su instantánea y
  reproduce exactamente los resultados publicados.

## Clarifications

### Session 2026-11-02

- Q: ¿Qué mercado y moneda priorizar en v1? → A: Ninguno en particular; v1 muy general,
  agnóstica de país y moneda, con parámetros de jurisdicción configurables por perfil.
- Q: ¿Fuente de datos para v1? → A: Archivos locales + fuentes públicas (FRED, Yahoo,
  bancos centrales), con ejercicios replicables con datos reales y entrega del esquema
  (estructura) de los insumos futuros.
- Q: ¿Curvas de rendimiento en v1? → A: No; interpolación/extrapolación de curvas irá
  en un paquete separado. Este paquete sólo consume nodos de tasas con un contrato de
  datos compatible para la comunicación futura.

## Assumptions

- Los usuarios son analistas con formación cuantitativa básica que trabajan en Python o
  notebooks; no se requiere interfaz gráfica en v1.
- Frecuencias soportadas en v1: diaria, semanal y mensual.
- Nivel de confianza por defecto para riesgo de capital: 99,5 % a un año (perfil
  genérico); cualquier jurisdicción se modela como un perfil configurable.
- Los conectores a fuentes públicas pueden requerir clave de API del usuario (p. ej.
  FRED); las claves se leen de variables de entorno y nunca se versionan.
- Las pruebas automatizadas no dependen de la red: usan instantáneas de datos o
  simulaciones; las descargas reales se prueban aparte con una marca específica.
- La modelación multivariada (VAR/VECM, cointegración, correlaciones dinámicas DCC),
  los generadores de escenarios económicos (ESG) y el calce activo-pasivo (ALM) quedan
  fuera de esta especificación y se abordarán en especificaciones posteriores.
- Modelos de machine learning / deep learning quedan fuera de v1; sólo se agregarán si
  superan estadísticamente a los modelos econométricos (Principio VII).
- No se incluyen datos confidenciales de la aseguradora en el repositorio.
