# Data Model: Integridad del procedimiento y datos en tiempo real

## RegistryHead

Estado de la bitácora en un momento.

| Campo | Tipo | Regla |
|-------|------|-------|
| `n_lines` | int ≥ 0 | líneas no vacías |
| `last_hash` | str (64 hex) | `line_hash` de la línea `n_lines`; `GENESIS` si `n_lines = 0` |

Se guarda en `result.json` como `registry_head_before` y `registry_head` (al terminar).
Verificación: para cada resultado, `len(bitácora) ≥ n_lines` y
`line_hash(bitácora[n_lines-1]) == last_hash`.

## RegistryLock

Archivo `<bitácora>.lock` (JSON).

| Campo | Tipo |
|-------|------|
| `pid` | int |
| `host` | str |
| `run_id` | str |
| `created_at` | ISO 8601 UTC |

Estados: libre → tomado (creación exclusiva) → liberado (borrado al terminar). Un bloqueo
está **vencido** si `host` es esta máquina y `pid` no existe, o si tiene más de 6 h; sólo
`experiment unlock` lo borra.

## SignalFingerprint

| Campo | Tipo | Valores |
|-------|------|---------|
| `hash` | str (32 hex) | |
| `coverage` | str | `builtin`, `source`, `bytecode`, `none` |
| `covered` | list[str] | nombres calificados de las funciones incluidas |

Entra en `trial_key` como `signal_fingerprint`. `coverage = "none"` agrega una razón de
exploratorio.

## ExperimentPhase y eventos nuevos de la bitácora

`phase ∈ {"calibration", "validation", "full_sample"}` (`full_sample` cuando no hay
`train_end`).

Evento nuevo `kind = "calibration"` (uno por ejecución de calibración):

| Campo | Contenido |
|-------|-----------|
| `run_id`, `experiment_id`, `experiment_sha256`, `bundle_sha256`, `git_commit` | identidad |
| `train_end` | fecha de corte |
| `frozen` | por idea: activo → parámetros elegidos; por modelo: especificación |
| `frozen_sha256` | hash canónico de `frozen` |

Evento `kind = "validation"` (existente) gana `calibration_run_id`, `frozen_sha256` y
`model` (para bloques econométricos).

Transiciones: `preregistration → signal/econometric* → calibration` (fase 1);
`validation` (fase 2) exige un `calibration` previo con el mismo `experiment_sha256` y
`bundle_sha256`.

## Contrato de datos `market` 1.1

| Columna | Tipo | Obligatoria | Regla |
|---------|------|-------------|-------|
| `date` … `source` | (como 1.0) | sí | sin cambios |
| `realtime_start` | fecha | no | ≥ fin del periodo de `date` |
| `realtime_end` | fecha o vacío | no | > `realtime_start`; vacío = vigente |

Unicidad: `(date, series_id)` sin columnas de tiempo real; `(date, series_id,
realtime_start)` con ellas. Intervalos sin solape por `(series_id, date)`.

## SeriesSpec (manifiesto) — campo nuevo

| Campo | Tipo | Regla |
|-------|------|-------|
| `vintage_mode` | `first_release` \| `all_vintages` \| ausente | sólo `exogenous` (y `risk_free` si se quiere); exige `realtime_start` en todas las filas de la serie; `first_release` ⇒ una fila por `date`; con `vintage_mode`, `point_in_time` es `true` y `release_lag` se ignora (se avisa si se declaró) |

## RealTimeExogenous

Extiende `Exogenous` (mismo nombre, transformación y frecuencia).

| Atributo | Contenido |
|----------|-----------|
| `vintages` | DataFrame largo `(date, value, realtime_start, realtime_end)` |
| `mode` | `first_release` \| `all_vintages` |

Operaciones:
- `available_series()`: en `first_release`, valores transformados indexados por
  `realtime_start`;
- `view(d)`: en `all_vintages`, serie transformada vigente en `d`;
- `truncate_available(cut)`: filas con `realtime_start ≤ cut`, reabriendo `realtime_end`
  si es mayor que `cut`.

## Bundle.as_of(cut)

Paquete en memoria con las mismas declaraciones:
- activos y tasa libre de riesgo con `date ≤ cut`;
- exógenas truncadas por disponibilidad o por `realtime_start` (como arriba).

`sha256` conserva la huella del paquete completo, y se agrega `as_of = cut`.

## ResultV1_2 (claves nuevas de `result.json`)

| Clave | Contenido |
|-------|-----------|
| `result_version` | `"1.2"` |
| `phase` | `calibration` \| `validation` \| `full_sample` |
| `calibration_run_id` | en validación |
| `registry_head_before`, `registry_head` | `RegistryHead` |
| `ideas.<n>.fingerprint` | `SignalFingerprint` |
| `econometric.<n>.ivx` | Wald IVX por regresor y conjunto con valores p |
| `econometric.<n>.vintage_modes` | modo por regresor |
| `assumptions.dsr_variance_rule` | `raw` \| `standardized` |
| `assumptions.sharpe_hac` | `newey_west` \| `prewhitened` |
| `status.out_of_sample` | `pendiente` \| `abierta` \| `ninguna` |
