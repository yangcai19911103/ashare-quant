"""龙虎榜跟随：机构净买入 / 一线游资席位上榜 → 次日跟随。"""
from __future__ import annotations

import pandas as pd

from ashare_quant.data.storage import get_storage
from ashare_quant.strategies.base import BaseStrategy, StrategyContext


class DragonTigerFollowStrategy(BaseStrategy):
    name = "dragon_tiger_follow"
    rebalance_freq = "D"

    def __init__(self, min_net_buy: float = 5e7,
                 inst_buy_count_min: int = 2,
                 holding_days: int = 3,
                 position_per_event: float = 0.05):
        super().__init__(min_net_buy=min_net_buy,
                         inst_buy_count_min=inst_buy_count_min,
                         holding_days=holding_days,
                         position_per_event=position_per_event)
        self._holdings: dict[str, int] = {}

    def on_start(self, ctx):
        df = get_storage().read_table("events/dragon_tiger")
        if df.empty:
            self._signal_by_date = {}
            return
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        mask = (df.get("net_buy", 0) >= self.params["min_net_buy"]) & \
               (df.get("buy_inst_count", 0) >= self.params["inst_buy_count_min"])
        df = df[mask]
        self._signal_by_date = {
            d: g["symbol"].tolist() for d, g in df.groupby("trade_date")
        }

    def on_bar(self, ctx: StrategyContext, bars):
        for sym in list(self._holdings):
            self._holdings[sym] += 1
            if self._holdings[sym] >= self.params["holding_days"]:
                if sym in bars and ctx.portfolio.available_qty(sym) > 0:
                    ctx.order_target_pct(sym, 0.0, bars[sym].close)
                    self._holdings.pop(sym, None)

        signals = self._signal_by_date.get(pd.Timestamp(ctx.trade_date), [])
        for sym in signals:
            if sym in bars and sym not in self._holdings:
                ctx.order_target_pct(sym, self.params["position_per_event"],
                                      bars[sym].open)
                self._holdings[sym] = 0
