"""TWAP（时间加权）算法单：把大单切成 N 个小单，按等时间间隔下出去。"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from ashare_quant.engine.event_driven.events import Order, OrderSide, OrderType
from ashare_quant.execution.base_gateway import BaseGateway
from ashare_quant.logging_setup import logger


@dataclass
class TWAPExecutor:
    """TWAP 切单。

    用法：
        twap = TWAPExecutor(gateway, symbol="600519.SH", side=OrderSide.BUY,
                             total_qty=10000, duration_min=30, slices=10)
        twap.start(now=datetime.now())
        # 在外部循环每分钟调用 twap.tick(now)
    """
    gateway: BaseGateway
    symbol: str
    side: OrderSide
    total_qty: int
    duration_min: int = 30
    slices: int = 10

    def __post_init__(self) -> None:
        # 每片必须是 100 整数倍
        per = self.total_qty // self.slices
        per = (per // 100) * 100
        self._per_slice = per
        self._submitted = 0
        self._start_time: datetime | None = None
        self._interval = timedelta(minutes=self.duration_min / self.slices)

    def start(self, now: datetime) -> None:
        self._start_time = now
        self._submitted = 0
        logger.info(f"TWAP 启动：{self.symbol} {self.side.value} 总量 {self.total_qty} → "
                    f"每片 {self._per_slice} 股，{self.slices} 片")

    def tick(self, now: datetime) -> None:
        """外部循环每 N 秒/分钟调用一次。"""
        if self._start_time is None or self._submitted >= self.total_qty:
            return
        elapsed = now - self._start_time
        target_slices = min(int(elapsed / self._interval) + 1, self.slices)
        while self._submitted < target_slices * self._per_slice and \
                self._submitted < self.total_qty:
            remaining = self.total_qty - self._submitted
            qty = min(self._per_slice, remaining)
            qty = (qty // 100) * 100
            if qty <= 0:
                break
            order = Order(order_id=uuid.uuid4().hex[:12], symbol=self.symbol,
                          side=self.side, quantity=qty, order_type=OrderType.MARKET,
                          create_time=now)
            self.gateway.submit_order(order)
            self._submitted += qty
            logger.info(f"TWAP 提交：{qty} 股，累计 {self._submitted}/{self.total_qty}")
