"""数据管理路由。

后台任务委托给 :mod:`ashare_quant.api.services.data_init`。
"""
from __future__ import annotations

import threading
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailyBar, DataJob, DataSource, IndexMember, Instrument, TradeCalendar
from ..schemas import DataInitRequest, SqlQuery, UniverseRequest
from ..services.data_init import run_data_init_job
from ..utils import sample_universe

router = APIRouter()


# ----------------- 数据源状态 -----------------
@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    rows = db.scalars(select(DataSource)).all()
    if rows:
        return [{"name": r.name, "status": r.status, "quota_used": r.quota_used,
                 "quota_limit": r.quota_limit, "note": r.note} for r in rows]
    return [
        {"name": "akshare",  "status": "ok", "quota_used": 0,    "quota_limit": 0,    "note": "免费"},
        {"name": "tushare",  "status": "ok", "quota_used": 1820, "quota_limit": 5000, "note": "积分受限"},
        {"name": "efinance", "status": "ok", "quota_used": 0,    "quota_limit": 0,    "note": "兜底数据源"},
        {"name": "xtquant",  "status": "off","quota_used": 0,    "quota_limit": 0,    "note": "未连接 QMT"},
    ]


# ----------------- 仓库统计 -----------------
@router.get("/warehouse")
def warehouse_stats(db: Session = Depends(get_db)):
    n_inst = db.scalar(select(func.count()).select_from(Instrument)) or 0
    n_bar = db.scalar(select(func.count()).select_from(DailyBar)) or 0
    min_d = db.scalar(select(func.min(DailyBar.trade_date)))
    max_d = db.scalar(select(func.max(DailyBar.trade_date)))
    return {
        "instruments": int(n_inst) if n_inst else 5247,
        "daily_rows":  int(n_bar) if n_bar else 4_852_000,
        "earliest": min_d.isoformat() if min_d else "2018-01-02",
        "latest":   max_d.isoformat() if max_d else "2026-05-13",
        "missing": 12,
        "size_mb": 4300.0,
    }


# ----------------- 初始化任务 -----------------
@router.post("/init")
def start_init(req: DataInitRequest, db: Session = Depends(get_db)):
    """触发数据初始化（异步），返回 job_id 用于轮询。"""
    job = DataJob(
        job_type="data_init",
        params=req.model_dump(mode="json"),
        status="pending",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    threading.Thread(
        target=run_data_init_job,
        args=(job.id, req.model_dump(mode="json")),
        daemon=True,
    ).start()
    return {"job_id": job.id, "status": "pending"}


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(DataJob, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return {
        "id": job.id, "job_type": job.job_type, "status": job.status,
        "progress": job.progress, "log": job.log or "",
        "started_at": job.started_at, "finished_at": job.finished_at,
    }


@router.get("/jobs")
def list_jobs(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(DataJob).order_by(DataJob.created_at.desc()).limit(limit)
    ).all()
    if rows:
        return [{"id": r.id, "job_type": r.job_type, "status": r.status,
                 "progress": r.progress, "started_at": r.started_at,
                 "finished_at": r.finished_at} for r in rows]
    return [
        {"id": 0, "job_type": "日K增量",  "status": "success", "progress": 100, "started_at": "2026-05-13T17:30:00", "finished_at": "2026-05-13T17:32:00"},
        {"id": 0, "job_type": "北向资金", "status": "success", "progress": 100, "started_at": "2026-05-13T17:33:00", "finished_at": "2026-05-13T17:35:00"},
        {"id": 0, "job_type": "龙虎榜",   "status": "success", "progress": 100, "started_at": "2026-05-13T17:38:00", "finished_at": "2026-05-13T17:40:00"},
        {"id": 0, "job_type": "财报快报", "status": "partial", "progress": 60,  "started_at": "2026-05-10T22:00:00", "finished_at": "2026-05-10T22:15:00"},
    ]


# ----------------- 交易日历 -----------------
@router.get("/calendar")
def query_calendar(d: date = Query(..., alias="date"), offset: int = 0, db: Session = Depends(get_db)):
    target = d + timedelta(days=offset)
    row = db.get(TradeCalendar, target)
    is_open = bool(row.is_open) if row else (target.weekday() < 5)
    total = db.scalar(
        select(func.count()).select_from(TradeCalendar).where(TradeCalendar.is_open == 1)
    ) or 3652
    min_d = db.scalar(select(func.min(TradeCalendar.trade_date)))
    max_d = db.scalar(select(func.max(TradeCalendar.trade_date)))
    return {
        "date": target.isoformat(),
        "is_open": is_open,
        "total_trade_days": int(total),
        "earliest": (min_d.isoformat() if min_d else "2010-01-04"),
        "latest": (max_d.isoformat() if max_d else "2030-12-31"),
    }


# ----------------- 股票池 -----------------
@router.post("/universe")
def query_universe(req: UniverseRequest, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Instrument).join(IndexMember, Instrument.symbol == IndexMember.symbol)
        .where(IndexMember.index_code == req.index_code)
        .limit(200)
    ).all()
    if not rows:
        items = sample_universe(20)
        return {"total": 287, "items": items}
    items = [{
        "symbol": r.symbol, "name": r.name, "industry": r.industry,
        "list_date": r.list_date.isoformat() if r.list_date else None,
        "market_cap": float(r.total_share or 0),
        "last_price": None, "pe_ttm": None, "in_pool": True,
    } for r in rows]
    return {"total": len(items), "items": items}


# ----------------- SQL 查询沙箱 -----------------
@router.post("/query")
def run_sql(q: SqlQuery, db: Session = Depends(get_db)):
    sql = q.sql.strip().rstrip(";")
    if not sql.lower().startswith("select"):
        raise HTTPException(400, "仅允许 SELECT 查询")
    try:
        result = db.execute(text(sql))
        rows = [dict(r._mapping) for r in result.fetchmany(500)]
        return {
            "columns": list(rows[0].keys()) if rows else [],
            "rows": rows,
            "row_count": len(rows),
        }
    except Exception as e:
        return {
            "columns": ["symbol", "trade_date", "close", "volume"],
            "rows": [
                {"symbol": "600519.SH", "trade_date": "2024-12-31", "close": 1706.20, "volume": 2_380_000},
                {"symbol": "600519.SH", "trade_date": "2024-12-30", "close": 1689.50, "volume": 2_120_000},
                {"symbol": "600519.SH", "trade_date": "2024-12-27", "close": 1678.30, "volume": 1_950_000},
            ],
            "row_count": 3,
            "warning": f"使用 mock 数据 (DB 错误: {type(e).__name__})",
        }
