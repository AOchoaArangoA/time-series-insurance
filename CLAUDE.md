# CLAUDE.md — guía para agentes de IA

Proyecto: `tsinsurance`, paquete Python de series de tiempo para la gestión de
inversiones de una aseguradora. Se desarrolla con **Spec-Driven Development**
([GitHub Spec Kit](https://github.com/github/spec-kit)).

## Reglas

- La constitución en `.specify/memory/constitution.md` es obligatoria. Léela antes de
  planear o implementar.
- No implementes funcionalidad sin especificación en `specs/NNN-*/` y plan aprobado.
- Flujo: `/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks`
  → `/speckit-analyze` → `/speckit-implement`.
- Tras `/speckit-plan` y antes de un PR, ejecuta el subagente `econometrics-reviewer`.
- TDD: escribe la prueba (proceso generador conocido o valor de referencia) antes del
  código.

## Comandos

```bash
uv sync                      # instalar entorno
uv run pytest                # pruebas + cobertura
uv run ruff check src tests  # lint
uv run ruff format src tests # formato
uv run mypy                  # tipos (strict)
```

## Estructura

- `src/tsinsurance/` — código del paquete (layout src, tipado estricto).
- `tests/` — pruebas (`pytest`, `hypothesis`; marca `slow` para Monte Carlo).
- `specs/` — especificaciones, planes y tareas por funcionalidad.
- `docs/methodology/` — documentación metodológica con referencias bibliográficas.
- `docs/roadmap.md` — hoja de ruta de especificaciones.

## Convenciones

- Entradas/salidas `pandas` con índice temporal y frecuencia validada.
- Resultados como dataclasses inmutables con `summary()`.
- Docstrings estilo NumPy con sección `References`.
- Reutilizar `statsmodels`, `arch`, `scipy`; justificar implementaciones propias.
- Simulaciones con `numpy.random.Generator` y semilla explícita.
