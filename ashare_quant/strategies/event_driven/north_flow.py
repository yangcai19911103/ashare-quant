"""北向资金加仓策略：单日加仓金额前 N → 次日开盘跟入。"""
from __future__ import annotations

import pandas as pd

from ashare_quant.data.storage import get_storage
from ashare_quant.strategies.base import BaseStrategy, StrategyContext


class NorthFlowStrategy(BaseStrategy):
    name = "north_flow_follow"
    rebalance_freq = "D"

    def __init__(self, top_n: int = 20, holding_days: int = 5,
                 position_per_event: float = 0.04):
        super().__init__(top_n=top_n, holding_days=holding_days,
                         position_per_event=position_per_event)
        self._holdings: dict[str, int] = {}

    def on_start(self, ctx):
        df = get_storage().read_table("money_flow/north_by_stock")
        if df.empty:
            self._signal_by_date = {}
            return
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        signal = {}
        for d, g in df.groupby("trade_date"):
            top = g.nlargest(self.params["top_n"], "north_net_inflow")
            signal[d] = top["symbol"].tolist()
        self._signal_by_date = signal

    def on_bar(self, ctx, bars):
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
