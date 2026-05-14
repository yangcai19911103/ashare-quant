"""Brinson / Barra 风格的归因分析（简化版）。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def brinson_attribution(
    portfolio_weights: pd.DataFrame,
    portfolio_returns: pd.DataFrame,
    benchmark_weights: pd.DataFrame,
    benchmark_returns: pd.DataFrame,
    industry_map: pd.Series,
) -> pd.DataFrame:
    """Brinson-Fachler 归因。

    返回：DataFrame index=industry, columns=[allocation, selection, interaction, total]
    所有输入按交易日对齐；这里实现单期的版本（一行）。
    """
    p_w = portfolio_weights.copy()
    p_r = portfolio_returns.copy()
    b_w = benchmark_weights.copy()
    b_r = benchmark_returns.copy()

    # 加上 industry 列
    for df, w in [(p_w, "p_w"), (p_r, "p_r"), (b_w, "b_w"), (b_r, "b_r")]:
        df["industry"] = df.index.map(industry_map)
    grp_pw = p_w.groupby("industry").sum()["weight"]
    grp_bw = b_w.groupby("industry").sum()["weight"]
    grp_pr = (p_w["weight"] * p_r["ret"]).groupby(p_r["industry"]).sum() / grp_pw.replace(0, np.nan)
    grp_br = (b_w["weight"] * b_r["ret"]).groupby(b_r["industry"]).sum() / grp_bw.replace(0, np.nan)

    inds = sorted(set(grp_pw.index).union(grp_bw.index))
    rows = []
    bench_total = (b_w["weight"] * b_r["ret"]).sum()
    for ind in inds:
        wp = grp_pw.get(ind, 0)
        wb = grp_bw.get(ind, 0)
        rp = grp_pr.get(ind, 0)
        rb = grp_br.get(ind, 0)
        alloc = (wp - wb) * (rb - bench_total)
        sel = wb * (rp - rb)
        inter = (wp - wb) * (rp - rb)
        rows.append({"industry": ind, "allocation": alloc, "selection": sel,
                     "interaction": inter, "total": alloc + sel + inter})
    return pd.DataFrame(rows).set_index("industry")


def barra_style_attribution(
    returns: pd.Series,
    factor_exposures: pd.DataFrame,
    factor_returns: pd.DataFrame,
) -> pd.DataFrame:
    """简化的风格归因：portfolio_returns = sum(exposure_t * factor_return_t) + alpha

    factor_exposures: index=date, columns=factor; 当期暴露
    factor_returns:   index=date, columns=factor; 因子收益
    """
    common = returns.index.intersection(factor_exposures.index).intersection(factor_returns.index)
    if len(common) == 0:
        return pd.DataFrame()
    r = returns.loc[common]
    e = factor_exposures.loc[common]
    f = factor_returns.loc[common]
    contrib = e * f
    alpha = r - contrib.sum(axis=1)
    out = contrib.sum().rename("contribution").to_frame()
    out["mean_exposure"] = e.mean()
    out["mean_factor_return"] = f.mean()
    out.loc["alpha", "contribution"] = alpha.sum()
    return out
