"""MACD 金叉死叉 + 量能过滤。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ashare_quant.strategies.base import BaseStrategy, StrategyContext


class MACDStrategy(BaseStrategy):
    name = "macd"
    rebalance_freq = "D"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9,
                 vol_filter_window: int = 20, max_position_pct: float = 0.9):
        super().__init__(fast=fast, slow=slow, signal=signal,
                         vol_filter_window=vol_filter_window,
                         max_position_pct=max_position_pct)

    @staticmethod
    def _ema(s: pd.Series, span: int) -> pd.Series:
        return s.ewm(span=span, adjust=False).mean()

    def on_bar(self, ctx: StrategyContext, bars):
        n = len(bars)
        if n == 0:
            return
        per = self.params["max_position_pct"] / n
        for sym, bar in bars.items():
            df = ctx.history.get(sym)
            need = self.params["slow"] + self.params["signal"] + 5
            if df is None or len(df) < need:
                continue
            close = df["close"]
            ema_fast = self._ema(close, self.params["fast"])
            ema_slow = self._ema(close, self.params["slow"])
            dif = ema_fast - ema_slow
            dea = self._ema(dif, self.params["signal"])
            macd = (dif - dea) * 2

            vol_mean = df["volume"].rolling(self.params["vol_filter_window"]).mean()
            vol_ok = df["volume"].iloc[-1] > vol_mean.iloc[-1]

            curr = macd.iloc[-1]
            prev = macd.iloc[-2]
            holding = (ctx.portfolio.positions.get(sym) or
                       type("p", (), {"quantity": 0})).quantity > 0

            if prev <= 0 and curr > 0 and vol_ok and not holding:
                ctx.order_target_pct(sym, per, bar.close)
            elif prev >= 0 and curr < 0 and holding:
                ctx.order_target_pct(sym, 0.0, bar.close)
