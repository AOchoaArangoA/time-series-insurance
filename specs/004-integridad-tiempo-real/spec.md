# Feature Specification: Integridad del procedimiento y datos en tiempo real

**Feature Branch**: `004-integridad-tiempo-real`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "Prioridad 1 del paquete: integridad del procedimiento de
experimentos y datos en tiempo real. (A) bitácora a prueba de recortes al final, revisión
en CI, bloqueo de archivo, un solo escritor a la vez; (B) huella del código de las señales
propias en la identidad de la prueba; (C) separación lógica de la validación en dos fases,
incluidos los bloques econométricos; (D) datos de ALFRED en modo 'solo primera
publicación' y, por pedido posterior del usuario, también 'todas las versiones'; (E) inferencia IVX verificada contra R; (F) EE HAC del Sharpe con
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

### User Story 4 - Variables macro en tiempo real: primera publicación y todas las versiones (Priority: P2)

El analista usa variables macro revisables (IPC, empleo, PIB) tal como se conocían en
cada fecha de decisión, con su fecha real de publicación, de modo que un modelo macro
pueda dejar de ser exploratorio. Puede elegir, por serie, entre dos modos:

- **Primera publicación**: cada observación con el valor con que salió la primera vez.
  Nunca usa el futuro, pero ignora correcciones que ya se conocían en la fecha de
  decisión.
- **Todas las versiones**: en cada fecha de decisión, para cada periodo, la última
  versión publicada hasta ese día (incluidas las correcciones ya conocidas). Es lo más
  fiel a lo que sabía un inversionista en ese momento.

**Why this priority**: Hoy todo modelo con IPC sale exploratorio por diseño; esta es la
condición para conclusiones macro que sirvan para decidir. Tener ambos modos permite
medir cuánto cambia una conclusión según se usen o no las correcciones conocidas.

**Independent Test**: Con una serie revisada conocida, comprobar que (a) en modo
primera publicación cada fecha de decisión usa el primer valor publicado y cambiar las
revisiones posteriores no altera ningún resultado; (b) en modo todas las versiones cada
fecha de decisión usa la versión vigente ese día y cambiar versiones publicadas después
de esa fecha no altera la decisión.

**Acceptance Scenarios**:

1. **Given** una receta que pide la primera publicación de una serie, **When** se
   descarga, **Then** el paquete de insumos guarda cada valor con su fecha real de
   publicación y la serie se declara punto-en-el-tiempo.
2. **Given** una fecha de decisión, **When** se construye la variable explicativa,
   **Then** sólo se usan observaciones cuya primera publicación es anterior o igual a esa
   fecha.
3. **Given** una receta que pide todas las versiones de una serie, **When** se descarga,
   **Then** el paquete guarda cada par (periodo, versión) con su fecha de publicación y su
   fecha de reemplazo.
4. **Given** el modo todas las versiones y una fecha de decisión, **When** se construye la
   variable, **Then** para cada periodo se usa la versión vigente ese día, y las
   transformaciones (diferencias, variaciones anuales) se calculan dentro de esa misma
   versión, no mezclando versiones de distintas fechas.
5. **Given** una misma serie y un mismo modelo, **When** se ejecuta en ambos modos,
   **Then** el informe permite comparar los resultados.
6. **Given** un paquete de insumos v1.0 sin fechas de publicación, **When** se carga,
   **Then** funciona como hoy (rezago de publicación declarado).
7. **Given** una señal o modelo que usa estas variables, **When** se ejecuta la prueba de
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

El ajuste por pruebas múltiples combina pruebas de ventanas y largos distintos de forma
comparable: cada Sharpe previo se **estandariza** por su número de observaciones (o su
error estándar) antes de combinarlo, en lugar de mezclar en una sola varianza Sharpe
estimados con ruidos distintos. El proceso documenta qué regla se usa y por qué.

(Revisión 2026-11-17: "descontar el ruido de muestreo" sería incorrecto bajo la hipótesis
nula, donde la dispersión entre Sharpe estimados *es* ese ruido; ver research R7.)

**Why this priority**: La regla puede hacer el Sharpe deflactado más o menos
conservador según los largos de las ventanas; por eso se adopta sólo con evidencia de
Monte Carlo sobre tamaño y potencia.

**Independent Test**: Simular familias de estrategias sin habilidad con ventanas de largo
distinto y comprobar el tamaño del Sharpe deflactado con y sin corrección.

**Acceptance Scenarios**:

1. **Given** pruebas previas con distinto número de observaciones, **When** se calcula el
   Sharpe deflactado, **Then** cada prueba se estandariza por su número de observaciones
   en las mismas unidades que su ratio, y el umbral se reescala al largo de la prueba
   actual.
2. **Given** el Monte Carlo de tamaño, **When** la corrección no conserva el tamaño
   nominal, **Then** se mantiene la regla actual y se documenta el resultado.
3. **Given** cualquiera de los dos resultados, **When** se lee la documentación del
   proceso y de la metodología, **Then** se explica la regla vigente, su evidencia y su
   efecto en la conservaduría.

---

### User Story 7 - Experimento de aceptación con TLT, TBX y TBF (Priority: P3)

El dueño del proyecto ve el flujo completo con las salvaguardas nuevas sobre el conjunto
que pidió originalmente ("TFT" = TLT): calibración, validación única abierta una vez,
variables macro en tiempo real y bitácora verificada.

Es una **demostración del procedimiento, no un resultado confirmatorio**: el periodo
2019-2025 ya se abrió para TBX y TBF en el experimento `inverse-treasury-etfs` y para TLT
en los ejemplos de la spec 002 (validación 2017-2025). El sistema debe detectarlo y
marcarlo solo (FR-009a).

**Why this priority**: Es la demostración integrada; depende de las historias anteriores.

**Independent Test**: Ejecutar el experimento desde su receta en un entorno limpio y
verificar que ambas fases quedan registradas y la bitácora es íntegra.

**Acceptance Scenarios**:

1. **Given** la receta y el experimento, **When** se ejecutan las dos fases, **Then**
   quedan un pre-registro, las pruebas de calibración y un evento de validación por idea
   y por modelo.
2. **Given** el resultado, **When** se lee el informe, **Then** las únicas razones de
   "exploratorio" son las declaradas y explicadas, incluida "periodo posterior a
   train_end ya visto en …" para TBX y TBF, generada automáticamente.
3. **Given** los dos modos de tiempo real del IPC, **When** se pre-registra el
   experimento, **Then** `first_release` es la especificación principal y
   `all_vintages` un análisis de sensibilidad declarado (no una selección), de modo que
   la comparación no fuerza el veredicto exploratorio.

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
- Versión de ALFRED de un solo día (inicio = fin inclusivo): es válida; con fin exclusivo
  dura un día.
- Validación con el paquete vuelto a descargar: se acepta si su truncado en la fecha de
  corte tiene la misma huella que el de la calibración; si Yahoo reescaló los precios
  ajustados, se rechaza y se indica conservar la instantánea.
- Modo todas las versiones con una revisión que cambia la definición o el año base de la
  serie: la vista de cada fecha usa sólo valores de la misma versión; si la versión
  vigente no cubre la ventana del modelo, la observación queda faltante y se informa.
- Volumen: series con muchas versiones (cientos por periodo) pueden multiplicar el
  tamaño del paquete; la validación informa el número de versiones por serie.

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
- **FR-007**: La fase de validación MUST exigir:
  - calibración pre-registrada en la **bitácora declarada** (validar con otra bitácora es
    un error);
  - la misma huella del experimento;
  - la misma huella del paquete **truncado en la fecha de corte** (se pueden agregar datos
    posteriores, nunca cambiar los anteriores);
  - las mismas huellas de código de las señales y la misma versión del paquete;
  - ausencia de cambios sin confirmar, incluidos archivos no rastreados en el directorio
    del experimento y en los módulos cubiertos por las huellas.

  Sin repositorio git, la validación se permite pero queda exploratoria con la causa.
- **FR-008**: La validación MUST evaluar sólo las configuraciones y especificaciones
  fijadas en la calibración y MUST registrar un evento de validación por idea y por
  modelo.
- **FR-009**: Reabrir una validación MUST marcar el resultado como exploratorio con el
  número de aperturas, también en los modelos econométricos. La identidad del periodo
  fuera de muestra es **(activo, intervalo posterior a la fecha de corte)**, independiente
  del id del experimento, de la huella del paquete y del fin de la ventana.
- **FR-009a**: Antes de validar, el sistema MUST recorrer la bitácora y marcar como
  exploratorio, con la ejecución y el experimento que lo vieron, todo activo cuyo periodo
  posterior a la fecha de corte ya haya sido cubierto por cualquier línea previa (pruebas
  de muestra completa, validaciones de otros experimentos).
- **FR-009b**: La validación MUST ajustar por pruebas múltiples entre todas las hipótesis
  que abre (activos × ideas × modelos, familia declarada en el pre-registro) y usar
  errores robustos a autocorrelación; la comparación contra exposición constante MUST
  usar la exposición de la calibración.
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
  versión 1.0, la fecha de publicación de cada observación y, en el modo todas las
  versiones, su fin de vigencia **exclusivo** (ALFRED publica un fin inclusivo; el
  conector lo convierte sumando un día y traduce `9999-12-31` a "vigente").
- **FR-015**: El conector de FRED/ALFRED MUST poder descargar la primera publicación de
  cada observación con su fecha real de publicación.
- **FR-016**: Las variables explicativas con fecha de publicación MUST usar, en cada fecha
  de decisión, sólo observaciones publicadas hasta esa fecha; el rezago de publicación
  declarado se usa sólo cuando no hay fecha de publicación.
- **FR-017**: Una serie con fecha de publicación en todas sus observaciones MUST
  considerarse punto-en-el-tiempo.
- **FR-018**: La prueba de anticipación MUST truncar las variables por fecha de
  publicación (en ambos modos) y MUST ejercitar el flujo completo: partir de las series
  sin alinear (precios y variables truncables), y hacer dentro de la función probada la
  alineación, las variables derivadas y el walk-forward. Un flujo que recibe datos ya
  alineados o una función de regresores no truncable no cuenta como prueba.
- **FR-018a**: Las variables derivadas (diferencias, variaciones) MUST calcularse dentro
  de cada vista de tiempo real, y la disponibilidad de un valor transformado MUST ser la
  más tardía de las fechas de publicación de sus insumos.
- **FR-019**: El conector y el contrato MUST soportar también el modo **todas las
  versiones**: cada observación con su periodo, su fecha de publicación y la fecha en que
  fue reemplazada por una versión posterior (abierta si sigue vigente).
- **FR-019a**: En el modo todas las versiones, la variable en cada fecha de decisión MUST
  construirse con la vista vigente ese día; las transformaciones MUST calcularse dentro de
  esa vista (consistencia de versión).
- **FR-019b**: El modo MUST declararse por serie en el manifiesto y registrarse en el
  resultado y en la identidad de la prueba (cambiar de modo es una prueba nueva).

**Inferencia (US5, US6)**

- **FR-020**: La validación de modelos MUST incluir la prueba IVX de los coeficientes y
  reportarla junto a la HAC.
- **FR-021**: El error estándar HAC del Sharpe MUST ofrecer preblanqueo e informar cuál se
  usa.
- **FR-022**: El Sharpe deflactado MUST poder estandarizar los Sharpe de las pruebas
  previas por su número de observaciones (en las mismas unidades que el ratio registrado)
  antes de combinarlos, y reescalar el umbral al largo de la prueba actual. Toda línea de
  la bitácora MUST registrar ese número; para líneas antiguas sin él se imputa desde su
  ventana o, si no se puede, se usa el largo de la prueba actual, y se declara.
- **FR-022a**: La varianza del umbral en la calibración MUST calcularse sólo con pruebas
  cuya ventana termina antes de la fecha de corte; las demás cuentan en el número de
  pruebas (conservador) y se informan aparte. Las líneas de validación nunca entran en
  esa varianza.
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
  la fecha en que se publicó (primera publicación) o, en el modo todas las versiones, con
  su fecha de publicación y su fecha de reemplazo.
- **Vista en tiempo real**: para una fecha de decisión, el conjunto de valores de cada
  periodo vigentes ese día.
- **Regla de varianza de pruebas previas**: cómo se combinan los Sharpe de pruebas
  anteriores en el Sharpe deflactado, con su evidencia.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los recortes de 1 a N líneas al final de la bitácora se
  detectan al contrastar con los resultados publicados.
- **SC-002**: El 100 % de los cambios que editan, reordenan o borran líneas de la
  bitácora se rechazan en la revisión automática; el 100 % de los que sólo agregan líneas
  se aceptan.
- **SC-003**: Con una copia fija de la bitácora, alterar arbitrariamente cualquiera de
  estas categorías deja la calibración idéntica número a número (salvo los campos de
  procedencia del paquete completo):
  - observaciones posteriores a la fecha de corte;
  - versiones publicadas después de la fecha de corte de periodos anteriores;
  - fines de vigencia posteriores a la fecha de corte;
  - primeras publicaciones posteriores a la fecha de corte de periodos anteriores (p. ej.
    el IPC de diciembre publicado en enero).

  La identidad de las pruebas de calibración usa la huella del paquete truncado. Las
  series no punto-en-el-tiempo quedan fuera de este criterio y siguen siendo
  exploratorias.
- **SC-004**: El 100 % de los intentos de validar sin pre-registro, con otra versión del
  experimento, con otra bitácora, con código de señal distinto, con archivos no
  rastreados o con cambios sin confirmar se rechazan con la causa. El 100 % de los
  intentos de eludir la reapertura (renombrar el experimento, volver a descargar el
  paquete, extender el fin de la ventana) quedan marcados como exploratorios.
- **SC-005**: Cambiar una línea del código de una señal propia cambia la identidad de la
  prueba en el 100 % de los casos; ejecutar la misma señal sin cambios la conserva.
- **SC-006**: Con una serie revisada conocida, alterar las revisiones posteriores a la
  primera publicación no cambia ningún resultado en el modo primera publicación; en el
  modo todas las versiones, alterar versiones publicadas después de una fecha de decisión
  no cambia la decisión de esa fecha (100 % de los casos de prueba).
- **SC-006b**: El modo todas las versiones reproduce exactamente la vista que devuelve
  ALFRED consultada con esa fecha como fecha de tiempo real, para fechas al azar **y** para
  cada fecha de inicio de versión y cada último día de vigencia (incluidas versiones de un
  solo día).
- **SC-007**: La prueba IVX coincide con la implementación de referencia en R con
  diferencia relativa ≤ 1e-6, y su tamaño al 5 % con un regresor de persistencia 0,99 y
  correlación de innovaciones −0,95 está entre 3 % y 7 % (n = 300 meses).
- **SC-008**: El error estándar del Sharpe con preblanqueo coincide con la referencia en
  R (diferencia relativa ≤ 1e-6) y reduce el sesgo medido con autocorrelación por debajo
  de la mitad del actual (≈ 9 %).
- **SC-009**: Monte Carlo con al menos 2 000 réplicas por escenario sobre familias de
  estrategias realistas (mallas de tendencia y momentum sobre precios simulados, ventanas
  solapadas y de largo distinto, correlación entre pruebas de 0 a 0,97, con y sin
  autocorrelación) y dos reglas de selección (mejor de la ejecución y mejor global). La
  regla estandarizada se adopta si su tamaño al 5 % es ≤ 5 % + 2,5 errores de Monte Carlo
  en todos los escenarios **y** su potencia no es menor que la de la regla vigente; si no,
  se mantiene la regla vigente. Tamaño, potencia y decisión se documentan.
- **SC-010**: El experimento de aceptación se ejecuta de punta a punta (descarga,
  calibración, validación) en menos de 5 minutos y la bitácora queda íntegra.

## Assumptions

- Un solo escritor de la bitácora a la vez (decisión del usuario, 2026-11-17); el trabajo
  en paralelo desde varias ramas no se soporta todavía.
- La separación de la validación es lógica (el código no entrega los datos posteriores a
  la fecha de corte y todo queda registrado), no física ni con aprobación humana
  (decisión del usuario).
- ALFRED se usa en dos modos: "primera publicación" (por defecto, decisión del usuario) y
  "todas las versiones" (agregado por el usuario); la clave de FRED se lee del entorno.
- Las series que no se revisan (tasas de mercado) siguen usando el rezago declarado.
- R con los paquetes `ivx` y `sandwich` está disponible para las pruebas de referencia; si
  no lo está, esas pruebas se omiten con aviso.
- Los precios de los ETFs siguen viniendo de Yahoo Finance y no se versionan.
- **Límites de la separación lógica**: una señal que lea por su cuenta los archivos del
  disco evita el truncado y también la prueba de anticipación. Borrar a la vez líneas de
  la bitácora y resultados **aún no confirmados**, o abandonar una rama con pruebas, no se
  detecta. La garantía cubre los resultados publicados (confirmados y fusionados).

## Clarifications

### Session 2026-11-17

- Q: ¿Qué tan dura debe ser la separación de la validación? → A: **Lógica**: el código
  impide ver los datos posteriores a la fecha de corte y todo queda registrado.
- Q: ¿Datos vintage completos o sólo la primera publicación? → A: **Primera publicación**
  como modo por defecto; en una segunda respuesta el usuario pidió agregar también
  **todas las versiones** al alcance de esta spec.
- Q: ¿Varios escritores de la bitácora en paralelo? → A: **Uno solo a la vez** por ahora.
- Q: ¿Corregir la varianza de los Sharpe previos? → A: Sí, **validada por Monte Carlo** y
  documentada en el proceso.
- Q: ¿"TFT"? → A: Es **TLT** (confirmado); el experimento de aceptación usa TLT, TBX y TBF.

### Revisión econométrica del diseño (2026-11-17)

El subagente `econometrics-reviewer` encontró 6 bloqueantes, corregidos en este texto:
- **B1**: la reapertura se podía eludir. Ahora la identidad es activo + periodo, y se
  detectan periodos ya vistos (FR-009, FR-009a).
- **B2**: el experimento de aceptación ya estaba contaminado. US7 pasa a ser demostración
  con detección automática.
- **B3**: el fin de vigencia de ALFRED es inclusivo. Se convierte a exclusivo (FR-014,
  SC-006b).
- **B4**: la prueba de anticipación no ejercitaba el tiempo real. Ahora recorre el flujo
  completo (FR-018, FR-018a).
- **B5**: faltaban precondiciones de validación (FR-007).
- **B6**: unidades de `n_obs` y contradicción con R7 (FR-022, FR-022a, US6).

También se reflejan en los criterios los importantes I3 (FR-022a), I6 (SC-003), I7
(FR-009b), I8 (US7) e I11 (SC-009). Los demás quedan como tareas (research R10).
