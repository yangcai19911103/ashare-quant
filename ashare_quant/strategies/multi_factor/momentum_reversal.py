"""动量 + 短期反转组合（中期持有 + 反转择时入场）。"""
from __future__ import annotations

from ashare_quant.strategies.multi_factor.equal_weight import EqualWeightMultiFactor


class MomentumReversalStrategy(EqualWeightMultiFactor):
    name = "mom_reversal"

    def __init__(self, top_n: int = 30, rebalance_freq: str = "M"):
        super().__init__(
            factors=("mom_6m", "mom_12m", "rev_1m", "dist_52w_high"),
            top_n=top_n,
            rebalance_freq=rebalance_freq,
        )
