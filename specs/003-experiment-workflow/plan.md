# Implementation Plan: Flujo de experimentos registrados, insumo base y entrega a agentes

**Branch**: `003-experiment-workflow` | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

## Summary

Tres capas sobre lo existente: (1) `tsinsurance.data.bundle` — paquete de insumos
independiente de la fuente (manifiesto + contrato v1.0) con recetas de descarga como
adaptadores; (2) `tsinsurance.experiments` — ejecución declarativa (`experiment.toml`),
registro de señales, bitácora JSONL de sólo agregado que alimenta el DSR, y salidas
`result.json` / `report.md`; (3) entrega a agentes (`AGENTS.md`, habilidad
`tsinsurance-experiment`) y documento de propuesta del proceso.

## Technical Context

**Language/Version**: Python >= 3.11 · **Primary Dependencies**: existentes (`tomllib`
para leer TOML; escritura TOML propia mínima para el manifiesto) · **Storage**: archivos
(TOML, CSV, JSONL, JSON, Markdown) · **Testing**: pytest · **Project Type**: library + CLI.

## Constitution Check

| Principio | Cumplimiento | Estado |
|-----------|--------------|--------|
| II / VIII punto en el tiempo | rezagos de publicación declarados en el manifiesto; prueba de anticipación obligatoria por idea | PASS |
| IV-bis datos con contrato | el paquete reutiliza el contrato v1.0 y su hash | PASS |
| VIII pruebas múltiples | bitácora permanente que acumula pruebas por activo en el DSR | PASS |
| V biblioteca primero | lógica en el paquete; CLI delgado | PASS |
| VI pruebas primero | catálogo de errores de manifiesto, acumulación de pruebas, reproducibilidad | PASS |

## Project Structure

```text
src/tsinsurance/
├── data/bundle.py            # SeriesSpec, Bundle, recetas (fetch_recipe), validación
├── experiments/
│   ├── __init__.py
│   ├── signals.py            # registro de señales por nombre
│   ├── spec.py               # ExperimentSpec (lectura/validación de experiment.toml)
│   ├── registry.py           # bitácora JSONL de sólo agregado
│   └── runner.py             # run_experiment → result.json, report.md, registry
└── cli.py                    # + bundle {template,validate,fetch}, experiment {run,list}
experiments/
├── registry.jsonl
├── inverse_treasury/{recipe.toml, experiment.toml}
└── results/<experiment_id>/<run_id>/{result.json, report.md}
AGENTS.md · .claude/skills/tsinsurance-experiment/SKILL.md
docs/propuesta-proceso.md · docs/politica-datos-y-publicacion.md · LICENSE
```

## Complexity Tracking

| Decisión | Por qué | Alternativa descartada |
|----------|---------|------------------------|
| Escritura TOML propia mínima | `tomllib` sólo lee; evitar dependencia nueva para un manifiesto plano | `tomli-w` (dependencia adicional) |
| DSR con pruebas previas resumidas (ratio de información por prueba) | la bitácora no guarda series completas | guardar retornos de cada prueba (pesado) |
