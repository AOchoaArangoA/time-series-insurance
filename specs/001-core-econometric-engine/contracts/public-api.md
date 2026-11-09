# Contrato: API pública de `tsinsurance` v0.1

Firmas estables (cambios incompatibles requieren versión MAJOR). Tipos en
[data-model.md](../data-model.md).

## Datos

```python
tsinsurance.data.schemas.MarketSeriesSchema / PortfolioSchema / RateNodesSchema
tsinsurance.data.write_template(kind: Literal["market","portfolio","rate_nodes"],
                                path: PathLike, fmt: Literal["csv","xlsx"] = "csv") -> Path
tsinsurance.data.export_schema(kind, fmt: Literal["json-schema","frictionless"]) -> dict
tsinsurance.data.validate(df: DataFrame, kind) -> ValidationReport   # lazy, todos los errores
tsinsurance.data.load(path_or_snapshot, kind) -> DataFrame           # carga + valida
tsinsurance.data.sources.get_source(name: str, **kw) -> DataSource   # "csv","excel","fred","yahoo", entry points
DataSource.fetch(ids: Sequence[str], start: date, end: date) -> Snapshot
tsinsurance.data.prepare(series, *, freq, transform: Literal["none","simple","log","diff"],
                         missing: Literal["drop","ffill","interpolate","error"]) -> PreparedSeries
```

## Diagnóstico

```python
tsinsurance.diagnostics.stationarity(series, *, trend: Literal["c","ct"]="c",
                                     alpha=0.05, max_d=2, breaks=True) -> StationarityReport
tsinsurance.diagnostics.adf / pp / kpss / zivot_andrews(series, ...) -> HypothesisTestResult
tsinsurance.diagnostics.describe(series, nlags=20) -> DescriptiveReport
tsinsurance.diagnostics.residual_diagnostics(resid, *, model_df=0, lags=None,
                                             standardized=False) -> ResidualDiagnostics
```

## Modelos y pronóstico

```python
tsinsurance.models.fit_arima(series, order, seasonal_order=None, trend=None) -> ArimaResult
tsinsurance.models.select_arima(series, *, d=None, max_p=5, max_q=5,
                                criterion: Literal["aic","bic","hqic"]="bic") -> SelectionResult
tsinsurance.models.fit_garch(returns, *, vol: Literal["GARCH","EGARCH","GJR"]="GARCH",
                             p=1, o=0, q=1, mean: Literal["zero","constant","AR"]="constant",
                             dist: Literal["normal","t","skewt"]="t", rescale=True) -> GarchResult
tsinsurance.models.select_garch(returns, *, criterion="bic") -> SelectionResult
FittedModel.forecast(horizon: int, levels=(0.80, 0.95), *, method="analytic",
                     n_sims=10_000, seed: int | None = None) -> Forecast
```

## Validación

```python
tsinsurance.validation.rolling_origin(series, model_factory: Callable[[Series], FittedModel],
        *, initial: int, horizon: int, step=1, scheme: Literal["expanding","rolling"]="expanding",
        refit_every=1, benchmarks=("random_walk","mean"), levels=(0.95,)) -> BacktestResult
tsinsurance.validation.diebold_mariano(e1, e2, *, h=1, loss="mse") -> HypothesisTestResult
```

## Riesgo

```python
tsinsurance.risk.value_at_risk(returns_or_model, *, level=None, horizon_days=None,
        method: Literal["historical","parametric","garch"], weights=None,
        profile: JurisdictionProfile | None = None,
        scaling: Literal["sqrt_time","simulation"]="simulation", seed=None) -> RiskMeasure
tsinsurance.risk.expected_shortfall(...)  # misma firma
tsinsurance.risk.backtest_var(var_series, realized, *, level) -> VaRBacktest
tsinsurance.risk.backtest_es(es_series, var_series, realized, *, level, n_sims=10_000, seed) -> HypothesisTestResult
```
`level`/`horizon_days` en `None` ⇒ se toman del perfil (por defecto `generic`).

## Reporte y configuración

```python
tsinsurance.config.load_profile(name_or_path="generic") -> JurisdictionProfile
tsinsurance.reporting.AnalysisReport(...).to_json() / .to_markdown() / .save(path)
```

## CLI

```text
tsinsurance template {market|portfolio|rate_nodes} --format {csv|xlsx} -o PATH
tsinsurance validate {market|portfolio|rate_nodes} PATH        # exit 0 válido, 1 errores
tsinsurance schema {market|portfolio|rate_nodes} --format {json-schema|frictionless}
```

## Errores

`TSInsuranceError` (base) → `DataValidationError` (con `ValidationReport`),
`InsufficientDataError` (con mínimo requerido), `ConvergenceError`,
`InadequateModelWarning` (warning, no excepción).
