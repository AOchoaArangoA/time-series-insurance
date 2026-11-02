# Data Model: Motor econométrico núcleo (001)

Todas las entidades de resultado son `@dataclass(frozen=True, slots=True)` con
`summary() -> str` y `to_dict() -> dict` (serializable a JSON canónico).

## Insumos (contrato de datos, versión `1.0`)

### MarketSeries (formato largo)

| Campo | Tipo | Reglas |
|-------|------|--------|
| `date` | fecha | obligatoria; única por `series_id`; monótona creciente |
| `series_id` | str | obligatoria; `^[A-Za-z0-9_.:-]+$` |
| `value` | float | obligatoria salvo faltante explícito; finita |
| `kind` | enum | `price` \| `return` \| `rate` \| `index` |
| `unit` | enum | `level` \| `percent` \| `decimal` \| `bps` |
| `currency` | str | ISO 4217 (3 letras) |
| `frequency` | enum | `D` \| `B` \| `W` \| `M` |
| `source` | str | opcional (p. ej. `fred:DGS10`) |

Reglas de conjunto: `price` > 0; una sola `frequency`, `unit`, `currency` por
`series_id`.

### Portfolio

| Campo | Tipo | Reglas |
|-------|------|--------|
| `as_of` | fecha | obligatoria, única en el archivo |
| `asset_id` | str | debe existir como `series_id` en MarketSeries |
| `weight` | float | opcional; si existe, `sum(weight) == 1 ± 1e-8` |
| `amount` | float | opcional; requerido si no hay `weight` |
| `currency` | str | ISO 4217 |
| `asset_class` | enum | `fixed_income` \| `equity` \| `real_estate` \| `cash` \| `other` |

### RateNodes (interoperabilidad con el paquete de curvas)

| Campo | Tipo | Reglas |
|-------|------|--------|
| `date` | fecha | obligatoria |
| `curve_id` | str | obligatoria |
| `tenor_years` | float | > 0 |
| `rate` | float | en `unit` declarada |
| `unit` | enum | `percent` \| `decimal` \| `bps` |
| `compounding` | enum | `continuous` \| `annual` \| `semiannual` \| `simple` |
| `day_count` | str | p. ej. `ACT/365`, `30/360` |

## Configuración

### JurisdictionProfile

`name`, `confidence_level` (0.995), `horizon_days` (252), `base_currency` (opcional),
`business_calendar` (`"weekdays"` por defecto), `stress_shocks: Mapping[str, float]`.

## Resultados

- **TestResult**: `name`, `statistic`, `p_value`, `critical_values`, `null_hypothesis`,
  `specification` (constante/tendencia/rezagos), `reject_at: dict[level, bool]`,
  `reference` (cita).
- **StationarityReport**: `series_id`, `tests: list[TestResult]`, `integration_order:
  int | None`, `conclusion: Literal["I(0)", "I(1)", "I(2)", "inconclusive"]`,
  `decision_rule: str`, `break_date: date | None`.
- **DescriptiveReport**: momentos, cuantiles, ACF/PACF con bandas, JB, ARCH-LM.
- **ResidualDiagnostics**: `ljung_box`, `ljung_box_sq`, `arch_lm`, `jarque_bera`,
  `stability`, `is_adequate: bool`, `failures: list[str]`.
- **FittedModel** (base) → `ArimaResult`, `GarchResult`: `spec`, `params`,
  `std_errors`, `se_type`, `information_criteria`, `diagnostics: ResidualDiagnostics`,
  `converged: bool`, `warnings: list[str]`, `n_obs`, `sample: (start, end)`.
- **SelectionResult**: `best: FittedModel`, `candidates: DataFrame` (orden, AIC, BIC,
  HQIC, apto), `criterion`.
- **Forecast**: `origin`, `horizon`, `mean: Series`, `intervals: dict[level, DataFrame]`,
  `method` (`analytic` \| `bootstrap` \| `simulation`), `model_ref`, `warnings`.
- **BacktestResult** (pronóstico): `errors: DataFrame` por origen y horizonte,
  `metrics: DataFrame`, `coverage: DataFrame`, `dm_tests: list[TestResult]`, `scheme`
  (`expanding` \| `rolling`), `window`, `refit_every`.
- **RiskMeasure**: `measure` (`VaR` \| `ES`), `level`, `horizon_days`, `method`,
  `value`, `by_asset: Series | None`, `scaling_method`, `assumptions: list[str]`.
- **VaRBacktest**: `n_obs`, `n_exceptions`, `kupiec`, `christoffersen_ind`,
  `christoffersen_cc`, `traffic_light: Literal["green","yellow","red"]`,
  `es_test: TestResult | None`.
- **Snapshot**: `path`, `source`, `query` (ids, rango), `retrieved_at`, `sha256`,
  `schema_version`.
- **AnalysisReport**: `package_version`, `dependency_versions`, `profile`, `seed`,
  `data_snapshots: list[Snapshot]`, `sections: list[resultado]`, `created_at`.

## Relaciones

```text
DataSource ──fetch──▶ Snapshot ──load+validate(schema)──▶ MarketSeries / Portfolio / RateNodes
MarketSeries ──prepare──▶ serie transformada ──▶ StationarityReport
serie estacionaria ──fit/select──▶ FittedModel ──▶ ResidualDiagnostics
FittedModel ──forecast──▶ Forecast ;  fábrica de modelos ──rolling_origin──▶ BacktestResult
GarchResult + Portfolio + JurisdictionProfile ──▶ RiskMeasure ──▶ VaRBacktest
todo ──▶ AnalysisReport
```

## Estados

`FittedModel`: `converged=False` → no se pronostica (error). `converged=True` y
`is_adequate=False` → se pronostica con advertencia registrada en `Forecast.warnings`.
