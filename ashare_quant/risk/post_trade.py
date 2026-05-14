"""事中/事后监控：最大回撤熔断、个股止损/止盈、单日亏损。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ashare_quant.config import get
from ashare_quant.engine.event_driven.portfolio import Portfolio


@dataclass
class RiskAlert:
    level: str           # INFO / WARN / CRITICAL
    code: str
    message: str
    payload: dict = field(default_factory=dict)


class PostTradeMonitor:
    """实时跟踪并产生风控信号。"""

    def __init__(
        self,
        max_drawdown_stop: float | None = None,
        daily_loss_stop: float | None = None,
        stock_stop_loss: float | None = None,
        stock_take_profit: float | None = None,
    ) -> None:
        self.max_dd = max_drawdown_stop if max_drawdown_stop is not None \
            else get("risk.max_drawdown_stop", 0.15)
        self.daily_loss = daily_loss_stop if daily_loss_stop is not None \
            else get("risk.daily_loss_stop", 0.05)
        self.stop_loss = stock_stop_loss if stock_stop_loss is not None \
            else get("risk.stock_stop_loss", 0.10)
        self.take_profit = stock_take_profit if stock_take_profit is not None \
            else get("risk.stock_take_profit", 0.30)
        self._peak_nav: float = 0.0
        self._prev_nav: float = 0.0
        self.alerts: list[RiskAlert] = []
        self.halted: bool = False

    # ------------------------ 触发 ------------------------
    def update(self, portfolio: Portfolio) -> list[RiskAlert]:
        new_alerts: list[RiskAlert] = []
        nav = portfolio.nav()
        if self._peak_nav == 0.0:
            self._peak_nav = nav
            self._prev_nav = nav
            return []

        # 最大回撤
        dd = nav / self._peak_nav - 1
        if dd <= -self.max_dd:
            self.halted = True
            new_alerts.append(RiskAlert(
                "CRITICAL", "MAX_DRAWDOWN",
                f"组合回撤 {dd:.2%} 触发熔断（阈值 {-self.max_dd:.2%}）",
                {"dd": float(dd), "nav": float(nav)},
            ))

        # 单日亏损
        daily = (nav / self._prev_nav - 1) if self._prev_nav > 0 else 0
        if daily <= -self.daily_loss:
            new_alerts.append(RiskAlert(
                "WARN", "DAILY_LOSS",
                f"单日亏损 {daily:.2%} 超过阈值 {-self.daily_loss:.2%}",
                {"daily_return": float(daily)},
            ))

        # 个股止损/止盈
        for sym, pos in portfolio.positions.items():
            if pos.quantity <= 0 or pos.avg_cost <= 0:
                continue
            ret = pos.last_price / pos.avg_cost - 1
            if ret <= -self.stop_loss:
                new_alerts.append(RiskAlert(
                    "WARN", "STOCK_STOP_LOSS",
                    f"{sym} 浮亏 {ret:.2%} 触发止损",
                    {"symbol": sym, "ret": float(ret)},
                ))
            elif ret >= self.take_profit:
                new_alerts.append(RiskAlert(
                    "INFO", "STOCK_TAKE_PROFIT",
                    f"{sym} 浮盈 {ret:.2%} 达到止盈",
                    {"symbol": sym, "ret": float(ret)},
                ))

        # 更新内部状态
        self._peak_nav = max(self._peak_nav, nav)
        self._prev_nav = nav

        self.alerts.extend(new_alerts)
        return new_alerts

    # ------------------------ 工具 ------------------------
    def stop_loss_symbols(self) -> set[str]:
        return {a.payload["symbol"] for a in self.alerts
                if a.code == "STOCK_STOP_LOSS"}

    def take_profit_symbols(self) -> set[str]:
        return {a.payload["symbol"] for a in self.alerts
                if a.code == "STOCK_TAKE_PROFIT"}
