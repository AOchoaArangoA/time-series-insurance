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

## Desarrollo

```bash
uv sync
uv run pytest
uv run ruff check src tests && uv run mypy
```

Requiere Python >= 3.11 y [uv](https://docs.astral.sh/uv/).
