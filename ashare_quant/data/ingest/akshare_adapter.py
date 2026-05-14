"""AkShare 数据适配器（免费、首选）。

AkShare 接口随版本变动较多，本模块只用最稳定的子集：
- ``stock_info_a_code_name``       全市场股票
- ``stock_zh_a_hist``               日K（含前/后复权）
- ``index_stock_cons_csindex``      中证指数成分（HS300/ZZ500/ZZ800/ZZ1000）
- ``stock_individual_info_em``      个股基础信息（上市日期）
- ``stock_hsgt_north_net_flow_in_em`` 北向资金
- ``stock_lhb_detail_em``           龙虎榜
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_fixed

from ashare_quant.data.ingest.base import BaseAdapter, normalize_symbol, split_symbol
from ashare_quant.logging_setup import logger


def _date_str(d: Any) -> str:
    if isinstance(d, str):
        return d.replace("-", "")
    return pd.Timestamp(d).strftime("%Y%m%d")


_INDEX_MAP = {
    "hs300": "000300",
    "zz500": "000905",
    "zz800": "000906",
    "zz1000": "000852",
}


class AkShareAdapter(BaseAdapter):
    name = "akshare"

    def __init__(self) -> None:
        try:
            import akshare  # noqa: F401
        except ImportError as exc:
            raise ImportError("未安装 akshare：pip install akshare") from exc

    # ------------------------ 基础信息 ------------------------
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def fetch_stock_list(self) -> pd.DataFrame:
        import akshare as ak

        df = ak.stock_info_a_code_name()
        df = df.rename(columns={"code": "code_raw", "name": "name"})
        df["symbol"] = df["code_raw"].map(normalize_symbol)
        df["exchange"] = df["symbol"].str.split(".").str[1]
        df["is_st"] = df["name"].str.contains("ST", na=False)

        # 兜底：list_date 用 1990-01-01；实盘可逐只查 stock_individual_info_em，
        # 但全量太慢，先空着，后续按需补
        df["list_date"] = pd.NaT
        return df[["symbol", "name", "exchange", "is_st", "list_date"]]

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1), reraise=False)
    def fetch_stock_info(self, symbol: str) -> dict[str, Any]:
        """补全单只股票的上市日期等。"""
        import akshare as ak

        code, _ = split_symbol(symbol)
        try:
            df = ak.stock_individual_info_em(symbol=code)
            info = dict(zip(df["item"], df["value"]))
            return {
                "list_date": pd.to_datetime(info.get("上市时间"), errors="coerce"),
                "total_share": pd.to_numeric(info.get("总股本"), errors="coerce"),
                "market_cap": pd.to_numeric(info.get("总市值"), errors="coerce"),
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"fetch_stock_info {symbol} 失败：{exc}")
            return {}

    # ------------------------ 日 K ------------------------
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def fetch_daily(self, symbol: str, start: Any, end: Any) -> pd.DataFrame:
        import akshare as ak

        code, _ = split_symbol(symbol)
        # 不复权 + qfq + hfq 三份，合并出 adj_factor
        kw = dict(symbol=code, period="daily", start_date=_date_str(start),
                  end_date=_date_str(end))
        try:
            raw = ak.stock_zh_a_hist(adjust="", **kw)
            hfq = ak.stock_zh_a_hist(adjust="hfq", **kw)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"AkShare 日K拉取失败 {symbol}: {exc}")
            return pd.DataFrame()

        if raw is None or raw.empty:
            return pd.DataFrame()

        col_map = {
            "日期": "trade_date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume",
            "成交额": "amount", "涨跌幅": "pct_chg", "换手率": "turnover",
        }
        raw = raw.rename(columns=col_map)
        raw["trade_date"] = pd.to_datetime(raw["trade_date"]).dt.normalize()

        if hfq is not None and not hfq.empty:
            hfq = hfq.rename(columns={"日期": "trade_date", "收盘": "hfq_close"})
            hfq["trade_date"] = pd.to_datetime(hfq["trade_date"]).dt.normalize()
            hfq = hfq[["trade_date", "hfq_close"]]
            df = raw.merge(hfq, on="trade_date", how="left")
            # adj_factor = hfq_close / close
            df["adj_factor"] = df["hfq_close"] / df["close"]
        else:
            df = raw
            df["adj_factor"] = 1.0

        keep = ["trade_date", "open", "high", "low", "close", "volume",
                "amount", "pct_chg", "turnover", "adj_factor"]
        keep = [c for c in keep if c in df.columns]
        return df[keep].reset_index(drop=True)

    # ------------------------ 指数成分 ------------------------
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
    def fetch_index_members(self, index_code: str) -> pd.DataFrame:
        import akshare as ak

        code = _INDEX_MAP.get(index_code.lower(), index_code)
        try:
            df = ak.index_stock_cons_csindex(symbol=code)
        except Exception:
            # 兜底：东财
            df = ak.index_stock_cons(symbol=code)

        col_map = {
            "成分券代码": "code_raw", "成份券代码": "code_raw", "品种代码": "code_raw",
            "成分券名称": "name", "成份券名称": "name", "品种名称": "name",
        }
        df = df.rename(columns=col_map)
        if "code_raw" not in df.columns:
            # 兜底从其它可能字段抽
            for c in df.columns:
                if df[c].astype(str).str.match(r"^\d{6}$").mean() > 0.9:
                    df["code_raw"] = df[c]
                    break
        df["symbol"] = df["code_raw"].astype(str).map(normalize_symbol)
        return df[["symbol", "name"]].drop_duplicates("symbol").reset_index(drop=True)

    # ------------------------ 北向资金 ------------------------
    def fetch_north_flow(self, start: Any, end: Any) -> pd.DataFrame:
        import akshare as ak

        try:
            df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"北向资金拉取失败：{exc}")
            return pd.DataFrame()
        df = df.rename(columns={"date": "trade_date", "value": "north_net_inflow"})
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
        df["north_net_inflow"] = pd.to_numeric(df["north_net_inflow"], errors="coerce")
        if start is not None:
            df = df[df["trade_date"] >= pd.Timestamp(start)]
        if end is not None:
            df = df[df["trade_date"] <= pd.Timestamp(end)]
        return df.reset_index(drop=True)

    # ------------------------ 龙虎榜 ------------------------
    def fetch_dragon_tiger(self, start: Any, end: Any) -> pd.DataFrame:
        import akshare as ak

        try:
            df = ak.stock_lhb_detail_em(start_date=_date_str(start), end_date=_date_str(end))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"龙虎榜拉取失败：{exc}")
            return pd.DataFrame()
        col_map = {
            "代码": "code_raw", "名称": "name", "上榜日": "trade_date",
            "买方机构数": "buy_inst_count", "卖方机构数": "sell_inst_count",
            "净买额": "net_buy", "解读": "reason",
        }
        df = df.rename(columns=col_map)
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.normalize()
        if "code_raw" in df.columns:
            df["symbol"] = df["code_raw"].astype(str).map(normalize_symbol)
        return df

    # ------------------------ 财报 ------------------------
    def fetch_financials(self, symbol: str) -> pd.DataFrame:
        """简化版：从东财摘取主要财务指标。"""
        import akshare as ak

        code, _ = split_symbol(symbol)
        try:
            df = ak.stock_financial_abstract_ths(symbol=code)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"财报拉取失败 {symbol}: {exc}")
            return pd.DataFrame()
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns={"报告期": "report_date"})
        df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
        df["symbol"] = symbol
        return df
