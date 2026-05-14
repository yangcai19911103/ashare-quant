"""事前风控：单票上限 / 行业暴露 / 流动性约束。"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ashare_quant.config import get
from ashare_quant.engine.event_driven.events import Bar, Order, OrderSide
from ashare_quant.engine.event_driven.portfolio import Portfolio


@dataclass
class RiskCheckResult:
    passed: bool
    reason: str = ""
    adjusted_qty: int | None = None    # 通过但被裁减后的数量


class PreTradeRiskChecker:
    """事前风控：拦截或调整订单。"""

    def __init__(
        self,
        max_position_per_stock: float | None = None,
        max_industry_exposure: float | None = None,
        liquidity_limit: float | None = None,
        industry_map: pd.Series | None = None,
    ) -> None:
        self.max_pos = max_position_per_stock if max_position_per_stock is not None \
            else get("risk.max_position_per_stock", 0.05)
        self.max_ind = max_industry_exposure if max_industry_exposure is not None \
            else get("risk.max_industry_exposure", 0.30)
        self.liq = liquidity_limit if liquidity_limit is not None \
            else get("risk.liquidity_limit", 0.05)
        self.industry_map = industry_map if industry_map is not None else pd.Series(dtype=str)

    # ------------------------ 各项检查 ------------------------
    def _check_position(self, order: Order, bar: Bar, portfolio: Portfolio) -> RiskCheckResult:
        if order.side == OrderSide.SELL:
            return RiskCheckResult(True)
        nav = portfolio.nav() or portfolio.initial_cash
        max_value = nav * self.max_pos
        order_value = order.quantity * bar.close
        existing = portfolio.positions.get(order.symbol)
        existing_val = existing.quantity * bar.close if existing else 0
        if existing_val + order_value <= max_value + 1e-6:
            return RiskCheckResult(True)
        room = max(max_value - existing_val, 0)
        adjusted = int(room / bar.close // 100) * 100
        if adjusted <= 0:
            return RiskCheckResult(False, "超过单票上限")
        return RiskCheckResult(True, "裁减至单票上限", adjusted_qty=adjusted)

    def _check_industry(self, order: Order, bar: Bar, portfolio: Portfolio) -> RiskCheckResult:
        if self.industry_map.empty or order.side == OrderSide.SELL:
            return RiskCheckResult(True)
        ind = self.industry_map.get(order.symbol)
        if ind is None or pd.isna(ind):
            return RiskCheckResult(True)
        # 累计该行业的持仓市值
        ind_value = 0.0
        for sym, pos in portfolio.positions.items():
            if self.industry_map.get(sym) == ind:
                ind_value += pos.market_value
        order_value = order.quantity * bar.close
        nav = portfolio.nav() or portfolio.initial_cash
        if (ind_value + order_value) / nav <= self.max_ind + 1e-6:
            return RiskCheckResult(True)
        room = max(self.max_ind * nav - ind_value, 0)
        adjusted = int(room / bar.close // 100) * 100
        if adjusted <= 0:
            return RiskCheckResult(False, f"行业 {ind} 暴露超限")
        return RiskCheckResult(True, "裁减至行业上限", adjusted_qty=adjusted)

    def _check_liquidity(self, order: Order, bar: Bar) -> RiskCheckResult:
        max_share = int(bar.volume * self.liq // 100) * 100
        if order.quantity <= max_share:
            return RiskCheckResult(True)
        if max_share <= 0:
            return RiskCheckResult(False, "流动性过低")
        return RiskCheckResult(True, "裁减至流动性上限", adjusted_qty=max_share)

    # ------------------------ 综合 ------------------------
    def check(self, order: Order, bar: Bar, portfolio: Portfolio) -> RiskCheckResult:
        for chk in (self._check_position, self._check_industry):
            r = chk(order, bar, portfolio)
            if not r.passed:
                return r
            if r.adjusted_qty is not None:
                order.quantity = r.adjusted_qty
        r = self._check_liquidity(order, bar)
        if not r.passed:
            return r
        if r.adjusted_qty is not None:
            order.quantity = r.adjusted_qty
        return RiskCheckResult(True)
