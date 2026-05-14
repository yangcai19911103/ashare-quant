"""Dual Thrust（适合日内/日频突破）。

每日上/下轨：
  upper = open + k1 * range,  lower = open - k2 * range
  range = max(HH - LC, HC - LL) of past N days
"""
from __future__ import annotations

from ashare_quant.strategies.base import BaseStrategy, StrategyContext


class DualThrustStrategy(BaseStrategy):
    name = "dual_thrust"
    rebalance_freq = "D"

    def __init__(self, n: int = 5, k1: float = 0.5, k2: float = 0.5,
                 max_position_pct: float = 0.9):
        super().__init__(n=n, k1=k1, k2=k2, max_position_pct=max_position_pct)

    def on_bar(self, ctx: StrategyContext, bars):
        m = len(bars)
        if m == 0:
            return
        per = self.params["max_position_pct"] / m
        n = self.params["n"]

        for sym, bar in bars.items():
            df = ctx.history.get(sym)
            if df is None or len(df) < n + 1:
                continue
            ref = df.iloc[-(n+1):-1]   # 不含今天
            HH = ref["high"].max()
            HC = ref["close"].max()
            LL = ref["low"].min()
            LC = ref["close"].min()
            R = max(HH - LC, HC - LL)
            today_open = bar.open
            upper = today_open + self.params["k1"] * R
            lower = today_open - self.params["k2"] * R
            holding = (ctx.portfolio.positions.get(sym) or
                       type("p", (), {"quantity": 0})).quantity > 0

            if bar.high >= upper and not holding:
                ctx.order_target_pct(sym, per, upper)
            elif bar.low <= lower and holding:
                ctx.order_target_pct(sym, 0.0, lower)
