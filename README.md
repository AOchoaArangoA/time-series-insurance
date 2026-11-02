# time-series-insurance (`tsinsurance`)

Paquete Python de series de tiempo para la gestión de las inversiones de una
aseguradora, con metodología econométrica y estadística robusta: estacionariedad,
modelos de media y volatilidad, pronóstico con incertidumbre, validación fuera de
muestra, VaR/ES con backtesting, curvas de rendimiento y ALM.

## Metodología de desarrollo: Spec-Driven Development con agentes de IA

El proyecto usa [GitHub Spec Kit](https://github.com/github/spec-kit) con Claude Code.
Spec Kit separa el **qué** (especificación) del **cómo** (plan) y hace que el agente
implemente por tareas verificables.

| Artefacto | Ubicación |
|-----------|-----------|
| Constitución (principios no negociables) | `.specify/memory/constitution.md` |
| Especificaciones por funcionalidad | `specs/NNN-*/spec.md` |
| Hoja de ruta | `docs/roadmap.md` |
| Comandos de Spec Kit para Claude Code | `.claude/skills/speckit-*` |
| Subagente revisor econométrico | `.claude/agents/econometrics-reviewer.md` |
| Guía para agentes | `CLAUDE.md` |

Flujo por funcionalidad, dentro de Claude Code:

```text
/speckit-specify   describe la funcionalidad
/speckit-clarify   resuelve ambigüedades
/speckit-plan      plan técnico (stack, contratos, modelo de datos)
/speckit-tasks     lista de tareas ordenadas por dependencias
/speckit-analyze   consistencia spec ↔ plan ↔ tareas
/speckit-implement implementación con TDD
```

## Uso rápido (v0.1 — preparación y diagnóstico)

```bash
uv sync --all-extras
uv run tsinsurance template market --format xlsx -o mis_series.xlsx   # plantilla de insumos
uv run tsinsurance validate market mis_series.csv                     # valida contra el contrato
uv run tsinsurance schema market --format json-schema                 # contrato publicado
uv run python examples/01_diagnostico_tasas_fred.py                   # ejercicio con datos reales
```

```python
from tsinsurance.data import Snapshot, prepare, to_wide
from tsinsurance.data.sources import get_source
from tsinsurance.diagnostics import describe, stationarity

snap = get_source("fred").fetch(["GS10"], "1990-01-01", "2025-12-31")  # requiere FRED_API_KEY
snap.save("data/gs10")                       # instantánea replicable (Parquet + metadatos + hash)
serie = prepare(to_wide(snap.data)["GS10"], freq="M").data
print(stationarity(serie).summary())         # ADF + PP + KPSS + Zivot-Andrews, regla confirmatoria
```

Las claves de API (p. ej. `FRED_API_KEY`) se leen de variables de entorno y nunca se versionan.

## Desarrollo

```bash
uv sync --all-extras
uv run pytest                 # rápido + simulaciones; sin red
uv run pytest -m network      # descargas reales (requiere FRED_API_KEY)
uv run ruff check src tests && uv run mypy
```

Requiere Python >= 3.11 y [uv](https://docs.astral.sh/uv/).
