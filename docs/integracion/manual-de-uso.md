# Manual de integración: cómo otro sistema se conecta a `tsinsurance` y lo consume

Este manual está pensado para **otro sistema** que quiera usar el paquete como
componente: un agente de IA, un orquestador (Airflow, Prefect, cron), una aplicación en
otro lenguaje o un *notebook*. Explica qué es el paquete, cómo se instala, cómo se
verifica la conexión y cuáles son sus tres interfaces: **entrada**, **configuración** y
**salida**. No describe ningún experimento en particular. Para eso están `AGENTS.md` y
`experiments/inverse_treasury/`.

> Prompt listo para entregar a un agente: [`prompt-agente.md`](prompt-agente.md).

---

## 1. Introducción: qué es y qué resuelve

`tsinsurance` es un paquete Python (MIT) de series de tiempo para **asistir decisiones
cuantitativas de inversión**, con foco en el portafolio de una aseguradora. Responde a
la pregunta *"¿esta idea o este modelo agrega valor de verdad, o es suerte o un
artefacto del backtest?"*.

Recibe series de precios, variables macro y una tasa libre de riesgo, más una
descripción declarativa de lo que se quiere probar. Con eso:

1. **Valida los datos** contra un contrato fijo (formato base independiente de la
   fuente).
2. **Prueba ideas cuantitativas**: señales de tendencia y volatilidad, o señales
   propias del usuario, con ejecución, costos y tasa libre de riesgo explícitos.
3. **Prueba modelos econométricos** con variables explicativas (regresión predictiva
   *walk-forward*).
4. **Aplica salvaguardas automáticas**:
   - prueba de anticipación (*look-ahead*);
   - datos punto-en-el-tiempo con rezago de publicación;
   - ajuste por pruebas múltiples (Sharpe deflactado, SPA de Hansen, Holm);
   - separación de calibración y validación única.
5. **Entrega el resultado** en formato de máquina (`result.json`) y para humanos
   (`report.md`).
6. **Registra cada prueba** en una bitácora permanente (`registry.jsonl`, encadenada
   por hash). Gracias a eso, el siguiente experimento "sabe" cuánto se ha probado antes
   y se ajusta por ello.

Lo que **no** hace:
- No da recomendaciones de inversión por sí mismo.
- No descarga datos salvo que se le pida con una receta.
- No interpola curvas de tasas: eso queda para un paquete hermano.

## 2. Formas de conexión

| Modo | Para quién | Cómo se invoca | Ventaja |
|------|-----------|----------------|---------|
| **A. Línea de comandos** | cualquier lenguaje u orquestador | `tsinsurance <comando>` por subproceso | No requiere escribir Python; entrada y salida en archivos |
| **B. Biblioteca Python** | aplicaciones y *notebooks* Python | `from tsinsurance... import ...` | Señales propias, control fino, objetos en memoria |
| **C. Agente de IA** | Claude Code, Codex, Cursor, agentes propios | el agente usa A o B guiado por `AGENTS.md` | Diseña, ejecuta e interpreta siguiendo las reglas |

En los tres modos el contrato es el mismo:

```text
  ENTRADA                        CONFIGURACIÓN                 SALIDA
  paquete de insumos      +      experiment.toml        ──▶    results/<run_id>/result.json  (máquina)
  (bundle.toml +                 (qué probar y con             results/<run_id>/report.md    (humanos)
   market_series.csv)             qué supuestos)               registry.jsonl                (bitácora, se agrega)
```

El sistema consumidor sólo necesita producir los dos archivos de entrada y el de
configuración, y luego leer el JSON de salida.

## 3. Instalación

Requisitos: **Python ≥ 3.11** y acceso a GitHub. No hacen falta claves, salvo para
descargar datos de FRED (`FRED_API_KEY` en el entorno; nunca en archivos).

```bash
# Versión fija (recomendada para producción, cuando exista la etiqueta v0.1.0):
pip install "tsinsurance[backtest] @ git+https://github.com/AOchoaArangoA/time-series-insurance@v0.1.0"

# Última versión de la rama principal:
pip install "tsinsurance[backtest] @ git+https://github.com/AOchoaArangoA/time-series-insurance@main"

# Con uv, en el proyecto consumidor:
uv add "tsinsurance[backtest] @ git+https://github.com/AOchoaArangoA/time-series-insurance@main"
```

| Extra | Agrega | Cuándo |
|-------|--------|--------|
| `backtest` | `bt` (motor de referencia) | recomendado siempre |
| `yahoo` | `yfinance` | recetas que descargan de Yahoo Finance |
| `excel` | `openpyxl` | insumos en Excel |
| `viz` | `matplotlib` | gráficos propios |

Para fijar la versión en un `requirements.txt` o `pyproject.toml`, use la etiqueta o el
*commit* exacto (`@<sha>`). El resultado registra siempre la versión del paquete y del
*commit*.

## 4. Prueba de conexión (2 minutos, sin red)

La carpeta [`examples/integracion/`](../../examples/integracion/) contiene una prueba
autosuficiente con datos simulados. Cópiela al proyecto consumidor y ejecute:

```bash
python generar_paquete_sintetico.py data          # 1. escribe y sella data/
tsinsurance bundle validate data                  # 2. ⇒ "Paquete válido: data"
tsinsurance experiment run experiment.toml        # 3. ⇒ calibración: "... línea(s) registradas; resultados en .../results/<run_id>"
tsinsurance experiment verify registry.jsonl      # 4. ⇒ "Bitácora íntegra."
python senal_propia.py                            # 5. (opcional) señal propia desde Python
```

La conexión es correcta si se cumple todo esto:
- los cuatro comandos terminan con **código de salida 0**;
- existe `results/<run_id>/result.json`;
- `result.json["status"]["exploratory_reasons"]` es una lista vacía (`[]`);
- **ninguna** idea sale significativa, porque los datos simulados no tienen habilidad.

Si algo aparece como significativo con datos simulados, avise: indica un problema.

Tiempo de referencia: unos 3 s para la ejecución del paso 3.

## 5. Estructura recomendada en el proyecto consumidor

```text
mi_proyecto/
├── experimentos/
│   ├── registry.jsonl            # bitácora ÚNICA del proyecto (la crea el paquete; nunca editar)
│   └── mi_experimento/
│       ├── recipe.toml           # (opcional) cómo descargar los datos
│       ├── data/                 # paquete de insumos (no versionar si no es redistribuible)
│       │   ├── bundle.toml
│       │   └── market_series.csv
│       ├── experiment.toml       # registry = "../registry.jsonl"
│       └── results/<run_id>/     # result.json, report.md (los escribe el paquete)
```

- Use **una sola bitácora por proyecto**, compartida por todos sus experimentos. Es lo
  que permite que el ajuste por pruebas múltiples acumule lo probado.
- Versione en git `experiment.toml`, `recipe.toml`, `results/` y `registry.jsonl`. Si
  ejecuta dentro de un repositorio git con cambios sin confirmar, el resultado se marca
  como **exploratorio**.

## 6. Interfaz de entrada: el paquete de insumos (formato base v1.0)

Es un directorio con dos archivos. Cualquier fuente sirve: un proveedor interno,
Bloomberg, Excel o Yahoo. El análisis nunca depende de ella.

### 6.1 `market_series.csv` (formato largo, una fila por fecha y serie)

| Columna | Tipo / valores permitidos |
|---------|---------------------------|
| `date` | fecha ISO `AAAA-MM-DD`. Datos mensuales con fecha de **fin de mes** |
| `series_id` | texto `[A-Za-z0-9_.:^=-]+`; debe coincidir con `id` del manifiesto |
| `value` | número. Para `kind = price` debe ser > 0 |
| `kind` | `price`, `return`, `rate`, `index` |
| `unit` | `level`, `percent`, `decimal`, `bps` |
| `currency` | código ISO de 3 letras (`USD`, `COP`, `EUR`…) |
| `frequency` | `D`, `B` (días hábiles), `W`, `M` |
| `source` | texto libre (proveedor) |

Para los precios, use **precios de retorno total** (ajustados por dividendos) con
`unit = level`.

### 6.2 `bundle.toml` (manifiesto)

```toml
[bundle]
version = "1.0"
schema_version = "1.0"
name = "mi_paquete"
description = "..."
sha256 = ""            # lo llena `tsinsurance bundle seal`

[[series]]             # uno por serie
id = "TLT"
role = "asset"         # asset | exogenous | risk_free (a lo sumo una)
license = "Yahoo Finance, uso personal"
redistributable = false

[[series]]
id = "T10Y2Y"
role = "exogenous"
release_lag = "1B"     # rezago de publicación desde el FIN del periodo: "1B", "20D", ...
transform = "level"    # level | diff | pct_change | yoy
point_in_time = true   # false si la serie se revisa y se usa su versión actual
license = "FRED"
redistributable = true

[[series]]
id = "DTB3"
role = "risk_free"
release_lag = "1B"
rf_convention = "dtb3_discount"   # dtb3_discount | annual_percent | period_decimal
license = "FRED"
redistributable = true
```

### 6.3 Cómo producirlo

| Origen de los datos | Comando |
|---------------------|---------|
| Archivos propios | `tsinsurance bundle template data` (plantilla), reemplace datos y declaraciones, luego `tsinsurance bundle seal data` |
| Yahoo / FRED / CSV con receta | `tsinsurance bundle fetch recipe.toml data` (ver `experiments/inverse_treasury/recipe.toml`) |
| Desde código | escriba los dos archivos y llame a `tsinsurance.data.bundle.seal_bundle("data")` |

Valide siempre con `tsinsurance bundle validate data` y revise el resumen con
`tsinsurance bundle show data`. El esquema formal está disponible en JSON Schema:
`tsinsurance schema market`.

## 7. Interfaz de configuración: `experiment.toml`

```toml
[experiment]
id = "mi-experimento"            # estable; identifica el experimento en la bitácora
hypothesis = "..."               # obligatoria, escrita ANTES de ejecutar
registry = "../registry.jsonl"   # relativa a este archivo

[data]
bundle = "data"                  # relativa a este archivo
assets = ["TLT", "IEF"]          # ids con role = "asset"

[execution]                      # supuestos explícitos
lag = 1                          # 1 = se opera al cierre siguiente (0 es optimista)
cost_bps = 5.0                   # o por activo: cost_bps = { TLT = 3.0, IEF = 2.0 }
slippage_bps = 2.0
allow_short = false

[validation]
alpha = 0.05                     # 0.01 | 0.025 | 0.05 | 0.10
reps = 500                       # repeticiones de bootstrap
seed = 1
train_end = "2018-12-31"         # selección hasta aquí; validación única después

[[ideas]]                        # 0 o más estrategias cuantitativas
name = "tendencia"
signal = "sma_crossover"         # `tsinsurance experiment signals` lista las disponibles
  [ideas.grid]                   # cada combinación cuenta como una prueba
  fast = [20, 50]
  slow = [150, 200]

[[econometric]]                  # 0 o más modelos con variables explicativas
name = "macro"
asset = "TLT"
regressors = ["T10Y2Y", "d_DGS10"]
derived = { d_DGS10 = { from = "DGS10", op = "diff" } }
position = "long_cash"           # long_cash | long_short | proportional
min_train = 60                   # meses mínimos antes del primer pronóstico
# n_specifications = 3           # declárelo si probó otras combinaciones de regresores
```

**Carteras y regímenes** (bloques `[[portfolios]]`, `[[regimes]]` y
`[[declared_prior_tests]]`): ver `AGENTS.md` y `docs/methodology/carteras-y-regimenes.md`.
En `result.json` aparecen como `portfolios.<nombre>` y `regimes.<nombre>` (calibración) y
`validation.portfolios` / `validation.regimes` (validación).

Señales incluidas: `sma_crossover` (`fast`, `slow`), `tsmom` (`lookback`, `skip`),
`ewma_vol_target` (`target`, `lam`), `tsmom_vol_target` (`lookback`, `skip`, `target`).

## 8. Ejecución

### Modo A, línea de comandos

```bash
tsinsurance experiment run experimentos/mi_experimento/experiment.toml        # 1. calibración
git add -A && git commit -m "Calibración"                                     # 2. confirmar
tsinsurance experiment validate experimentos/mi_experimento/experiment.toml \
    --calibration RUN_ID                                                      # 3. validación única
tsinsurance experiment verify experimentos/registry.jsonl --results experimentos
tsinsurance experiment list experimentos/registry.jsonl
```

**Dos fases (desde 0.2.0).** Con `train_end`, `run` sólo **calibra**: recibe los datos
truncados en esa fecha y fija las configuraciones en la bitácora. `validate` abre el
periodo posterior **una vez** y exige: la calibración registrada, el mismo
`experiment.toml`, los mismos datos hasta `train_end`, la misma versión del paquete y git
sin cambios (incluidos archivos no rastreados en la carpeta del experimento). Si ese
periodo ya lo miró cualquier experimento para el mismo activo, el resultado es
exploratorio. La validación ajusta por Holm la familia de hipótesis fijada en la
calibración.

Opciones útiles:
- `--output DIR` cambia la carpeta de resultados.
- `--registry RUTA` usa otra bitácora, pero si difiere de la declarada el resultado
  queda **exploratorio**.

Convención de errores: código de salida **0** = éxito, **1** = la validación o verificación
no pasa, **2** = error de uso o de ejecución y **3** = bitácora bloqueada por otra ejecución. En el error, la
causa aparece en *stderr* con la serie, el campo y la regla incumplida.

### Modo B, biblioteca Python

```python
from tsinsurance.experiments import run_experiment, register_signal, read_registry

res = run_experiment("experimentos/mi_experimento/experiment.toml")
r = res.result              # el mismo dict que result.json
print(res.summary())        # resumen legible
print(res.exploratory)      # True si hay alguna razón de exploratorio
```

**Señal propia.** Es una función `(precios: DataFrame, **parámetros) -> pesos objetivo`
con las mismas columnas que los precios. Debe ser causal: el peso en t sólo usa datos
hasta t. Se registra antes de ejecutar y se nombra en `signal = "..."`:

```python
def ruptura(precios, ventana=120):
    maximo = precios.rolling(ventana).max().shift(1)
    return (precios > maximo).astype(float).where(precios.notna())

register_signal("ruptura", ruptura)
run_experiment("experiment_senal_propia.toml")
```

**Huella del código.** El paquete identifica cada señal por su código: el AST, los
valores por defecto, las funciones y constantes que usa y, si no hay código fuente, el
*bytecode*. Cambiar una línea de la señal cuenta como una prueba nueva, y la validación
exige la misma huella que la calibración. Una cobertura `partial` (algún objeto que no
se pudo resumir) deja el resultado como exploratorio.

Si la señal mira el futuro, la idea sale `"status": "rechazada_por_anticipacion"` con
las fechas afectadas, y no se evalúa. Ejemplo completo en
`examples/integracion/senal_propia.py`.

Funciones de nivel más bajo, si se necesitan:
- `tsinsurance.data.bundle.Bundle.load(dir)` con `.assets()`, `.exogenous()` y
  `.risk_free()`;
- `tsinsurance.backtest.run_backtest`, `check_lookahead`, `sweep` y
  `backtest_econometric`;
- `tsinsurance.diagnostics`, para las pruebas de estacionariedad.

## 9. Interfaz de salida: `result.json` (versión 1.2)

Cada ejecución escribe `results/<run_id>/result.json` y `report.md`, y agrega líneas a
la bitácora. El `run_id` tiene la forma `AAAAMMDDTHHMMSSZ-<hash>`.

| Clave | Contenido |
|-------|-----------|
| `result_version` | `"1.2"`. Lea primero esta clave; los cambios incompatibles suben el número mayor |
| `phase` | `calibration` (validación pendiente), `validation` o `full_sample` (sin validación fuera de muestra) |
| `registry_head_before`, `registry_head` | estado de la bitácora antes y después de la ejecución |
| `experiment` | `id`, `title`, `author`, `hypothesis`, `file`, `sha256` del `experiment.toml` |
| `provenance` | `run_id`, `package_version`, `git`, `bundle` (huella SHA-256), `seed`, `registry`, `prior_trials_by_asset` |
| `assumptions` | `execution`, `alpha`, `train_end`, `window`, `selection_window_end`, `risk_free`, `asset_start` |
| `status` | **resumen para decidir rápido**: `exploratory_reasons` (lista), `significant_by_idea` (activos significativos por idea), `econometric_quadrants`, `lines_registered` |
| `ideas.<nombre>.status` | `evaluada` o `rechazada_por_anticipacion` |
| `ideas.<nombre>.lookahead` | por activo: combinaciones probadas y las que fallaron, con su resumen |
| `ideas.<nombre>.selection` | por activo: `best`, `sharpe`, `psr`, `ir_vs_bh`, `exposure`, `timing_ir`, `n_trials` (incluye la bitácora), `dsr`, `spa_p`, `spa_p_holm`, `significant` |
| `ideas.<nombre>.configurations` | métricas de cada combinación de parámetros |
| `calibration` | fase de calibración: `frozen` (parámetros, exposición, especificaciones y familia de hipótesis fijados) y `validate_with` |
| `validation.ideas.<nombre>.assets[]` | fase de validación: `params`, `sharpe_oos`, `ci95`, `p_vs_cash_hac`, `buy_hold_sharpe_oos`, `exposure_calibration`, `timing_sharpe_diff`, `timing_p`, `p_holm`, `previously_seen_in` |
| `validation.econometric.<nombre>` | fase de validación: veredicto con pronósticos posteriores a `train_end`, `p_holm` |
| `econometric.<nombre>` | `verdict` (`quadrant`, `statistical`, `economic`, `exploratory`, `inconclusive`, `diagnostics_passed`, `explanation`), `oos_r2`, `clark_west_p`, `pesaran_timmermann_p`, `hit_rate`, `sharpe_model`, `sharpe_benchmark_rule`, `economic_p`, `n_forecasts`, `warnings` |

**Formato de las tablas.** `selection` y `configurations` vienen orientadas por columna,
como `{"columna": {"0": valor, "1": valor}}`. Para convertirlas:

```python
import json, pandas as pd
r = json.load(open("results/<run_id>/result.json"))
sel = pd.DataFrame(r["ideas"]["tendencia"]["selection"]).set_index("asset")
print(sel[["best", "sharpe", "dsr", "spa_p", "significant"]])
```

**Cuadrantes econométricos:**
- `estadistica_y_economica`;
- `solo_estadistica`: predice la dirección pero no genera valor neto;
- `solo_economica`: mejora el desempeño sin respaldo estadístico;
- `sin_evidencia`.

**Razones de "exploratorio"** (`status.exploratory_reasons`): cambios sin confirmar en
git; bitácora distinta de la declarada; ejecución sin registro (`record=False`);
paquete sin sellar; variables no punto-en-el-tiempo; diagnósticos de modelos no
superados; periodo de validación ya visto por otra ejecución; sin repositorio git al
validar.

## 10. Reglas de interpretación (obligatorias para cualquier consumidor)

1. **Significativo** sólo si `significant = true`, es decir DSR > 1 − α **y**
   SPA p < α, deflactado con todo lo registrado. Un Sharpe alto sin eso no es evidencia.
2. Compare contra la **exposición constante** (`timing_ir`, `timing_sharpe_diff`), no
   sólo contra comprar y mantener. Una regla invertida parte del tiempo puede "ganarle"
   a un activo que cae sin tener habilidad de *timing*.
3. Reporte el veredicto econométrico **completo**: cuadrante + exploratorio + no
   concluyente + diagnósticos.
4. Un resultado con `exploratory_reasons` no vacío **no** sirve para decidir: sirve para
   generar hipótesis.
5. La validación fuera de muestra se abre **una vez**. Repetirla con otros parámetros
   queda marcado en la bitácora.

## 11. Reglas para el sistema consumidor

- **Nunca** editar, truncar ni borrar `registry.jsonl`. Es sólo de agregado y su
  integridad se verifica con `experiment verify`.
- Escribir `hypothesis` y fijar `train_end` **antes** de ejecutar; no moverlos tras ver
  la validación.
- Declarar `n_specifications` si se probaron otras combinaciones de regresores.
- No desactivar ni esquivar la prueba de anticipación: corregir la señal.
- No publicar ni versionar paquetes con `redistributable = false`.
- No poner claves en archivos: `FRED_API_KEY` se lee del entorno.

## 12. Errores frecuentes

| Mensaje | Causa | Solución |
|---------|-------|----------|
| `campo=unit: isin([...])` | unidad fuera del dominio (p. ej. `index`) | usar `level`, `percent`, `decimal` o `bps` |
| `bundle.toml: no existe` | ruta de paquete equivocada | `data.bundle` es relativa a `experiment.toml` |
| paquete sin sellar ⇒ exploratorio | se editó a mano sin sellar | `tsinsurance bundle seal data` |
| `cambios sin confirmar en git` | se ejecuta con cambios pendientes | confirmar (*commit*) antes de la ejecución confirmatoria |
| `Señal '...' desconocida` | la señal propia no se registró en ese proceso | `register_signal(...)` en el mismo script que `run_experiment` |
| `rechazada_por_anticipacion` | la señal usa datos futuros (p. ej. `shift(-k)`) | hacerla causal (`shift(1)`) |
| `experiment verify` lista problemas en lugar de "Bitácora íntegra." | alguien editó `registry.jsonl` | restaurar desde git; no editar a mano |

## 13. Versionado y compatibilidad

| Elemento | Versión actual | Política |
|----------|----------------|----------|
| Paquete | 0.1.0 | SemVer; fije etiqueta o *commit* |
| Contrato de datos (`market_series.csv`) | 1.0 | `schema_version` en el manifiesto |
| Manifiesto (`bundle.toml`) | 1.0 | `[bundle].version` |
| `result.json` | 1.1 | `result_version`; los campos nuevos son aditivos dentro de 1.x |

Más información:
- metodología en [`docs/methodology/`](../methodology/);
- proceso completo en [`docs/propuesta-proceso.md`](../propuesta-proceso.md);
- reglas para agentes en [`AGENTS.md`](../../AGENTS.md).
