"""回测路由。

后台计算委托给 :mod:`ashare_quant.api.services.backtest_runner`。
"""
from __future__ import annotations

import threading
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BacktestNav, BacktestRun, BacktestTrade
from ..schemas import BacktestRequest
from ..services.backtest_runner import run_backtest_job
from ..utils import monthly_returns

router = APIRouter()


@router.post("/run")
def start_backtest(req: BacktestRequest, db: Session = Depends(get_db)):
    run_id = uuid.uuid4().hex[:16]
    run = BacktestRun(
        id=run_id, strategy=req.strategy, engine=req.engine, universe=req.universe,
        start_date=req.start_date, end_date=req.end_date, init_capital=req.init_capital,
        benchmark=req.benchmark, params=req.params, status="pending", progress=0,
    )
    db.add(run)
    db.commit()
    threading.Thread(
        target=run_backtest_job, args=(run_id, req), daemon=True
    ).start()
    return {"run_id": run_id, "status": "pending"}


@router.get("/status/{run_id}")
def get_status(run_id: str, db: Session = Depends(get_db)):
    run = db.get(BacktestRun, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return {
        "id": run.id, "status": run.status, "progress": run.progress,
        "current_date": run.current_date_progress.isoformat() if run.current_date_progress else None,
        "log": run.log or "",
    }


@router.get("/result/{run_id}")
def get_result(run_id: str, db: Session = Depends(get_db)):
    run = db.get(BacktestRun, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    if run.status != "finished":
        raise HTTPException(409, f"backtest still {run.status}")

    nav_rows = db.scalars(
        select(BacktestNav).where(BacktestNav.run_id == run_id)
        .order_by(BacktestNav.trade_date)
    ).all()
    dates = [r.trade_date.isoformat() for r in nav_rows]
    port = [float(r.nav) for r in nav_rows]
    bench = [float(r.benchmark_nav or r.nav) for r in nav_rows]
    peak = -1.0
    dd = []
    for v in port:
        peak = max(peak, v)
        dd.append(round((v - peak) / peak, 6))

    trade_rows = db.scalars(
        select(BacktestTrade).where(BacktestTrade.run_id == run_id).limit(50)
    ).all()
    trades = [{
        "trade_date": t.trade_date.isoformat(), "symbol": t.symbol, "side": t.side,
        "qty": t.qty, "price": float(t.price), "amount": float(t.amount),
        "fee": float(t.fee), "pnl": float(t.pnl) if t.pnl else None,
    } for t in trade_rows]

    return {
        "id": run.id, "strategy": run.strategy,
        "metrics": {
            "total_return": float(run.total_return or 0),
            "annual_return": float(run.annual_return or 0),
            "sharpe": float(run.sharpe or 0),
            "max_drawdown": float(run.max_drawdown or 0),
            "calmar": float(run.calmar or 0),
            "win_rate": float(run.win_rate or 0),
            "turnover": float(run.turnover or 0),
        },
        "nav_dates": dates,
        "nav_portfolio": port,
        "nav_benchmark": bench,
        "drawdown": dd,
        "monthly": monthly_returns(dates, port),
        "industry":       {"白酒": 22, "银行": 18, "医药": 14, "新能源": 12, "电子": 10, "地产": 8, "消费": 7, "汽车": 5, "化工": 2, "机械": 2},
        "industry_bench": {"白酒": 12, "银行": 16, "医药": 11, "新能源": 9,  "电子": 12, "地产": 7, "消费": 9, "汽车": 7, "化工": 9, "机械": 8},
        "trades": trades,
    }


@router.get("/runs")
def list_runs(limit: int = 30, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit)
    ).all()
    return [{
        "id": r.id, "strategy": r.strategy, "status": r.status, "progress": r.progress,
        "start_date": r.start_date.isoformat(), "end_date": r.end_date.isoformat(),
        "total_return": float(r.total_return or 0),
        "sharpe": float(r.sharpe or 0),
        "max_drawdown": float(r.max_drawdown or 0),
        "created_at": r.created_at,
    } for r in rows]
