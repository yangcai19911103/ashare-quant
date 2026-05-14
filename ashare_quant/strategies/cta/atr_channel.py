"""ATR 通道突破策略。"""
from __future__ import annotations

import pandas as pd

from ashare_quant.strategies.base import BaseStrategy, StrategyContext
from ashare_quant.strategies.cta.turtle import TurtleStrategy


class ATRChannelStrategy(BaseStrategy):
    name = "atr_channel"
    rebalance_freq = "D"

    def __init__(self, ma_window: int = 20, atr_window: int = 20,
                 k_up: float = 2.0, k_dn: float = 2.0,
                 max_position_pct: float = 0.9):
        super().__init__(ma_window=ma_window, atr_window=atr_window,
                         k_up=k_up, k_dn=k_dn,
                         max_position_pct=max_position_pct)

    def on_bar(self, ctx: StrategyContext, bars):
        m = len(bars)
        if m == 0:
            return
        per = self.params["max_position_pct"] / m

        for sym, bar in bars.items():
            df = ctx.history.get(sym)
            need = max(self.params["ma_window"], self.params["atr_window"]) + 2
            if df is None or len(df) < need:
                continue
            mid = df["close"].rolling(self.params["ma_window"]).mean().iloc[-1]
            atr = TurtleStrategy._atr(df, self.params["atr_window"])
            upper = mid + self.params["k_up"] * atr
            lower = mid - self.params["k_dn"] * atr
            pos = ctx.portfolio.positions.get(sym)
            holding = pos and pos.quantity > 0

            if bar.close > upper and not holding:
                ctx.order_target_pct(sym, per, bar.close)
            elif holding and bar.close < lower:
                ctx.order_target_pct(sym, 0.0, bar.close)
