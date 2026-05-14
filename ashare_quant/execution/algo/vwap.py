"""VWAP（成交量加权）算法单。

简化版：按当日典型成交量曲线（前 30 分钟/中间/最后 30 分钟）分配份额。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from ashare_quant.engine.event_driven.events import Order, OrderSide, OrderType
from ashare_quant.execution.base_gateway import BaseGateway
from ashare_quant.logging_setup import logger


# A 股典型当日成交量分布（30 分钟分桶，9:30-15:00，去除午休）
_VOL_WEIGHTS = [
    0.18,   # 9:30-10:00
    0.12,   # 10:00-10:30
    0.08,   # 10:30-11:00
    0.07,   # 11:00-11:30
    0.07,   # 13:00-13:30
    0.08,   # 13:30-14:00
    0.10,   # 14:00-14:30
    0.15,   # 14:30-15:00
    0.15,   # 15:00 收盘集合
]


@dataclass
class VWAPExecutor:
    gateway: BaseGateway
    symbol: str
    side: OrderSide
    total_qty: int
    bucket_size_min: int = 30

    _submitted: int = 0
    _last_bucket: int = -1

    def _bucket_index(self, t: datetime) -> int:
        """把当前时刻映射到 0..8 的桶序号。"""
        minutes = (t.hour - 9) * 60 + t.minute - 30
        if minutes < 0:
            return -1
        if t.hour >= 13:
            minutes -= 90       # 减去午休
        idx = minutes // self.bucket_size_min
        return min(max(idx, 0), len(_VOL_WEIGHTS) - 1)

    def tick(self, now: datetime) -> None:
        if self._submitted >= self.total_qty:
            return
        b = self._bucket_index(now)
        if b == self._last_bucket or b < 0:
            return
        # 进入新桶：把该桶应交的量一次性下出去
        cum_target = int(sum(_VOL_WEIGHTS[:b + 1]) * self.total_qty)
        cum_target = (cum_target // 100) * 100
        qty = cum_target - self._submitted
        if qty <= 0:
            self._last_bucket = b
            return
        order = Order(order_id=uuid.uuid4().hex[:12], symbol=self.symbol,
                      side=self.side, quantity=qty, order_type=OrderType.MARKET,
                      create_time=now)
        self.gateway.submit_order(order)
        self._submitted += qty
        self._last_bucket = b
        logger.info(f"VWAP 桶{b}: 提交 {qty} 股，累计 {self._submitted}/{self.total_qty}")
