"""数据采集编排：全量初始化 / 增量更新 / 指数成分 / 财报。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from typing import Any, Iterable

import pandas as pd
from tqdm import tqdm

from ashare_quant.config import get
from ashare_quant.data.calendar import get_calendar
from ashare_quant.data.ingest.base import BaseAdapter
from ashare_quant.data.storage import get_storage
from ashare_quant.logging_setup import logger


def _build_adapter(name: str) -> BaseAdapter:
    if name == "akshare":
        from ashare_quant.data.ingest.akshare_adapter import AkShareAdapter
        return AkShareAdapter()
    if name == "tushare":
        from ashare_quant.data.ingest.tushare_adapter import TushareAdapter
        return TushareAdapter()
    raise ValueError(f"未知数据源：{name}")


def _select_primary() -> BaseAdapter:
    """按 settings.yaml 配置选第一个能用的数据源。"""
    sources = get("data.sources", ["akshare"])
    last_err = None
    for name in sources:
        try:
            return _build_adapter(name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"数据源 {name} 不可用：{exc}")
            last_err = exc
    raise RuntimeError(f"所有数据源都不可用，最后错误：{last_err}")


# ------------------------ 步骤 ------------------------
def init_stock_list(adapter: BaseAdapter | None = None) -> pd.DataFrame:
    """全量股票清单 → instruments/stocks.parquet."""
    adapter = adapter or _select_primary()
    logger.info(f"[stocks] 拉取全市场股票（{adapter.name}）...")
    df = adapter.fetch_stock_list()
    get_storage().write_table("instruments/stocks", df)
    logger.info(f"[stocks] 入库 {len(df)} 只")
    return df


def init_index_members(adapter: BaseAdapter | None = None,
                       index_codes: Iterable[str] = ("hs300", "zz500", "zz800", "zz1000")
                       ) -> None:
    """指数成分股 → instruments/index_members/{code}.parquet."""
    adapter = adapter or _select_primary()
    for code in index_codes:
        try:
            df = adapter.fetch_index_members(code)
            if df.empty:
                logger.warning(f"[index] {code} 成分为空")
                continue
            get_storage().write_table(f"instruments/index_members/{code}", df)
            logger.info(f"[index] {code} 入库 {len(df)} 只")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[index] {code} 失败：{exc}")


def _fetch_one_daily(adapter: BaseAdapter, symbol: str,
                     start: Any, end: Any) -> tuple[str, pd.DataFrame]:
    try:
        df = adapter.fetch_daily(symbol, start, end)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[daily] {symbol} 失败：{exc}")
        df = pd.DataFrame()
    return symbol, df


def ingest_daily(
    symbols: Iterable[str] | None = None,
    start: Any | None = None,
    end: Any | None = None,
    incremental: bool = True,
    max_workers: int = 6,
    adapter: BaseAdapter | None = None,
) -> None:
    """批量拉取日 K（多线程）。

    - incremental=True：从本地已有最新日期 +1 开始
    - incremental=False：按 start/end 全量覆盖写
    """
    adapter = adapter or _select_primary()
    storage = get_storage()
    if symbols is None:
        stocks = storage.read_table("instruments/stocks")
        if stocks.empty:
            init_stock_list(adapter)
            stocks = storage.read_table("instruments/stocks")
        symbols = stocks["symbol"].tolist()

    symbols = list(symbols)
    if end is None:
        end = pd.Timestamp(date.today())
    if start is None:
        start = pd.Timestamp(get("data.history_start", "2018-01-01"))

    def _resolve_range(sym: str):
        if not incremental:
            return start, end
        local = storage.read_daily(sym)
        if local.empty:
            return start, end
        last = local["trade_date"].max()
        next_start = (last + pd.Timedelta(days=1)).normalize()
        if next_start > pd.Timestamp(end):
            return None
        return max(next_start, pd.Timestamp(start)), end

    logger.info(f"[daily] 增量拉取 {len(symbols)} 只 ({start} ~ {end})")
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {}
        for sym in symbols:
            rng = _resolve_range(sym)
            if rng is None:
                continue
            s, e = rng
            futs[pool.submit(_fetch_one_daily, adapter, sym, s, e)] = sym

        with tqdm(total=len(futs), desc="daily", ncols=80) as bar:
            for fut in as_completed(futs):
                sym, df = fut.result()
                if not df.empty:
                    if incremental:
                        old = storage.read_daily(sym)
                        if not old.empty:
                            df = pd.concat([old, df], ignore_index=True)
                            df = df.drop_duplicates("trade_date").sort_values("trade_date")
                    storage.write_daily(sym, df)
                bar.update(1)


def ingest_north_flow(adapter: BaseAdapter | None = None,
                      start: Any | None = None, end: Any | None = None) -> None:
    adapter = adapter or _select_primary()
    if start is None:
        start = get("data.history_start", "2018-01-01")
    if end is None:
        end = date.today()
    df = adapter.fetch_north_flow(start, end)
    if not df.empty:
        get_storage().write_table("money_flow/north", df)
        logger.info(f"[north] 入库 {len(df)} 行")


def ingest_dragon_tiger(adapter: BaseAdapter | None = None,
                        start: Any | None = None, end: Any | None = None) -> None:
    adapter = adapter or _select_primary()
    if start is None:
        start = (pd.Timestamp.today() - pd.Timedelta(days=365)).date()
    if end is None:
        end = date.today()
    df = adapter.fetch_dragon_tiger(start, end)
    if not df.empty:
        get_storage().write_table("events/dragon_tiger", df)
        logger.info(f"[lhb] 入库 {len(df)} 行")


# ------------------------ 一键流水线 ------------------------
def init_all(start: Any | None = None, end: Any | None = None,
             include_index: bool = True, include_north: bool = True) -> None:
    """首次全量初始化。"""
    adapter = _select_primary()
    init_stock_list(adapter)
    if include_index:
        init_index_members(adapter)
    ingest_daily(start=start, end=end, incremental=False, adapter=adapter)
    if include_north:
        try:
            ingest_north_flow(adapter, start=start, end=end)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"北向资金初始化失败：{exc}")


def update_daily() -> None:
    """每日增量任务（盘后调度调用）。"""
    cal = get_calendar()
    today = pd.Timestamp(date.today())
    if not cal.is_trade_day(today):
        logger.info("今日非交易日，跳过更新")
        return
    ingest_daily(incremental=True)
    try:
        ingest_north_flow(start=(today - pd.Timedelta(days=7)).date(), end=today.date())
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"北向资金增量失败：{exc}")
