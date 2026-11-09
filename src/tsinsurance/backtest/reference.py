"""Motor de referencia independiente basado en la librería ``bt`` (extra ``[backtest]``).

Se usa para validar ``run_backtest`` (SC-001): posiciones fraccionarias, comisión
proporcional al valor negociado y rebalanceo al objetivo en cada fecha de ejecución.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from tsinsurance.backtest.config import ExecutionConfig
from tsinsurance.errors import TSInsuranceError

__all__ = ["run_with_bt"]


def run_with_bt(
    prices: pd.Series | pd.DataFrame,
    target_weights: pd.Series | pd.DataFrame,
    config: ExecutionConfig | None = None,
) -> pd.Series:
    """Retornos netos por periodo según ``bt`` con la misma convención de ejecución.

    Soporta ``rebalance="every_bar"``, costo único (no por activo), sin tasa libre de
    riesgo ni cortos: es una referencia de verificación, no un motor de producción.
    """
    try:
        import bt
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise TSInsuranceError(
            "Instale el extra opcional: pip install 'tsinsurance[backtest]'"
        ) from exc
    cfg = config or ExecutionConfig()
    if cfg.rebalance != "every_bar" or cfg.allow_short:
        raise TSInsuranceError("run_with_bt sólo cubre rebalanceo cada barra y sin cortos.")
    px = prices.to_frame() if isinstance(prices, pd.Series) else prices
    tw = target_weights.to_frame() if isinstance(target_weights, pd.Series) else target_weights
    tw = tw.reindex(columns=px.columns)
    decided = tw.reindex(px.index.union(tw.index)).ffill().reindex(px.index).fillna(0.0)
    executed = decided.shift(cfg.lag).fillna(0.0)
    rate = cfg.cost_rate([str(c) for c in px.columns])[0]

    def commission(quantity: float, price: float) -> float:
        return abs(quantity) * price * rate

    strategy = bt.Strategy("ref", [bt.algos.WeighTarget(executed), bt.algos.Rebalance()])
    kwargs: dict[str, Any] = {
        "commissions": commission,
        "initial_capital": 1_000_000.0,
        "integer_positions": False,
        "progress_bar": False,
    }
    test = bt.Backtest(strategy, px, **kwargs)
    res = bt.run(test)
    value = res.prices.iloc[:, 0]
    out: pd.Series = value.pct_change().reindex(px.index).fillna(0.0)
    out.name = "bt"
    return out
