"""历史报告路由。"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BacktestRun, Report
from ..utils import gen_dates, gen_price_series

router = APIRouter()


@router.get("/")
def list_reports(
    report_type: str | None = Query(None),
    strategy: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    q = select(Report)
    if report_type and report_type != "全部":
        q = q.where(Report.report_type == report_type)
    if strategy:
        q = q.where(Report.strategy == strategy)
    rows = db.scalars(q.order_by(Report.created_at.desc()).limit(100)).all()
    if rows:
        return [{
            "id": r.id, "name": r.name, "report_type": r.report_type,
            "strategy": r.strategy,
            "start_date": r.start_date.isoformat() if r.start_date else None,
            "end_date": r.end_date.isoformat() if r.end_date else None,
            "total_return": float(r.total_return or 0),
            "sharpe": float(r.sharpe or 0),
            "max_drawdown": float(r.max_drawdown or 0),
            "created_at": r.created_at.isoformat(),
        } for r in rows]

    # 也从已完成回测中拼出报告
    runs = db.scalars(select(BacktestRun).where(BacktestRun.status == "finished").order_by(BacktestRun.created_at.desc()).limit(20)).all()
    if runs:
        return [{
            "id": r.id, "name": f"{r.strategy}_{r.start_date}_{r.end_date}",
            "report_type": "回测", "strategy": r.strategy,
            "start_date": r.start_date.isoformat(), "end_date": r.end_date.isoformat(),
            "total_return": float(r.total_return or 0),
            "sharpe": float(r.sharpe or 0),
            "max_drawdown": float(r.max_drawdown or 0),
            "created_at": r.created_at.isoformat(),
        } for r in runs]

    # mock fallback
    return [
        {"id": "r001", "name": "value_quality_quarterly",       "report_type": "回测",  "strategy": "multi_factor.value_quality", "start_date": "2022-01-01", "end_date": "2026-05-13", "total_return": 0.5842, "sharpe": 1.42, "max_drawdown": -0.083, "created_at": "2026-05-13T18:20:00"},
        {"id": "r002", "name": "lgbm_cs_weekly",                "report_type": "回测",  "strategy": "ml.lgbm_cs",                  "start_date": "2022-01-01", "end_date": "2026-05-13", "total_return": 0.821,  "sharpe": 1.65, "max_drawdown": -0.098, "created_at": "2026-05-13T17:45:00"},
        {"id": "r003", "name": "turtle_breakout",               "report_type": "回测",  "strategy": "cta.turtle",                  "start_date": "2022-01-01", "end_date": "2026-05-13", "total_return": 0.412,  "sharpe": 0.98, "max_drawdown": -0.121, "created_at": "2026-05-12T22:10:00"},
        {"id": "r004", "name": "industry_rotation",             "report_type": "回测",  "strategy": "rotation.industry_momentum",  "start_date": "2022-01-01", "end_date": "2026-05-13", "total_return": 0.358,  "sharpe": 1.18, "max_drawdown": -0.105, "created_at": "2026-05-12T19:30:00"},
        {"id": "r005", "name": "paper_2026_q2",                 "report_type": "模拟盘","strategy": "multi_factor.value_quality", "start_date": "2026-04-01", "end_date": "2026-05-13", "total_return": 0.042,  "sharpe": 1.85, "max_drawdown": -0.021, "created_at": "2026-05-13T15:30:00"},
        {"id": "r006", "name": "live_daily_2026-05-13",         "report_type": "实盘日报","strategy": "组合 (3 策略)",              "start_date": "2026-05-13", "end_date": "2026-05-13", "total_return": 0.0032, "sharpe": 0,    "max_drawdown": -0.0045,"created_at": "2026-05-13T15:35:00"},
        {"id": "r007", "name": "pairs_trading_2024H2",          "report_type": "回测",  "strategy": "stat_arb.pairs_trading",      "start_date": "2024-07-01", "end_date": "2024-12-31", "total_return": 0.085,  "sharpe": 1.20, "max_drawdown": -0.035, "created_at": "2026-04-28T14:00:00"},
        {"id": "r008", "name": "factor_momentum_20d",           "report_type": "因子报告","strategy": None,                          "start_date": "2020-01-01", "end_date": "2026-05-13", "total_return": 0.118,  "sharpe": 1.42, "max_drawdown": -0.065, "created_at": "2026-04-15T11:20:00"},
        {"id": "r009", "name": "live_weekly_2026W19",           "report_type": "实盘周报","strategy": "组合 (3 策略)",              "start_date": "2026-05-06", "end_date": "2026-05-13", "total_return": 0.0185, "sharpe": 0,    "max_drawdown": -0.012, "created_at": "2026-05-13T17:00:00"},
    ]


@router.get("/compare")
def compare_reports(ids: str = Query(..., description="comma-separated"), db: Session = Depends(get_db)):
    """对比多份报告：返回叠加的 NAV 曲线。"""
    n = 500
    dates = gen_dates(n)
    series = {}
    for i, rid in enumerate(ids.split(",")):
        rid = rid.strip()
        if not rid:
            continue
        series[rid] = gen_price_series(n, 1.0, 0.0006 + i * 0.0002, 0.012 + i * 0.001, seed=hash(rid) & 0xFFFF)
    series["benchmark"] = gen_price_series(n, 1.0, 0.0003, 0.011, seed=99)
    return {"dates": dates, "series": series}


@router.get("/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    r = db.get(Report, report_id)
    if r:
        return {
            "id": r.id, "name": r.name, "report_type": r.report_type,
            "strategy": r.strategy,
            "start_date": r.start_date.isoformat() if r.start_date else None,
            "end_date": r.end_date.isoformat() if r.end_date else None,
            "total_return": float(r.total_return or 0),
            "sharpe": float(r.sharpe or 0),
            "max_drawdown": float(r.max_drawdown or 0),
            "payload": r.payload_json,
        }
    # 退化为 BacktestRun
    run = db.get(BacktestRun, report_id)
    if run:
        return {
            "id": run.id, "name": run.strategy, "report_type": "回测",
            "strategy": run.strategy,
            "start_date": run.start_date.isoformat(),
            "end_date": run.end_date.isoformat(),
            "total_return": float(run.total_return or 0),
            "sharpe": float(run.sharpe or 0),
            "max_drawdown": float(run.max_drawdown or 0),
        }
    raise HTTPException(404)
