"""因子评估：IC / Rank-IC / IR / 分层回测。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class ICReport:
    ic_series: pd.Series
    mean_ic: float
    ic_ir: float
    pos_ratio: float
    rank_ic_series: pd.Series
    mean_rank_ic: float

    def to_dict(self) -> dict[str, float]:
        return {
            "mean_ic": self.mean_ic,
            "ic_ir": self.ic_ir,
            "pos_ratio": self.pos_ratio,
            "mean_rank_ic": self.mean_rank_ic,
        }


def compute_ic(factor: pd.DataFrame, forward_returns: pd.DataFrame,
               lag: int = 1) -> ICReport:
    """IC / Rank-IC 序列与汇总。

    forward_returns: 未来 N 日收益（已对齐 factor 的日期/股票）。
    lag: factor.loc[t] 与 forward_returns.loc[t+lag] 对齐（默认 t+1 即明日收益）。
    """
    if factor.empty or forward_returns.empty:
        empty = pd.Series(dtype=float)
        return ICReport(empty, np.nan, np.nan, np.nan, empty, np.nan)

    f = factor.shift(lag)
    common_dates = f.index.intersection(forward_returns.index)
    common_cols = f.columns.intersection(forward_returns.columns)
    f = f.loc[common_dates, common_cols]
    r = forward_returns.loc[common_dates, common_cols]

    ic_list, rank_ic_list = [], []
    for t in common_dates:
        x = f.loc[t]
        y = r.loc[t]
        mask = x.notna() & y.notna()
        if mask.sum() < 10:
            continue
        ic_list.append((t, x[mask].corr(y[mask])))
        rank_ic_list.append((t, x[mask].rank().corr(y[mask].rank())))

    ic_s = pd.Series(dict(ic_list))
    rk_s = pd.Series(dict(rank_ic_list))
    mean_ic = ic_s.mean()
    ic_ir = mean_ic / max(ic_s.std(), 1e-12) if len(ic_s) > 1 else np.nan
    pos = (ic_s > 0).mean() if len(ic_s) > 0 else np.nan
    return ICReport(ic_s, mean_ic, ic_ir, pos, rk_s, rk_s.mean())


def layered_backtest(
    factor: pd.DataFrame,
    forward_returns: pd.DataFrame,
    n_groups: int = 10,
    lag: int = 1,
) -> pd.DataFrame:
    """分层回测：把每个截面按因子值排序分 N 层，计算每层未来收益。

    返回 DataFrame：index=date, columns=group_0..group_{N-1}, 长短组合.
    """
    if factor.empty or forward_returns.empty:
        return pd.DataFrame()

    f = factor.shift(lag)
    common_dates = f.index.intersection(forward_returns.index)
    common_cols = f.columns.intersection(forward_returns.columns)
    f = f.loc[common_dates, common_cols]
    r = forward_returns.loc[common_dates, common_cols]

    rows = []
    for t in common_dates:
        x = f.loc[t]
        y = r.loc[t]
        mask = x.notna() & y.notna()
        if mask.sum() < n_groups * 3:
            continue
        x = x[mask]
        y = y[mask]
        try:
            groups = pd.qcut(x, q=n_groups, labels=False, duplicates="drop")
        except ValueError:
            continue
        row = {f"group_{i}": float(y[groups == i].mean()) for i in range(n_groups)}
        rows.append((t, row))

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame({t: r for t, r in rows}).T.sort_index()
    out["long_short"] = out[f"group_{n_groups - 1}"] - out["group_0"]
    return out


def long_short_performance(layered: pd.DataFrame) -> dict[str, float]:
    """计算多空组合年化收益、夏普、最大回撤等。"""
    if layered.empty or "long_short" not in layered.columns:
        return {}
    rets = layered["long_short"].dropna()
    if len(rets) < 10:
        return {}
    cum = (1 + rets).cumprod()
    ann_ret = cum.iloc[-1] ** (252 / len(rets)) - 1
    ann_vol = rets.std() * np.sqrt(252)
    sharpe = ann_ret / max(ann_vol, 1e-12)
    dd = cum / cum.cummax() - 1
    return {
        "ann_return": float(ann_ret),
        "ann_vol": float(ann_vol),
        "sharpe": float(sharpe),
        "max_drawdown": float(dd.min()),
        "win_rate": float((rets > 0).mean()),
    }
