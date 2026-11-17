# Feature Specification: Integridad del procedimiento y datos en tiempo real

**Feature Branch**: `004-integridad-tiempo-real`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "Prioridad 1 del paquete: integridad del procedimiento de
experimentos y datos en tiempo real. (A) bitácora a prueba de recortes al final, revisión
en CI, bloqueo de archivo, un solo escritor a la vez; (B) huella del código de las señales
propias en la identidad de la prueba; (C) separación lógica de la validación en dos fases,
incluidos los bloques econométricos; (D) datos de ALFRED en modo 'solo primera
publicación'; (E) inferencia IVX verificada contra R; (F) EE HAC del Sharpe con
preblanqueo verificado contra R; (G) corrección de la varianza de los Sharpe previos,
adoptada sólo si el Monte Carlo conserva el tamaño del DSR y documentada en el proceso.
Prueba de aceptación: experimento registrado con TLT, TBX y TBF."

## Contexto

La versión 0.1 aplica las salvaguardas del Principio VIII, pero una revisión del código
(2026-11-17) encontró vías por las que un resultado puede parecer válido sin serlo:

1. Borrar las últimas líneas de la bitácora no se detecta (verificado: se borraron 6 de
   17 líneas y la verificación respondió "íntegra"). Recortar las pruebas fallidas
   abarata el ajuste por pruebas múltiples.
2. Los modelos econométricos se evalúan sobre toda la ventana, incluido el periodo de
   validación: quien elige regresores ve ese periodo y puede volver a elegir.
3. La separación de calibración y validación de las ideas es una regla del ejecutor, no
   una propiedad de los datos que recibe.
4. Dos señales distintas con el mismo nombre cuentan como la misma prueba.
5. Las variables macro revisables (IPC, empleo) se usan en su versión actual; todo modelo
   que las use sale "exploratorio" por diseño.

Esta especificación cierra esas vías y afina la inferencia.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bitácora a prueba de recortes (Priority: P1)

Un analista, un agente o un auditor necesita confiar en que la bitácora contiene **todas**
las pruebas hechas, no sólo las que convenía dejar. Cada resultado publicado guarda el
estado de la bitácora en ese momento (cuántas líneas tenía y la huella de la última), y
la integración continua rechaza cualquier cambio que no sea agregar líneas al final.

**Why this priority**: Sin esto, el ajuste por pruebas múltiples puede manipularse sin
dejar rastro, y todas las demás salvaguardas dependen de que la bitácora esté completa.

**Independent Test**: Ejecutar un experimento, borrar 1..N líneas del final de la
bitácora y comprobar que la verificación detecta el recorte comparando con el resultado
publicado; abrir un cambio que modifica una línea antigua y comprobar que la revisión
automática lo rechaza.

**Acceptance Scenarios**:

1. **Given** una bitácora con resultados publicados, **When** se borran las últimas
   líneas, **Then** la verificación informa el recorte e indica qué resultado lo
   demuestra.
2. **Given** un cambio propuesto que agrega líneas al final de la bitácora, **When** se
   revisa automáticamente, **Then** se acepta.
3. **Given** un cambio propuesto que edita, reordena o borra líneas existentes, **When**
   se revisa automáticamente, **Then** se rechaza con la línea afectada.
4. **Given** una ejecución en curso que escribe en la bitácora, **When** otra ejecución
   intenta escribir al mismo tiempo, **Then** la segunda se detiene con un mensaje claro
   sin dañar la bitácora.

---

### User Story 2 - Validación única con separación lógica (Priority: P1)

El analista calibra sus ideas y modelos sin poder ver el periodo de validación, y abre la
validación **una vez**, de forma explícita y registrada. Aplica tanto a las ideas
cuantitativas como a los modelos econométricos.

**Why this priority**: Es la diferencia entre un resultado fuera de muestra y uno
optimizado mirando el resultado. Hoy los modelos econométricos no la tienen.

**Independent Test**: Modificar arbitrariamente los datos posteriores a la fecha de corte
y comprobar que la fase de calibración produce exactamente el mismo resultado; intentar
abrir la validación sin pre-registro o con cambios sin confirmar y comprobar que se
rechaza.

**Acceptance Scenarios**:

1. **Given** un experimento con fecha de corte, **When** se ejecuta la fase de
   calibración, **Then** ni las señales ni los modelos ni los informes reciben datos
   posteriores a la fecha de corte (incluidos los datos publicados después de ella).
2. **Given** una calibración terminada y confirmada, **When** se abre la validación,
   **Then** se evalúa una sola vez la configuración elegida y queda un evento de
   validación en la bitácora.
3. **Given** una validación ya abierta, **When** se intenta abrir de nuevo, **Then** se
   permite sólo marcando el resultado como exploratorio e indicando cuántas veces se
   abrió.
4. **Given** cambios sin confirmar en el código o el experimento, o un experimento cuya
   calibración no está pre-registrada, **When** se intenta abrir la validación, **Then**
   se rechaza con la causa.
5. **Given** un bloque econométrico, **When** se calibra, **Then** el pronóstico y el
   veredicto usan sólo la ventana de calibración; **When** se valida, **Then** se
   reporta el desempeño fuera de muestra posterior a la fecha de corte con la
   especificación fijada.

---

### User Story 3 - Identidad del código de las señales (Priority: P2)

Cuando un agente registra una señal propia, la prueba queda identificada por **lo que la
señal hace**, no sólo por su nombre. Cambiar el código de la señal cuenta como una prueba
nueva.

**Why this priority**: Los agentes iteran señales rápidamente; sin esto, varias versiones
de una señal se cuentan como una y el ajuste por pruebas múltiples se subestima.

**Independent Test**: Registrar dos señales con el mismo nombre y código distinto y
comprobar que generan identidades distintas; registrar la misma señal dos veces y
comprobar que la identidad coincide.

**Acceptance Scenarios**:

1. **Given** dos señales con el mismo nombre y distinto código, **When** se ejecutan,
   **Then** se registran como pruebas distintas.
2. **Given** la misma señal ejecutada dos veces sin cambios, **When** se registra,
   **Then** comparte identidad (se cuenta una sola vez).
3. **Given** una señal cuyo código no puede leerse, **When** se ejecuta, **Then** se
   usa una huella alternativa y, si tampoco es posible, el resultado se marca como
   exploratorio con la causa.

---

### User Story 4 - Variables macro en su primera publicación (Priority: P2)

El analista usa variables macro revisables (IPC, empleo, PIB) tal como se conocieron **la
primera vez que se publicaron**, con su fecha real de publicación, de modo que un modelo
macro pueda dejar de ser exploratorio.

**Why this priority**: Hoy todo modelo con IPC sale exploratorio por diseño; esta es la
condición para conclusiones macro que sirvan para decidir.

**Independent Test**: Con una serie revisada conocida, comprobar que cada fecha de
decisión usa el valor de la primera publicación disponible en esa fecha y que cambiar
las revisiones posteriores no altera ningún resultado.

**Acceptance Scenarios**:

1. **Given** una receta que pide la primera publicación de una serie, **When** se
   descarga, **Then** el paquete de insumos guarda cada valor con su fecha real de
   publicación y la serie se declara punto-en-el-tiempo.
2. **Given** una fecha de decisión, **When** se construye la variable explicativa,
   **Then** sólo se usan observaciones cuya primera publicación es anterior o igual a esa
   fecha.
3. **Given** un paquete de insumos v1.0 sin fechas de publicación, **When** se carga,
   **Then** funciona como hoy (rezago de publicación declarado).
4. **Given** una señal o modelo que usa estas variables, **When** se ejecuta la prueba de
   anticipación, **Then** trunca por fecha de publicación.

---

### User Story 5 - Inferencia robusta a regresores persistentes y autocorrelación (Priority: P3)

El validador obtiene valores p correctos para los coeficientes de modelos con regresores
muy persistentes (pendiente de la curva, diferenciales) y errores estándar del Sharpe con
menos sesgo cuando los retornos tienen autocorrelación.

**Why this priority**: Afina los números de diagnóstico; no cambia la validez del
procedimiento (Clark-West ya mostró tamaño correcto con regresores persistentes).

**Independent Test**: Comparar ambos cálculos con las implementaciones de referencia en R
sobre los mismos datos y medir su tamaño por Monte Carlo.

**Acceptance Scenarios**:

1. **Given** un modelo con un regresor de persistencia alta, **When** se valida,
   **Then** el informe incluye la prueba IVX del coeficiente junto a la HAC, y la
   advertencia de persistencia remite a la IVX.
2. **Given** retornos con autocorrelación, **When** se calcula el error estándar del
   Sharpe, **Then** se ofrece la versión con preblanqueo y se informa cuál se usa.

---

### User Story 6 - Varianza de las pruebas previas corregida y documentada (Priority: P3)

El ajuste por pruebas múltiples combina pruebas de ventanas y largos distintos sin
confundir el ruido de muestreo con la dispersión real entre estrategias, y el proceso
documenta qué corrección se usa y por qué.

**Why this priority**: La corrección reduce el umbral del Sharpe deflactado (lo hace
menos conservador); por eso se adopta sólo con evidencia de Monte Carlo.

**Independent Test**: Simular familias de estrategias sin habilidad con ventanas de largo
distinto y comprobar el tamaño del Sharpe deflactado con y sin corrección.

**Acceptance Scenarios**:

1. **Given** pruebas previas con distinto número de observaciones, **When** se calcula el
   Sharpe deflactado, **Then** la varianza descuenta el ruido de muestreo de cada prueba.
2. **Given** el Monte Carlo de tamaño, **When** la corrección no conserva el tamaño
   nominal, **Then** se mantiene la regla actual y se documenta el resultado.
3. **Given** cualquiera de los dos resultados, **When** se lee la documentación del
   proceso y de la metodología, **Then** se explica la regla vigente, su evidencia y su
   efecto en la conservaduría.

---

### User Story 7 - Experimento de aceptación con TLT, TBX y TBF (Priority: P3)

El dueño del proyecto ve el flujo completo con las salvaguardas nuevas sobre el conjunto
que pidió originalmente ("TFT" = TLT): calibración, validación única abierta una vez,
variables macro de primera publicación y bitácora verificada.

**Why this priority**: Es la demostración integrada; depende de las historias anteriores.

**Independent Test**: Ejecutar el experimento desde su receta en un entorno limpio y
verificar que ambas fases quedan registradas y la bitácora es íntegra.

**Acceptance Scenarios**:

1. **Given** la receta y el experimento, **When** se ejecutan las dos fases, **Then**
   quedan un pre-registro, las pruebas de calibración y un evento de validación por idea
   y por modelo.
2. **Given** el resultado, **When** se lee el informe, **Then** las únicas razones de
   "exploratorio" son las declaradas y explicadas.

---

### Edge Cases

- Experimento sin fecha de corte: no hay fase de validación; el resultado lo informa y no
  puede presentarse como validado fuera de muestra.
- Validación pedida antes de la calibración, o con una calibración de otra versión del
  experimento: se rechaza.
- Ejecución interrumpida con la bitácora bloqueada: el bloqueo vencido se detecta y se
  informa cómo liberarlo sin perder líneas.
- Bitácora de una rama atrasada respecto de la principal: la revisión automática la
  rechaza y explica que hay que partir de la bitácora vigente (un solo escritor).
- Resultado publicado que apunta a más líneas de las que tiene la bitácora: recorte
  detectado; si apunta a menos, normal (se agregaron pruebas después).
- Bitácoras antiguas sin el estado guardado en los resultados: siguen verificando su
  cadena; la detección de recortes cubre desde la primera ejecución con esta versión.
- Primera publicación con fecha anterior al fin del periodo observado: dato inválido,
  se rechaza al validar el paquete.
- Serie con fechas de publicación sólo para parte del historial: se rechaza mezclar; o se
  declara la serie completa como no punto-en-el-tiempo.
- Señal definida como función anónima o que depende de otras funciones del usuario: la
  huella cubre lo que pueda leerse y declara la cobertura.
- Regresor no persistente en la prueba IVX: el resultado debe ser consistente con la
  inferencia HAC.
- Pocas pruebas previas (0 o 1): la corrección de varianza no aplica y se informa.

## Requirements *(mandatory)*

### Functional Requirements

**Bitácora (US1)**

- **FR-001**: Cada resultado MUST registrar el estado de la bitácora al terminar: número
  de líneas y huella de la última línea.
- **FR-002**: La verificación de la bitácora MUST poder contrastarse con los resultados
  publicados y MUST informar cualquier recorte al final, indicando el resultado que lo
  demuestra.
- **FR-003**: El proyecto MUST incluir una revisión automática de cambios que acepte sólo
  bitácoras que comienzan exactamente con la bitácora de la rama principal.
- **FR-004**: La escritura en la bitácora MUST ser exclusiva: una sola ejecución escribe a
  la vez; las demás se detienen con un mensaje claro. El reencadenado de bitácoras de
  ramas distintas queda fuera de alcance.

**Validación única (US2)**

- **FR-005**: La ejecución MUST separarse en dos fases explícitas: calibración y
  validación.
- **FR-006**: En la fase de calibración, las señales, los modelos y los informes MUST
  recibir sólo datos disponibles hasta la fecha de corte (por fecha de observación y,
  para variables con fecha de publicación, por fecha de publicación).
- **FR-007**: La fase de validación MUST exigir: calibración pre-registrada de la misma
  versión del experimento y del paquete de insumos, y ausencia de cambios sin confirmar.
- **FR-008**: La validación MUST evaluar sólo las configuraciones y especificaciones
  fijadas en la calibración y MUST registrar un evento de validación por idea y por
  modelo.
- **FR-009**: Reabrir una validación MUST marcar el resultado como exploratorio con el
  número de aperturas (comportamiento vigente, extendido a los modelos econométricos).
- **FR-010**: Los bloques econométricos MUST calibrarse con la ventana de calibración y
  validarse fuera de muestra después de la fecha de corte con la especificación fijada.

**Identidad de las señales (US3)**

- **FR-011**: La identidad de una prueba MUST incluir una huella del código de la señal
  propia; las señales incluidas en el paquete se identifican por la versión del paquete.
- **FR-012**: Si el código no puede leerse, MUST usarse una huella alternativa del
  comportamiento compilado; si tampoco es posible, el resultado MUST marcarse como
  exploratorio con la causa.
- **FR-013**: Las pruebas registradas con versiones anteriores (sin huella de código)
  MUST seguir contando en el ajuste por pruebas múltiples.

**Primera publicación (US4)**

- **FR-014**: El contrato de datos MUST admitir, de forma opcional y compatible con la
  versión 1.0, la fecha de publicación de cada observación.
- **FR-015**: El conector de FRED/ALFRED MUST poder descargar la primera publicación de
  cada observación con su fecha real de publicación.
- **FR-016**: Las variables explicativas con fecha de publicación MUST usar, en cada fecha
  de decisión, sólo observaciones publicadas hasta esa fecha; el rezago de publicación
  declarado se usa sólo cuando no hay fecha de publicación.
- **FR-017**: Una serie con fecha de publicación en todas sus observaciones MUST
  considerarse punto-en-el-tiempo.
- **FR-018**: La prueba de anticipación MUST truncar las variables por fecha de
  publicación.
- **FR-019**: La descarga de todas las versiones (no sólo la primera) queda fuera de
  alcance.

**Inferencia (US5, US6)**

- **FR-020**: La validación de modelos MUST incluir la prueba IVX de los coeficientes y
  reportarla junto a la HAC.
- **FR-021**: El error estándar HAC del Sharpe MUST ofrecer preblanqueo e informar cuál se
  usa.
- **FR-022**: El Sharpe deflactado MUST poder descontar de la varianza de las pruebas
  previas el ruido de muestreo de cada una según su número de observaciones.
- **FR-023**: La corrección de FR-022 MUST adoptarse como regla por defecto sólo si el
  Monte Carlo de tamaño la valida (SC-009); en caso contrario se mantiene la regla vigente.
- **FR-024**: La regla vigente, su evidencia de Monte Carlo y su efecto en la
  conservaduría MUST documentarse en el proceso y en la metodología.

**Compatibilidad, documentación y aceptación**

- **FR-025**: Los resultados MUST mantener compatibilidad aditiva (versión 1.x); las
  bitácoras existentes MUST seguir verificándose.
- **FR-026**: El manual de integración, la guía para agentes y la habilidad de
  experimentos MUST describir las dos fases y los nuevos campos.
- **FR-027**: MUST existir un experimento registrado con TLT, TBX y TBF que use las dos
  fases y variables macro de primera publicación.

### Key Entities

- **Estado de la bitácora**: número de líneas y huella de la última línea en un momento
  dado; se guarda en cada resultado.
- **Fase de experimento**: calibración o validación; cada una produce su resultado y sus
  eventos en la bitácora.
- **Huella de señal**: identidad del código de una señal propia, con su cobertura (código
  fuente, compilado o no disponible).
- **Observación con fecha de publicación**: valor de una serie para un periodo junto con
  la fecha en que se publicó por primera vez.
- **Regla de varianza de pruebas previas**: cómo se combinan los Sharpe de pruebas
  anteriores en el Sharpe deflactado, con su evidencia.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los recortes de 1 a N líneas al final de la bitácora se
  detectan al contrastar con los resultados publicados.
- **SC-002**: El 100 % de los cambios que editan, reordenan o borran líneas de la
  bitácora se rechazan en la revisión automática; el 100 % de los que sólo agregan líneas
  se aceptan.
- **SC-003**: Alterar arbitrariamente los datos posteriores a la fecha de corte deja la
  fase de calibración idéntica (mismo resultado, número a número) en todas las pruebas.
- **SC-004**: El 100 % de los intentos de validar sin pre-registro, con otra versión del
  experimento o con cambios sin confirmar se rechazan con la causa.
- **SC-005**: Cambiar una línea del código de una señal propia cambia la identidad de la
  prueba en el 100 % de los casos; ejecutar la misma señal sin cambios la conserva.
- **SC-006**: Con una serie revisada conocida, alterar las revisiones posteriores a la
  primera publicación no cambia ningún resultado.
- **SC-007**: La prueba IVX coincide con la implementación de referencia en R con
  diferencia relativa ≤ 1e-6, y su tamaño al 5 % con un regresor de persistencia 0,99 y
  correlación de innovaciones −0,95 está entre 3 % y 7 % (n = 300 meses).
- **SC-008**: El error estándar del Sharpe con preblanqueo coincide con la referencia en
  R (diferencia relativa ≤ 1e-6) y reduce el sesgo medido con autocorrelación por debajo
  de la mitad del actual (≈ 9 %).
- **SC-009**: Con la corrección de varianza, el tamaño del Sharpe deflactado con
  estrategias sin habilidad y ventanas de largo distinto es ≤ 6,9 % al 5 %, y la potencia
  se reporta frente a la regla vigente; si no se cumple, la regla vigente se mantiene y
  la documentación lo registra.
- **SC-010**: El experimento de aceptación se ejecuta de punta a punta (descarga,
  calibración, validación) en menos de 5 minutos y la bitácora queda íntegra.

## Assumptions

- Un solo escritor de la bitácora a la vez (decisión del usuario, 2026-11-17); el trabajo
  en paralelo desde varias ramas no se soporta todavía.
- La separación de la validación es lógica (el código no entrega los datos posteriores a
  la fecha de corte y todo queda registrado), no física ni con aprobación humana
  (decisión del usuario).
- ALFRED se usa en modo "primera publicación" (decisión del usuario); la clave de FRED se
  lee del entorno.
- Las series que no se revisan (tasas de mercado) siguen usando el rezago declarado.
- R con los paquetes `ivx` y `sandwich` está disponible para las pruebas de referencia; si
  no lo está, esas pruebas se omiten con aviso.
- Los precios de los ETFs siguen viniendo de Yahoo Finance y no se versionan.

## Clarifications

### Session 2026-11-17

- Q: ¿Qué tan dura debe ser la separación de la validación? → A: **Lógica**: el código
  impide ver los datos posteriores a la fecha de corte y todo queda registrado.
- Q: ¿Datos vintage completos o sólo la primera publicación? → A: **Sólo primera
  publicación**.
- Q: ¿Varios escritores de la bitácora en paralelo? → A: **Uno solo a la vez** por ahora.
- Q: ¿Corregir la varianza de los Sharpe previos? → A: Sí, **validada por Monte Carlo** y
  documentada en el proceso.
- Q: ¿"TFT"? → A: Es **TLT** (confirmado); el experimento de aceptación usa TLT, TBX y TBF.
