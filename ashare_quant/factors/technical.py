"""技术面因子：动量 / 反转 / 波动率 / 流动性。

不依赖财报数据，仅用 OHLCV，可直接通过 ``storage.read_daily_panel`` 喂入。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ashare_quant.factors.base import Factor, register


# ============================================================================
# 动量
# ============================================================================
@register("mom_1m")
class Momentum1M(Factor):
    """近 21 个交易日动量。"""
    direction = +1
    category = "momentum"

    def __init__(self, window: int = 21):
        super().__init__(window=window)

    def compute(self, panel, **_):
        close = panel["close"]
        return close.pct_change(self.params["window"])


@register("mom_3m")
class Momentum3M(Momentum1M):
    def __init__(self, window: int = 63):
        super().__init__(window=window)


@register("mom_6m")
class Momentum6M(Momentum1M):
    def __init__(self, window: int = 126):
        super().__init__(window=window)


@register("mom_12m")
class Momentum12M(Momentum1M):
    """12-1 动量（剔除最近 1 个月，经典学术因子）。"""
    direction = +1
    category = "momentum"

    def __init__(self):
        super().__init__(window=252)

    def compute(self, panel, **_):
        close = panel["close"]
        return close.shift(21).pct_change(252 - 21)


@register("dist_52w_high")
class DistTo52wHigh(Factor):
    """距 52 周新高的距离（越小越接近新高，正向）。"""
    direction = +1
    category = "momentum"

    def compute(self, panel, **_):
        close = panel["close"]
        roll_max = close.rolling(252, min_periods=60).max()
        return close / roll_max  # 越接近 1 越好


# ============================================================================
# 反转
# ============================================================================
@register("rev_1w")
class Reversal1W(Factor):
    """短期反转：上周收益。"""
    direction = -1
    category = "reversal"

    def compute(self, panel, **_):
        return panel["close"].pct_change(5)


@register("rev_1m")
class Reversal1M(Factor):
    direction = -1
    category = "reversal"

    def compute(self, panel, **_):
        return panel["close"].pct_change(21)


# ============================================================================
# 波动率
# ============================================================================
@register("low_vol")
class LowVolatility(Factor):
    """年化波动率倒数（低波动正向）。"""
    direction = +1
    category = "volatility"

    def __init__(self, window: int = 60):
        super().__init__(window=window)

    def compute(self, panel, **_):
        rets = panel["close"].pct_change()
        vol = rets.rolling(self.params["window"]).std() * np.sqrt(252)
        return -vol  # 越小越好 → 取负，方向变 +


@register("idio_vol")
class IdiosyncraticVol(Factor):
    """特异波动率（残差波动）：用过去 60 日个股收益对市场（等权宽基均值）回归取残差 std。"""
    direction = +1
    category = "volatility"

    def __init__(self, window: int = 60):
        super().__init__(window=window)

    def compute(self, panel, **_):
        rets = panel["close"].pct_change()
        mkt = rets.mean(axis=1)
        win = self.params["window"]
        idio = pd.DataFrame(index=rets.index, columns=rets.columns, dtype=float)

        # 滚动 OLS（轻量近似：直接用残差 std）
        mkt_var = mkt.rolling(win).var().replace(0, np.nan)
        for col in rets.columns:
            cov = rets[col].rolling(win).cov(mkt)
            beta = cov / mkt_var
            resid = rets[col] - beta * mkt
            idio[col] = resid.rolling(win).std()
        return -idio


# ============================================================================
# 流动性
# ============================================================================
@register("turnover_20d")
class Turnover20D(Factor):
    """20 日均换手率（高换手往往多头疲弱，方向 -1）。"""
    direction = -1
    category = "liquidity"

    def __init__(self, window: int = 20):
        super().__init__(window=window)

    def compute(self, panel, **_):
        if "turnover" in panel:
            return panel["turnover"].rolling(self.params["window"]).mean()
        # 用 volume/circ 近似（缺数据时退化为 volume rolling mean）
        return panel["volume"].rolling(self.params["window"]).mean()


@register("amihud_illiquidity")
class AmihudIlliquidity(Factor):
    """Amihud 非流动性 = mean(|ret| / amount) * 1e8 ；高 → 越差 → 方向 -1."""
    direction = -1
    category = "liquidity"

    def __init__(self, window: int = 20):
        super().__init__(window=window)

    def compute(self, panel, **_):
        rets = panel["close"].pct_change().abs()
        amt = panel.get("amount")
        if amt is None or amt.empty:
            return pd.DataFrame()
        ratio = rets / amt.replace(0, np.nan) * 1e8
        return ratio.rolling(self.params["window"]).mean()


# ============================================================================
# 技术指标（构造特征）
# ============================================================================
@register("ma_cross")
class MACross(Factor):
    """快 / 慢均线比（>1 多头排列）。"""
    direction = +1
    category = "momentum"

    def __init__(self, fast: int = 5, slow: int = 20):
        super().__init__(fast=fast, slow=slow)

    def compute(self, panel, **_):
        close = panel["close"]
        return close.rolling(self.params["fast"]).mean() / \
               close.rolling(self.params["slow"]).mean()


@register("rsi_14")
class RSI(Factor):
    """RSI(14)：超买（>70）超卖（<30）；中性区间适合反转。"""
    direction = -1
    category = "momentum"

    def __init__(self, window: int = 14):
        super().__init__(window=window)

    def compute(self, panel, **_):
        delta = panel["close"].diff()
        up = delta.clip(lower=0).rolling(self.params["window"]).mean()
        dn = (-delta.clip(upper=0)).rolling(self.params["window"]).mean()
        rs = up / dn.replace(0, np.nan)
        return 100 - 100 / (1 + rs)


@register("bbands_pos")
class BollingerPosition(Factor):
    """布林带位置 (0=下轨, 1=上轨)；偏高 → 超买，方向 -1."""
    direction = -1
    category = "momentum"

    def __init__(self, window: int = 20, k: float = 2.0):
        super().__init__(window=window, k=k)

    def compute(self, panel, **_):
        close = panel["close"]
        mu = close.rolling(self.params["window"]).mean()
        sd = close.rolling(self.params["window"]).std()
        upper = mu + self.params["k"] * sd
        lower = mu - self.params["k"] * sd
        return (close - lower) / (upper - lower)
