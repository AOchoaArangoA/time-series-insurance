# Quickstart de validación (spec 004)

Escenarios ejecutables que demuestran cada historia. Prerrequisitos: `uv sync
--all-extras`. Para los escenarios de referencia, R con los paquetes `ivx` y `sandwich`.
Para los escenarios con datos reales, `FRED_API_KEY` y red.

## 1. Bitácora a prueba de recortes (US1)

```bash
cd examples/integracion && python generar_paquete_sintetico.py data
tsinsurance experiment run experiment.toml
head -n -3 registry.jsonl > recortada.jsonl
tsinsurance experiment verify recortada.jsonl --results results   # ⇒ salida 1: "recorte: results/<run>/result.json espera 11 líneas"
tsinsurance experiment verify registry.jsonl --base recortada.jsonl  # ⇒ salida 0 (sólo agrega)
tsinsurance experiment verify recortada.jsonl --base registry.jsonl  # ⇒ salida 1
```

**Escenario de bloqueo.** Lanzar dos `experiment run` a la vez: el segundo termina con
salida 2 y nombra el `run_id` dueño del bloqueo.

## 2. Validación única en dos fases (US2)

```bash
tsinsurance experiment run experiment.toml            # imprime RUN_ID y el comando de validación
tsinsurance experiment validate experiment.toml --calibration RUN_ID
tsinsurance experiment validate experiment.toml --calibration RUN_ID   # ⇒ exploratorio: "abierta 1 vez antes"
```

Prueba automática de SC-003:
1. alterar los datos posteriores a `train_end`;
2. volver a sellar el paquete;
3. calibrar de nuevo;
4. comparar los dos `result.json` sin los campos de procedencia: deben ser idénticos.

## 3. Huella de señales (US3)

```bash
python senal_propia.py     # ruptura con shift(1)
# cambiar 120 → 121 en el valor por defecto, o un operador en el cuerpo, y repetir
tsinsurance experiment list registry.jsonl   # ⇒ dos huellas distintas para "ruptura"
```

## 4. Tiempo real (US4)

```bash
tsinsurance bundle fetch experiments/tlt_treasury/recipe.toml experiments/tlt_treasury/data
tsinsurance bundle show experiments/tlt_treasury/data   # versiones por serie y cobertura de ALFRED
```

Pruebas sin red, con una serie sintética de versiones conocidas:
- en `first_release`, alterar las revisiones no cambia ningún resultado;
- en `all_vintages`, alterar versiones posteriores a `d` no cambia la decisión en `d`;
- en `all_vintages`, la vista en `d` coincide con la respuesta de ALFRED grabada
  (`tests/data/alfred_*.json`).

## 5. Inferencia (US5, US6)

```bash
uv run pytest tests/reference -k "ivx or prewhit"         # vs R: ≤ 1e-6
uv run pytest tests/simulation -m slow -k "ivx or prewhit or dsr_variance"
```

Las simulaciones imprimen tamaño y potencia. El resultado de la corrección de varianza se
copia a `docs/methodology/backtesting.md`.

## 6. Aceptación (US7)

```bash
tsinsurance experiment run experiments/tlt_treasury/experiment.toml
git add -A && git commit -m "Calibración TLT"
tsinsurance experiment validate experiments/tlt_treasury/experiment.toml --calibration RUN_ID
tsinsurance experiment verify experiments/registry.jsonl --results experiments
```

**Resultado esperado.**
- La bitácora queda íntegra.
- Hay un evento `calibration` y un evento `validation` por idea y por modelo.
- El tiempo total es < 5 min.
