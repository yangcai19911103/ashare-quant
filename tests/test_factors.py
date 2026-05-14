"""M2 因子库测试。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# 触发注册
import ashare_quant.factors.technical  # noqa: F401
from ashare_quant.factors import get_registry
from ashare_quant.factors.base import Factor
from ashare_quant.factors.evaluation import compute_ic, layered_backtest, long_short_performance
from ashare_quant.factors.neutralize import industry_neutralize, winsorize_zscore


def _build_panel(n_days=120, n_stocks=20, seed=42):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-01", periods=n_days)
    symbols = [f"{i:06d}.SH" for i in range(n_stocks)]
    rets = rng.normal(0.0005, 0.02, size=(n_days, n_stocks))
    close = pd.DataFrame(100 * np.cumprod(1 + rets, axis=0), index=dates, columns=symbols)
    high = close * 1.01
    low = close * 0.99
    op = close.shift(1).fillna(close)
    vol = pd.DataFrame(rng.integers(1e6, 5e7, size=(n_days, n_stocks)),
                       index=dates, columns=symbols, dtype=float)
    amt = vol * close
    return {"close": close, "open": op, "high": high, "low": low,
            "volume": vol, "amount": amt}


def test_factor_registry_has_built_ins():
    reg = get_registry()
    names = reg.names()
    assert "mom_1m" in names
    assert "rev_1m" in names
    assert "low_vol" in names
    assert "turnover_20d" in names


@pytest.mark.parametrize("name", [
    "mom_1m", "mom_3m", "mom_6m", "mom_12m",
    "rev_1w", "rev_1m",
    "low_vol", "turnover_20d",
    "ma_cross", "rsi_14", "bbands_pos",
    "dist_52w_high",
])
def test_factor_compute_shape(name):
    panel = _build_panel(n_days=300)
    factor = get_registry().get(name)
    out = factor.compute(panel)
    assert isinstance(out, pd.DataFrame)
    assert out.shape[1] == panel["close"].shape[1]


def test_winsorize_zscore():
    df = pd.DataFrame(np.random.randn(60, 30))
    out = winsorize_zscore(df)
    assert out.shape == df.shape
    # 经过 z-score 后，每行均值近似 0
    assert abs(out.mean(axis=1).mean()) < 0.1


def test_industry_neutralize():
    df = pd.DataFrame({
        "A": [1.0, 2.0],
        "B": [3.0, 4.0],
        "C": [5.0, 6.0],
        "D": [7.0, 8.0],
    })
    ind = pd.Series({"A": "I1", "B": "I1", "C": "I2", "D": "I2"})
    out = industry_neutralize(df, ind)
    # 每个行业每行去均值
    assert out.loc[0, "A"] == pytest.approx(-1.0)
    assert out.loc[0, "B"] == pytest.approx(1.0)
    assert out.loc[0, "C"] == pytest.approx(-1.0)


def test_compute_ic_basic():
    panel = _build_panel(n_days=120)
    close = panel["close"]
    # 用未来 5 日收益对 1 月动量算 IC
    fwd = close.pct_change(5).shift(-5)
    mom = get_registry().get("mom_1m").compute(panel)
    rep = compute_ic(mom, fwd, lag=1)
    assert not np.isnan(rep.mean_ic)
    assert len(rep.ic_series) > 30


def test_layered_backtest():
    panel = _build_panel(n_days=200)
    close = panel["close"]
    fwd = close.pct_change(5).shift(-5)
    factor = get_registry().get("mom_3m").compute(panel)
    layered = layered_backtest(factor, fwd, n_groups=5)
    assert not layered.empty
    assert "long_short" in layered.columns
    perf = long_short_performance(layered)
    assert "sharpe" in perf
