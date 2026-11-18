# Contrato de la línea de comandos (spec 004)

Códigos de salida (convención vigente de la CLI): `0` = éxito; `1` = la verificación o
validación no pasa; `2` = error de uso o de ejecución (causa en *stderr*); `3` = bitácora
bloqueada por otra ejecución.

## `tsinsurance experiment run EXP.toml [--registry R] [--output DIR]`

- **Con `train_end`**: fase de **calibración**. Recibe sólo `Bundle.as_of(train_end)`.
  Escribe `preregistration`, `signal`, `econometric` y `calibration`. Imprime el `run_id`
  y el comando exacto para validar.
- **Sin `train_end`**: fase `full_sample`; el resultado informa que no hay validación
  fuera de muestra.
- **Cambio frente a la v0.1**: ya no abre la validación.

## `tsinsurance experiment validate EXP.toml --calibration RUN_ID [--output DIR]`

Precondiciones (si falla alguna: salida 1 y no escribe nada):

1. es la bitácora declarada en el experimento, íntegra (cadena y resultados) y no
   bloqueada;
2. existe el evento `calibration` con `RUN_ID`;
3. `experiment_sha256` coincide, y la huella de `as_of(train_end)` del paquete actual es
   igual a la de la calibración;
4. las huellas de código de las señales y `package_version` coinciden con las fijadas;
5. git sin cambios sin confirmar, incluidos archivos no rastreados en el directorio del
   experimento y en los módulos de las huellas.

Sin repositorio git: se permite, pero queda exploratoria.

Además, antes de evaluar, marca exploratorio todo activo cuyo periodo posterior a
`train_end` ya aparezca en la bitácora, indicando ejecución y experimento (FR-009a).

Efecto:
- evalúa las configuraciones fijadas después de `train_end`;
- escribe un evento `validation` por idea y por modelo;
- deja `result.json` con `phase = "validation"`.

Una segunda validación de lo mismo se permite y queda exploratoria.

## `tsinsurance experiment verify REGISTRY [--base BASE] [--results DIR]`

- Siempre verifica la cadena de hashes.
- `--base`: exige que REGISTRY comience byte a byte con BASE. Si no, informa la primera
  línea distinta.
- `--results`: exige que cada `result.json` bajo DIR sea consistente con REGISTRY (sin
  recortes). Si no, informa el resultado y la línea esperada.
- Salida `0` sólo si todo pasa.

## `tsinsurance experiment unlock REGISTRY [--force]`

Muestra el bloqueo (PID, máquina, `run_id`, antigüedad).
- Lo borra sólo si está vencido.
- Con `--force`, lo borra siempre y lo informa.

## `tsinsurance bundle fetch RECIPE DIR`

La receta acepta por serie de FRED `vintage_mode = "first_release" | "all_vintages"`.
`bundle show` informa, por serie con versiones:
- el número de versiones;
- el inicio de la cobertura de ALFRED;
- las observaciones afectadas por esa cobertura.
