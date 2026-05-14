"""调仓辅助：把目标权重 → 实际下单。"""
from __future__ import annotations

import pandas as pd

from ashare_quant.engine.event_driven.events import OrderSide
from ashare_quant.strategies.base import StrategyContext


def rebalance_to_weights(ctx: StrategyContext, weights: pd.Series,
                          bars, min_change_pct: float = 0.005) -> None:
    """根据目标权重调仓；剔除变动 < min_change_pct 的小调整以减少手续费。"""
    nav = ctx.portfolio.nav() or ctx.portfolio.initial_cash

    # 计算当前权重
    current = {}
    for sym, pos in ctx.portfolio.positions.items():
        current[sym] = pos.market_value / nav if nav > 0 else 0.0

    # 清掉不再持有的
    for sym in list(current):
        if sym not in weights.index or weights[sym] < 1e-6:
            if sym in bars and ctx.portfolio.available_qty(sym) > 0:
                ctx.order_target_pct(sym, 0.0, bars[sym].close)

    # 调整到目标
    for sym, w in weights.items():
        if sym not in bars or w <= 0:
            continue
        curr_w = current.get(sym, 0.0)
        if abs(w - curr_w) < min_change_pct:
            continue
        ref_price = bars[sym].open if hasattr(bars[sym], "open") else bars[sym]
        ctx.order_target_pct(sym, float(w), float(ref_price))
