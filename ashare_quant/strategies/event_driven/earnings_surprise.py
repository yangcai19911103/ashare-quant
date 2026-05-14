"""业绩预增事件驱动：公告 +1 日开盘买入，持有 N 日卖出。

数据需求：``events/earnings_forecast.parquet``，列：trade_date, symbol, surprise_pct
"""
from __future__ import annotations

import pandas as pd

from ashare_quant.data.storage import get_storage
from ashare_quant.strategies.base import BaseStrategy, StrategyContext


class EarningsSurpriseStrategy(BaseStrategy):
    name = "earnings_surprise"
    rebalance_freq = "D"

    def __init__(self, surprise_threshold: float = 0.30,
                 holding_days: int = 5, position_per_event: float = 0.05):
        super().__init__(surprise_threshold=surprise_threshold,
                         holding_days=holding_days,
                         position_per_event=position_per_event)
        self._open_positions: dict[str, int] = {}  # symbol -> days_held

    def on_start(self, ctx):
        events = get_storage().read_table("events/earnings_forecast")
        if events.empty:
            self._events_by_date = {}
            return
        events["trade_date"] = pd.to_datetime(events["trade_date"])
        events = events[events["surprise_pct"] >= self.params["surprise_threshold"]]
        self._events_by_date = {
            d: g["symbol"].tolist()
            for d, g in events.groupby("trade_date")
        }

    def on_bar(self, ctx: StrategyContext, bars):
        # 持仓计天数 → 到期清仓
        for sym in list(self._open_positions):
            self._open_positions[sym] += 1
            if self._open_positions[sym] >= self.params["holding_days"]:
                if sym in bars and ctx.portfolio.available_qty(sym) > 0:
                    ctx.order_target_pct(sym, 0.0, bars[sym].close)
                    self._open_positions.pop(sym, None)

        # 今日 +1 即昨日有公告
        events_today = self._events_by_date.get(pd.Timestamp(ctx.trade_date), [])
        for sym in events_today:
            if sym in bars and sym not in self._open_positions:
                ctx.order_target_pct(sym, self.params["position_per_event"],
                                      bars[sym].open)
                self._open_positions[sym] = 0
