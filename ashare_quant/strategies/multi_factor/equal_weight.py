"""等权合成多因子选股。

流程：
1. 取若干因子，按方向归一（direction 自动对齐为越大越好）
2. 截面 z-score → 等权求和 → 综合得分
3. 调仓日选 top-N，等权配置
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

import ashare_quant.factors.fundamental  # noqa: F401   触发注册
import ashare_quant.factors.sentiment    # noqa: F401
import ashare_quant.factors.technical    # noqa: F401
from ashare_quant.factors import get_registry
from ashare_quant.factors.neutralize import winsorize_zscore
from ashare_quant.strategies.base import BaseStrategy, StrategyContext


class EqualWeightMultiFactor(BaseStrategy):
    """等权多因子选股。

    参数：
      factors: 因子名列表，例如 ["mom_3m", "low_vol", "pb_inv"]
      top_n: 选股数
      top_pct: 若指定 top_pct（如 0.1），按比例选；优先级低于 top_n
      rebalance_freq: D/W/M/Q
    """

    name = "eq_multi_factor"

    def __init__(self, factors: Iterable[str] = ("mom_3m", "low_vol", "rev_1m"),
                 top_n: int = 20, top_pct: float | None = None,
                 rebalance_freq: str = "M"):
        super().__init__(factors=list(factors), top_n=top_n, top_pct=top_pct)
        self.rebalance_freq = rebalance_freq

    def _compose_score(self, panel) -> pd.DataFrame:
        reg = get_registry()
        score = None
        for fname in self.params["factors"]:
            f = reg.get(fname)
            val = f.compute(panel)
            if val.empty:
                continue
            normed = winsorize_zscore(val) * f.direction
            score = normed if score is None else score.add(normed, fill_value=0)
        return score if score is not None else pd.DataFrame()

    def _build_panel_from_history(self, ctx: StrategyContext):
        """把 ctx.history(dict[sym, df]) 拼成 wide-panel。"""
        close, high, low, op, vol, amt = {}, {}, {}, {}, {}, {}
        for sym, df in ctx.history.items():
            if df.empty:
                continue
            close[sym] = df["close"]
            high[sym] = df.get("high")
            low[sym] = df.get("low")
            op[sym] = df.get("open")
            vol[sym] = df.get("volume")
            amt[sym] = df.get("amount")
        panel = {
            "close": pd.DataFrame(close).sort_index(),
            "high": pd.DataFrame(high).sort_index(),
            "low": pd.DataFrame(low).sort_index(),
            "open": pd.DataFrame(op).sort_index(),
            "volume": pd.DataFrame(vol).sort_index(),
            "amount": pd.DataFrame(amt).sort_index(),
        }
        return panel

    def on_rebalance(self, ctx: StrategyContext, bars):
        panel = self._build_panel_from_history(ctx)
        if panel["close"].empty:
            return
        score = self._compose_score(panel)
        if score.empty:
            return

        latest = score.iloc[-1].dropna()
        if latest.empty:
            return

        # 选股
        n = self.params["top_n"]
        if self.params.get("top_pct"):
            n = max(1, int(len(latest) * self.params["top_pct"]))
        chosen = latest.nlargest(n).index.tolist()

        # 等权目标权重
        per = 1.0 / max(len(chosen), 1) * 0.95   # 留 5% 现金缓冲
        target = {sym: per for sym in chosen}

        # 清掉不再 hold 的（受 T+1 限制）
        for sym in list(ctx.portfolio.positions):
            if sym not in target and ctx.portfolio.available_qty(sym) > 0:
                ctx.order_target_pct(sym, 0.0, bars[sym].close
                                     if sym in bars else 1.0)

        # 调整目标股
        for sym, w in target.items():
            if sym in bars:
                ctx.order_target_pct(sym, w, bars[sym].open)

    def on_bar(self, ctx, bars):
        # 调仓由 on_rebalance 处理；on_bar 留空即可（也可加止损）
        pass
