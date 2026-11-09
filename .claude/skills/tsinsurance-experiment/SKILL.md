---
name: tsinsurance-experiment
description: Diseña, ejecuta, registra e interpreta experimentos de backtesting responsable con tsinsurance (paquete de insumos → experiment.toml → tsinsurance experiment run → result.json). Úsalo cuando el usuario quiera probar una idea cuantitativa, una señal o un modelo econométrico sobre series específicas (ETFs, tasas, índices).
---

# Experimento registrado con tsinsurance

Sigue `AGENTS.md` (raíz del repositorio). Resumen operativo:

1. **Hipótesis primero.** Escríbela en `[experiment].hypothesis` antes de ver datos de
   validación. Usa un `id` estable y descriptivo.
2. **Datos como paquete de insumos.**
   - Si los datos vienen de Yahoo/FRED: crea `recipe.toml` (copia
     `experiments/inverse_treasury/recipe.toml`), declara cada serie con `role`,
     `release_lag`, `license`, `redistributable`, y ejecuta
     `uv run tsinsurance bundle fetch recipe.toml data` (FRED requiere `FRED_API_KEY`).
   - Si el usuario trae sus archivos: `uv run tsinsurance bundle template data` y llénalo.
   - Siempre: `uv run tsinsurance bundle validate data`.
3. **Experimento.** Escribe `experiment.toml` (ver `AGENTS.md`). Señales disponibles:
   `uv run tsinsurance experiment signals`. Para una señal nueva, regístrala con
   `tsinsurance.experiments.register_signal` en un script y llama a `run_experiment`.
4. **Ejecuta.** `uv run tsinsurance experiment run <exp>/experiment.toml`. No uses otra
   bitácora distinta de `experiments/registry.jsonl` salvo para pruebas del paquete.
5. **Interpreta** `results/<run_id>/result.json`:
   - idea rechazada por anticipación ⇒ corrige la señal;
   - `significant` exige DSR > 1 − α y SPA p < α (deflactado con todo lo probado);
   - modelos econométricos: reporta cuadrante + marcas (exploratorio, no concluyente,
     diagnósticos no superados), R² fuera de muestra y la prueba económica.
6. **Reporta** al usuario: hipótesis, datos (fuente, licencia, ventana), supuestos,
   número de pruebas acumuladas, resultado con incertidumbre y limitaciones. Nunca
   presentes un Sharpe alto como evidencia si `significant` es falso.

Prohibido: editar o borrar la bitácora, mover `train_end` tras ver la validación,
desactivar la prueba de anticipación, versionar datos con `redistributable = false`.
