"""数据源适配器基类。

不同数据源（AkShare / Tushare / efinance / XtQuant）实现统一接口；
上游 pipeline 不关心来源。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class BaseAdapter(ABC):
    """统一数据源接口。

    所有 DataFrame 列名遵循小写蛇形：
        trade_date, open, high, low, close, volume, amount, pct_chg, adj_factor
    symbol 统一为 6 位代码 + 后缀（.SH / .SZ / .BJ），例如 '600519.SH'。
    """

    name: str = "base"

    # --- 基础信息 ---
    @abstractmethod
    def fetch_stock_list(self) -> pd.DataFrame:
        """返回全市场股票列表。

        必备列：symbol, name, list_date, exchange, is_st (bool)
        可选列：sw_l1, sw_l2, market_cap, total_share
        """

    # --- 行情 ---
    @abstractmethod
    def fetch_daily(self, symbol: str, start: Any, end: Any) -> pd.DataFrame:
        """单只股票日K（含 adj_factor）。"""

    # --- 指数成分 ---
    @abstractmethod
    def fetch_index_members(self, index_code: str) -> pd.DataFrame:
        """指数成分股，列：symbol, weight（可选）, in_date（可选）."""

    # --- 财报（可选） ---
    def fetch_financials(self, symbol: str) -> pd.DataFrame:  # noqa: B027
        return pd.DataFrame()

    # --- 北向资金（可选） ---
    def fetch_north_flow(self, start: Any, end: Any) -> pd.DataFrame:  # noqa: B027
        return pd.DataFrame()

    # --- 龙虎榜（可选） ---
    def fetch_dragon_tiger(self, start: Any, end: Any) -> pd.DataFrame:  # noqa: B027
        return pd.DataFrame()


def normalize_symbol(code: str) -> str:
    """把 '600519' / 'sh600519' / '600519.SH' 统一成 '600519.SH'.

    规则：
      - 6 / 60 / 68 开头 → .SH（上证）
      - 0 / 3   开头 → .SZ（深证）
      - 4 / 8 / 92 开头 → .BJ（北交所）
    """
    s = str(code).strip().upper()
    # 已带后缀
    if "." in s:
        head, suf = s.split(".", 1)
        return f"{head.zfill(6)}.{suf}"
    # 'sh600519' 形式
    if s.startswith(("SH", "SZ", "BJ")) and len(s) >= 8:
        suf, head = s[:2], s[2:]
        return f"{head.zfill(6)}.{suf}"
    # 纯数字
    head = s.zfill(6)
    if head.startswith(("6",)):
        return f"{head}.SH"
    if head.startswith(("0", "3")):
        return f"{head}.SZ"
    if head.startswith(("4", "8", "92")):
        return f"{head}.BJ"
    return f"{head}.SH"


def split_symbol(symbol: str) -> tuple[str, str]:
    """'600519.SH' -> ('600519', 'SH')."""
    s = normalize_symbol(symbol)
    code, suf = s.split(".")
    return code, suf
