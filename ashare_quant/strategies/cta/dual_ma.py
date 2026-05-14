"""双均线择时（单/多品种通用）。

- fast 上穿 slow：开多
- fast 下穿 slow：清仓
"""
from __future__ import annotations

from ashare_quant.strategies.base import BaseStrategy, StrategyContext


class DualMACrossStrategy(BaseStrategy):
    name = "dual_ma"
    rebalance_freq = "D"

    def __init__(self, fast: int = 5, slow: int = 20, max_position_pct: float = 0.95):
        super().__init__(fast=fast, slow=slow, max_position_pct=max_position_pct)

    def on_bar(self, ctx: StrategyContext, bars):
        n = len(bars)
        if n == 0:
            return
        per = self.params["max_position_pct"] / n
        fast = self.params["fast"]
        slow = self.params["slow"]

        for sym, bar in bars.items():
            df = ctx.history.get(sym)
            if df is None or len(df) < slow + 1:
                continue
            close = df["close"]
            ma_fast = close.rolling(fast).mean()
            ma_slow = close.rolling(slow).mean()
            curr_diff = ma_fast.iloc[-1] - ma_slow.iloc[-1]
            prev_diff = ma_fast.iloc[-2] - ma_slow.iloc[-2]
            in_pos = ctx.portfolio.positions.get(sym)
            holding = in_pos.quantity > 0 if in_pos else False

            # 金叉
            if prev_diff <= 0 and curr_diff > 0 and not holding:
                ctx.order_target_pct(sym, per, bar.close)
            # 死叉
            elif prev_diff >= 0 and curr_diff < 0 and holding:
                ctx.order_target_pct(sym, 0.0, bar.close)
