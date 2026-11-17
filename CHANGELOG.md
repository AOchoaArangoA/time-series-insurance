# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado
semántico.

## [0.2.0] — en desarrollo (spec 004)

### Cambios incompatibles

- `tsinsurance experiment run` dejará de abrir la validación fuera de muestra en la misma
  ejecución: calibrará y la validación se abrirá con `tsinsurance experiment validate`
  (US2). Mientras US2 no esté implementada, `result.json` marca esas ejecuciones con
  `phase = "calibration_and_validation"`.

### Agregado

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
