# Constitución de `tsinsurance` (Time Series for Insurance Investments)

Paquete Python para modelar, pronosticar y medir el riesgo de las inversiones de una
aseguradora con series de tiempo, siguiendo una metodología econométrica y estadística
robusta, reproducible y auditable.

## Core Principles

### I. Rigor econométrico antes que ajuste (NO NEGOCIABLE)

Ningún modelo se declara válido sólo por su ajuste dentro de muestra.

- Todo flujo de modelado MUST seguir el ciclo Box-Jenkins extendido: identificación
  → estimación → diagnóstico → validación fuera de muestra → uso.
- Antes de estimar, el paquete MUST evaluar estacionariedad con al menos dos pruebas de
  hipótesis nula opuesta (p. ej. ADF/Phillips-Perron y KPSS) y reportar el orden de
  integración elegido y su justificación. Para series con posibles quiebres MUST
  ofrecerse una prueba con quiebre estructural (p. ej. Zivot-Andrews).
- Tras estimar, MUST ejecutarse y reportarse diagnósticos de residuos: autocorrelación
  (Ljung-Box), heterocedasticidad condicional (ARCH-LM), normalidad (Jarque-Bera) y
  estabilidad de parámetros (CUSUM o equivalente).
- Para sistemas multivariados (VAR/VECM) MUST evaluarse cointegración (Johansen) y la
  estabilidad del sistema (raíces dentro del círculo unitario).
- Un modelo que falla diagnósticos MUST marcarse explícitamente como tal en su
  resultado; nunca se oculta el fallo.

### II. Validación fuera de muestra sin fuga de información

- La evaluación de pronósticos MUST usar validación temporal (rolling o expanding
  window); está prohibido el k-fold aleatorio sobre series de tiempo.
- Ninguna transformación (escalado, imputación, selección de orden) puede usar
  información posterior al origen del pronóstico. Las pruebas MUST verificarlo.
- Toda comparación de modelos MUST incluir un benchmark ingenuo (random walk / media
  histórica) y una prueba formal de igualdad de precisión (Diebold-Mariano, o
  Giacomini-White cuando aplique).
- Los modelos de riesgo (VaR / Expected Shortfall) MUST pasar backtesting formal:
  Kupiec (POF), Christoffersen (independencia) y, para ES, una prueba acorde
  (p. ej. Acerbi-Szekely).

### III. Cuantificación de la incertidumbre

- Todo pronóstico MUST devolver intervalos o la distribución predictiva, no sólo la
  media. Se documenta el método (analítico, bootstrap, simulación).
- Los parámetros MUST reportarse con errores estándar; cuando haya heterocedasticidad
  o autocorrelación se usan errores robustos (HC/HAC Newey-West) y se indica cuál.
- Los escenarios de estrés y simulaciones MUST ser reproducibles mediante semilla
  explícita (`numpy.random.Generator`).

### IV. Pertinencia actuarial, agnóstica de jurisdicción

- El dominio central es el portafolio de inversiones de una aseguradora: renta fija,
  renta variable, inmuebles y efectivo, y su calce con los pasivos (ALM).
- Las métricas de riesgo MUST ser compatibles con marcos de capital basados en riesgo
  (Solvencia II / RBC): VaR y Expected Shortfall a nivel y horizonte configurables,
  escenarios de choque de tasas y spreads.
- El paquete MUST ser agnóstico de país, moneda y regulador: todo parámetro de
  jurisdicción (nivel, horizonte, choques, calendario, moneda) se inyecta mediante un
  perfil explícito; ningún valor regulatorio se fija en el código.
- La construcción, interpolación y extrapolación de curvas de rendimiento
  (Nelson-Siegel, Svensson, Smith-Wilson) vive en un paquete hermano. Este paquete
  consume nodos de tasas mediante un contrato de datos compartido y MUST mantener esa
  interfaz estable para la interoperabilidad.
- Supuestos de dominio (frecuencia, convención de días, moneda, horizonte) MUST ser
  explícitos en la API, nunca implícitos.

### IV-bis. Datos reales, replicables y con contrato

- Todo insumo MUST validarse contra un esquema versionado y publicado (contrato de
  datos) que el paquete puede exportar y convertir en plantillas para el usuario.
- Los ejercicios con datos reales MUST poder re-ejecutarse a partir de una instantánea
  versionada con metadatos de fuente, consulta y hash.
- Las pruebas automatizadas MUST NOT depender de la red.

### V. Biblioteca primero, API tipada y reproducible

- Toda funcionalidad vive en el paquete `tsinsurance` (layout `src/`), es importable,
  testeable de forma aislada y documentada; un CLI delgado es opcional encima.
- La API pública MUST tener anotaciones de tipo completas (`mypy --strict`) y
  docstrings estilo NumPy con referencias bibliográficas para cada método estadístico.
- Entradas y salidas MUST ser `pandas` con `DatetimeIndex`/`PeriodIndex` y frecuencia
  validada; los resultados se devuelven como objetos inmutables (dataclasses) con un
  método `summary()` legible.
- Se reutilizan bibliotecas consolidadas (`statsmodels`, `arch`, `scipy`) antes que
  implementaciones propias; una implementación propia MUST justificarse y validarse
  contra una referencia publicada o contra R/statsmodels.

### VI. Pruebas primero y verificación numérica

- TDD: las pruebas se escriben antes de la implementación y deben fallar primero.
- Cada estimador MUST tener: (a) pruebas con datos simulados de un proceso generador
  conocido que recuperen los parámetros dentro de una tolerancia, (b) pruebas de
  regresión contra valores de referencia publicados o de otro software, y (c) pruebas
  de propiedades (`hypothesis`) cuando sea razonable.
- Cobertura mínima de 90 % en `src/tsinsurance`; CI MUST correr `ruff`, `mypy` y
  `pytest` en cada PR.

### VII. Simplicidad y transparencia

- Se empieza por el modelo más simple que pasa los diagnósticos (parsimonia; criterio
  de información AIC/BIC/HQIC reportado). La complejidad adicional (ML, deep learning)
  MUST justificarse con mejora estadísticamente significativa fuera de muestra.
- Sin "cajas negras": cada resultado expone supuestos, parámetros y diagnósticos.

## Restricciones técnicas

- Python >= 3.11; gestión de entorno y dependencias con `uv`; empaquetado con
  `pyproject.toml` (hatchling).
- Dependencias núcleo: `numpy`, `pandas`, `scipy`, `statsmodels`, `arch`.
  Dependencias opcionales por extras (`[data]`, `[ml]`, `[viz]`).
- Calidad: `ruff` (lint + formato), `mypy --strict`, `pytest` + `pytest-cov` +
  `hypothesis`, `pre-commit`.
- Datos: el paquete no incluye datos confidenciales; los ejemplos usan datos públicos
  (p. ej. FRED, bancos centrales) o simulados. Las credenciales nunca se versionan.

## Flujo de desarrollo (Spec-Driven Development)

- Cada capacidad nueva sigue el flujo Spec Kit:
  `/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks`
  → `/speckit-analyze` → `/speckit-implement`.
- Las especificaciones (`specs/NNN-*/spec.md`) describen el QUÉ y el PORQUÉ en términos
  de negocio y estadística; el plan describe el CÓMO.
- Todo PR MUST referenciar su especificación y pasar la revisión de la sección
  "Constitution Check" del plan.
- Los cambios metodológicos (nuevo test, nuevo estimador, cambio de supuesto) MUST
  documentarse en `docs/methodology/` con referencias bibliográficas.

## Governance

- Esta constitución prevalece sobre cualquier otra práctica del repositorio.
- Enmiendas: se proponen por PR modificando este archivo, con justificación y plan de
  migración si afecta código existente; requieren aprobación del responsable del
  proyecto.
- Versionado semántico de la constitución: MAJOR para eliminar o redefinir principios,
  MINOR para agregar principios o secciones, PATCH para aclaraciones.
- Cada revisión de código verifica cumplimiento de los principios I-VII (incluido IV-bis); toda
  excepción se registra en la tabla "Complexity Tracking" del plan correspondiente.
- La guía operativa para agentes de IA está en `CLAUDE.md`.

**Version**: 1.1.0 | **Ratified**: 2026-11-02 | **Last Amended**: 2026-11-02
