# Quickstart de validación (spec 005)

1. **Prueba unitaria y de integración (sin red):**
   ```bash
   uv run pytest tests/experiments/test_portfolios.py tests/experiments/test_regimes.py
   ```
   Comprueba la anticipación, el registro, la memoria por universo, los estados punto en
   el tiempo, Holm y las dos fases.
2. **Monte Carlo (SC-001, SC-002, SC-004):**
   ```bash
   uv run pytest tests/simulation -m slow -k "portfolio or regime"
   ```
3. **Demostración sectorial (SC-007; requiere red para Yahoo):**
   ```bash
   uv run tsinsurance bundle fetch experiments/sectores_gics/recipe.toml experiments/sectores_gics/data
   uv run tsinsurance experiment run experiments/sectores_gics/rotacion_regimenes.toml
   git add -A && git commit -m "Calibración rotación y regímenes"
   uv run tsinsurance experiment validate experiments/sectores_gics/rotacion_regimenes.toml --calibration RUN_ID
   uv run tsinsurance experiment verify experiments/registry.jsonl --results experiments
   ```
   **Esperado:** la validación sale exploratoria con "periodo … ya visto" en los sectores.
