"""数据仓库：Parquet 分区存储 + DuckDB 查询。

目录布局：
  data_warehouse/
    instruments/
      stocks.parquet                # 股票基础信息（含上市日、ST 标记）
      industry_sw.parquet           # 申万一级行业映射
      index_members/{index}.parquet # 指数成分（HS300 / ZZ500 ...）
    daily/
      <symbol>.parquet              # 日 K（不复权 + qfq + hfq 因子）
    minute/
      <symbol>/<yyyy>.parquet       # 分钟 K
    financial/
      income.parquet / balance.parquet / cashflow.parquet
    money_flow/
      north.parquet                 # 北向资金
      margin.parquet                # 融资融券
    events/
      dragon_tiger.parquet
      earnings_forecast.parquet
    calendar/
      trade_days.parquet
"""
from __future__ import annotations

import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import duckdb
import pandas as pd

from ashare_quant.config import storage_root
from ashare_quant.logging_setup import logger


class Storage:
    """轻量数据仓库封装。"""

    def __init__(self, root: Path | None = None) -> None:
        self.root: Path = Path(root) if root else storage_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self._duck_lock = threading.Lock()
        self._duck: duckdb.DuckDBPyConnection | None = None

    # ------------------------ DuckDB ------------------------
    @property
    def duck(self) -> duckdb.DuckDBPyConnection:
        if self._duck is None:
            with self._duck_lock:
                if self._duck is None:
                    self._duck = duckdb.connect(database=str(self.root / "aq.duckdb"))
                    self._duck.execute("PRAGMA threads=4")
        return self._duck

    # ------------------------ 路径 ------------------------
    def path(self, sub: str) -> Path:
        p = self.root / sub
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def daily_path(self, symbol: str) -> Path:
        return self.path(f"daily/{symbol}.parquet")

    def minute_path(self, symbol: str, year: int) -> Path:
        return self.path(f"minute/{symbol}/{year}.parquet")

    # ------------------------ 读写：日K ------------------------
    def write_daily(self, symbol: str, df: pd.DataFrame) -> None:
        """写入日 K（覆盖写）。

        Columns 期望：trade_date, open, high, low, close, volume, amount,
                      pct_chg, adj_factor, qfq_close, hfq_close（可选）
        """
        if df is None or df.empty:
            return
        df = self._normalize_daily(df.copy())
        p = self.daily_path(symbol)
        df.to_parquet(p, index=False)

    def read_daily(
        self,
        symbol: str,
        start: Any = None,
        end: Any = None,
        adjust: str = "none",
    ) -> pd.DataFrame:
        """读取单只股票日 K。adjust: none|qfq|hfq."""
        p = self.daily_path(symbol)
        if not p.exists():
            return pd.DataFrame()
        df = pd.read_parquet(p)
        if start is not None:
            df = df[df["trade_date"] >= pd.Timestamp(start)]
        if end is not None:
            df = df[df["trade_date"] <= pd.Timestamp(end)]
        return self._apply_adjust(df, adjust)

    def read_daily_panel(
        self,
        symbols: Iterable[str],
        fields: Iterable[str] = ("close",),
        start: Any = None,
        end: Any = None,
        adjust: str = "qfq",
    ) -> dict[str, pd.DataFrame]:
        """读取多只股票，返回 {field: wide_df(date×symbol)}。"""
        out: dict[str, list[pd.Series]] = {f: [] for f in fields}
        symbols = list(symbols)
        for sym in symbols:
            df = self.read_daily(sym, start=start, end=end, adjust=adjust)
            if df.empty:
                continue
            df = df.set_index("trade_date")
            for f in fields:
                if f in df.columns:
                    s = df[f].rename(sym)
                    out[f].append(s)
        result = {}
        for f, series_list in out.items():
            if not series_list:
                result[f] = pd.DataFrame()
            else:
                wide = pd.concat(series_list, axis=1).sort_index()
                result[f] = wide
        return result

    # ------------------------ 通用 ------------------------
    def write_table(self, name: str, df: pd.DataFrame) -> None:
        if df is None or df.empty:
            return
        p = self.path(f"{name}.parquet")
        df.to_parquet(p, index=False)

    def read_table(self, name: str) -> pd.DataFrame:
        p = self.path(f"{name}.parquet")
        if not p.exists():
            return pd.DataFrame()
        return pd.read_parquet(p)

    def list_symbols(self) -> list[str]:
        d = self.root / "daily"
        if not d.exists():
            return []
        return sorted([p.stem for p in d.glob("*.parquet")])

    # ------------------------ 内部 ------------------------
    @staticmethod
    def _normalize_daily(df: pd.DataFrame) -> pd.DataFrame:
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
        df = df.sort_values("trade_date").drop_duplicates("trade_date")
        # 数值类型
        for col in ["open", "high", "low", "close", "volume", "amount",
                    "pct_chg", "adj_factor"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.reset_index(drop=True)

    @staticmethod
    def _apply_adjust(df: pd.DataFrame, adjust: str) -> pd.DataFrame:
        """按 adj_factor 复权。

        - none: 不变
        - qfq: 前复权，最新一日为基准，历史价格 = 原价 * (factor / factor_last)
        - hfq: 后复权，第一日为基准，历史价格 = 原价 * factor
        """
        if df.empty or adjust == "none" or "adj_factor" not in df.columns:
            return df
        df = df.copy()
        af = df["adj_factor"].fillna(method="ffill").fillna(1.0)
        if adjust == "qfq":
            base = af.iloc[-1]
            ratio = af / base
        elif adjust == "hfq":
            ratio = af
        else:
            return df
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = df[col] * ratio
        return df

    # ------------------------ DuckDB 视图 ------------------------
    def register_daily_view(self, view_name: str = "daily") -> None:
        """把 daily/*.parquet 注册成 DuckDB 视图，方便 SQL 查询。"""
        pattern = str((self.root / "daily" / "*.parquet").as_posix())
        self.duck.execute(
            f"CREATE OR REPLACE VIEW {view_name} AS "
            f"SELECT regexp_extract(filename, '([^/]+)\\.parquet$', 1) AS symbol, * "
            f"FROM read_parquet('{pattern}', filename=true)"
        )
        logger.info(f"DuckDB 视图已注册：{view_name}")


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    return Storage()
