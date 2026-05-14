"""Tushare Pro 适配器（基本面 / 北向 / 财报，需要 token）。"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_fixed

from ashare_quant.config import get
from ashare_quant.data.ingest.base import BaseAdapter, normalize_symbol
from ashare_quant.logging_setup import logger


def _ts_token() -> str:
    return os.environ.get("TUSHARE_TOKEN", "") or get("data.tushare_token", "") or ""


def _ts_code(symbol: str) -> str:
    """'600519.SH' (本项目格式) 与 tushare 的 '600519.SH' 一致。"""
    return normalize_symbol(symbol)


class TushareAdapter(BaseAdapter):
    name = "tushare"

    def __init__(self) -> None:
        try:
            import tushare as ts
        except ImportError as exc:
            raise ImportError("未安装 tushare：pip install tushare") from exc
        token = _ts_token()
        if not token:
            raise RuntimeError("Tushare token 未设置：环境变量 TUSHARE_TOKEN 或 settings.yaml")
        ts.set_token(token)
        self.api = ts.pro_api()

    # ------------------------ 基础信息 ------------------------
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def fetch_stock_list(self) -> pd.DataFrame:
        df = self.api.stock_basic(
            exchange="", list_status="L",
            fields="ts_code,symbol,name,area,industry,list_date,market,is_hs",
        )
        df = df.rename(columns={"ts_code": "symbol"})
        df["exchange"] = df["symbol"].str.split(".").str[1]
        df["is_st"] = df["name"].str.contains("ST", na=False)
        df["list_date"] = pd.to_datetime(df["list_date"], errors="coerce")
        return df[["symbol", "name", "exchange", "is_st", "list_date", "industry"]]

    # ------------------------ 日 K ------------------------
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def fetch_daily(self, symbol: str, start: Any, end: Any) -> pd.DataFrame:
        s = pd.Timestamp(start).strftime("%Y%m%d")
        e = pd.Timestamp(end).strftime("%Y%m%d")
        ts_code = _ts_code(symbol)
        daily = self.api.daily(ts_code=ts_code, start_date=s, end_date=e)
        if daily is None or daily.empty:
            return pd.DataFrame()
        adj = self.api.adj_factor(ts_code=ts_code, start_date=s, end_date=e)
        if adj is not None and not adj.empty:
            daily = daily.merge(adj[["trade_date", "adj_factor"]], on="trade_date", how="left")
        else:
            daily["adj_factor"] = 1.0

        daily = daily.rename(columns={"vol": "volume", "pct_chg": "pct_chg"})
        daily["trade_date"] = pd.to_datetime(daily["trade_date"]).dt.normalize()
        daily = daily.sort_values("trade_date").reset_index(drop=True)
        keep = ["trade_date", "open", "high", "low", "close", "volume",
                "amount", "pct_chg", "adj_factor"]
        return daily[[c for c in keep if c in daily.columns]]

    # ------------------------ 指数成分 ------------------------
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def fetch_index_members(self, index_code: str) -> pd.DataFrame:
        ts_index_map = {
            "hs300": "399300.SZ",
            "zz500": "000905.SH",
            "zz800": "000906.SH",
            "zz1000": "000852.SH",
        }
        idx = ts_index_map.get(index_code.lower(), index_code)
        df = self.api.index_weight(index_code=idx, start_date="20240101", end_date="20991231")
        if df is None or df.empty:
            return pd.DataFrame()
        latest = df["trade_date"].max()
        df = df[df["trade_date"] == latest].copy()
        df = df.rename(columns={"con_code": "symbol", "weight": "weight"})
        df["symbol"] = df["symbol"].map(normalize_symbol)
        return df[["symbol", "weight"]].reset_index(drop=True)

    # ------------------------ 北向 ------------------------
    def fetch_north_flow(self, start: Any, end: Any) -> pd.DataFrame:
        s = pd.Timestamp(start).strftime("%Y%m%d")
        e = pd.Timestamp(end).strftime("%Y%m%d")
        try:
            df = self.api.moneyflow_hsgt(start_date=s, end_date=e)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Tushare 北向资金拉取失败：{exc}")
            return pd.DataFrame()
        if df is None or df.empty:
            return pd.DataFrame()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
        df["north_net_inflow"] = df.get("north_money", 0)
        return df.sort_values("trade_date").reset_index(drop=True)

    # ------------------------ 财报 ------------------------
    def fetch_financials(self, symbol: str) -> pd.DataFrame:
        """简化版：拿 ROE / 净利润同比等关键指标。"""
        ts_code = _ts_code(symbol)
        try:
            df = self.api.fina_indicator(ts_code=ts_code)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Tushare 财报拉取失败 {symbol}: {exc}")
            return pd.DataFrame()
        if df is None or df.empty:
            return pd.DataFrame()
        df["symbol"] = symbol
        df["report_date"] = pd.to_datetime(df["end_date"], errors="coerce")
        return df
