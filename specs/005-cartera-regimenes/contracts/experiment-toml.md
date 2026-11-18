# Contrato: bloques nuevos de `experiment.toml`

```toml
[[portfolios]]
name = "rotacion"
universe = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
signal = "cross_sectional_momentum"        # o "inverse_volatility", o una registrada
  [portfolios.grid]
  lookback_m = [6, 12]
  top_k = [3, 4]

[[regimes]]
name = "curva_invertida"
type = "spread"
variables = ["^TNX", "^IRX"]               # a − b; cada una con su rezago declarado
op = "<"
value = 0.0
assets = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
min_months = 12

[[regimes]]
name = "vix_alto"
type = "threshold"
variable = "^VIX"
op = ">"
value = 25.0

[[regimes]]
name = "mercado_bajista"
type = "trend"
asset = "SPY"
months = 10
```

## API de Python

```python
from tsinsurance.experiments import register_portfolio_signal, available_portfolio_signals

register_portfolio_signal("mi_rotacion", fn)   # fn(prices: DataFrame, **params) -> pesos
```

## CLI

`tsinsurance experiment signals` lista también las señales de cartera. Los comandos `run`
y `validate` no cambian.
