"""策略基类。

策略是回测/实盘的统一接口；引擎不关心策略内部细节，只把 Bar 与组合状态喂入，
并提供 ``ctx.order(...)`` 类似的下单 API。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from ashare_quant.engine.event_driven.broker_sim import SimBroker
from ashare_quant.engine.event_driven.events import Bar, OrderSide, OrderType
from ashare_quant.engine.event_driven.portfolio import Portfolio


@dataclass
class StrategyContext:
    """暴露给策略的运行时上下文。"""
    trade_date: datetime
    portfolio: Portfolio
    broker: SimBroker
    universe: list[str]
    # 各只股票"截至当前可用的历史数据" panel：dict[field, DataFrame]
    history: dict[str, pd.DataFrame] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)

    # ------------------------ 下单封装 ------------------------
    def order_shares(self, symbol: str, shares: int, side: OrderSide | str = OrderSide.BUY,
                     order_type: OrderType | str = OrderType.MARKET,
                     price: float | None = None):
        if isinstance(side, str):
            side = OrderSide(side)
        if isinstance(order_type, str):
            order_type = OrderType(order_type)
        return self.broker.submit(symbol, side, shares, order_type, price, self.trade_date)

    def order_target_pct(self, symbol: str, target_pct: float, ref_price: float):
        """按目标占组合权重下单（自动算成 100 的整数倍）。"""
        nav = self.portfolio.nav()
        target_value = nav * target_pct
        target_qty = int(target_value / ref_price // 100) * 100
        current_qty = self.portfolio.positions.get(symbol)
        current = current_qty.quantity if current_qty else 0
        diff = target_qty - current
        if diff > 0:
            return self.order_shares(symbol, diff, OrderSide.BUY)
        if diff < 0:
            avail = self.portfolio.available_qty(symbol)
            sell_qty = min(-diff, avail)
            sell_qty = (sell_qty // 100) * 100
            if sell_qty > 0:
                return self.order_shares(symbol, sell_qty, OrderSide.SELL)
        return None

    def close_all(self):
        """清仓所有持仓（受 T+1 限制）。"""
        for sym, pos in list(self.portfolio.positions.items()):
            if pos.available > 0:
                qty = (pos.available // 100) * 100
                if qty > 0:
                    self.order_shares(sym, qty, OrderSide.SELL)


class BaseStrategy(ABC):
    """策略基类。

    Lifecycle:
      1. ``on_start(ctx)``         回测/实盘启动时调用一次
      2. ``on_bar(ctx, bars)``     每个交易日调用一次（bars: dict[symbol, Bar]）
      3. ``on_rebalance(ctx)``     调仓日单独调用（频率由 settings.backtest.rebalance_freq）
      4. ``on_end(ctx)``           收尾
    """

    name: str = "base"
    rebalance_freq: str = "D"          # D / W / M / Q

    def __init__(self, **params: Any) -> None:
        self.params = params

    def on_start(self, ctx: StrategyContext) -> None:  # noqa: B027
        """启动时初始化（默认空实现）。"""

    @abstractmethod
    def on_bar(self, ctx: StrategyContext, bars: dict[str, Bar]) -> None:
        """每根 Bar 触发。"""

    def on_rebalance(self, ctx: StrategyContext, bars: dict[str, Bar]) -> None:  # noqa: B027
        """调仓日触发（默认空实现）。"""

    def on_end(self, ctx: StrategyContext) -> None:  # noqa: B027
        """收尾。"""

    def __repr__(self) -> str:
        return f"<Strategy {self.name} params={self.params}>"
