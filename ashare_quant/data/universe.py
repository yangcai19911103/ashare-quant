"""股票池（universe）构建。"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable

import pandas as pd

from ashare_quant.config import get
from ashare_quant.data.calendar import get_calendar
from ashare_quant.data.storage import get_storage
from ashare_quant.logging_setup import logger


def _stocks_info() -> pd.DataFrame:
    df = get_storage().read_table("instruments/stocks")
    if df.empty:
        logger.warning("instruments/stocks 表为空，请先运行数据初始化")
    return df


def _index_members(index_code: str) -> list[str]:
    df = get_storage().read_table(f"instruments/index_members/{index_code}")
    if df.empty:
        return []
    return df["symbol"].astype(str).tolist()


def all_a_share_symbols() -> list[str]:
    df = _stocks_info()
    return df["symbol"].astype(str).tolist() if not df.empty else []


def build_universe(name: str | None = None, date_ref: Any = None) -> list[str]:
    """根据 settings.yaml 的 universe 段，构建当前股票池。"""
    name = name or get("universe.default", "hs300")
    cal = get_calendar()
    if date_ref is None:
        date_ref = cal.latest()
    date_ref = pd.Timestamp(date_ref)

    # 1. 候选集合
    if name == "all":
        candidates = all_a_share_symbols()
    elif name.startswith("sw_industry:"):
        code = name.split(":", 1)[1]
        df = _stocks_info()
        candidates = df.loc[df.get("sw_l1") == code, "symbol"].astype(str).tolist()
    elif name in {"hs300", "zz500", "zz800", "zz1000"}:
        candidates = _index_members(name)
        if not candidates:
            logger.warning(f"指数 {name} 成分缺失，回退到全市场")
            candidates = all_a_share_symbols()
    else:
        candidates = all_a_share_symbols()

    # 2. 过滤
    filters = get("universe.filters", {}) or {}
    info = _stocks_info()
    if info.empty:
        return candidates

    info = info.set_index("symbol")
    keep = []
    drop_st = filters.get("drop_st", True)
    drop_new_days = int(filters.get("drop_new_days", 60))
    cutoff_listing = (date_ref - pd.Timedelta(days=drop_new_days)).normalize()

    for sym in candidates:
        if sym not in info.index:
            continue
        row = info.loc[sym]
        if drop_st and bool(row.get("is_st", False)):
            continue
        list_date = row.get("list_date")
        if pd.notna(list_date) and pd.Timestamp(list_date) > cutoff_listing:
            continue
        keep.append(sym)

    logger.info(f"universe={name} 候选 {len(candidates)} → 过滤后 {len(keep)}")
    return keep
