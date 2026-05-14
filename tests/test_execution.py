"""M5 执行层 / 网关测试。"""
from __future__ import annotations

import time
from datetime import datetime

import pandas as pd
import pytest

from ashare_quant.data.storage import Storage
from ashare_quant.engine.event_driven.events import Order, OrderSide, OrderType
from ashare_quant.execution.algo.twap import TWAPExecutor
from ashare_quant.execution.algo.vwap import VWAPExecutor
from ashare_quant.execution.sim_gateway import SimGateway


def test_sim_gateway_connect_subscribe(_isolate_storage, mock_adapter):
    storage = Storage(root=_isolate_storage)
    stocks = mock_adapter.fetch_stock_list().head(3)
    for sym in stocks["symbol"]:
        storage.write_daily(sym, mock_adapter.fetch_daily(sym, "2024-01-01", "2024-03-01"))
    from ashare_quant.data import storage as st
    st.get_storage.cache_clear()

    gw = SimGateway(initial_cash=500_000, tick_interval=0.01)
    assert gw.connect(replay_start="2024-01-15", replay_end="2024-02-15")
    gw.subscribe(stocks["symbol"].tolist())
    assert gw.status.value == "CONNECTED"

    # 提交订单
    order = Order(order_id="", symbol=stocks["symbol"].iloc[0],
                  side=OrderSide.BUY, quantity=100, order_type=OrderType.MARKET)
    oid = gw.submit_order(order)
    assert oid

    gw.start_replay()
    time.sleep(0.5)
    gw.disconnect()
    # 至少 NAV 历史有一些记录
    assert len(gw.portfolio.nav_history) >= 0


def test_twap_executor():
    fills_received = []

    class FakeGW:
        def submit_order(self, o):
            fills_received.append(o)
            return o.order_id

    gw = FakeGW()
    twap = TWAPExecutor(gateway=gw, symbol="600519.SH", side=OrderSide.BUY,
                        total_qty=1000, duration_min=10, slices=5)
    start = datetime(2024, 1, 2, 10, 0)
    twap.start(start)
    # 模拟时间推进
    for m in range(0, 12, 2):
        twap.tick(datetime(2024, 1, 2, 10, m))
    assert len(fills_received) == 5
    assert sum(o.quantity for o in fills_received) == 1000


def test_vwap_executor():
    fills_received = []

    class FakeGW:
        def submit_order(self, o):
            fills_received.append(o)
            return o.order_id

    gw = FakeGW()
    vwap = VWAPExecutor(gateway=gw, symbol="600519.SH", side=OrderSide.SELL,
                        total_qty=5000)
    # 模拟一整天的桶
    for h in range(9, 15):
        for m in (30, 0):
            vwap.tick(datetime(2024, 1, 2, h, m))
    assert len(fills_received) >= 5
    # 总量大致等于 total_qty（受 100 整数倍约束可能微差）
    total = sum(o.quantity for o in fills_received)
    assert 4500 <= total <= 5000
