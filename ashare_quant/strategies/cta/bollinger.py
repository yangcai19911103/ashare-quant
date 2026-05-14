"""布林带突破/回归策略。

模式：
- 'breakout'：上轨突破开多，跌破中轨清仓（趋势跟随）
- 'mean_revert'：跌破下轨开多，回到中轨清仓（反转）
"""
from __future__ import annotations

from ashare_quant.strategies.base import BaseStrategy, StrategyContext


class BollingerBreakoutStrategy(BaseStrategy):
    name = "bollinger"
    rebalance_freq = "D"

    def __init__(self, window: int = 20, k: float = 2.0,
                 mode: str = "breakout", max_position_pct: float = 0.9):
        super().__init__(window=window, k=k, mode=mode,
                         max_position_pct=max_position_pct)

    def on_bar(self, ctx: StrategyContext, bars):
        n = len(bars)
        if n == 0:
            return
        per = self.params["max_position_pct"] / n
        w = self.params["window"]
        k = self.params["k"]
        mode = self.params["mode"]

        for sym, bar in bars.items():
            df = ctx.history.get(sym)
            if df is None or len(df) < w + 2:
                continue
            close = df["close"]
            mu = close.rolling(w).mean()
            sd = close.rolling(w).std()
            upper = mu + k * sd
            lower = mu - k * sd
            mid = mu

            price = close.iloc[-1]
            prev = close.iloc[-2]
            holding = (ctx.portfolio.positions.get(sym) or
                       type("p", (), {"quantity": 0})).quantity > 0

            if mode == "breakout":
                if prev <= upper.iloc[-2] and price > upper.iloc[-1] and not holding:
                    ctx.order_target_pct(sym, per, bar.close)
                elif holding and price < mid.iloc[-1]:
                    ctx.order_target_pct(sym, 0.0, bar.close)
            else:  # mean_revert
                if price < lower.iloc[-1] and not holding:
                    ctx.order_target_pct(sym, per, bar.close)
                elif holding and price >= mid.iloc[-1]:
                    ctx.order_target_pct(sym, 0.0, bar.close)
