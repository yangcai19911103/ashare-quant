"""M2 引擎测试：T+1、涨跌停、费用、撮合、组合状态机、端到端回测。"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from ashare_quant.engine.event_driven.events import (
    Bar,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)
from ashare_quant.engine.event_driven.matcher import AshareMatcher, FeeModel
from ashare_quant.engine.event_driven.portfolio import Portfolio
from ashare_quant.engine.event_driven.broker_sim import SimBroker


def _bar(symbol="600519.SH", close=100.0, prev_close=95.0):
    return Bar(symbol=symbol, trade_date=datetime(2024, 1, 2),
               open=close, high=close * 1.01, low=close * 0.99, close=close,
               volume=1e6, amount=close * 1e6, prev_close=prev_close)


# ------------------------ Fee Model ------------------------
def test_fee_model_defaults():
    fm = FeeModel()
    assert fm.commission_rate == 0.00025
    assert fm.stamp_duty == 0.001


# ------------------------ Matcher: 基础成交 ------------------------
def test_match_buy_basic():
    m = AshareMatcher(trade_price="open")
    o = Order("o1", "600519.SH", OrderSide.BUY, 100, OrderType.MARKET)
    fill = m.match(o, _bar())
    assert fill is not None
    assert o.status == OrderStatus.FILLED
    assert fill.quantity == 100
    assert fill.commission >= 5.0
    assert fill.stamp_duty == 0


def test_match_sell_basic():
    m = AshareMatcher(trade_price="open")
    o = Order("o2", "600519.SH", OrderSide.SELL, 200, OrderType.MARKET)
    fill = m.match(o, _bar(), available_shares=200)
    assert fill is not None
    assert fill.stamp_duty > 0  # 卖出有印花税


# ------------------------ Matcher: 涨停买不到 ------------------------
def test_limit_up_buy_blocked():
    m = AshareMatcher()
    # prev_close=100，今日 high=110 = 涨停
    bar = Bar("600519.SH", datetime(2024, 1, 2), 109, 110, 108, 110,
              1e6, 1.1e8, prev_close=100.0)
    o = Order("o", "600519.SH", OrderSide.BUY, 100)
    fill = m.match(o, bar)
    assert fill is None
    assert o.status == OrderStatus.REJECTED
    assert "涨停" in o.reject_reason


def test_limit_down_sell_blocked():
    m = AshareMatcher()
    bar = Bar("600519.SH", datetime(2024, 1, 2), 91, 92, 90, 90,
              1e6, 9e7, prev_close=100.0)
    o = Order("o", "600519.SH", OrderSide.SELL, 100)
    fill = m.match(o, bar, available_shares=100)
    assert fill is None
    assert "跌停" in o.reject_reason


def test_chinext_20pct_limit():
    """创业板 20% 涨跌停。"""
    m = AshareMatcher()
    # 300xxx 创业板，prev=10，high=12 = 20% 涨停
    bar = Bar("300750.SZ", datetime(2024, 1, 2), 11.8, 12, 11.5, 12,
              1e6, 1.2e7, prev_close=10.0)
    o = Order("o", "300750.SZ", OrderSide.BUY, 100)
    fill = m.match(o, bar)
    assert fill is None


# ------------------------ Matcher: 数量校验 ------------------------
def test_quantity_must_be_multiple_of_100():
    m = AshareMatcher()
    o = Order("o", "600519.SH", OrderSide.BUY, 150)
    fill = m.match(o, _bar())
    assert fill is None
    assert "100" in o.reject_reason


def test_zero_volume_rejected():
    m = AshareMatcher()
    bar = _bar()
    bar.volume = 0
    o = Order("o", "600519.SH", OrderSide.BUY, 100)
    fill = m.match(o, bar)
    assert fill is None
    assert "停牌" in o.reject_reason


# ------------------------ Portfolio + T+1 ------------------------
def test_t1_lock_then_release():
    pf = Portfolio(initial_cash=1e6)
    m = AshareMatcher(trade_price="open")
    broker = SimBroker(pf, m)

    bar = _bar()
    bars = {"600519.SH": bar}

    # Day1 买入 200 股
    broker.submit("600519.SH", OrderSide.BUY, 200)
    fills = broker.process_bars(bars)
    assert len(fills) == 1
    pos = pf.positions["600519.SH"]
    assert pos.quantity == 200
    assert pos.available == 0          # T+1：当日不可卖

    # Day1 收盘
    pf.on_close(datetime(2024, 1, 2), {"600519.SH": 100.0})

    # 当日尝试卖出 → 应被拒
    broker.submit("600519.SH", OrderSide.SELL, 100)
    fills = broker.process_bars(bars)
    assert len(fills) == 0
    # Day2 盘前
    pf.on_open(datetime(2024, 1, 3))
    assert pf.positions["600519.SH"].available == 200

    # Day2 卖出 100 股
    broker.submit("600519.SH", OrderSide.SELL, 100)
    fills2 = broker.process_bars(bars)
    assert len(fills2) == 1
    assert pf.positions["600519.SH"].quantity == 100


def test_portfolio_nav_tracking():
    pf = Portfolio(initial_cash=100_000)
    m = AshareMatcher(trade_price="open")
    broker = SimBroker(pf, m)

    bar = _bar(close=50.0, prev_close=49.0)
    bars = {"600519.SH": bar}
    broker.submit("600519.SH", OrderSide.BUY, 100)
    broker.process_bars(bars)
    pf.on_close(datetime(2024, 1, 2), {"600519.SH": 55.0})
    assert pf.nav() > 100_000 - 100 * 50 - 100   # 减去佣金后仍然增值
    assert len(pf.nav_history) == 1


# ------------------------ 端到端：简单 buy-and-hold ------------------------
class BuyAndHold:
    name = "buy_and_hold"
    rebalance_freq = "M"
    params: dict = {}
    bought: bool = False

    def __init__(self, **params):
        self.params = params
        self.bought = False

    def on_start(self, ctx):
        pass

    def on_bar(self, ctx, bars):
        if self.bought:
            return
        n = len(bars)
        if n == 0:
            return
        per = 0.9 / n
        for sym, bar in bars.items():
            ctx.order_target_pct(sym, per, bar.open)
        self.bought = True

    def on_rebalance(self, ctx, bars):
        pass

    def on_end(self, ctx):
        pass


def test_end_to_end_backtest_with_mock(_isolate_storage, mock_adapter):
    """完整跑一遍 mock → 引擎 → 回测，验证管线连通。"""
    from ashare_quant.data.storage import Storage
    from ashare_quant.engine.event_driven.engine import BacktestEngine

    storage = Storage(root=_isolate_storage)
    stocks = mock_adapter.fetch_stock_list()
    storage.write_table("instruments/stocks", stocks)

    for sym in stocks["symbol"].head(5):
        df = mock_adapter.fetch_daily(sym, "2024-01-01", "2024-06-30")
        storage.write_daily(sym, df)

    # 引擎用单例 storage，所以要 patch
    from ashare_quant.data import storage as storage_mod
    storage_mod.get_storage.cache_clear()

    engine = BacktestEngine(
        strategy=BuyAndHold(),
        universe=stocks["symbol"].head(5).tolist(),
        start="2024-01-15",
        end="2024-06-15",
        initial_cash=1_000_000,
        adjust="none",
        trade_price="open",
    )
    result = engine.run()
    metrics = result.metrics()
    assert "sharpe" in metrics
    assert metrics["n_trades"] >= 1
    assert metrics["final_nav"] > 0
