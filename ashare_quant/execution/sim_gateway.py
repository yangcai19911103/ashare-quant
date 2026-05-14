"""模拟交易网关：根据本地历史/实时行情 + 撮合器仿真实盘。

适合：
- 策略稳定性验证
- UI 监控看板的"假数据"流
- 教学 / Demo
"""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime
from typing import Any

import pandas as pd

from ashare_quant.data.storage import get_storage
from ashare_quant.engine.event_driven.broker_sim import SimBroker
from ashare_quant.engine.event_driven.events import (
    Bar,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)
from ashare_quant.engine.event_driven.matcher import AshareMatcher, FeeModel
from ashare_quant.engine.event_driven.portfolio import Portfolio
from ashare_quant.execution.base_gateway import BaseGateway, GatewayStatus, TickData
from ashare_quant.logging_setup import logger


class SimGateway(BaseGateway):
    """模拟网关。

    工作方式：
    - 在后台线程按 ``tick_interval`` 秒回放最近 N 日的数据
    - 收到订单后用 ``AshareMatcher`` + 当前 Bar 撮合
    """

    name = "sim"

    def __init__(self, initial_cash: float = 1_000_000,
                 fee_model: FeeModel | None = None,
                 tick_interval: float = 1.0) -> None:
        super().__init__()
        self.portfolio = Portfolio(initial_cash=initial_cash)
        self.matcher = AshareMatcher(fee_model=fee_model)
        self.broker = SimBroker(self.portfolio, self.matcher)
        self.tick_interval = tick_interval
        self._subscribed: set[str] = set()
        self._current_bars: dict[str, Bar] = {}
        self._running = False
        self._thread: threading.Thread | None = None
        self._replay_dates: list[pd.Timestamp] = []
        self._date_cursor = 0

    # ------------------------ 生命周期 ------------------------
    def connect(self, replay_start: str | None = None,
                replay_end: str | None = None, **_: Any) -> bool:
        self.status = GatewayStatus.CONNECTING
        if replay_start:
            self._replay_dates = list(pd.bdate_range(replay_start,
                                                     replay_end or datetime.now()))
        self.status = GatewayStatus.CONNECTED
        logger.info(f"SimGateway 连接成功，初始资金 {self.portfolio.initial_cash}")
        return True

    def disconnect(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.status = GatewayStatus.DISCONNECTED

    # ------------------------ 订阅 ------------------------
    def subscribe(self, symbols: list[str]) -> None:
        self._subscribed.update(symbols)

    def start_replay(self) -> None:
        """开始后台回放（在线程里推送 tick / 撮合）。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        storage = get_storage()
        while self._running and self._date_cursor < len(self._replay_dates):
            dt = self._replay_dates[self._date_cursor]
            self.portfolio.on_open(dt.to_pydatetime())
            bars: dict[str, Bar] = {}
            for sym in self._subscribed:
                df = storage.read_daily(sym, start=dt, end=dt, adjust="qfq")
                if df.empty:
                    continue
                row = df.iloc[0]
                prev = storage.read_daily(sym, start=dt - pd.Timedelta(days=10),
                                          end=dt - pd.Timedelta(days=1), adjust="qfq")
                prev_close = float(prev["close"].iloc[-1]) if not prev.empty else None
                bar = Bar(
                    symbol=sym, trade_date=dt.to_pydatetime(),
                    open=float(row["open"]), high=float(row["high"]),
                    low=float(row["low"]), close=float(row["close"]),
                    volume=float(row.get("volume", 0)),
                    amount=float(row.get("amount", 0)),
                    pct_chg=float(row.get("pct_chg", 0)),
                    prev_close=prev_close,
                )
                bars[sym] = bar
                self._emit_tick(TickData(
                    symbol=sym, timestamp=dt.to_pydatetime(),
                    last_price=bar.close, volume=bar.volume, amount=bar.amount,
                ))
            self._current_bars = bars
            fills = self.broker.process_bars(bars)
            for f in fills:
                self._emit_fill(f)
            last_prices = {s: b.close for s, b in bars.items()}
            self.portfolio.on_close(dt.to_pydatetime(), last_prices)
            self._date_cursor += 1
            time.sleep(self.tick_interval)
        self._running = False

    # ------------------------ 下单 ------------------------
    def submit_order(self, order: Order) -> str:
        if not order.order_id:
            order.order_id = uuid.uuid4().hex[:12]
        order.create_time = datetime.now()
        self.broker.pending_orders.append(order)
        self.broker.all_orders.append(order)
        self._emit_order(order)
        return order.order_id

    def cancel_order(self, order_id: str) -> bool:
        for o in list(self.broker.pending_orders):
            if o.order_id == order_id:
                o.status = OrderStatus.CANCELLED
                self.broker.pending_orders.remove(o)
                return True
        return False

    # ------------------------ 查询 ------------------------
    def query_positions(self) -> dict[str, dict]:
        return {sym: {"quantity": p.quantity, "available": p.available,
                      "avg_cost": p.avg_cost, "last_price": p.last_price,
                      "market_value": p.market_value,
                      "unrealized_pnl": p.unrealized_pnl}
                for sym, p in self.portfolio.positions.items() if p.quantity > 0}

    def query_account(self) -> dict:
        return self.portfolio.summary()
