"""A股交易日历。

数据源优先级：
1. AkShare ``tool_trade_date_hist_sina``（历史交易日列表）
2. 兜底：周一至周五（不含节假日，仅作为离线兜底）
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List

import pandas as pd

from ashare_quant.config import storage_root
from ashare_quant.logging_setup import logger


CALENDAR_FILE = "calendar/trade_days.parquet"


def _to_date(d) -> date:
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, pd.Timestamp):
        return d.date()
    return pd.Timestamp(d).date()


class TradingCalendar:
    """A 股交易日历。"""

    def __init__(self, trade_days: Iterable) -> None:
        days = pd.to_datetime(list(trade_days)).normalize()
        self._days: pd.DatetimeIndex = pd.DatetimeIndex(sorted(set(days)))

    # ------------------------ 工厂 ------------------------
    @classmethod
    def from_akshare(cls) -> "TradingCalendar":
        try:
            import akshare as ak

            df = ak.tool_trade_date_hist_sina()
            return cls(df["trade_date"].tolist())
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"AkShare 交易日历获取失败：{exc}，使用兜底日历")
            return cls._fallback()

    @classmethod
    def _fallback(cls) -> "TradingCalendar":
        """工作日兜底（不含法定节假日，仅离线兜底）。"""
        days = pd.bdate_range("2010-01-01", "2030-12-31")
        return cls(days.tolist())

    @classmethod
    def load_or_build(cls, force_refresh: bool = False) -> "TradingCalendar":
        """从本地缓存加载，否则从 AkShare 构建并缓存。"""
        cache = storage_root() / CALENDAR_FILE
        if cache.exists() and not force_refresh:
            df = pd.read_parquet(cache)
            return cls(df["trade_date"].tolist())
        cal = cls.from_akshare()
        cache.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"trade_date": cal._days}).to_parquet(cache, index=False)
        logger.info(f"交易日历已缓存到 {cache}（{len(cal._days)} 个交易日）")
        return cal

    # ------------------------ 查询 ------------------------
    @property
    def days(self) -> pd.DatetimeIndex:
        return self._days

    def is_trade_day(self, d) -> bool:
        return pd.Timestamp(_to_date(d)) in self._days

    def trade_days_between(self, start, end) -> pd.DatetimeIndex:
        s = pd.Timestamp(_to_date(start))
        e = pd.Timestamp(_to_date(end))
        return self._days[(self._days >= s) & (self._days <= e)]

    def prev_trade_day(self, d, n: int = 1) -> pd.Timestamp:
        ts = pd.Timestamp(_to_date(d))
        idx = self._days.searchsorted(ts, side="left")
        target = idx - n
        if target < 0:
            raise IndexError(f"前 {n} 个交易日越界")
        return self._days[target]

    def next_trade_day(self, d, n: int = 1) -> pd.Timestamp:
        ts = pd.Timestamp(_to_date(d))
        idx = self._days.searchsorted(ts, side="right")
        target = idx + n - 1
        if target >= len(self._days):
            raise IndexError(f"后 {n} 个交易日越界")
        return self._days[target]

    def offset(self, d, n: int) -> pd.Timestamp:
        """n 为正取后，n 为负取前，n=0 当日（必须为交易日）。"""
        if n == 0:
            ts = pd.Timestamp(_to_date(d))
            if ts not in self._days:
                raise ValueError(f"{d} 不是交易日")
            return ts
        return self.next_trade_day(d, n) if n > 0 else self.prev_trade_day(d, -n)

    def count(self, start, end) -> int:
        return len(self.trade_days_between(start, end))

    def latest(self, before=None) -> pd.Timestamp:
        ref = pd.Timestamp(date.today()) if before is None else pd.Timestamp(_to_date(before))
        mask = self._days <= ref
        if not mask.any():
            raise IndexError("没有早于参考日的交易日")
        return self._days[mask][-1]


@lru_cache(maxsize=1)
def get_calendar(force_refresh: bool = False) -> TradingCalendar:
    return TradingCalendar.load_or_build(force_refresh=force_refresh)
