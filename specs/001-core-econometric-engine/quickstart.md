# Quickstart / guía de validación (001)

Escenarios ejecutables que prueban la funcionalidad de punta a punta. API en
[contracts/public-api.md](./contracts/public-api.md).

## Prerrequisitos

```bash
uv sync --all-extras
export FRED_API_KEY=...        # sólo para refrescar snapshots (opcional)
```

## Escenario 1 — Contrato de insumos (US1, FR-019b, SC-008)

```bash
uv run tsinsurance template market --format csv -o /tmp/market.csv
uv run tsinsurance validate market /tmp/market.csv     # plantilla vacía: válida
uv run tsinsurance validate market tests/fixtures/market_bad.csv
```
Esperado: el archivo malo reporta cada error con fila, columna y regla; exit code 1.

## Escenario 2 — Diagnóstico de tasas con datos reales (US1, FR-004/005)

```bash
uv run python examples/01_diagnostico_tasas_fred.py
```
Esperado: carga el snapshot `examples/data/fred_dgs10/`, reporta ADF/PP/KPSS/ZA,
concluye `I(1)` para el nivel de la tasa a 10 años e `I(0)` para su diferencia, con
fecha candidata de quiebre.

## Escenario 3 — ARMA-GARCH sobre índice accionario (US2, US3)

```bash
uv run python examples/02_garch_indice_accionario.py
```
Esperado: tabla de candidatos con BIC, modelo elegido con SE robustos, diagnósticos
`is_adequate=True`, pronóstico a 10 días con intervalos 80/95 %, validación expansiva
con DM vs random walk.

## Escenario 4 — VaR de portafolio y backtesting (US4)

```bash
uv run python examples/03_var_portafolio_backtesting.py
```
Esperado: VaR/ES 99,5 % a un año (perfil `generic`) por método histórico, paramétrico y
GARCH; backtesting diario al 99 % con Kupiec, Christoffersen y zona semáforo.

## Escenario 5 — Reproducibilidad (US5, SC-007, SC-009)

```bash
uv run python examples/03_var_portafolio_backtesting.py --report out1.json
uv run python examples/03_var_portafolio_backtesting.py --report out2.json
cmp out1.json out2.json   # idénticos salvo created_at (excluido del hash)
```

## Suite de verificación

```bash
uv run pytest -m "not slow and not network"   # rápido (CI)
uv run pytest -m slow                          # Monte Carlo SC-001/002/004/005
```
