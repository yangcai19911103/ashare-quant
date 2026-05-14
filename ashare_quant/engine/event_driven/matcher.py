"""A股撮合器：T+1 / 涨跌停 / 停牌 / 一手 100 股 / 印花税 / 佣金 / 过户费 / 滑点."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ashare_quant.config import get
from ashare_quant.data.corporate_actions import (
    is_limit_down,
    is_limit_up,
    limit_up_threshold,
)
from ashare_quant.engine.event_driven.events import (
    Bar,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)


class T1ViolationError(RuntimeError):
    pass


@dataclass
class FeeModel:
    commission_rate: float = 0.00025
    commission_min: float = 5.0
    stamp_duty: float = 0.001
    transfer_fee: float = 0.00001
    slippage_bps: float = 5.0

    @classmethod
    def from_settings(cls) -> "FeeModel":
        return cls(
            commission_rate=get("broker.commission_rate", 0.00025),
            commission_min=get("broker.commission_min", 5.0),
            stamp_duty=get("broker.stamp_duty", 0.001),
            transfer_fee=get("broker.transfer_fee", 0.00001),
            slippage_bps=get("broker.slippage_bps", 5.0),
        )


class AshareMatcher:
    """撮合规则封装。

    设计：撮合器自身无状态，状态（如 T+1 锁定股数）由 Portfolio 维护。
    撮合器只判定订单能否在某根 Bar 上成交。
    """

    def __init__(self, fee_model: FeeModel | None = None,
                 trade_price: str = "next_open") -> None:
        self.fee = fee_model or FeeModel.from_settings()
        # trade_price: 'open' | 'close' | 'vwap' | 'next_open'
        self.trade_price = trade_price

    # ------------------------ 价格 ------------------------
    def reference_price(self, bar: Bar, order: Order) -> float:
        """获取撮合参考价。"""
        if order.order_type == OrderType.LIMIT and order.price is not None:
            return order.price
        if self.trade_price == "open":
            return bar.open
        if self.trade_price == "close":
            return bar.close
        if self.trade_price == "vwap":
            return bar.amount / max(bar.volume, 1)
        return bar.open  # next_open 由调用方传入"次日 bar"

    # ------------------------ 涨跌停 ------------------------
    def is_limit_up(self, bar: Bar) -> bool:
        if bar.prev_close is None or bar.prev_close <= 0:
            return False
        threshold = limit_up_threshold(bar.symbol, bar.name)
        return is_limit_up(bar.prev_close, bar.high, threshold)

    def is_limit_down(self, bar: Bar) -> bool:
        if bar.prev_close is None or bar.prev_close <= 0:
            return False
        threshold = limit_up_threshold(bar.symbol, bar.name)
        return is_limit_down(bar.prev_close, bar.low, threshold)

    # ------------------------ 主流程 ------------------------
    def match(self, order: Order, bar: Bar, available_shares: int | None = None
              ) -> Fill | None:
        """尝试撮合一笔订单；返回 Fill 或 None（被拒）。

        - BUY  + limit_up：买不到（除非订单价已经突破涨停，仍然忽略）
        - SELL + limit_down：卖不出
        - SELL：必须可卖股数 >= 数量（available_shares 由 Portfolio 传入，T+1 约束）
        - LIMIT：bar 区间内可触达才成交
        - 数量必须 >= 100 且为 100 的整数倍（已在 Portfolio 端校验，这里再保险）
        """
        if bar.volume <= 0:                # 停牌
            order.status = OrderStatus.REJECTED
            order.reject_reason = "停牌"
            return None

        if order.quantity < 100 or order.quantity % 100 != 0:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "数量必须为 100 整数倍"
            return None

        if order.side == OrderSide.BUY and self.is_limit_up(bar):
            order.status = OrderStatus.REJECTED
            order.reject_reason = "涨停买不到"
            return None
        if order.side == OrderSide.SELL and self.is_limit_down(bar):
            order.status = OrderStatus.REJECTED
            order.reject_reason = "跌停卖不出"
            return None
        if order.side == OrderSide.SELL and available_shares is not None:
            if available_shares < order.quantity:
                order.status = OrderStatus.REJECTED
                order.reject_reason = f"可卖股数不足(T+1)：{available_shares}<{order.quantity}"
                return None

        ref = self.reference_price(bar, order)
        # 限价单的区间触达校验
        if order.order_type == OrderType.LIMIT and order.price is not None:
            if order.side == OrderSide.BUY and order.price < bar.low:
                order.status = OrderStatus.REJECTED
                order.reject_reason = "限价低于当日最低，未触达"
                return None
            if order.side == OrderSide.SELL and order.price > bar.high:
                order.status = OrderStatus.REJECTED
                order.reject_reason = "限价高于当日最高，未触达"
                return None
            ref = max(bar.low, min(bar.high, order.price))

        # 滑点
        slip = ref * self.fee.slippage_bps / 1e4
        fill_price = ref + slip if order.side == OrderSide.BUY else ref - slip
        fill_price = max(fill_price, 0.01)

        # 费用
        gross = fill_price * order.quantity
        commission = max(gross * self.fee.commission_rate, self.fee.commission_min)
        stamp = gross * self.fee.stamp_duty if order.side == OrderSide.SELL else 0.0
        transfer = gross * self.fee.transfer_fee

        fill = Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            trade_date=bar.trade_date,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
            stamp_duty=stamp,
            transfer_fee=transfer,
            slippage=slip * order.quantity,
        )
        order.status = OrderStatus.FILLED
        order.filled_qty = order.quantity
        order.filled_price = fill_price
        return fill
