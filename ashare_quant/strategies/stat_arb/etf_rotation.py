"""行业 / 主题 ETF 动量轮动。

每月按过去 N 个月动量选 Top-K 个 ETF 等权持有。
"""
from __future__ import annotations

import pandas as pd

from ashare_quant.strategies.base import BaseStrategy, StrategyContext


class ETFRotationStrategy(BaseStrategy):
    name = "etf_rotation"
    rebalance_freq = "M"

    def __init__(self, momentum_window: int = 60, top_k: int = 3,
                 max_position_pct: float = 0.9):
        super().__init__(momentum_window=momentum_window, top_k=top_k,
                         max_position_pct=max_position_pct)

    def on_rebalance(self, ctx: StrategyContext, bars):
        if not bars:
            return
        w = self.params["momentum_window"]
        scores = {}
        for sym, df in ctx.history.items():
            if df is None or len(df) < w + 1:
                continue
            close = df["close"]
            scores[sym] = close.iloc[-1] / close.iloc[-w - 1] - 1
        if not scores:
            return
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        chosen = [s for s, _ in ranked[: self.params["top_k"]]]
        per = self.params["max_position_pct"] / max(len(chosen), 1)

        # 清掉其他
        for sym in list(ctx.portfolio.positions):
            if sym not in chosen and ctx.portfolio.available_qty(sym) > 0 and sym in bars:
                ctx.order_target_pct(sym, 0.0, bars[sym].close)
        for sym in chosen:
            if sym in bars:
                ctx.order_target_pct(sym, per, bars[sym].open)

    def on_bar(self, ctx, bars):
        pass
