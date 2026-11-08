# Data Model: Backtesting responsable (002)

Resultados: `@dataclass(frozen=True, slots=True)` con `summary()` / `to_dict()` /
`to_json()` (ver `tsinsurance.results.ResultMixin`).

## Configuración

### ExecutionConfig

| Campo | Tipo | Regla / default |
|-------|------|-----------------|
| `lag` | int | ≥ 0; default 1 (barra siguiente). `0` ⇒ nota "optimista" |
| `cost_bps` | float \| Mapping[str, float] | ≥ 0; default 5; por activo si es Mapping |
| `slippage_bps` | float | ≥ 0; default 0 |
| `rebalance` | str | `"every_bar"` \| `"W"` \| `"M"`; default `"every_bar"` |
| `max_gross` | float | > 0; default 1.0 (Σ|w| máximo; se recorta y se informa) |
| `financing_spread_bps` | float | ≥ 0; default 0 (sobre efectivo negativo y cortos) |
| `allow_short` | bool | default False (pesos negativos ⇒ error si False) |
| `periods_per_year` | int \| None | None ⇒ inferido (B/D=252, W=52, M=12) |

### Exogenous

`name`, `series: pd.Series`, `frequency: "B"|"D"|"W"|"M"`, `release_lag: DateOffset`
(desde el fin del periodo), `transform: "level"|"diff"|"pct_change"|"yoy"`,
`point_in_time: bool = True`. Disponibilidad = `to_period(freq).end_time.normalize()` +
`release_lag`.

## Resultados

- **BacktestResult**: `name`, `returns` (Serie de retornos netos de la estrategia),
  `gross_returns`, `excess_returns`, `weights` (pesos mantenidos), `turnover`, `costs`,
  `equity`, `benchmark_returns`, `config: ExecutionConfig`, `metrics: PerformanceMetrics`,
  `benchmark_metrics`, `warmup_end`, `notes`.
- **PerformanceMetrics**: `annual_return`, `annual_volatility`, `sharpe`, `sortino`,
  `max_drawdown`, `calmar`, `hit_rate`, `avg_turnover`, `n_periods`, `periods_per_year`.
- **SharpeInference**: `sharpe` (anualizado), `se_iid` (Mertens), `se_hac` (método
  delta Newey-West), `ci_low`, `ci_high` (bootstrap estacionario), `psr` (vs 0),
  `block_length`, `reps`, `seed`.
- **SharpeDifference**: `sharpe_a`, `sharpe_b`, `difference`, `p_value` (unilateral,
  bootstrap estacionario), `cer_gain` (γ = 3, anualizada).
- **DeflatedSharpe**: `sharpe` (por periodo), `n_trials`, `n_effective`,
  `trials_sharpe_variance` (por periodo), `sr0` (por periodo), `dsr`.
- **SPAResult**: `pvalue_consistent`, `pvalue_lower`, `pvalue_upper`, `n_models`,
  `block_size`, `reps`, `seed`.
- **ForecastEvaluation**: `oos_r2`, `clark_west: HypothesisTestResult`,
  `diebold_mariano: HypothesisTestResult`, `pesaran_timmermann: HypothesisTestResult`,
  `hit_rate`, `n_forecasts`.
- **ModelValidation**: `coefficients` (DataFrame: coef, se_hac, t, p),
  `r2`, `adj_r2`, `regressor_stationarity: dict[str, StationarityReport]`,
  `persistence: DataFrame` (ρ, δ, sesgo de Stambaugh por regresor),
  `residual_tests: list[HypothesisTestResult]` (LB con `model_df`, ARCH-LM, JB, CUSUM),
  `diagnostics_passed: bool`, `warnings`. Descriptivo ex post: no se usa para elegir
  especificaciones.
- **WalkForwardForecast**: `forecasts` (Serie decidida en `t` para `t+1`),
  `forecast_se`, `benchmark_forecasts` (media histórica de la misma ventana), `realized`,
  `coefficient_path` (β por re-estimación), `n_refits`, `scheme`, `min_train`,
  `refit_every`.
- **EconometricBacktest**: `forecast: WalkForwardForecast`, `validation: ModelValidation`,
  `forecast_evaluation: ForecastEvaluation`, `backtest: BacktestResult`,
  `spa: SPAResult`, `verdict: Verdict`.
- **Verdict**: `statistical: bool`, `economic: bool`, `quadrant`
  (`"estadistica_y_economica"`, `"solo_estadistica"`, `"solo_economica"`,
  `"sin_evidencia"`), `diagnostics_passed: bool`, `n_specifications: int`,
  `exploratory: bool`, `inconclusive: bool`, `alpha`, `statistical_test: str`,
  `rule: str`, `explanation: str`.
- **LookaheadReport**: `has_lookahead: bool`, `cuts: list[Timestamp]`,
  `affected_dates: list[Timestamp]`, `max_abs_diff: float`.
- **TrialRegistry**: lista de `Trial(name, params, returns)`; `n_trials`,
  `sharpe_table()`, `deflated_sharpe(best)`, `spa(benchmark)`.
- **SweepResult**: `table: DataFrame` (activo × parámetros × métricas), `registry`,
  `best`, `deflated_sharpe`, `spa`.
- **CalibrationResult**: `best_params`, `in_sample`, `out_of_sample: BacktestResult`,
  `train_end`, `n_trials`.

## Flujo

```text
precios (Snapshot→to_wide) ──► signals.* / PredictiveRegression ──► pesos objetivo (t)
macro (Snapshot) ──► Exogenous(release_lag) ──► align_point_in_time ──┘
pesos objetivo ──► run_backtest(ExecutionConfig) ──► BacktestResult ─► inference / verdict
check_lookahead(signal_fn) ──► LookaheadReport (bloquea si hay fuga)
sweep(grid) ──► TrialRegistry ──► DSR + SPA
```
