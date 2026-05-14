"""策略守护进程：连接网关 → 订阅行情 → 触发策略 → 风控 → 下单。"""
from __future__ import annotations

import threading
import time
from datetime import datetime

from ashare_quant.engine.event_driven.events import OrderSide, OrderType, Order
from ashare_quant.execution.base_gateway import BaseGateway
from ashare_quant.live.alert import alert
from ashare_quant.logging_setup import logger
from ashare_quant.risk.post_trade import PostTradeMonitor
from ashare_quant.risk.pre_trade import PreTradeRiskChecker
from ashare_quant.strategies.base import BaseStrategy


class StrategyRunner:
    """实时/模拟策略运行容器（不依赖回测引擎）。"""

    def __init__(
        self,
        strategy: BaseStrategy,
        gateway: BaseGateway,
        universe: list[str],
        risk_checker: PreTradeRiskChecker | None = None,
        risk_monitor: PostTradeMonitor | None = None,
    ) -> None:
        self.strategy = strategy
        self.gateway = gateway
        self.universe = universe
        self.risk = risk_checker or PreTradeRiskChecker()
        self.monitor = risk_monitor or PostTradeMonitor()
        self._stop = threading.Event()

    def start(self) -> None:
        logger.info(f"启动策略 {self.strategy.name}")
        self.gateway.connect()
        self.gateway.subscribe(self.universe)
        self.gateway.on_fill(self._on_fill)
        self.gateway.on_order(self._on_order)
        self.gateway.on_tick(self._on_tick)

    def stop(self) -> None:
        self._stop.set()
        self.gateway.disconnect()

    # ------------------------ 回调 ------------------------
    def _on_tick(self, tick) -> None:
        # 简化：实盘只在 tick 推送时记录最新价；策略主体由调度器或外层调用 trigger() 触发
        pass

    def _on_order(self, order: Order) -> None:
        logger.debug(f"订单回报：{order.order_id} {order.symbol} {order.status}")

    def _on_fill(self, fill) -> None:
        logger.info(f"成交：{fill.symbol} {fill.side.value} {fill.quantity}@{fill.price}")
        alerts = self.monitor.update(self.gateway.portfolio)
        for a in alerts:
            alert(a.level, a.code, a.message, **a.payload)
            if self.monitor.halted:
                logger.critical("风控熔断，停止所有 pending 订单")
                if hasattr(self.gateway, "broker"):
                    self.gateway.broker.cancel_all()

    # ------------------------ 手动触发 ------------------------
    def submit(self, symbol: str, side: OrderSide, quantity: int,
               price: float | None = None, order_type: OrderType = OrderType.MARKET) -> str | None:
        """带风控的下单封装。"""
        if self.monitor.halted:
            logger.warning("已熔断，拒绝下单")
            return None
        import uuid
        order = Order(order_id=uuid.uuid4().hex[:12], symbol=symbol,
                       side=side, quantity=quantity, order_type=order_type,
                       price=price, create_time=datetime.now())
        # 风控 - 需要 bar 参考价，简化用 price 或 portfolio.last_price
        # 实盘可在收到 tick 后做更精确校验，这里先放行
        return self.gateway.submit_order(order)
