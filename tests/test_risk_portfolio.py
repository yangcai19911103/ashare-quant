"""M4 风控 + 组合优化测试。"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from ashare_quant.engine.event_driven.events import Bar, Order, OrderSide
from ashare_quant.engine.event_driven.portfolio import Portfolio, Position
from ashare_quant.portfolio.optimizer import PortfolioOptimizer
from ashare_quant.risk.attribution import brinson_attribution
from ashare_quant.risk.post_trade import PostTradeMonitor
from ashare_quant.risk.pre_trade import PreTradeRiskChecker


def _bar(sym="600519.SH", close=100.0, vol=1e7):
    return Bar(symbol=sym, trade_date=datetime(2024, 1, 2),
               open=close, high=close * 1.01, low=close * 0.99, close=close,
               volume=vol, amount=close * vol, prev_close=close * 0.99)


# ------------------------ 单票上限 ------------------------
def test_pre_trade_single_stock_cap():
    pf = Portfolio(initial_cash=1_000_000)
    chk = PreTradeRiskChecker(max_position_per_stock=0.05,
                              max_industry_exposure=1.0)
    # 想买 1000 股 @ 100 = 100,000 = 10% NAV，超过 5% 上限
    o = Order("o", "600519.SH", OrderSide.BUY, 1000)
    r = chk.check(o, _bar(close=100.0), pf)
    assert r.passed
    # 应被裁减到 5%/100 = 500 股
    assert o.quantity == 500


def test_pre_trade_liquidity_cap():
    pf = Portfolio(initial_cash=10_000_000)
    chk = PreTradeRiskChecker(max_position_per_stock=1.0,
                              max_industry_exposure=1.0,
                              liquidity_limit=0.05)
    # 当日成交量 1e7 股，5% = 50万股
    o = Order("o", "600519.SH", OrderSide.BUY, 800_000)
    r = chk.check(o, _bar(close=100.0, vol=1e7), pf)
    assert r.passed
    assert o.quantity == 500_000


def test_pre_trade_industry_cap():
    pf = Portfolio(initial_cash=1_000_000)
    pf.positions["600519.SH"] = Position(symbol="600519.SH", quantity=2000,
                                          available=2000, avg_cost=100, last_price=100)
    industry = pd.Series({"600519.SH": "白酒", "000858.SZ": "白酒"})
    chk = PreTradeRiskChecker(max_position_per_stock=1.0,
                              max_industry_exposure=0.30,
                              industry_map=industry)
    # 当前白酒 = 20万 (20% NAV)，再买 000858 1000 股 = 10 万 → 30% 临界
    o = Order("o", "000858.SZ", OrderSide.BUY, 1500)
    r = chk.check(o, _bar(sym="000858.SZ", close=100.0), pf)
    assert r.passed
    # 应被裁减到刚好 30%
    assert o.quantity <= 1000


# ------------------------ 回撤熔断 ------------------------
def test_post_trade_max_drawdown_halt():
    pf = Portfolio(initial_cash=1_000_000)
    mon = PostTradeMonitor(max_drawdown_stop=0.10)
    # 初始
    pf.cash = 1_000_000
    pf.on_close(datetime(2024, 1, 2), {})
    mon.update(pf)
    # 跌 15%
    pf.cash = 850_000
    alerts = mon.update(pf)
    assert mon.halted
    assert any(a.code == "MAX_DRAWDOWN" for a in alerts)


def test_post_trade_stock_stop_loss():
    pf = Portfolio(initial_cash=1_000_000)
    pf.positions["600519.SH"] = Position(
        symbol="600519.SH", quantity=100, available=100,
        avg_cost=100.0, last_price=85.0,
    )
    mon = PostTradeMonitor(stock_stop_loss=0.10, max_drawdown_stop=0.5,
                            daily_loss_stop=0.5)
    mon.update(pf)
    mon.update(pf)
    assert "600519.SH" in mon.stop_loss_symbols()


# ------------------------ Brinson 归因 ------------------------
def test_brinson_attribution_basic():
    p_w = pd.DataFrame({"weight": [0.5, 0.5]}, index=["A", "B"])
    p_r = pd.DataFrame({"ret": [0.02, 0.01]}, index=["A", "B"])
    b_w = pd.DataFrame({"weight": [0.7, 0.3]}, index=["A", "B"])
    b_r = pd.DataFrame({"ret": [0.01, 0.01]}, index=["A", "B"])
    ind_map = pd.Series({"A": "I1", "B": "I2"})
    out = brinson_attribution(p_w, p_r, b_w, b_r, ind_map)
    assert set(out.columns) >= {"allocation", "selection", "interaction", "total"}
    # 行业 I1：超配 A 0.5 vs 0.7 → 低配 → 净贡献符号合理
    assert out.loc["I1", "total"] + out.loc["I2", "total"] != 0


# ------------------------ 优化器 ------------------------
@pytest.mark.parametrize("method", ["equal", "risk_parity", "min_var", "mvo"])
def test_optimizer_smoke(method):
    rng = np.random.default_rng(42)
    rets = pd.DataFrame(rng.normal(0.001, 0.02, size=(100, 5)),
                        columns=list("ABCDE"))
    opt = PortfolioOptimizer(method=method, max_weight=0.5)
    w = opt.optimize(rets)
    assert len(w) == 5
    assert abs(w.sum() - 1.0) < 1e-6
    assert (w >= -1e-6).all()
    assert (w <= 0.5 + 1e-6).all()


def test_optimizer_black_litterman_with_views():
    rng = np.random.default_rng(42)
    rets = pd.DataFrame(rng.normal(0.001, 0.02, size=(200, 4)),
                        columns=list("ABCD"))
    opt = PortfolioOptimizer(method="black_litterman", max_weight=0.6)
    # A 看多
    w = opt.optimize(rets, views={"A": 0.5})
    assert w["A"] >= w["D"]
