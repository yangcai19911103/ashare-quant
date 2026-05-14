"""端到端集成测试：覆盖完整链路。

数据 → 因子 → 策略 → 引擎 → 风控 → 报告
"""
from __future__ import annotations

import pandas as pd
import pytest

from ashare_quant.data.storage import Storage
from ashare_quant.engine.event_driven.engine import BacktestEngine
from ashare_quant.reporting import generate_report
from ashare_quant.strategies.registry import create_strategy


def test_full_pipeline(_isolate_storage, mock_adapter):
    """完整跑一个多因子策略：写数据 → 回测 → 生成报告。"""
    storage = Storage(root=_isolate_storage)
    stocks = mock_adapter.fetch_stock_list()
    storage.write_table("instruments/stocks", stocks)
    for sym in stocks["symbol"]:
        df = mock_adapter.fetch_daily(sym, "2022-01-01", "2024-06-30")
        storage.write_daily(sym, df)
    # 基准也作为一只"股票"写入
    bench_df = mock_adapter.fetch_daily("000300.SH", "2022-01-01", "2024-06-30")
    storage.write_daily("000300.SH", bench_df)

    # 清空 storage 单例缓存
    from ashare_quant.data import storage as st
    st.get_storage.cache_clear()

    # 构造策略
    strat = create_strategy(
        "multi_factor.equal_weight",
        factors=["mom_3m", "low_vol", "rev_1m"],
        top_n=3,
        rebalance_freq="M",
    )

    # 跑回测
    engine = BacktestEngine(
        strategy=strat,
        universe=stocks["symbol"].tolist(),
        start="2023-03-01",
        end="2024-06-15",
        initial_cash=1_000_000,
        benchmark="000300.SH",
        adjust="none",
        trade_price="open",
    )
    result = engine.run()
    metrics = result.metrics()

    # 报告
    report = generate_report(result, name="integration_test")
    assert metrics["final_nav"] > 0
    assert "sharpe" in metrics
    assert "max_drawdown" in metrics

    # 与基准对比
    alpha = report.alpha_vs_benchmark()
    assert "beta" in alpha or alpha == {}  # 至少不抛错

    # 月度收益分布
    monthly = report.monthly_returns()
    assert not monthly.empty
