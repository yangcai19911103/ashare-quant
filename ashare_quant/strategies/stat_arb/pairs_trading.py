"""配对交易（协整 + Z-score）。

A 股不能直接做空个股，因此本策略采用"长腿替代"近似：
- 持有低估腿（spread < -开仓阈值）
- 不持有高估腿（不做空，避免无法实现）
- 收敛时平仓（|spread| < 平仓阈值）
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

from ashare_quant.strategies.base import BaseStrategy, StrategyContext


class PairsTradingStrategy(BaseStrategy):
    name = "pairs_trading"
    rebalance_freq = "D"

    def __init__(self, pair: tuple[str, str], window: int = 60,
                 entry_z: float = 2.0, exit_z: float = 0.5,
                 max_position_pct: float = 0.4):
        super().__init__(pair=tuple(pair), window=window,
                         entry_z=entry_z, exit_z=exit_z,
                         max_position_pct=max_position_pct)

    def on_bar(self, ctx: StrategyContext, bars):
        a, b = self.params["pair"]
        if a not in bars or b not in bars:
            return
        da, db = ctx.history.get(a), ctx.history.get(b)
        if da is None or db is None:
            return
        w = self.params["window"]
        if len(da) < w + 5 or len(db) < w + 5:
            return

        joined = pd.concat([da["close"].rename("a"), db["close"].rename("b")],
                           axis=1).dropna().tail(w + 1)
        if len(joined) < w:
            return
        # 对数价比的 z-score 作为 spread 信号
        ratio = np.log(joined["a"] / joined["b"])
        mean = ratio.rolling(w).mean().iloc[-1]
        std = ratio.rolling(w).std().iloc[-1]
        if std == 0 or np.isnan(std):
            return
        z = (ratio.iloc[-1] - mean) / std

        pos_a = ctx.portfolio.positions.get(a)
        pos_b = ctx.portfolio.positions.get(b)
        holding_a = pos_a and pos_a.quantity > 0
        holding_b = pos_b and pos_b.quantity > 0

        pct = self.params["max_position_pct"] / 2

        # z < -entry：a 相对 b 便宜 → 持有 a；同时清掉 b（如果还在持有）
        if z < -self.params["entry_z"]:
            if holding_b:
                ctx.order_target_pct(b, 0.0, bars[b].close)
            if not holding_a:
                ctx.order_target_pct(a, pct, bars[a].close)
        elif z > self.params["entry_z"]:
            if holding_a:
                ctx.order_target_pct(a, 0.0, bars[a].close)
            if not holding_b:
                ctx.order_target_pct(b, pct, bars[b].close)
        # 收敛 → 平仓
        elif abs(z) < self.params["exit_z"]:
            if holding_a:
                ctx.order_target_pct(a, 0.0, bars[a].close)
            if holding_b:
                ctx.order_target_pct(b, 0.0, bars[b].close)

    @staticmethod
    def coint_pvalue(a: pd.Series, b: pd.Series) -> float:
        """协整检验 p-value。"""
        return float(coint(a, b)[1])
