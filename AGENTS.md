# AGENTS.md — guía para agentes que usan `tsinsurance`

Este archivo es para **cualquier agente de IA** (Claude Code, Codex, Cursor, agentes
propios) que deba usar el paquete para probar ideas cuantitativas o modelos
econométricos. Para *desarrollar* el paquete, lea además `CLAUDE.md` y la constitución
`.specify/memory/constitution.md`.

## Qué es

Un paquete Python de series de tiempo para decisiones cuantitativas de inversión con
backtesting **responsable**: supuestos explícitos, datos punto-en-el-tiempo, prueba de
anticipación, inferencia con incertidumbre, ajuste por pruebas múltiples y validación
doble (estadística + económica) de los modelos econométricos.

## Flujo en 5 pasos (sin escribir código)

```bash
uv sync --all-extras                                  # 0. entorno

# 1. Datos: un PAQUETE DE INSUMOS (formato base, independiente de la fuente)
uv run tsinsurance bundle template mi_exp/data        #    a) plantilla para llenar a mano, o
uv run tsinsurance bundle fetch mi_exp/recipe.toml mi_exp/data   # b) receta (Yahoo/FRED/CSV)
uv run tsinsurance bundle validate mi_exp/data        #    debe decir "Paquete válido"

# 2. Experimento: mi_exp/experiment.toml (ver ejemplo abajo)
uv run tsinsurance experiment signals                 #    señales disponibles

# 3. Ejecutar (registra cada prueba en la bitácora)
uv run tsinsurance experiment run mi_exp/experiment.toml

# 4. Leer mi_exp/results/<run_id>/result.json  (máquina) y report.md (humanos)
# 5. Reportar según las reglas de interpretación (abajo)
```

Ejemplo completo y real: `experiments/inverse_treasury/` (receta, experimento, resultados).

## Paquete de insumos (formato base)

Directorio con `bundle.toml` (manifiesto) y `market_series.csv` (contrato de datos v1.0,
formato largo: `date, series_id, value, kind, unit, currency, frequency, source`).

Cada serie del manifiesto (`[[series]]`):

| Campo | Obligatorio | Valores |
|-------|-------------|---------|
| `id` | sí | igual a `series_id` en el CSV |
| `role` | sí | `asset` (precio de retorno total), `exogenous` (variable explicativa), `risk_free` (a lo sumo una) |
| `release_lag` | exógenas y rf | rezago de publicación desde el **fin del periodo**: `"1B"` (mercado), `"20D"` (IPC)… |
| `transform` | no | `level`, `diff`, `pct_change`, `yoy` |
| `point_in_time` | no | `false` si la serie se revisa y se usa su versión actual |
| `rf_convention` | rf | `dtb3_discount`, `annual_percent`, `period_decimal` |
| `license`, `redistributable` | sí | condiciones de uso de la fuente |

Cualquier fuente sirve: el paquete nunca depende de Yahoo ni de FRED; esas sólo aparecen
en la receta.

## `experiment.toml`

```toml
[experiment]
id = "mi-experimento"            # estable: identifica el experimento en la bitácora
hypothesis = "..."               # OBLIGATORIO escribirla ANTES de ejecutar
registry = "../registry.jsonl"   # bitácora compartida (no cambiar sin razón)

[data]
bundle = "data"
assets = ["TLT", "TBF"]

[execution]                       # supuestos explícitos
lag = 1                           # 0 = optimista (órdenes al cierre)
cost_bps = 5.0                    # o tabla por activo: cost_bps = { TBF = 8.0 }
slippage_bps = 2.0
allow_short = false

[validation]
alpha = 0.05                      # 0.01, 0.025, 0.05 o 0.10
reps = 500
seed = 1
train_end = "2018-12-31"          # calibración hasta aquí; validación única después

[[ideas]]
name = "tendencia"
signal = "sma_crossover"          # ver `tsinsurance experiment signals`
  [ideas.grid]
  fast = [20, 50]
  slow = [150, 200]

[[econometric]]
name = "macro"
asset = "TBF"
regressors = ["T10Y2Y", "d_DGS10"]
derived = { d_DGS10 = { from = "DGS10", op = "diff" } }
position = "long_cash"            # long_cash, long_short, proportional
min_train = 60
```

## `result.json` (versión 1.0)

| Clave | Contenido |
|-------|-----------|
| `provenance` | `run_id`, versión del paquete, commit de git, huella del paquete de insumos, semilla, pruebas previas por activo |
| `assumptions` | ejecución, α, ventana, inicio de cada activo |
| `ideas.<nombre>.lookahead` | prueba de anticipación por activo (`has_lookahead`, `conclusive`) |
| `ideas.<nombre>.selection` | por activo: mejor configuración, `sharpe`, `info_ratio` (vs comprar y mantener), `n_trials` (incluye bitácora), `dsr`, `spa_p`, `significant` |
| `ideas.<nombre>.configurations` | métricas de cada configuración |
| `calibration.<nombre>` | elección en calibración y resultado fuera de muestra (una sola vez) |
| `econometric.<nombre>` | `verdict` (cuadrante, exploratorio, no concluyente, diagnósticos), `oos_r2`, `clark_west_p`, `pesaran_timmermann_p`, Sharpe del modelo vs la regla con media histórica y su valor p |

## Reglas no negociables para agentes

1. **No borre ni edite** `experiments/registry.jsonl`. Es la memoria de todo lo probado y
   alimenta el ajuste por pruebas múltiples. Toda ejecución queda registrada.
2. **Escriba la hipótesis antes de ejecutar** y no cambie `train_end` después de ver la
   validación. Re-optimizar mirando el periodo de validación invalida el resultado.
3. **Declare las especificaciones probadas**: si probó varias combinaciones de regresores,
   ponga `n_specifications` en cada bloque `[[econometric]]` (el veredicto será
   "exploratorio").
4. **"Significativo" significa** `significant = true` (DSR > 1 − α **y** SPA p < α). Un
   Sharpe alto sin eso no es evidencia.
5. **Interprete el veredicto econométrico completo**: cuadrante + marcas
   (exploratorio, no concluyente, diagnósticos no superados).
6. **No use datos con `point_in_time = false`** para conclusiones de decisión sin decirlo.
7. Si una idea sale `rechazada_por_anticipacion`, corrija la señal; nunca desactive la
   prueba.
8. No publique paquetes con `redistributable = false` (ver
   `docs/politica-datos-y-publicacion.md`).

## API de Python (si necesita más control)

```python
from tsinsurance.data.bundle import Bundle
from tsinsurance.experiments import run_experiment, register_signal
from tsinsurance.backtest import run_backtest, sweep, check_lookahead, backtest_econometric

register_signal("mi_idea", lambda prices, k=1.0: ...)   # pesos objetivo causales
res = run_experiment("mi_exp/experiment.toml")
print(res.result["ideas"]["tendencia"]["selection"])
```

Documentación metodológica: `docs/methodology/`. Proceso completo:
`docs/propuesta-proceso.md`.
