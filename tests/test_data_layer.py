"""M1 数据层冒烟测试。"""
from __future__ import annotations

import pandas as pd
import pytest

from ashare_quant.data.calendar import TradingCalendar
from ashare_quant.data.corporate_actions import (
    apply_adjustment,
    is_limit_down,
    is_limit_up,
    limit_up_threshold,
)
from ashare_quant.data.ingest.base import normalize_symbol, split_symbol
from ashare_quant.data.ingest.mock_adapter import MockAdapter
from ashare_quant.data.storage import Storage


# ------------------------ symbol 规范化 ------------------------
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("600519", "600519.SH"),
        ("000001", "000001.SZ"),
        ("300750", "300750.SZ"),
        ("688981", "688981.SH"),
        ("sh600519", "600519.SH"),
        ("600519.sh", "600519.SH"),
        ("830799", "830799.BJ"),
    ],
)
def test_normalize_symbol(raw, expected):
    assert normalize_symbol(raw) == expected


def test_split_symbol():
    code, suf = split_symbol("600519.SH")
    assert code == "600519" and suf == "SH"


# ------------------------ 涨跌停阈值 ------------------------
def test_limit_thresholds():
    assert limit_up_threshold("600519", "贵州茅台") == 0.10
    assert limit_up_threshold("300750", "宁德时代") == 0.20
    assert limit_up_threshold("688981", "中芯国际") == 0.20
    assert limit_up_threshold("600519", "*ST 测试") == 0.05
    assert limit_up_threshold("830799", "新股") == 0.30  # 北交所


def test_is_limit_up_down():
    assert is_limit_up(100.0, 110.0, 0.10)
    assert not is_limit_up(100.0, 109.9, 0.10)
    assert is_limit_down(100.0, 90.0, 0.10)


# ------------------------ 复权 ------------------------
def test_apply_adjustment_qfq():
    df = pd.DataFrame({
        "trade_date": pd.date_range("2024-01-01", periods=3),
        "open": [10.0, 12.0, 13.0],
        "close": [10.5, 12.5, 13.5],
        "high": [11.0, 13.0, 14.0],
        "low": [9.5, 11.5, 12.5],
        "adj_factor": [1.0, 1.0, 2.0],
    })
    qfq = apply_adjustment(df, mode="qfq")
    # 最新一日是基准（factor=2），故倒数第一日 close 不变
    assert qfq["close"].iloc[-1] == pytest.approx(13.5)
    # 前两日打折一半
    assert qfq["close"].iloc[0] == pytest.approx(5.25)


def test_apply_adjustment_hfq():
    df = pd.DataFrame({
        "trade_date": pd.date_range("2024-01-01", periods=3),
        "open": [10.0, 12.0, 13.0],
        "high": [11.0, 13.0, 14.0],
        "low": [9.5, 11.5, 12.5],
        "close": [10.5, 12.5, 13.5],
        "adj_factor": [1.0, 1.5, 2.0],
    })
    hfq = apply_adjustment(df, mode="hfq")
    assert hfq["close"].iloc[0] == pytest.approx(10.5)
    assert hfq["close"].iloc[1] == pytest.approx(18.75)
    assert hfq["close"].iloc[2] == pytest.approx(27.0)


# ------------------------ 交易日历 ------------------------
def test_trading_calendar_fallback():
    cal = TradingCalendar._fallback()
    days = cal.trade_days_between("2024-01-02", "2024-01-12")
    assert len(days) > 0
    # 周末不应在内
    assert all(d.weekday() < 5 for d in days)
    # offset
    d0 = days[0]
    assert cal.next_trade_day(d0, 1) == days[1]
    assert cal.prev_trade_day(days[1], 1) == d0


# ------------------------ Mock adapter + Storage 全链路 ------------------------
def test_mock_adapter_e2e(_isolate_storage, mock_adapter):
    storage = Storage(root=_isolate_storage)

    stocks = mock_adapter.fetch_stock_list()
    assert not stocks.empty
    storage.write_table("instruments/stocks", stocks)
    back = storage.read_table("instruments/stocks")
    pd.testing.assert_frame_equal(stocks.reset_index(drop=True),
                                  back.reset_index(drop=True))

    # 单只日 K
    sym = stocks["symbol"].iloc[0]
    df = mock_adapter.fetch_daily(sym, "2024-01-01", "2024-03-31")
    assert {"trade_date", "open", "high", "low", "close", "adj_factor"} <= set(df.columns)
    storage.write_daily(sym, df)
    back = storage.read_daily(sym)
    assert len(back) == len(df)

    # 多只 panel
    for s in stocks["symbol"].head(3):
        storage.write_daily(s, mock_adapter.fetch_daily(s, "2024-01-01", "2024-03-31"))
    panel = storage.read_daily_panel(stocks["symbol"].head(3), fields=["close"])
    assert panel["close"].shape[1] == 3


def test_storage_list_symbols(_isolate_storage, mock_adapter):
    storage = Storage(root=_isolate_storage)
    stocks = mock_adapter.fetch_stock_list()
    for s in stocks["symbol"].head(2):
        storage.write_daily(s, mock_adapter.fetch_daily(s, "2024-01-01", "2024-01-31"))
    syms = storage.list_symbols()
    assert len(syms) >= 2
