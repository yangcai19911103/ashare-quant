"""价值 + 质量组合（巴菲特风格的简化 GARP 思路）。"""
from __future__ import annotations

from ashare_quant.strategies.multi_factor.equal_weight import EqualWeightMultiFactor


class ValueQualityStrategy(EqualWeightMultiFactor):
    name = "value_quality"

    def __init__(self, top_n: int = 30, rebalance_freq: str = "Q"):
        super().__init__(
            factors=("pe_ttm_inv", "pb_inv", "roe", "gross_margin",
                     "net_profit_yoy", "accruals"),
            top_n=top_n,
            rebalance_freq=rebalance_freq,
        )
