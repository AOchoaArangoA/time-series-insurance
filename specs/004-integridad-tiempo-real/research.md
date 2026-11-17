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
  vector vigente `{date: value | realtime_start ≤ d < realtime_end}` y las
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
- Requiere `n_obs` por prueba. Las líneas de señales ya lo tienen; las econométricas
  usan `n_forecasts`; las líneas antiguas sin `n_obs` se combinan con la regla vigente y
  el resultado lo informa.

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
- IPC desestacionalizado `CPIAUCSL` (sí se revisa) en dos bloques econométricos, uno en
  `first_release` y otro en `all_vintages`, declarados con `n_specifications = 2`;
- `train_end = 2018-12-31`.

Se ejecutan las dos fases; el README documenta ambas y la comparación entre los dos
modos. Requiere `FRED_API_KEY` y red; los datos no se versionan.
