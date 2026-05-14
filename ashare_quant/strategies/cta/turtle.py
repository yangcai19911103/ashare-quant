"""海龟交易：N 日突破入场 + ATR 头寸 + 2N ATR 止损。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ashare_quant.strategies.base import BaseStrategy, StrategyContext


class TurtleStrategy(BaseStrategy):
    name = "turtle"
    rebalance_freq = "D"

    def __init__(self, entry_window: int = 20, exit_window: int = 10,
                 atr_window: int = 20, atr_stop: float = 2.0,
                 risk_per_trade: float = 0.01):
        super().__init__(entry_window=entry_window, exit_window=exit_window,
                         atr_window=atr_window, atr_stop=atr_stop,
                         risk_per_trade=risk_per_trade)

    @staticmethod
    def _atr(df: pd.DataFrame, window: int) -> float:
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ], axis=1).max(axis=1)
        return float(tr.rolling(window).mean().iloc[-1])

    def on_bar(self, ctx: StrategyContext, bars):
        for sym, bar in bars.items():
            df = ctx.history.get(sym)
            need = max(self.params["entry_window"], self.params["atr_window"]) + 2
            if df is None or len(df) < need:
                continue
            ew = self.params["entry_window"]
            xw = self.params["exit_window"]
            highest = df["high"].rolling(ew).max().iloc[-2]
            lowest = df["low"].rolling(xw).min().iloc[-2]
            atr = self._atr(df, self.params["atr_window"])
            pos = ctx.portfolio.positions.get(sym)
            holding = pos and pos.quantity > 0

            if not holding and bar.close > highest:
                # 基于风险预算定头寸：单位 = (NAV * risk) / (ATR_stop * ATR)
                nav = ctx.portfolio.nav()
                risk_cash = nav * self.params["risk_per_trade"]
                stop_distance = max(self.params["atr_stop"] * atr, 0.01)
                shares = int(risk_cash / stop_distance // 100) * 100
                if shares > 0:
                    pct = min(shares * bar.close / nav, 0.2)
                    ctx.order_target_pct(sym, pct, bar.close)
            elif holding and bar.close < lowest:
                ctx.order_target_pct(sym, 0.0, bar.close)
            elif holding and pos.avg_cost > 0:
                # 2 ATR 止损
                if bar.close < pos.avg_cost - self.params["atr_stop"] * atr:
                    ctx.order_target_pct(sym, 0.0, bar.close)
