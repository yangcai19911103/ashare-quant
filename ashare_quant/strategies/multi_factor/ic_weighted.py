"""IC 加权多因子合成。

用滚动 IC（半衰）作为权重，强相关因子可适度去重。
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from ashare_quant.factors import get_registry
from ashare_quant.factors.neutralize import winsorize_zscore
from ashare_quant.strategies.multi_factor.equal_weight import EqualWeightMultiFactor


class ICWeightedMultiFactor(EqualWeightMultiFactor):
    """IC 加权多因子。

    参数：
      ic_window: 计算滚动 IC 的窗口（天数）
      forward_days: 前向收益窗口
    其余继承自 EqualWeightMultiFactor。
    """

    name = "ic_weighted_mf"

    def __init__(self, factors: Iterable[str] = ("mom_3m", "low_vol", "rev_1m"),
                 top_n: int = 20, rebalance_freq: str = "M",
                 ic_window: int = 60, forward_days: int = 21):
        super().__init__(factors=factors, top_n=top_n, rebalance_freq=rebalance_freq)
        self.params.update({"ic_window": ic_window, "forward_days": forward_days})

    def _compose_score(self, panel):
        reg = get_registry()
        close = panel["close"]
        fwd = close.pct_change(self.params["forward_days"]).shift(-self.params["forward_days"])

        weighted_score = None
        for fname in self.params["factors"]:
            f = reg.get(fname)
            val = f.compute(panel)
            if val.empty:
                continue
            normed = winsorize_zscore(val) * f.direction
            # 截面 IC：每天计算 corr(normed_today, fwd_today)，再取最近 ic_window 的均值
            ic_series = (normed.shift(1) * fwd).mean(axis=1)  # 简化代理
            recent_ic = ic_series.tail(self.params["ic_window"]).mean()
            weight = max(recent_ic, 0)    # 负 IC 因子权重置 0
            if np.isnan(weight) or weight == 0:
                continue
            contrib = normed * weight
            weighted_score = contrib if weighted_score is None else weighted_score.add(contrib, fill_value=0)
        return weighted_score if weighted_score is not None else pd.DataFrame()
