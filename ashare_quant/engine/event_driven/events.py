"""事件类型定义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class Bar:
    """单根 K 线。"""
    symbol: str
    trade_date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    pct_chg: float = 0.0
    prev_close: float | None = None    # 给涨跌停判定用
    is_st: bool = False
    name: str = ""


@dataclass
class Order:
    """订单。"""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int                       # 股数（必须 100 的整数倍，A 股一手 = 100）
    order_type: OrderType = OrderType.MARKET
    price: float | None = None          # 限价单的价格
    create_time: datetime | None = None
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: int = 0
    filled_price: float = 0.0
    reject_reason: str = ""

    def remaining(self) -> int:
        return self.quantity - self.filled_qty


@dataclass
class Fill:
    """成交回报。"""
    order_id: str
    symbol: str
    trade_date: datetime
    side: OrderSide
    quantity: int
    price: float
    commission: float = 0.0
    stamp_duty: float = 0.0
    transfer_fee: float = 0.0
    slippage: float = 0.0

    @property
    def total_cost(self) -> float:
        return self.commission + self.stamp_duty + self.transfer_fee

    @property
    def gross_amount(self) -> float:
        return self.quantity * self.price
