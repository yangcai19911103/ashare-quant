"""离线测试用 Mock 适配器：生成确定性的合成 A 股数据。

便于在没有网络/API 限流的环境下验证整个 pipeline、引擎和策略。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ashare_quant.data.ingest.base import BaseAdapter, normalize_symbol


_DEFAULT_SYMBOLS = [
    ("600519", "贵州茅台"),
    ("000858", "五粮液"),
    ("601318", "中国平安"),
    ("000333", "美的集团"),
    ("600036", "招商银行"),
    ("000651", "格力电器"),
    ("600276", "恒瑞医药"),
    ("000001", "平安银行"),
    ("002594", "比亚迪"),
    ("300750", "宁德时代"),
]


def _gen_price_series(seed: int, n: int, s0: float = 100.0,
                       mu: float = 0.0005, sigma: float = 0.02) -> np.ndarray:
    rng = np.random.default_rng(seed)
    rets = rng.normal(mu, sigma, size=n)
    return s0 * np.exp(np.cumsum(rets))


class MockAdapter(BaseAdapter):
    name = "mock"

    def __init__(self, symbols: list[tuple[str, str]] | None = None,
                 start: str = "2018-01-01", end: str | None = None) -> None:
        self.symbols = symbols or _DEFAULT_SYMBOLS
        self.start = pd.Timestamp(start)
        self.end = pd.Timestamp(end) if end else pd.Timestamp.today().normalize()

    # ------------------------ 基础信息 ------------------------
    def fetch_stock_list(self) -> pd.DataFrame:
        rows = []
        for i, (code, name) in enumerate(self.symbols):
            rows.append({
                "symbol": normalize_symbol(code),
                "name": name,
                "exchange": "SH" if code.startswith("6") else "SZ",
                "is_st": False,
                "list_date": pd.Timestamp("2010-01-01"),
                "industry": ["白酒", "白酒", "保险", "家电", "银行",
                             "家电", "医药", "银行", "汽车", "电池"][i % 10],
            })
        return pd.DataFrame(rows)

    # ------------------------ 日 K ------------------------
    def fetch_daily(self, symbol: str, start: Any, end: Any) -> pd.DataFrame:
        s = max(self.start, pd.Timestamp(start))
        e = min(self.end, pd.Timestamp(end))
        days = pd.bdate_range(s, e)
        if len(days) == 0:
            return pd.DataFrame()

        seed = abs(hash(symbol)) % (2**31)
        close = _gen_price_series(seed, len(days), s0=20 + (seed % 80))
        # 简化 OHLC：以 close 为中心 +/- 1%
        rng = np.random.default_rng(seed + 1)
        wiggle = rng.uniform(0.99, 1.01, size=(len(days), 2))
        opens = close * rng.uniform(0.99, 1.01, size=len(days))
        highs = np.maximum.reduce([close, opens]) * wiggle[:, 0].clip(min=1.0)
        lows = np.minimum.reduce([close, opens]) * wiggle[:, 1].clip(max=1.0)
        volume = rng.integers(1e6, 5e7, size=len(days)).astype(float)
        amount = volume * close
        pct = pd.Series(close).pct_change().fillna(0.0).values * 100

        df = pd.DataFrame({
            "trade_date": days.normalize(),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": close,
            "volume": volume,
            "amount": amount,
            "pct_chg": pct,
            "adj_factor": 1.0,
        })
        return df

    # ------------------------ 指数成分 ------------------------
    def fetch_index_members(self, index_code: str) -> pd.DataFrame:
        return pd.DataFrame({
            "symbol": [normalize_symbol(c) for c, _ in self.symbols],
            "weight": [10.0] * len(self.symbols),
        })

    # ------------------------ 北向 ------------------------
    def fetch_north_flow(self, start: Any, end: Any) -> pd.DataFrame:
        days = pd.bdate_range(start, end)
        rng = np.random.default_rng(42)
        return pd.DataFrame({
            "trade_date": days.normalize(),
            "north_net_inflow": rng.normal(0, 1e9, size=len(days)),
        })
