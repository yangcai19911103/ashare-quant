"""M3 策略冒烟测试：每个策略至少能完成一次端到端回测。"""
from __future__ import annotations

import pandas as pd
import pytest

from ashare_quant.data.storage import Storage
from ashare_quant.engine.event_driven.engine import BacktestEngine
from ashare_quant.strategies.registry import (
    create_strategy,
    list_strategies,
)


def _prepare_storage(_isolate_storage, mock_adapter, n=8):
    storage = Storage(root=_isolate_storage)
    stocks = mock_adapter.fetch_stock_list().head(n)
    storage.write_table("instruments/stocks", stocks)
    for sym in stocks["symbol"]:
        storage.write_daily(sym, mock_adapter.fetch_daily(sym, "2022-01-01", "2024-06-30"))
    # 重置单例
    from ashare_quant.data import storage as st
    st.get_storage.cache_clear()
    return stocks["symbol"].tolist()


def test_registry_lists_strategies():
    names = list_strategies()
    assert "multi_factor.value_quality" in names
    assert "cta.dual_ma" in names
    assert "cta.turtle" in names
    assert "stat_arb.etf_rotation" in names
    assert "rotation.industry_momentum" in names


@pytest.mark.parametrize("strat_name,params", [
    ("multi_factor.equal_weight",
     {"factors": ["mom_3m", "low_vol", "rev_1m"], "top_n": 3}),
    ("multi_factor.momentum_reversal",
     {"top_n": 3, "rebalance_freq": "M"}),
    ("multi_factor.low_vol",
     {"top_n": 3, "rebalance_freq": "M"}),
    ("cta.dual_ma",
     {"fast": 5, "slow": 20}),
    ("cta.bollinger",
     {"window": 20, "k": 2.0, "mode": "breakout"}),
    ("cta.turtle",
     {"entry_window": 10, "exit_window": 5, "atr_window": 10}),
    ("cta.atr_channel",
     {"ma_window": 10, "atr_window": 10}),
    ("cta.dual_thrust",
     {"n": 3}),
    ("cta.macd",
     {"fast": 12, "slow": 26, "signal": 9}),
    ("stat_arb.etf_rotation",
     {"momentum_window": 20, "top_k": 2}),
    ("rotation.industry_momentum",
     {"lookback": 20, "top_k": 2}),
])
def test_strategy_smoke(_isolate_storage, mock_adapter, strat_name, params):
    symbols = _prepare_storage(_isolate_storage, mock_adapter)
    strat = create_strategy(strat_name, **params)
    engine = BacktestEngine(
        strategy=strat,
        universe=symbols,
        start="2023-03-01",
        end="2024-03-01",
        initial_cash=1_000_000,
        adjust="none",
        trade_price="open",
    )
    result = engine.run()
    metrics = result.metrics()
    assert "sharpe" in metrics
    assert metrics["final_nav"] > 0


def test_pairs_trading(_isolate_storage, mock_adapter):
    symbols = _prepare_storage(_isolate_storage, mock_adapter)
    a, b = symbols[0], symbols[1]
    strat = create_strategy("stat_arb.pairs", pair=(a, b), window=30,
                            entry_z=1.5, exit_z=0.3)
    engine = BacktestEngine(
        strategy=strat,
        universe=[a, b],
        start="2023-03-01",
        end="2024-03-01",
        initial_cash=500_000,
        adjust="none",
        trade_price="open",
    )
    result = engine.run()
    assert result.metrics()["final_nav"] > 0
