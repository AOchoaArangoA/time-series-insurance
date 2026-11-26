# Contrato de la API de Python (spec 007)

Todos los resultados son dataclasses inmutables con `summary()` y `to_dict()`. Toda
función aleatoria recibe un `numpy.random.Generator` o una `seed`.

```python
# stochastics
VasicekP.fit(r: pd.Series, dt: float = 1/252, *, bootstrap: int = 499, jackknife: bool = False) -> ShortRateFit
CIRP.fit(r, dt=1/252, ...) -> ShortRateFit                     # Feller con IC; tasas ≤ 0 ⇒ error claro
ShortRateFit.simulate(r0, horizon, n_paths, rng, antithetic=False) -> np.ndarray   # exacta
ShortRateFit.diagnostics() -> ShortRateDiagnostics              # FR-001b
MarkovShortRate.fit(r, k_regimes=2, dt=1/252, search_reps=20) -> RegimeFit       # ordena por σ
RegimeFit.filtered(t) / smoothed / params_estimation_end / simulate(...)
zero_coupon(model: Literal["vasicek","cir"], params_q, r_t, tau) -> np.ndarray
calibrate_q(model, quotes: RateQuotes, r_short: pd.Series, window) -> QCalibration  # λ ± ee
HullWhite(a, sigma, curve: Curve).simulate(...)                 # r = x + α(t)
class Curve(Protocol): discount(t), zero_rate(t), forward(t)
NodeCurve(tenors, zero_rates)                                   # mínima, no producción

# simulation
fit_factors(node_changes: pd.DataFrame, method="pca"|"diebold_li", k=3) -> FactorModel
historical(...), filtered_historical(..., vol="ewma"|"garch", asof=...), factor_mc(...), short_rate_mc(...) -> Scenarios
Scenarios: values, state_measure, pricing_measure, method, seed, window, mapping
control_variate(estimand, control, control_mean, pilot) -> VRResult(estimate, se, reduction_factor)

# sensitivities
FixedBond(maturity, coupon, freq), BondPortfolio([(bond, qty)])
measures(portfolio, curve) -> Sensitivities(pv, dv01, krd, duration_eff, convexity)
factor_greeks(portfolio, curve, factor_model, step_bp=1.0) -> FactorGreeks(delta, gamma)
approximate(portfolio, curve, scenarios, order=1|2) -> ApproxReport(full, delta, delta_gamma, errors)
attribute_pnl(...) -> PnLAttribution(by_factor, quadratic, residual)

# portfolio_risk
var_es(losses, levels=(0.99, 0.975), ci="bootstrap"|"block") -> RiskMeasure
backtest_var(realized, forecasts, level) -> VaRBacktest(kupiec, christoffersen, duration, z2)
stress(portfolio, curve, factor_model, shocks) -> StressReport
immunize(portfolio, hedges, targets, bounds) -> HedgeResult(quantities, residual_exposure, feasible)
```
