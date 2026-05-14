"""复权与公司行为辅助。

约定：
- ``adj_factor`` 单调递增，新股上市日通常为 1.0；
- 前复权 (qfq) 价格 = 原价 * (factor / factor_today)
- 后复权 (hfq) 价格 = 原价 * factor
"""
from __future__ import annotations

import pandas as pd


def apply_adjustment(df: pd.DataFrame, mode: str = "qfq",
                     cols: tuple[str, ...] = ("open", "high", "low", "close")) -> pd.DataFrame:
    """对 OHLC 列做复权变换，原表必须含 ``adj_factor``。

    参数
    ----
    mode: 'qfq' / 'hfq' / 'none'
    """
    if df is None or df.empty or mode == "none":
        return df
    if "adj_factor" not in df.columns:
        return df
    out = df.copy()
    af = out["adj_factor"].ffill().fillna(1.0)
    if mode == "qfq":
        base = af.iloc[-1]
        ratio = af / base
    elif mode == "hfq":
        ratio = af
    else:
        raise ValueError(f"unknown adjust mode: {mode}")
    for c in cols:
        if c in out.columns:
            out[c] = out[c] * ratio
    return out


def derive_returns(df: pd.DataFrame, price_col: str = "close",
                   adjust: str = "hfq") -> pd.Series:
    """计算简单收益率（默认 hfq 价格）。"""
    if df.empty:
        return pd.Series(dtype=float)
    adj = apply_adjustment(df, mode=adjust)
    return adj[price_col].pct_change()


def limit_up_threshold(symbol: str, name: str = "") -> float:
    """涨跌停幅度（小数）。

    - 主板 (60/00 头) 普通：10%
    - ST/*ST：5%
    - 创业板 (300/301)、科创板 (688) 注册制后：20%
    - 北交所 (8/4)：30%
    """
    if "ST" in (name or ""):
        return 0.05
    head = symbol[:3]
    if head.startswith(("300", "301", "688")):
        return 0.20
    if head.startswith(("8", "9", "4")):
        return 0.30
    return 0.10


def is_limit_up(prev_close: float, today_close: float, threshold: float,
                tol: float = 1e-4) -> bool:
    if prev_close <= 0:
        return False
    return today_close >= prev_close * (1 + threshold) - tol


def is_limit_down(prev_close: float, today_close: float, threshold: float,
                  tol: float = 1e-4) -> bool:
    if prev_close <= 0:
        return False
    return today_close <= prev_close * (1 - threshold) + tol
