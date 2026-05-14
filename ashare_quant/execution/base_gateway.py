"""统一网关接口（模拟 / QMT / Ptrade / CTP）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable

# 直接复用回测里的事件类型（避免重复定义）
from ashare_quant.engine.event_driven.events import (  # noqa: F401
    Bar,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)


class GatewayStatus(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"


@dataclass
class TickData:
    symbol: str
    timestamp: datetime
    last_price: float
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_volume: int = 0
    ask_volume: int = 0
    volume: float = 0.0
    amount: float = 0.0


class BaseGateway(ABC):
    """所有网关的基类。"""

    name: str = "base"

    def __init__(self) -> None:
        self.status: GatewayStatus = GatewayStatus.DISCONNECTED
        self._on_tick: list[Callable[[TickData], None]] = []
        self._on_fill: list[Callable[[Fill], None]] = []
        self._on_order: list[Callable[[Order], None]] = []

    # ------------------------ 生命周期 ------------------------
    @abstractmethod
    def connect(self, **kwargs: Any) -> bool: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    # ------------------------ 订阅 / 下单 ------------------------
    @abstractmethod
    def subscribe(self, symbols: list[str]) -> None: ...

    @abstractmethod
    def submit_order(self, order: Order) -> str: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    def query_positions(self) -> dict[str, dict]: ...

    @abstractmethod
    def query_account(self) -> dict: ...

    # ------------------------ 回调注册 ------------------------
    def on_tick(self, cb: Callable[[TickData], None]) -> None:
        self._on_tick.append(cb)

    def on_fill(self, cb: Callable[[Fill], None]) -> None:
        self._on_fill.append(cb)

    def on_order(self, cb: Callable[[Order], None]) -> None:
        self._on_order.append(cb)

    # ------------------------ 内部分发 ------------------------
    def _emit_tick(self, tick: TickData) -> None:
        for cb in self._on_tick:
            try:
                cb(tick)
            except Exception:  # noqa: BLE001
                pass

    def _emit_fill(self, fill: Fill) -> None:
        for cb in self._on_fill:
            try:
                cb(fill)
            except Exception:  # noqa: BLE001
                pass

    def _emit_order(self, order: Order) -> None:
        for cb in self._on_order:
            try:
                cb(order)
            except Exception:  # noqa: BLE001
                pass
