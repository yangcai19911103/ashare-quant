"""因子中性化：行业 / 市值 / Beta 等。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def industry_neutralize(factor: pd.DataFrame, industry_map: pd.Series) -> pd.DataFrame:
    """对每个截面，按行业做去均值。

    industry_map: Series, index = symbol, value = industry_code
    """
    if factor.empty or industry_map.empty:
        return factor
    inds = industry_map.reindex(factor.columns)
    out = factor.copy()
    for ind, syms in inds.groupby(inds).groups.items():
        cols = [s for s in syms if s in out.columns]
        if not cols:
            continue
        sub = out[cols]
        mean = sub.mean(axis=1)
        out[cols] = sub.sub(mean, axis=0)
    return out


def size_neutralize(factor: pd.DataFrame, log_mcap: pd.DataFrame) -> pd.DataFrame:
    """对每个截面，做因子值对 log(市值) 的横截面回归取残差。

    log_mcap: DataFrame, index=date, columns=symbol
    """
    if factor.empty or log_mcap.empty:
        return factor
    common = factor.columns.intersection(log_mcap.columns)
    factor = factor[common]
    log_mcap = log_mcap.reindex(index=factor.index, columns=common)

    out = pd.DataFrame(index=factor.index, columns=common, dtype=float)
    for t in factor.index:
        y = factor.loc[t]
        x = log_mcap.loc[t]
        mask = y.notna() & x.notna()
        if mask.sum() < 10:
            out.loc[t] = y
            continue
        yy = y[mask].values
        xx = x[mask].values
        # 一元 OLS
        xm = xx.mean()
        ym = yy.mean()
        beta = ((xx - xm) * (yy - ym)).sum() / max(((xx - xm) ** 2).sum(), 1e-12)
        alpha = ym - beta * xm
        resid = yy - (alpha + beta * xx)
        out.loc[t, mask[mask].index] = resid
    return out


def winsorize_zscore(factor: pd.DataFrame, lower: float = 0.025, upper: float = 0.975
                     ) -> pd.DataFrame:
    """先按截面缩尾，再 z-score。"""
    if factor.empty:
        return factor
    ql = factor.quantile(lower, axis=1)
    qh = factor.quantile(upper, axis=1)
    w = factor.clip(lower=ql, upper=qh, axis=0)
    mu = w.mean(axis=1)
    sd = w.std(axis=1).replace(0, np.nan)
    return w.sub(mu, axis=0).div(sd, axis=0)
