"""模拟经纪商：接收订单 → 暂存 → 日内/次日撮合。"""
from __future__ import annotations

import uuid
from collections import defaultdict, deque
from datetime import datetime
from typing import Iterable

from ashare_quant.engine.event_driven.events import (
    Bar,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)
from ashare_quant.engine.event_driven.matcher import AshareMatcher
from ashare_quant.engine.event_driven.portfolio import Portfolio


class SimBroker:
    """简化模拟经纪商：每日只撮合一次（按 trade_price 配置）。"""

    def __init__(self, portfolio: Portfolio, matcher: AshareMatcher) -> None:
        self.portfolio = portfolio
        self.matcher = matcher
        self.pending_orders: deque[Order] = deque()
        self.all_orders: list[Order] = []

    # ------------------------ 下单 ------------------------
    def submit(self, symbol: str, side: OrderSide, quantity: int,
               order_type: OrderType = OrderType.MARKET,
               price: float | None = None, now: datetime | None = None) -> Order:
        order = Order(
            order_id=uuid.uuid4().hex[:12],
            symbol=symbol,
            side=side,
            quantity=int(quantity),
            order_type=order_type,
            price=price,
            create_time=now,
        )
        self.pending_orders.append(order)
        self.all_orders.append(order)
        return order

    def cancel_all(self) -> None:
        for o in self.pending_orders:
            o.status = OrderStatus.CANCELLED
        self.pending_orders.clear()

    # ------------------------ 撮合 ------------------------
    def process_bars(self, bars: dict[str, Bar]) -> list[Fill]:
        """对当前 pending_orders，使用同一交易日的 bars 撮合。"""
        fills: list[Fill] = []
        new_pending: deque[Order] = deque()
        while self.pending_orders:
            order = self.pending_orders.popleft()
            bar = bars.get(order.symbol)
            if bar is None:
                # 当日无行情 → 拒单
                order.status = OrderStatus.REJECTED
                order.reject_reason = "无行情"
                continue
            avail = self.portfolio.available_qty(order.symbol) \
                    if order.side == OrderSide.SELL else None
            fill = self.matcher.match(order, bar, available_shares=avail)
            if fill is not None:
                self.portfolio.on_fill(fill)
                fills.append(fill)
            # 拒单/未触达：丢弃（不滚动到次日）
        self.pending_orders = new_pending
        return fills
