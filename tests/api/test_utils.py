"""API utils 工具函数单元测试。"""
from __future__ import annotations

import math
import re

import pytest

from ashare_quant.api.utils import (gen_dates, gen_drawdown, gen_price_series,
                                    metrics_from_nav, monthly_returns,
                                    sample_universe)


class TestGenDates:
    def test_count(self):
        out = gen_dates(10)
        assert len(out) == 10

    def test_iso_format(self):
        out = gen_dates(5)
        for d in out:
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", d)

    def test_chronological(self):
        out = gen_dates(20)
        assert out == sorted(out)

    def test_weekday_only(self):
        from datetime import date
        out = gen_dates(30, weekday_only=True)
        for s in out:
            y, m, d = [int(x) for x in s.split("-")]
            assert date(y, m, d).weekday() < 5

    def test_calendar_day(self):
        out = gen_dates(7, weekday_only=False)
        assert len(out) == 7


class TestGenPriceSeries:
    def test_length(self):
        s = gen_price_series(100)
        assert len(s) == 100

    def test_positive(self):
        s = gen_price_series(60, s0=1.0)
        assert all(v > 0 for v in s)

    def test_deterministic_seed(self):
        a = gen_price_series(50, seed=42)
        b = gen_price_series(50, seed=42)
        assert a == b

    def test_different_seed_differs(self):
        a = gen_price_series(50, seed=1)
        b = gen_price_series(50, seed=2)
        assert a != b


class TestGenDrawdown:
    def test_first_is_zero(self):
        dd = gen_drawdown([1.0, 1.1, 1.05])
        assert dd[0] == 0.0

    def test_monotone_increasing_no_dd(self):
        dd = gen_drawdown([1.0, 1.1, 1.2, 1.3])
        assert all(d == 0.0 for d in dd)

    def test_drop(self):
        dd = gen_drawdown([1.0, 1.2, 0.96])
        # peak=1.2, 当前 0.96 → -0.2
        assert dd[-1] == pytest.approx(-0.2, rel=1e-6)


class TestMetricsFromNav:
    def test_empty(self):
        m = metrics_from_nav([])
        assert m["total_return"] == 0
        assert m["sharpe"] == 0

    def test_single(self):
        m = metrics_from_nav([1.0])
        assert m["total_return"] == 0

    def test_positive_series(self):
        nav = [1.0 + 0.001 * i for i in range(252)]
        m = metrics_from_nav(nav)
        assert m["total_return"] > 0
        assert m["annual_return"] > 0
        assert m["win_rate"] >= 0.99

    def test_keys_present(self):
        m = metrics_from_nav(gen_price_series(252))
        for k in ["total_return", "annual_return", "sharpe", "max_drawdown",
                  "calmar", "win_rate"]:
            assert k in m


class TestMonthlyReturns:
    def test_empty(self):
        assert monthly_returns([], []) == []

    def test_basic(self):
        dates = ["2024-01-02", "2024-01-15", "2024-01-31", "2024-02-01", "2024-02-28"]
        nav = [1.0, 1.05, 1.10, 1.10, 1.21]
        r = monthly_returns(dates, nav)
        assert len(r) == 2
        # Jan: 1.0 -> 1.10 = +10%
        jan = next(x for x in r if x["month"] == 1)
        assert jan["ret"] == pytest.approx(0.10, rel=1e-6)


class TestSampleUniverse:
    def test_count(self):
        u = sample_universe(5)
        assert len(u) == 5

    def test_fields(self):
        u = sample_universe(3)
        for item in u:
            assert "symbol" in item and "name" in item
            assert "industry" in item
            assert item["in_pool"] is True
