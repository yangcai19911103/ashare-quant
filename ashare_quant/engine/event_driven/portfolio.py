"""组合 / 持仓 / 现金管理。T+1 由 Portfolio 维护。"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from ashare_quant.engine.event_driven.events import Fill, OrderSide


@dataclass
class Position:
    symbol: str
    quantity: int = 0                   # 总持仓
    available: int = 0                  # 可卖股数（A 股 T+1：当日买入次日才可卖）
    avg_cost: float = 0.0
    last_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.last_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.last_price - self.avg_cost) * self.quantity


@dataclass
class Portfolio:
    """组合状态机。"""
    initial_cash: float
    cash: float = 0.0
    positions: Dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    total_commission: float = 0.0
    nav_history: List[tuple[datetime, float]] = field(default_factory=list)
    fills_history: List[Fill] = field(default_factory=list)
    # T+1：今日新买入暂记入此处，次日盘前 release 到 available
    _pending_today: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def __post_init__(self) -> None:
        if self.cash == 0.0:
            self.cash = self.initial_cash

    # ------------------------ 状态查询 ------------------------
    def market_value(self) -> float:
        return sum(p.market_value for p in self.positions.values())

    def nav(self) -> float:
        return self.cash + self.market_value()

    def available_qty(self, symbol: str) -> int:
        p = self.positions.get(symbol)
        return p.available if p else 0

    # ------------------------ 事件 ------------------------
    def on_open(self, trade_date: datetime) -> None:
        """每日盘前调用：把昨日的 T+1 待解锁股数释放到 available。"""
        for sym, qty in self._pending_today.items():
            pos = self.positions.setdefault(sym, Position(symbol=sym))
            pos.available += qty
        self._pending_today.clear()

    def on_fill(self, fill: Fill) -> None:
        """收到成交回报，更新持仓和现金。"""
        self.fills_history.append(fill)
        sym = fill.symbol
        pos = self.positions.setdefault(sym, Position(symbol=sym))
        cost = fill.gross_amount + fill.total_cost

        if fill.side == OrderSide.BUY:
            # 加权平均成本（不算费用）
            new_qty = pos.quantity + fill.quantity
            if new_qty > 0:
                pos.avg_cost = (pos.avg_cost * pos.quantity + fill.gross_amount) / new_qty
            pos.quantity = new_qty
            self._pending_today[sym] += fill.quantity   # T+1
            self.cash -= cost
        else:  # SELL
            pos.quantity -= fill.quantity
            pos.available -= fill.quantity
            # 已实现盈亏
            realized = (fill.price - pos.avg_cost) * fill.quantity - fill.total_cost
            self.realized_pnl += realized
            self.cash += fill.gross_amount - fill.total_cost
            if pos.quantity <= 0:
                pos.quantity = 0
                pos.available = 0
                pos.avg_cost = 0.0
        self.total_commission += fill.total_cost

    def on_close(self, trade_date: datetime, last_prices: dict[str, float]) -> None:
        """每日收盘后调用：更新持仓最新价、记录 NAV。"""
        for sym, pos in self.positions.items():
            if sym in last_prices:
                pos.last_price = last_prices[sym]
        self.nav_history.append((trade_date, self.nav()))

    # ------------------------ 报告 ------------------------
    def summary(self) -> dict[str, float]:
        return {
            "initial_cash": self.initial_cash,
            "cash": self.cash,
            "market_value": self.market_value(),
            "nav": self.nav(),
            "realized_pnl": self.realized_pnl,
            "total_commission": self.total_commission,
            "n_positions": sum(1 for p in self.positions.values() if p.quantity > 0),
            "n_fills": len(self.fills_history),
        }
