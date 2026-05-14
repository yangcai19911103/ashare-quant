"""VectorBT 适配器：用于 CTA 类策略的参数网格扫描（加速）。

可选依赖：``pip install vectorbt``。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _ensure_vbt():
    try:
        import vectorbt as vbt  # noqa: F401
        return vbt
    except ImportError as exc:
        raise ImportError("未安装 vectorbt：pip install vectorbt（可选）") from exc


def ma_cross_grid(close: pd.DataFrame, fast_list: list[int], slow_list: list[int],
                  init_cash: float = 1e6, fees: float = 0.00025,
                  slippage: float = 0.0005) -> pd.DataFrame:
    """双均线参数网格扫描，返回每组 (fast, slow) 的夏普/收益。

    close: DataFrame, index=date, columns=symbol(或单列)
    """
    vbt = _ensure_vbt()
    fast = vbt.MA.run(close, window=fast_list, short_name="fast")
    slow = vbt.MA.run(close, window=slow_list, short_name="slow")
    entries = fast.ma_crossed_above(slow)
    exits = fast.ma_crossed_below(slow)
    pf = vbt.Portfolio.from_signals(
        close, entries, exits,
        init_cash=init_cash, fees=fees, slippage=slippage, freq="1D",
    )
    stats = pf.stats(agg_func=None)
    return stats


def rsi_grid(close: pd.DataFrame, windows: list[int],
             lower: float = 30, upper: float = 70,
             init_cash: float = 1e6) -> pd.DataFrame:
    vbt = _ensure_vbt()
    rsi = vbt.RSI.run(close, window=windows)
    entries = rsi.rsi_crossed_below(lower)
    exits = rsi.rsi_crossed_above(upper)
    pf = vbt.Portfolio.from_signals(close, entries, exits,
                                    init_cash=init_cash, freq="1D")
    return pf.stats(agg_func=None)
