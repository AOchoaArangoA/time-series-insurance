# Contrato de la API de Python (spec 004)

Todas las funciones nuevas son tipadas (mypy --strict) y devuelven dataclasses inmutables
con `summary()`.

## tsinsurance.experiments

```python
run_experiment(path, *, registry=None, output_root=None, record=True) -> ExperimentResult
# Con train_end: fase de calibración (antes calibraba y validaba).

validate_experiment(path, calibration_run_id, *, registry=None, output_root=None) -> ExperimentResult
# Lanza ValidationPreconditionError (subclase de TSInsuranceError) si falla una precondición.

fingerprint(fn) -> SignalFingerprint          # tsinsurance.experiments.fingerprint
```

## tsinsurance.experiments.registry

```python
registry_head(path) -> RegistryHead
verify_registry(path, *, base=None, results=None) -> list[str]   # [] = íntegra
registry_lock(path, run_id) -> ContextManager[None]              # RegistryLockedError si está tomada
unlock_registry(path, *, force=False) -> LockInfo | None
```

`verify_registry(path)` sin argumentos conserva su comportamiento actual.

## tsinsurance.data.bundle

```python
Bundle.as_of(cut) -> Bundle        # vista truncada en memoria; .as_of_date = cut
```

## tsinsurance.backtest.pit

```python
RealTimeExogenous(name, vintages, frequency, transform="level", mode="first_release")
    .available_series() -> pd.Series            # first_release
    .view(d) -> pd.Series                        # all_vintages
    .truncate_available(cut) -> RealTimeExogenous
```

Es compatible con `align_point_in_time` y `check_lookahead`.

## tsinsurance.backtest.econometric

```python
ivx_test(y, X, *, c_z=1.0, beta=0.95) -> IvxResult    # Wald por regresor y conjunto, p-valores
PredictiveRegression.walk_forward(y, X | Callable[[pd.Timestamp], pd.DataFrame])
```

`ModelValidation` gana el campo `ivx: IvxResult`.

## tsinsurance.backtest.inference

```python
sharpe_inference(..., hac="newey_west" | "prewhitened")
deflated_sharpe(returns, n_trials, trials_sharpe_variance, *, n_effective=None,
                trials_n_obs=None, variance_rule="raw" | "standardized")
```

El valor por defecto de `variance_rule` y de `hac` lo fija el resultado del Monte Carlo
(FR-023, SC-008). Se documenta en `docs/methodology/backtesting.md`.
