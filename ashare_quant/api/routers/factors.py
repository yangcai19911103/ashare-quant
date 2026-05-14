"""因子探索路由。"""
from __future__ import annotations

import random
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import FactorDef, FactorEval
from ..schemas import FactorComputeRequest
from ..utils import gen_dates, gen_price_series

router = APIRouter()


FACTOR_LIBRARY = [
    {"name": "momentum_20d",       "category": "技术",   "direction": "pos"},
    {"name": "momentum_60d",       "category": "技术",   "direction": "pos"},
    {"name": "reversal_5d",        "category": "技术",   "direction": "neg"},
    {"name": "reversal_20d",       "category": "技术",   "direction": "neg"},
    {"name": "volatility_20d",     "category": "技术",   "direction": "neg"},
    {"name": "turnover_20d",       "category": "技术",   "direction": "neg"},
    {"name": "ma_cross_5_20",      "category": "技术",   "direction": "pos"},
    {"name": "rsi_14",             "category": "技术",   "direction": "neg"},
    {"name": "boll_band_pos",      "category": "技术",   "direction": "neg"},
    {"name": "pe_ttm",             "category": "基本面", "direction": "neg"},
    {"name": "pb",                 "category": "基本面", "direction": "neg"},
    {"name": "roe",                "category": "基本面", "direction": "pos"},
    {"name": "profit_growth_qoq",  "category": "基本面", "direction": "pos"},
    {"name": "north_flow_5d",      "category": "情绪",   "direction": "pos"},
    {"name": "margin_balance_chg", "category": "情绪",   "direction": "pos"},
]


@router.get("/")
def list_factors(db: Session = Depends(get_db)):
    rows = db.scalars(select(FactorDef)).all()
    if rows:
        return [{
            "name": r.name, "category": r.category, "direction": r.direction,
            "description": r.description,
        } for r in rows]
    return FACTOR_LIBRARY


@router.get("/registry")
def factor_registry(db: Session = Depends(get_db)):
    """已注册因子库（含评估指标）。"""
    rows = db.execute(
        select(FactorDef, FactorEval).join(FactorEval, FactorEval.factor == FactorDef.name, isouter=True)
    ).all()
    if rows:
        out = []
        for fd, fe in rows:
            out.append({
                "name": fd.name, "category": fd.category, "direction": fd.direction,
                "ic_mean": float(fe.ic_mean) if fe and fe.ic_mean is not None else None,
                "rank_ic_mean": float(fe.rank_ic_mean) if fe and fe.rank_ic_mean is not None else None,
                "ic_ir": float(fe.ic_ir) if fe and fe.ic_ir is not None else None,
                "ls_annual": float(fe.ls_annual) if fe and fe.ls_annual is not None else None,
            })
        return out
    # mock 数据
    return [
        {"name": "momentum_20d", "category": "技术",   "direction": "pos", "ic_mean": 0.054, "rank_ic_mean": 0.062, "ic_ir": 0.82, "ls_annual": 0.118},
        {"name": "reversal_5d",  "category": "技术",   "direction": "neg", "ic_mean": -0.038, "rank_ic_mean": -0.044, "ic_ir": 0.71, "ls_annual": 0.084},
        {"name": "volatility_20d","category": "技术",  "direction": "neg", "ic_mean": -0.029, "rank_ic_mean": -0.035, "ic_ir": 0.55, "ls_annual": 0.062},
        {"name": "turnover_20d", "category": "技术",   "direction": "neg", "ic_mean": -0.041, "rank_ic_mean": -0.046, "ic_ir": 0.68, "ls_annual": 0.078},
        {"name": "pe_ttm",       "category": "基本面", "direction": "neg", "ic_mean": -0.032, "rank_ic_mean": -0.038, "ic_ir": 0.50, "ls_annual": 0.051},
        {"name": "roe",          "category": "基本面", "direction": "pos", "ic_mean": 0.048, "rank_ic_mean": 0.052, "ic_ir": 0.78, "ls_annual": 0.096},
        {"name": "north_flow_5d","category": "情绪",   "direction": "pos", "ic_mean": 0.026, "rank_ic_mean": 0.031, "ic_ir": 0.45, "ls_annual": 0.048},
    ]


@router.post("/compute")
def compute_factor(req: FactorComputeRequest, db: Session = Depends(get_db)):
    rng = random.Random(hash(req.factor) & 0xFFFF)
    n = 120
    dates = gen_dates(n)
    ic = [round(0.05 + 0.03 * rng.gauss(0, 1), 4) for _ in range(n)]
    rank_ic = [round(v + 0.005 * rng.gauss(0, 1), 4) for v in ic]
    ic_mean = round(sum(ic) / n, 4)
    rank_ic_mean = round(sum(rank_ic) / n, 4)
    ic_var = sum((v - ic_mean) ** 2 for v in ic) / n
    ic_ir = round(ic_mean / (ic_var ** 0.5), 4) if ic_var > 0 else 0
    ic_win = round(sum(1 for v in ic if v > 0) / n, 4)

    qd = gen_dates(250)
    quantile_nav = {f"Q{i+1}": gen_price_series(250, 1.0, 0.0009 - i * 0.0002, 0.012, seed=i + 7) for i in range(10)}
    long_short = [q1 / q10 for q1, q10 in zip(quantile_nav["Q1"], quantile_nav["Q10"])]
    quantile_nav["LS"] = long_short

    # 月度 IC 热图
    monthly_ic = []
    for year in [2022, 2023, 2024, 2025, 2026]:
        for m in range(1, 13):
            monthly_ic.append({"year": year, "month": m, "ic": round(rng.gauss(0.03, 0.04), 4)})

    # 分组统计
    quantile_stats = []
    for i in range(10):
        ann = 0.136 - i * 0.020
        quantile_stats.append({
            "group": f"Q{i+1}",
            "total_return": round(ann * 4.5, 4),
            "annual": round(ann, 4),
            "sharpe": round(1.55 - i * 0.20, 2),
            "max_drawdown": round(-0.08 - i * 0.011, 4),
            "win_rate": round(0.63 - i * 0.025, 4),
        })
    quantile_stats.append({
        "group": "LS",
        "total_return": 0.734, "annual": 0.118, "sharpe": 1.42,
        "max_drawdown": -0.065, "win_rate": 0.65,
    })

    return {
        "factor": req.factor,
        "ic_mean": ic_mean,
        "rank_ic_mean": rank_ic_mean,
        "ic_ir": ic_ir,
        "ic_win_rate": ic_win,
        "ls_annual": round(quantile_nav["LS"][-1] ** (252 / 250) - 1, 4),
        "ls_sharpe": 1.42,
        "dates": dates,
        "ic": ic,
        "rank_ic": rank_ic,
        "quantile_nav": quantile_nav,
        "quantile_dates": qd,
        "monthly_ic": monthly_ic,
        "quantile_stats": quantile_stats,
    }
