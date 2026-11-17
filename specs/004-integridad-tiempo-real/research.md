# Research: Integridad del procedimiento y datos en tiempo real

Decisiones de diseño de la spec 004. Cada una indica qué se eligió, por qué y qué se
descartó. Las verificaciones hechas el 2026-11-17 se marcan con ✔.

---

## R1. Bitácora a prueba de recortes (US1)

**Hallazgo ✔.** `verify_registry` sólo recorre la cadena desde el génesis: borrar las
últimas 6 de 17 líneas devuelve "Bitácora íntegra.". La cadena detecta ediciones y
reordenamientos intermedios, no recortes al final.

**Decisión.** Dos anclas independientes:

1. **Estado en cada resultado**: `result.json` guarda `registry_head = {n_lines,
   last_hash}` al terminar (y `registry_head_before` al empezar). `experiment verify
   --results DIR` recorre todos los `result.json` bajo `DIR` y exige, para cada uno, que la
   bitácora tenga al menos `n_lines` líneas y que el hash de la línea `n_lines` sea
   `last_hash`. Como los resultados se versionan, un recorte deja un resultado que lo
   delata.
2. **Prefijo exacto en la integración continua**: `experiment verify --base ARCHIVO`
   exige que la bitácora actual **comience byte a byte** con la de la rama principal
   (`git show origin/main:experiments/registry.jsonl`). Cubre el caso de borrar a la vez
   las líneas y los resultados.

**Bloqueo (un solo escritor).** Archivo `registry.jsonl.lock` creado con
`O_CREAT | O_EXCL` (portable a Windows, a diferencia de `fcntl`), con PID, máquina, hora y
`run_id`. Una segunda ejecución falla con un mensaje que nombra al dueño del bloqueo. Un
bloqueo es **vencido** si el PID no existe en la misma máquina o tiene más de 6 h; se
informa y se libera sólo con `tsinsurance experiment unlock` (nunca automáticamente). La
escritura se hace con `flush` + `fsync` antes de liberar.

**Alternativas descartadas.** Sellado de tiempo externo o anclaje en un servicio
(infraestructura que el proyecto no tiene); árbol de Merkle (no agrega nada frente a la
cadena con ancla); confiar sólo en git (no cubre ejecuciones no confirmadas todavía).

---

## R2. Huella del código de las señales (US3)

**Decisión.** `fingerprint(fn) -> SignalFingerprint(hash, coverage)`:

- Señales incluidas en el paquete: `builtin:<nombre>@<versión del paquete>`.
- Señales propias, `coverage = "source"`: `inspect.getsource` → `ast.parse` →
  `ast.dump` (ignora comentarios, espacios y docstrings) de la función **y**, de forma
  transitiva, de las funciones del usuario a las que se refiere por nombre global en el
  mismo módulo; más los valores por defecto y las variables de cierre (`repr` canónico).
- Respaldo, `coverage = "bytecode"`: si no hay código fuente (lambdas definidas en un
  intérprete interactivo, funciones generadas), hash recursivo del objeto de código
  (`co_code`, `co_consts`, `co_names`) + versión de Python.
- `coverage = "none"`: si nada de lo anterior es posible; el resultado queda exploratorio
  (FR-012).

La huella entra en `trial_key` (FR-011). Las líneas antiguas sin huella conservan su clave
y siguen contando (FR-013): sólo las re-ejecuciones idénticas comparten clave, así que una
señal re-ejecutada con la versión nueva cuenta como una prueba adicional — conservador.

**Alternativas descartadas.** Hash del módulo completo (cualquier edición de otra señal
del mismo archivo cambiaría todas las identidades); sólo el bytecode (depende de la
versión de Python: la misma señal cambiaría de identidad al actualizar Python).

---

## R3. Validación única en dos fases (US2)

**Hallazgos ✔.**
- Los bloques `[[econometric]]` se evalúan sobre `spec.start : spec.end`, incluido el
  periodo de validación (`runner.py`, cálculo de `px_e`).
- Cada `experiment run` con `train_end` abre la validación en la misma ejecución: quien
  itera ve el resultado fuera de muestra en cada vuelta (queda marcado, pero lo ve).

**Decisión.**

| Fase | Comando | Datos que recibe | Escribe |
|------|---------|------------------|---------|
| Calibración | `tsinsurance experiment run exp.toml` | `Bundle.as_of(train_end)` | `preregistration`, `signal`, `econometric`, `calibration` (configuraciones fijadas) |
| Validación | `tsinsurance experiment validate exp.toml --calibration RUN_ID` | paquete completo | `validation` por idea y por modelo |

- `Bundle.as_of(cut)` devuelve un paquete nuevo, en memoria, sin acceso al original: activos
  y tasa libre de riesgo con fecha ≤ `cut`; exógenas con **disponibilidad** ≤ `cut` (fin de
  periodo + rezago, o fecha de publicación si existe); en el modo todas las versiones,
  versiones publicadas ≤ `cut` con su `realtime_end` reabierto si era posterior (ver R4).
  El ejecutor carga el paquete y llama a `as_of` antes de cualquier otro uso; la huella
  del paquete completo se conserva sólo como procedencia.
- Sin `train_end` no hay validación: el resultado lo dice (`status.out_of_sample =
  "ninguna"`) y no se presenta como validado.
- **Requisitos de `validate` (FR-007)**: existe el evento `calibration` con ese `run_id`
  en la bitácora; `experiment_sha256` y `bundle_sha256` coinciden; git sin cambios sin
  confirmar (si el experimento está en un repositorio); bitácora íntegra. Si falla alguno,
  error con la causa (no un resultado exploratorio).
- **Reapertura (FR-009)**: permitida, marcada exploratoria con el número de aperturas
  (identidad de validación = experimento + configuración fijada + ventana + paquete).
- **Modelos econométricos (FR-010)**: en calibración, el walk-forward corre hasta
  `train_end` y el veredicto usa esos pronósticos (pseudo fuera de muestra). En
  validación, con la especificación fijada, el walk-forward continúa (el modelo se
  re-estima con datos hasta cada fecha, sin seleccionar nada) y el veredicto usa **sólo**
  los pronósticos posteriores a `train_end`.

**SC-003 (verificación).** Se alteran al azar todas las observaciones posteriores a
`train_end` y se re-sella el paquete; la calibración debe ser idéntica número a número en
todo salvo los campos de procedencia (huella del paquete, claves derivadas de ella).

**Cambio de comportamiento.** `experiment run` deja de validar en la misma ejecución.
Es incompatible con el flujo de la v0.1 y por eso la versión del paquete pasa a 0.2.0; el
`result.json` pasa a 1.2 (campos aditivos: `phase`, `calibration_run_id`,
`registry_head`).

**Alternativas descartadas.** Separación física en archivos (descartada por el usuario);
aprobación humana firmada (descartada por el usuario); mantener la validación automática
con advertencia (es lo que hay hoy y no impide mirar).

---

## R4. ALFRED: primera publicación y todas las versiones (US4)

**API (documentada; verificar en la implementación con `FRED_API_KEY`).**
`GET /fred/series/observations` con `realtime_start=1776-07-04` y
`realtime_end=9999-12-31` devuelve cada versión como fila `(date, value, realtime_start,
realtime_end)`.
- `output_type=4` ("sólo publicación inicial") devuelve la primera publicación.
- `output_type=1` (periodo de tiempo real) devuelve todas las versiones.
- Paginación con `limit` (máx. 100 000) y `offset`.
- Se evita `output_type=2/3` (vintages en columnas), que tiene un límite de 2 000 fechas
  de versión.

**Contrato de datos 1.1 (compatible con 1.0).** Columnas opcionales en
`market_series.csv`:
- `realtime_start`: fecha de publicación de la versión;
- `realtime_end`: fecha en que la versión fue reemplazada; vacía si sigue vigente.

Clave única `(date, series_id, realtime_start)`. En el manifiesto, por serie, `vintage_mode
= "first_release" | "all_vintages"` (ausente: rezago declarado, como hoy). Reglas de
validación:
- `realtime_start` ≥ fin del periodo de `date`;
- intervalos `[realtime_start, realtime_end)` sin solapes por `(series_id, date)`;
- en `first_release`, una fila por `date`;
- una serie con `vintage_mode` debe traer `realtime_start` en **todas** sus filas.

**Construcción en tiempo real.**
- `first_release` (la "diagonal"): cada observación disponible desde su
  `realtime_start`. Las transformaciones se calculan sobre los valores de primera
  publicación.
- `all_vintages` (la "vista de cada fecha"): en cada fecha de decisión `d` se arma el
  vector vigente `{date: value | realtime_start ≤ d < realtime_end_excl}` (fin exclusivo, ver R10-B3) y las
  transformaciones se calculan **dentro de ese vector** (FR-019a). La regresión
  walk-forward en `d` se estima con la historia completa de la vista `d` y pronostica con
  su último valor. Esto exige que `PredictiveRegression.walk_forward` acepte una matriz
  de regresores distinta por fecha (función `X_at(d)`).
- Referencia: Croushore y Stark (2001), "A real-time data set for macroeconomists";
  Koenig, Dolmas y Piger (2003) sobre diagonal frente a vista.

**Prueba de anticipación.** `truncate_available(cut)` conserva las filas con
`realtime_start ≤ cut` y **reabre** `realtime_end` si era posterior a `cut`: saber que una
versión fue reemplazada después de `cut` ya es información futura.

**Riesgo: cobertura de ALFRED.** Para muchas series, la primera versión archivada es de los
años noventa; las observaciones anteriores aparecen "publicadas" en esa fecha. En modo
estricto (por defecto) esas observaciones sólo están disponibles desde esa fecha; la
validación del paquete informa el inicio de la cobertura real y cuántas observaciones
quedan afectadas. No se mezcla con el rezago declarado (una serie es toda de un tipo).

**Alternativas descartadas.** Vintages como columnas (límite de 2 000 y formato ancho
fuera del contrato); archivo aparte de versiones (rompe la regla de un solo CSV por
paquete; las columnas opcionales mantienen la compatibilidad).

---

## R5. Inferencia IVX (US5)

**Decisión.** Implementar IVX de Kostakis, Magdalinos y Stamatogiannis (2015) para
horizonte 1 en `tsinsurance.backtest.econometric`: instrumento
`z_t = Σ_{j} R_z^{t-j} Δx_j` con `R_z = 1 − c_z / n^β`, Wald con la corrección de muestra
finita del artículo; mismos valores por defecto que el paquete `ivx` de R (que se
confirmarán leyendo su fuente C++ en la implementación).

- Se reporta junto a la HAC en `ModelValidation` y en `result.json`
  (`ivx_wald`, `ivx_p` por regresor y conjunto).
- La advertencia de persistencia remite a la IVX.
- No cambia el veredicto (que se basa en Pesaran-Timmermann / Clark-West fuera de
  muestra); sí entra en "diagnósticos".

**Verificación.**
- Paquete `ivx` 1.1.1 de R instalado ✔ (CRAN). Diferencia relativa ≤ 1e-6 sobre datos
  simulados y sobre GS10/T10Y2Y.
- Monte Carlo de tamaño: ρ = 0,99, δ = −0,95, n = 300, 2 000 réplicas.

**Alternativas descartadas.**
- Corrección de Stambaugh (sólo corrige el sesgo del coeficiente, no la inferencia);
- Campbell-Yogo (requiere tablas y no es multivariada);
- llamar a R desde Python (dependencia pesada en tiempo de ejecución).

---

## R6. EE HAC del Sharpe con preblanqueo (US5)

**Situación.** `sharpe_inference` usa Newey-West (Bartlett) con
`floor(4 (n/100)^{2/9})` rezagos sobre los momentos `(r, r²)` y el método delta. El
sesgo medido es de ≈ 9 % con autocorrelación.

**Decisión.** Opción `hac="prewhitened"` según Andrews y Monahan (1992):
1. VAR(1) sobre la serie de momentos;
2. kernel espectral cuadrático con ancho de banda automático de Andrews (1991) sobre los
   residuos;
3. "recoloreado" con `(I − A)^{-1}`.

El resultado informa qué estimador se usa. Por defecto se mantiene Newey-West hasta que
el Monte Carlo (SC-008) muestre la reducción del sesgo; entonces pasa a ser el
predeterminado y se documenta.

**Verificación.** `sandwich::vcovHAC(prewhite = 1, kernel = "Quadratic Spectral", bw =
bwAndrews)` en R ✔ (instalado) sobre la regresión de los momentos en una constante.

---

## R7. Varianza de los Sharpe de las pruebas previas (US6)

**Corrección conceptual importante.** La tarea original (003-T018) proponía "descontar
el ruido de muestreo 1/T". Eso es **incorrecto bajo la hipótesis nula** del Sharpe
deflactado: si ninguna estrategia tiene habilidad, la dispersión entre los Sharpe
estimados *es* el ruido de muestreo, y es justamente lo que genera el máximo esperado
(Bailey y López de Prado 2014). Restarlo llevaría el umbral a ≈ 0 y el DSR sería
permisivo.

El problema real es la **heterogeneidad de T**. Las pruebas previas con ventanas más
cortas tienen más ruido (≈ 1/T_i por periodo) y, mezcladas en una sola varianza, la
inflan o la achican según su largo frente a la prueba actual.

**Decisión propuesta.** Estandarizar antes de combinar:

```text
z_i  = SR_i · sqrt(T_i)                     (comparables entre ventanas; ~N(0,1) bajo H0 iid)
V_z  = var(z_i)
SR_0 = E[max_N z] / sqrt(T_actual)          (E[max] de Bailey-López de Prado con V_z)
```

- Si todas las pruebas tienen el mismo T, coincide con la regla vigente. Si no, corrige
  en el sentido que corresponda: puede ser más o menos conservadora.
- Requiere `n_obs` por prueba **en las mismas unidades que el ratio registrado** (días
  para ambos tipos de línea; no `n_forecasts`, que son meses). Ver R10-B6.

**Criterio de adopción (FR-023, SC-009).** Monte Carlo con familias de 20 a 200
estrategias sin habilidad, ventanas mezcladas (T de 60 a 300 meses y de 2 520 a 5 000
días), con y sin autocorrelación, y comparación de tamaño y potencia de la regla vigente
frente a la estandarizada.
- Se adopta como regla por defecto sólo si el tamaño es ≤ 6,9 % al 5 % en todos los
  escenarios.
- En cualquier caso se documenta en `docs/methodology/backtesting.md` (regla vigente,
  tabla de tamaño y potencia, fecha) según la regla de gobernanza agregada a
  `docs/propuesta-proceso.md`.

---

## R8. Revisión en la integración continua

En `.github/workflows/ci.yml`, un paso en `pull_request`:

```bash
git fetch origin "$GITHUB_BASE_REF" --depth=1
git show "origin/$GITHUB_BASE_REF:experiments/registry.jsonl" > "$RUNNER_TEMP/base.jsonl" || : > "$RUNNER_TEMP/base.jsonl"
uv run tsinsurance experiment verify experiments/registry.jsonl \
    --base "$RUNNER_TEMP/base.jsonl" --results experiments
```

Si la bitácora no existe en la rama base, la base vacía acepta cualquier bitácora válida.

---

## R9. Experimento de aceptación (US7)

`experiments/tlt_treasury/`:
- activos TLT, TBX y TBF (Yahoo);
- exógenas de mercado T10Y2Y y DGS10 (rezago 1B, no se revisan);
- IPC desestacionalizado `CPIAUCSL` (sí se revisa): especificación principal en
  `first_release` y análisis de sensibilidad declarado en `all_vintages` (no cuenta como
  selección; revisión I8);
- es una **demostración**: el periodo 2019-2025 ya se abrió para estos activos (R10-B2);
- `train_end = 2018-12-31`.

Se ejecutan las dos fases; el README documenta ambas y la comparación entre los dos
modos. Requiere `FRED_API_KEY` y red; los datos no se versionan.

---

## R10. Correcciones tras la revisión econométrica (2026-11-17)

### Bloqueantes (corregidos en spec, data model y contratos)

| # | Hallazgo | Decisión |
|---|----------|----------|
| B1 | La identidad de reapertura incluía id del experimento, huella del paquete y fin de ventana: renombrar o volver a descargar la eludía; no se detectaban periodos vistos por otros experimentos | Identidad del periodo fuera de muestra = (activo, intervalo > `train_end`). `validate` recorre la bitácora: si cualquier línea previa (señal, econométrica, validación; de cualquier experimento) cubrió fechas > `train_end` del activo, el resultado queda exploratorio con la ejecución y el experimento que lo vieron (FR-009, FR-009a) |
| B2 | La bitácora ya tiene validaciones 2019-2025 de TBX y TBF y econométricas de toda la ventana; TLT 2017-2025 se mostró en la spec 002 | US7 es demostración del procedimiento; B1 genera la razón automáticamente |
| B3 | `realtime_end` de ALFRED es inclusivo; hay versiones de un día | El conector guarda `realtime_end` exclusivo (= ALFRED + 1 día; `9999-12-31` → vacío). La vista usa `start ≤ d < end`; regla `end > start`; reabrir en el truncado si `end > cut`. SC-006b prueba bordes |
| B4 | El flujo econométrico de `check_lookahead` recibía `x` ya alineado; una función `X_at` no es truncable; `derived` se calculaba después de alinear | El flujo probado parte de precios y de objetos `Exogenous`/`RealTimeExogenous`, y hace dentro la alineación, las derivadas y el walk-forward. `X_at` se construye dentro, nunca entra como parámetro. Las derivadas pasan a calcularse por vista (o como `transform`). Prueba de mutación: un rezago omitido y el uso de `realtime_end` se detectan |
| B5 | `validate` no comparaba huellas de señales ni versión del paquete; ignoraba no rastreados; sin git se saltaba; aceptaba otra bitácora | `frozen` guarda huellas y versión; se recalculan y deben coincidir. `git status --porcelain` incluyendo no rastreados (directorio del experimento y módulos de las huellas). Sin git: exploratorio. Sólo la bitácora declarada |
| B6 | Las líneas econométricas registran IR diarios; `n_forecasts` (meses) achicaría z en ≈ √21 | `n_obs` = largo de la ventana del IR, registrado en toda línea. Imputación desde `eval_start`/`eval_end` para líneas antiguas; si falta, T actual (equivale a la regla vigente para esa línea) y se declara |

### Importantes (tareas con criterio de aceptación)

| # | Tema | Decisión / tarea |
|---|------|------------------|
| I1 | Bloqueo | Cubre toda la ejecución: se toma antes de verificar y leer la bitácora y se libera tras la última escritura; `flush` + `fsync`; recuperación de una última línea truncada |
| I2 | Huella no conservadora | Recorrer referencias globales (nombres y atributos): llamables del usuario fuera de site-packages y de la biblioteca estándar, transitivas y entre módulos; no llamables por hash de su valor (arreglos y DataFrames por sus bytes); quitar docstrings a mano; `coverage = "partial"` con la lista si algo no se puede hashear; huella AST también para las señales incluidas. Se elimina "nunca de menos" del plan |
| I3 | DSR de calibración con información posterior | FR-022a: V sólo con líneas con `eval_end ≤ cut`; N con todas; las validaciones nunca entran |
| I4 | Vista `all_vintages` incompleta | Dentro de la vista `d`, cada fecha histórica `t` recibe el último periodo cuya primera publicación es ≤ `t`, con el valor de la vista `d`. Diagnósticos e IVX sobre la vista en `train_end` (calibración) y la vista final (validación). Advertencia de Koenig-Dolmas-Piger en `docs/methodology/realtime.md` |
| I5 | Transformaciones en `first_release` | Disponibilidad = máximo de los `realtime_start` de los insumos. Documentar que mezclar primeras publicaciones puede sesgar (factores estacionales). SC-006 se prueba derivando `first_release` desde un conjunto sintético de todas las versiones |
| I6 | SC-003 | Claves de calibración con la huella de `as_of(cut)`; bitácora fija en la prueba; categorías de mutación enumeradas; series no punto-en-el-tiempo fuera |
| I7 | Validación sin pruebas múltiples | FR-009b: Holm sobre la familia pre-registrada; p frente a efectivo por HAC o bootstrap estacionario; exposición constante de la calibración |
| I8 | Dos modos fuerzan exploratorio | `first_release` principal y `all_vintages` como sensibilidad declarada (no cuenta como selección) |
| I9 | Referencia del preblanqueo | HAC sobre la influencia escalar ψ_t con `kernHAC(prewhite=1, kernel="Quadratic Spectral", bw=bwAndrews, adjust=FALSE, ar.method="ols")`; declarar si se ajustan los autovalores; SC-008 con procesos generadores fijos (AR(1) φ ∈ {0, 0,1, 0,3}, n ∈ {250, 2 520}, t de Student) y criterios de sesgo relativo, ECM y cobertura |
| I10 | IVX | Convención de R: `Rz = 1 − 1/(n−1)^0,95` con n efectivo; excluir rezagos AR de y o documentarlo; verificar en la fuente C++ la corrección de muestra finita; escenarios ρ ∈ {0,9, 0,99, 1} × δ ∈ {0, −0,5, −0,95} y potencia con β ≠ 0; salidas de R y series guardadas como datos de prueba versionados para que CI verifique sin R. Citar Phillips y Magdalinos (2009) |
| I11 | Monte Carlo de R7 | SC-009 reescrito: mallas reales, ρ entre pruebas 0-0,97, dos reglas de selección, ≥ 2 000 réplicas, umbral 5 % + 2,5 EE de Monte Carlo, decisión por potencia con tamaño acotado; variante estandarizada por el EE HAC de cada prueba (registrar `sharpe_se_hac`). Hallazgo preliminar del revisor: con T heterogéneo y pruebas muy correlacionadas, la regla vigente tiene tamaño ≈ 0 (pérdida grave de potencia) y la estandarizada 3,4-4,4 % |
| I12 | `calibrate_validate` | Deprecarla (aviso) y marcar su resultado como exploratorio |
| I13 | Huella del paquete entre fases | Precondición sobre la huella de `as_of(train_end)`; conservar la instantánea |
| I14 | CI y riesgo residual | `git cat-file -e` para distinguir "no existe en la base" de un error; verificación también en `push` a main contra `github.event.before`; `--results` filtra por `provenance.registry`; riesgo residual declarado en la spec (Assumptions) |

### Menores

| # | Tarea |
|---|-------|
| M1 | PID vivo en Windows con `OpenProcess` (no `os.kill(pid, 0)`) |
| M2 | La antigüedad sólo vence bloqueos de otra máquina; en la misma máquina con PID vivo, sólo `--force` |
| M3 | `schema_version` acepta {1.0, 1.1} |
| M4 | `vintage_mode` prohibido en `risk_free` en esta versión |
| M5 | Desfase de publicación por serie (p. ej. +1B si se publica después del cierre) |
| M6 | `train_end` debe ser fecha de decisión (o embargo del mes que lo cruza); filtrar los pronósticos de validación por fecha objetivo > `train_end` |
| M7 | Valores "." en filas de versiones: faltante explícito |
| M8 | `quality_warnings`, `window` y `asset_start` sobre `as_of` |
| M9 | Numeración de escenarios de US4 (corregida); `head -n -3` del quickstart sólo funciona con GNU |
| M10 | Límite de la separación lógica declarado en la spec (señal que lee el disco) |
