"""低波动 + 高质量（防御型组合，适合震荡市）。"""
from __future__ import annotations

from ashare_quant.strategies.multi_factor.equal_weight import EqualWeightMultiFactor


class LowVolStrategy(EqualWeightMultiFactor):
    name = "low_vol_quality"

    def __init__(self, top_n: int = 30, rebalance_freq: str = "M"):
        super().__init__(
            factors=("low_vol", "idio_vol", "roe", "gross_margin",
                     "amihud_illiquidity"),
            top_n=top_n,
            rebalance_freq=rebalance_freq,
        )
