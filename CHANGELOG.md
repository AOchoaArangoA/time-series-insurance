# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado
semántico.

## [0.2.0] — en desarrollo (spec 004)

### Cambios incompatibles

- `tsinsurance experiment run` ya **no** abre la validación fuera de muestra: con
  `train_end` sólo calibra (recibe los datos truncados en esa fecha) y fija la
  configuración. La validación se abre una vez con `tsinsurance experiment validate EXP
  --calibration RUN_ID` (spec 004, US2).
- `calibrate_validate` queda obsoleta (`DeprecationWarning`; resultado exploratorio).

### Agregado

- Spec 004 US3: **huella del código de las señales** en la identidad de cada prueba
  (`tsinsurance.experiments.fingerprint`). Cubre el AST sin docstrings ni formato, los
  valores por defecto, las variables de cierre, las funciones y constantes del usuario
  referenciadas (también entre módulos), `functools.partial`, y arreglos y DataFrames por
  sus bytes. Sin código fuente usa el *bytecode*. Si la cobertura es parcial, el resultado
  es exploratorio. Cambiar el código de una señal con el mismo nombre cuenta como pruebas
  nuevas, y la validación se rechaza si la huella no es la de la calibración. Las pruebas
  registradas antes de esta versión no tienen huella: sus claves no coinciden con las
  nuevas, así que re-ejecutarlas cuenta como pruebas adicionales (conservador, FR-013).

- Spec 006 (datos de panel; extra opcional `[panel]` con `linearmodels`):
  - `tsinsurance.panel.fit_panel`: MCO agrupado, efectos fijos, dos vías, primeras
    diferencias y efectos aleatorios; regresores absorbidos, G₁ y supuestos causales;
  - Driscoll-Kraay propio (igual a `plm::vcovSCC`) con corrección por grados de libertad;
    valores p por wild bootstrap restringido por bloques de periodos en los experimentos y
    fixed-b analítico en `fit_panel`, calibrados por Monte Carlo (el t(T−1) previsto
    sobre-rechazaba con T = 36); estabilidad Nyblom-Hansen; wild cluster bootstrap
    restringido como sensibilidad;
  - Mundlak/CRE y Hausman; diagnósticos de Wooldridge, CD de Pesaran, estacionariedad,
    ARCH, CUSUM y persistencia tipo Stambaugh;
  - diferencias en diferencias con estudio de evento, prueba de tendencias previas,
    permutación con una sola unidad tratada y advertencia de adopción escalonada;
  - bloques `[[panels]]` en experimentos con dos fases, memoria por universo parecido y
    efecto mínimo detectable.

- Spec 007 (procesos estocásticos, MVP):
  - `stochastics`: Vasicek y CIR bajo ℙ con MV y simulación exactas, IC por bootstrap
    paramétrico básico (θ con κ corregido por sesgo), *jackknife* y diagnósticos;
    regímenes de Markov ordenados por σ con filtro de Hamilton de parámetros fijos;
    cupón cero cerrado (Vasicek, CIR), Hull-White r = x + α(t), calibración ℚ con λ;
    interfaz `Curve` y `NodeCurve` mínima;
  - `simulation`: PCA y Diebold-Li (λ fija), escenarios histórico, histórico filtrado,
    Monte Carlo de factores y de la tasa corta (ℙ/ℚ declaradas), variable de control
    exacta y antitéticas;
  - `sensitivities`: bonos de flujos fijos, KRD analíticas (Σ = Fisher-Weil), convexidad,
    hessiana por nodos, Δ/Γ por factor, ΔΓ frente a revaluación completa, atribución;
  - `portfolio_risk`: VaR/ES con IC, Kupiec, Christoffersen, duraciones, Z2, estrés,
    escenarios por régimen e inmunización;
  - contrato `rate_nodes` aditivo (`rate_type`, `discount_act360`) y campos de nodo
    opcionales en el manifiesto sin cambiar huellas;
  - demostración `experiments/tesoro_riesgo/`.

### Cambiado

- Reparto de α entre familias de la validación: estrategias 0,7α, regímenes 0,15α y
  paneles 0,15α, **renormalizado** entre las familias presentes y congelado en
  `frozen.alpha_split` (antes 0,8α / 0,2α fijo en el código, aunque sólo hubiera
  regímenes). Las calibraciones anteriores conservan su reparto.

### Agregado (continuación)

- Spec 005:
  - ideas de cartera (`[[portfolios]]`) con benchmark igual ponderado de los elegibles,
    rebalanceo mensual y memoria por universo parecido (Jaccard ≥ 0,5);
  - regímenes del ciclo (`[[regimes]]`) punto en el tiempo, con HC3, Holm con variantes
    previas y justificación obligatoria;
  - `[[declared_prior_tests]]` para lo probado fuera de la bitácora;
  - familias de Holm separadas en la validación (estrategias 0,8α, regímenes 0,2α).

- Validación única en dos fases: `Bundle.as_of`, evento `calibration` con lo fijado,
  `validate_experiment` con precondiciones (bitácora declarada, mismos datos hasta el
  corte, mismo experimento y versión, git limpio), detección de periodos ya vistos por
  cualquier experimento, Holm sobre la familia pre-registrada, valor p HAC frente al
  efectivo y exposición de la calibración en la comparación de timing. Los modelos
  econométricos se calibran hasta el corte y se validan sólo con pronósticos posteriores.
- La varianza del umbral del DSR en calibración sólo usa pruebas previas cuya ventana
  termina antes del corte; las demás cuentan en N.
- "Diagnósticos de modelos no superados" es razón de exploratorio; el informe nunca dice
  "confirmatorio" en la fase de calibración.
- Advertencias de calidad de datos con escala local y sin marcar movimientos de todo el
  universo (49 falsos positivos → 0 en los ETFs sectoriales); van en un anexo.
- Conector de Yahoo: omite días sin cotización y admite `kind`/`unit` por bloque.

- Bitácora a prueba de recortes: `registry_head_before`/`registry_head` en cada
  `result.json`; `tsinsurance experiment verify REGISTRY --base BASE --results DIR`.
- Un solo escritor a la vez: bloqueo `registry.jsonl.lock` durante toda la ejecución;
  `tsinsurance experiment unlock`; código de salida 3 si la bitácora está bloqueada.
- Verificación en CI de que la bitácora sólo agrega líneas respecto de la rama base.
- Toda línea `signal`/`econometric` registra `n_obs` (en las unidades del ratio),
  `eval_start`, `eval_end` y `sharpe_se_hac`.
- `result.json` 1.2: `phase`, `status.out_of_sample`, `registry_head_before`,
  `registry_head`.
- Excepciones `ValidationPreconditionError`, `RegistryLockedError`,
  `RegistryTruncatedError`.

## [0.1.0] — 2026-11-09

Primera versión pública: contrato de datos, diagnósticos de estacionariedad, backtesting
responsable, experimentos registrados y guía para agentes (specs 001-003).
