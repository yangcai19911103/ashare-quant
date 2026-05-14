"""基本面因子：价值 / 质量 / 成长。

为了在缺财报数据时仍能运行（mock / 测试），所有因子在数据缺失时返回空 DataFrame。
真实环境下从 ``data_warehouse/financial/*.parquet`` 读取。
"""
from __future__ import annotations

import pandas as pd

from ashare_quant.data.storage import get_storage
from ashare_quant.factors.base import Factor, register
from ashare_quant.logging_setup import logger


def _load_fundamentals(table: str) -> pd.DataFrame:
    """从仓库读取基础财务表（如 'fundamentals/pe', 'fundamentals/roe'）。

    约定列：trade_date, symbol, value
    """
    df = get_storage().read_table(table)
    if df.empty:
        return pd.DataFrame()
    if "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def _pivot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.pivot(index="trade_date", columns="symbol", values="value").sort_index()


# ============================================================================
# 价值
# ============================================================================
@register("pe_ttm_inv")
class PEReciprocal(Factor):
    """1/PE_TTM，越大越便宜。"""
    direction = +1
    category = "value"

    def compute(self, panel, **_):
        df = _pivot(_load_fundamentals("fundamentals/pe_ttm"))
        if df.empty:
            return pd.DataFrame()
        return 1.0 / df.replace([0, float("inf"), -float("inf")], None)


@register("pb_inv")
class PBReciprocal(Factor):
    """1/PB；越大越便宜。"""
    direction = +1
    category = "value"

    def compute(self, panel, **_):
        df = _pivot(_load_fundamentals("fundamentals/pb"))
        if df.empty:
            return pd.DataFrame()
        return 1.0 / df.replace([0, float("inf"), -float("inf")], None)


@register("ps_ttm_inv")
class PSReciprocal(Factor):
    direction = +1
    category = "value"

    def compute(self, panel, **_):
        df = _pivot(_load_fundamentals("fundamentals/ps_ttm"))
        if df.empty:
            return pd.DataFrame()
        return 1.0 / df.replace([0, float("inf"), -float("inf")], None)


@register("dividend_yield")
class DividendYield(Factor):
    direction = +1
    category = "value"

    def compute(self, panel, **_):
        df = _pivot(_load_fundamentals("fundamentals/dv_ratio"))
        return df


# ============================================================================
# 质量
# ============================================================================
@register("roe")
class ROE(Factor):
    direction = +1
    category = "quality"

    def compute(self, panel, **_):
        return _pivot(_load_fundamentals("fundamentals/roe"))


@register("roic")
class ROIC(Factor):
    direction = +1
    category = "quality"

    def compute(self, panel, **_):
        return _pivot(_load_fundamentals("fundamentals/roic"))


@register("gross_margin")
class GrossMargin(Factor):
    direction = +1
    category = "quality"

    def compute(self, panel, **_):
        return _pivot(_load_fundamentals("fundamentals/grossprofit_margin"))


@register("accruals")
class Accruals(Factor):
    """应计项目占比，越小越好（盈余质量越高）→ direction = -1."""
    direction = -1
    category = "quality"

    def compute(self, panel, **_):
        ni = _pivot(_load_fundamentals("fundamentals/n_income"))
        cfo = _pivot(_load_fundamentals("fundamentals/n_cashflow_act"))
        if ni.empty or cfo.empty:
            return pd.DataFrame()
        # 简化：(ni - cfo) / |ni|，越大越差
        return -(ni - cfo) / ni.abs().replace(0, None)


# ============================================================================
# 成长
# ============================================================================
@register("net_profit_yoy")
class NetProfitYoY(Factor):
    direction = +1
    category = "growth"

    def compute(self, panel, **_):
        return _pivot(_load_fundamentals("fundamentals/netprofit_yoy"))


@register("revenue_yoy")
class RevenueYoY(Factor):
    direction = +1
    category = "growth"

    def compute(self, panel, **_):
        return _pivot(_load_fundamentals("fundamentals/or_yoy"))


@register("peg")
class PEG(Factor):
    """PEG = PE / growth；越小越好。"""
    direction = -1
    category = "growth"

    def compute(self, panel, **_):
        pe = _pivot(_load_fundamentals("fundamentals/pe_ttm"))
        g = _pivot(_load_fundamentals("fundamentals/netprofit_yoy"))
        if pe.empty or g.empty:
            return pd.DataFrame()
        return pe / g.replace(0, None)
