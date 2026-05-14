"""美林时钟简化版（PMI / CPI 两维度 → 4 象限 → 大类资产 / 行业组合）。

实际投资中需要宏观数据（PMI/CPI），本实现作框架性占位：
输入需要 ``macro/pmi.parquet`` (trade_date, value) 和 ``macro/cpi.parquet`` (trade_date, value).
"""
from __future__ import annotations

import pandas as pd

from ashare_quant.data.storage import get_storage
from ashare_quant.strategies.base import BaseStrategy, StrategyContext


# 4 象限 → 推荐行业（简化版）
_QUADRANT_INDUSTRY = {
    "recovery":   ["consumer_discretionary", "tech", "finance"],
    "overheat":   ["energy", "materials", "industrials"],
    "stagflation": ["energy", "utilities", "healthcare"],
    "reflation":  ["consumer_staples", "healthcare", "utilities"],
}


class MerrillClockStrategy(BaseStrategy):
    name = "merrill_clock"
    rebalance_freq = "M"

    def __init__(self, industry_symbol_map: dict[str, list[str]] | None = None,
                 max_position_pct: float = 0.9):
        super().__init__(industry_symbol_map=industry_symbol_map or {},
                         max_position_pct=max_position_pct)

    @staticmethod
    def _quadrant(pmi: float, cpi: float, pmi_thresh: float = 50.0,
                  cpi_thresh: float = 2.0) -> str:
        """PMI > 50 经济扩张；CPI > 2 通胀上行。"""
        if pmi > pmi_thresh and cpi <= cpi_thresh:
            return "recovery"
        if pmi > pmi_thresh and cpi > cpi_thresh:
            return "overheat"
        if pmi <= pmi_thresh and cpi > cpi_thresh:
            return "stagflation"
        return "reflation"

    def on_rebalance(self, ctx: StrategyContext, bars):
        storage = get_storage()
        pmi_df = storage.read_table("macro/pmi")
        cpi_df = storage.read_table("macro/cpi")
        if pmi_df.empty or cpi_df.empty:
            return

        pmi = pmi_df.sort_values("trade_date").iloc[-1]["value"]
        cpi = cpi_df.sort_values("trade_date").iloc[-1]["value"]
        q = self._quadrant(pmi, cpi)

        target_inds = _QUADRANT_INDUSTRY[q]
        chosen = []
        for ind in target_inds:
            chosen += self.params["industry_symbol_map"].get(ind, [])
        chosen = [s for s in chosen if s in bars]
        if not chosen:
            return

        per = self.params["max_position_pct"] / len(chosen)
        for sym in list(ctx.portfolio.positions):
            if sym not in chosen and ctx.portfolio.available_qty(sym) > 0 and sym in bars:
                ctx.order_target_pct(sym, 0.0, bars[sym].close)
        for sym in chosen:
            ctx.order_target_pct(sym, per, bars[sym].open)

    def on_bar(self, ctx, bars):
        pass
