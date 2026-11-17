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
