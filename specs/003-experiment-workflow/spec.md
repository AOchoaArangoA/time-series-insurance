# Feature Specification: Flujo de experimentos registrados, insumo base y entrega a agentes

**Feature Branch**: `003-experiment-workflow`

**Created**: 2026-11-09

**Status**: Implemented v0.1 (decisión por defecto a confirmar: TFT → TBT)

**Input**: User description: "Testear los ETFs TFT, TBX y TBF y registrarlo como muestra de
la funcionalidad. Entregar el paquete a otro agente para que sea capaz de usarlo y se
alimente de este proceso. Propuesta total del proceso. Zoom a cómo se llama la
información: un formato de input base con una estructura propuesta sin depender de un
insumo (p. ej. Yahoo). Publicar el repositorio para que cualquier proyecto lo use."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Insumo base independiente de la fuente (Priority: P1)

El analista (o un agente) arma un **paquete de insumos**: un directorio con un manifiesto
que describe cada serie (rol, unidades, moneda, frecuencia, rezago de publicación,
procedencia y licencia) y los datos en el contrato v1.0. Cualquier fuente (Yahoo, FRED,
Bloomberg, un Excel interno) es sólo un adaptador que produce ese paquete; el resto del
paquete nunca habla con una fuente.

**Independent Test**: un paquete escrito a mano (CSV + manifiesto) y uno generado desde
Yahoo/FRED producen exactamente el mismo tipo de objeto y pasan la misma validación.

**Acceptance Scenarios**:

1. **Given** una plantilla de paquete vacía, **When** el usuario la llena con sus datos,
   **Then** `tsinsurance bundle validate` reporta todos los errores de datos y de
   manifiesto (series sin declarar, roles inválidos, rezagos ilegibles, hash alterado).
2. **Given** una receta de descarga, **When** se ejecuta `tsinsurance bundle fetch`,
   **Then** se obtiene un paquete con la procedencia y la licencia de cada serie.

### User Story 2 - Experimentos declarativos y registrados (Priority: P1)

Un experimento se describe en un archivo `experiment.toml` (hipótesis, paquete de
insumos, activos, ideas con su malla de parámetros, supuestos de ejecución, división
calibración/validación, modelos econométricos). `tsinsurance experiment run` lo ejecuta
con todas las salvaguardas del backtesting responsable y deja: un resultado legible por
máquina (`result.json`), un reporte para humanos (`report.md`) y una línea por prueba en
una **bitácora permanente** (`registry.jsonl`) que alimenta el ajuste por pruebas
múltiples de los experimentos siguientes.

**Independent Test**: un experimento nuevo con configuraciones distintas sobre el mismo
activo se deflacta con las pruebas previas; repetir el mismo experimento no infla el
número de pruebas (una configuración cuenta una vez).

**Acceptance Scenarios**:

1. **Given** `experiment.toml` para TBT, TBX y TBF, **When** se ejecuta, **Then** cada
   idea pasa la prueba de anticipación, se reporta por activo con DSR y SPA y se registra.
2. **Given** una bitácora con pruebas anteriores sobre un activo, **When** se ejecuta un
   experimento nuevo sobre ese activo, **Then** el número de pruebas del DSR incluye las
   anteriores.

### User Story 3 - Entrega a otro agente (Priority: P2)

Un agente sin contexto previo puede, leyendo `AGENTS.md` y la habilidad
`tsinsurance-experiment`, crear un paquete de insumos, escribir un experimento,
ejecutarlo, leer `result.json` y respetar las reglas (no borrar la bitácora, declarar
todas las especificaciones probadas, no re-optimizar sobre el periodo de validación).

**Independent Test**: siguiendo sólo `AGENTS.md`, un experimento nuevo se ejecuta sin
modificar código del paquete.

### User Story 4 - Propuesta del proceso completo y publicación (Priority: P2)

Un documento describe el proceso de punta a punta (idea → receta de datos → paquete →
experimento → validación → bitácora → reporte para comité), el flujo de la información y
los pasos para publicar el paquete (licencia, política de datos de terceros, rama
principal, visibilidad).

### Edge Cases

- Serie en los datos sin declarar en el manifiesto (o al revés): error.
- Paquete modificado después de generado: el hash no coincide ⇒ error.
- Serie con licencia que no permite redistribución: el paquete se marca
  `redistributable = false` y la política de publicación lo excluye del repositorio.
- Experimento con una señal desconocida: error con la lista de señales registradas.
- Activos con historias de distinto largo (TBX inicia en 2011): cada activo usa su propia
  ventana y se informa.

## Requirements *(mandatory)*

- **FR-001**: El sistema MUST definir un paquete de insumos versionado (manifiesto
  `bundle.toml` + `market_series.csv` en el contrato v1.0) independiente de la fuente.
- **FR-002**: Cada serie del manifiesto MUST declarar `role` (`asset`, `exogenous`,
  `risk_free`), y las exógenas su `frequency`, `release_lag`, `transform` y
  `point_in_time`; la tasa libre de riesgo su convención (`dtb3_discount`,
  `annual_percent`, `period_decimal`).
- **FR-003**: Cada serie MUST registrar procedencia (fuente, consulta, fecha) y licencia
  (`license`, `redistributable`).
- **FR-004**: El sistema MUST validar el paquete (contrato de datos, coherencia
  manifiesto-datos, hash) y ofrecer plantilla, validación y descarga por receta desde la
  línea de comandos.
- **FR-005**: El sistema MUST ejecutar experimentos declarados en TOML con señales de un
  registro extensible y producir `result.json`, `report.md` y líneas en `registry.jsonl`.
- **FR-006**: La bitácora MUST ser de sólo agregado y alimentar el número de pruebas y
  la varianza de ratios de información del DSR por activo.
- **FR-007**: Cada ejecución MUST registrar huella del paquete, versión del paquete,
  commit de git y semilla.
- **FR-008**: El repositorio MUST incluir una guía para agentes (`AGENTS.md`) y una
  habilidad de Claude Code para el flujo de experimentos.
- **FR-009**: El sistema MUST documentar el proceso completo y la política de
  publicación (licencia del código, datos de terceros).

## Success Criteria *(mandatory)*

- **SC-001**: Un paquete escrito a mano y uno descargado producen el mismo tipo de objeto
  y la misma validación (prueba automatizada).
- **SC-002**: El 100 % de las inconsistencias de manifiesto del catálogo de pruebas se
  detecta con un mensaje que nombra la serie y el campo.
- **SC-003**: Un experimento con configuraciones nuevas incrementa el número de pruebas
  del DSR en esa cantidad; repetir exactamente el mismo experimento no lo incrementa.
- **SC-004**: El experimento de ETFs inversos del Tesoro se re-ejecuta sin red desde su
  paquete y reproduce los mismos valores redondeados.

## Clarifications

### Session 2026-11-09

- Q: ¿"TFT"? → A: No existe en Yahoo Finance; con TBX y TBF forma la familia de ETFs
  inversos del Tesoro de ProShares cuyo tercer miembro es **TBT** (UltraShort 20+ años).
  Se asume TBT y se agrega TLT como referencia. *Decisión por defecto, confirmar.*
- Q: ¿Formato base? → A: paquete de insumos (manifiesto TOML + CSV del contrato v1.0);
  las fuentes son adaptadores. La receta de descarga es un archivo aparte.
- Q: ¿Variables macro para el experimento? → A: sólo series públicas y sin revisiones
  relevantes: T10Y2Y, DGS10, T10YIE (inflación implícita) y CPIAUCNS; se excluye BAA10Y
  (Moody's, con derechos de autor).

## Assumptions

- La publicación (visibilidad pública, fusión a `main`) la ejecuta el dueño del
  repositorio; este flujo sólo prepara los artefactos.
- Los datos de Yahoo Finance no se redistribuyen en un repositorio público; se versiona
  la receta y la huella esperada, y el paquete se regenera localmente.
