# Data Model: Ideas de cartera y regímenes

## PortfolioSpec (`[[portfolios]]` en experiment.toml)

| Campo | Tipo | Regla |
|---|---|---|
| `name` | str | único en el experimento |
| `universe` | list[str] | ≥ 2 activos del paquete (`role = "asset"`) |
| `signal` | str | señal de cartera registrada |
| `grid` | dict[str, list] | cada combinación es una prueba |
| `description` | str | opcional |

**Identidad del universo:** `"U:" + "+".join(sorted(universe))`.

## RegimeSpec (`[[regimes]]`)

| Campo | Tipo | Regla |
|---|---|---|
| `name` | str | único |
| `type` | `threshold` \| `spread` \| `trend` | |
| `variable` | str | `threshold`: id exógena o de la tasa libre de riesgo |
| `variables` | list[str] (2) | `spread`: a − b |
| `asset` | str | `trend`: activo de referencia |
| `months` | int ≥ 2 | `trend` |
| `op` | `>` \| `<` | `threshold`, `spread` |
| `value` | float | `threshold`, `spread` |
| `assets` | list[str] | activos analizados (por defecto `[data].assets`) |
| `min_months` | int ≥ 6 | por defecto 12 |

## Líneas nuevas de la bitácora

- `kind = "portfolio"`: los campos de `signal`, con `asset` = identidad del universo y
  `universe` (lista).
- `kind = "regime"`: `asset`, `regime`, `definition`, `months_on`, `months_off`,
  `diff_ann`, `t_hac`, `p`, `eval_start`, `eval_end`, `n_obs`.
- `kind = "validation"`: con `portfolio` o `regime`, según corresponda.

## result.json (aditivo, 1.2)

| Clave | Fase | Contenido |
|---|---|---|
| `portfolios.<n>` | calibración | `universe_id`, `lookahead`, `configurations`, `selection` (como `ideas.<n>`), `benchmark` = `equal_weight` |
| `regimes.<n>` | calibración | `definition`, `states_months`, `rows[]` por activo (`months_on/off`, `ann_on/off`, `diff_ann`, `t_hac`, `p`, `p_holm`, `inconclusive`) |
| `calibration.frozen.portfolios`, `.regimes` | calibración | lo fijado |
| `validation.portfolios.<n>`, `validation.regimes.<n>` | validación | evaluación única, `p_holm` en la familia |
