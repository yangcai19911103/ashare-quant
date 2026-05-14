"""行业动量轮动：用 28 个申万一级行业指数 / 行业 ETF 做动量轮动。"""
from __future__ import annotations

import pandas as pd

from ashare_quant.strategies.base import BaseStrategy, StrategyContext


class IndustryMomentumRotation(BaseStrategy):
    name = "industry_momentum"
    rebalance_freq = "M"

    def __init__(self, lookback: int = 63, top_k: int = 3,
                 max_position_pct: float = 0.95):
        super().__init__(lookback=lookback, top_k=top_k,
                         max_position_pct=max_position_pct)

    def on_rebalance(self, ctx: StrategyContext, bars):
        if not bars:
            return
        scores = {}
        lb = self.params["lookback"]
        for sym, df in ctx.history.items():
            if df is None or len(df) < lb + 1:
                continue
            close = df["close"]
            scores[sym] = close.iloc[-1] / close.iloc[-lb - 1] - 1
        if not scores:
            return
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        chosen = [s for s, _ in ranked[: self.params["top_k"]]]
        per = self.params["max_position_pct"] / max(len(chosen), 1)

        for sym in list(ctx.portfolio.positions):
            if sym not in chosen and ctx.portfolio.available_qty(sym) > 0 and sym in bars:
                ctx.order_target_pct(sym, 0.0, bars[sym].close)
        for sym in chosen:
            if sym in bars:
                ctx.order_target_pct(sym, per, bars[sym].open)

    def on_bar(self, ctx, bars):
        pass
