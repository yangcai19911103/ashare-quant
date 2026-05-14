"""情绪因子：北向资金 / 融资融券 / 资金流。"""
from __future__ import annotations

import pandas as pd

from ashare_quant.data.storage import get_storage
from ashare_quant.factors.base import Factor, register


@register("north_inflow_5d")
class NorthInflow5D(Factor):
    """北向资金 5 日净买入（个股级，若有；否则用市场总量做粗略代理）。"""
    direction = +1
    category = "sentiment"

    def __init__(self, window: int = 5):
        super().__init__(window=window)

    def compute(self, panel, **_):
        # 个股级表 columns: trade_date, symbol, north_net_inflow
        df = get_storage().read_table("money_flow/north_by_stock")
        if df.empty:
            return pd.DataFrame()
        wide = (df.pivot(index="trade_date", columns="symbol", values="north_net_inflow")
                  .sort_index())
        return wide.rolling(self.params["window"]).sum()


@register("margin_balance_chg")
class MarginBalanceChange(Factor):
    """融资余额 5 日变化率。"""
    direction = +1
    category = "sentiment"

    def __init__(self, window: int = 5):
        super().__init__(window=window)

    def compute(self, panel, **_):
        df = get_storage().read_table("money_flow/margin")
        if df.empty:
            return pd.DataFrame()
        wide = (df.pivot(index="trade_date", columns="symbol", values="margin_balance")
                  .sort_index())
        return wide.pct_change(self.params["window"])


@register("net_amount_5d")
class NetAmount5D(Factor):
    """主力资金 5 日净流入率（用 (close - open) * volume 的近似代理）。"""
    direction = +1
    category = "sentiment"

    def __init__(self, window: int = 5):
        super().__init__(window=window)

    def compute(self, panel, **_):
        if "close" not in panel or "open" not in panel:
            return pd.DataFrame()
        net = (panel["close"] - panel["open"]) * panel.get("volume", 1)
        return net.rolling(self.params["window"]).sum()
