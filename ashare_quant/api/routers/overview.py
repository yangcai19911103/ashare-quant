"""总览页路由。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, Alert, BacktestRun, NavSnapshot, Order
from ..utils import (INDUSTRY_WEIGHTS, gen_dates, gen_price_series,
                     metrics_from_nav)

router = APIRouter()


@router.get("/")
def get_overview(db: Session = Depends(get_db)):
    # 账户合计
    accounts = db.scalars(select(Account)).all()
    total_asset = sum(float(a.total_asset or 0) for a in accounts) or 1_184_520.0
    today_pnl = sum(float(a.today_pnl or 0) for a in accounts) or 3_827.0
    cnt_strategies = db.scalar(select(func.count()).select_from(BacktestRun)) or 18
    running = db.scalar(select(func.count()).select_from(BacktestRun).where(BacktestRun.status == "running")) or 3
    alert_cnt = db.scalar(select(func.count()).select_from(Alert).where(Alert.resolved == 0)) or 2

    # NAV：优先取 default 账户的 nav_snapshot，没有则生成 mock
    dates = gen_dates(90)
    portfolio = gen_price_series(90, 1.0, 0.0008, 0.012, seed=1)
    benchmark = gen_price_series(90, 1.0, 0.0003, 0.011, seed=2)
    if accounts:
        rows = db.scalars(
            select(NavSnapshot).where(NavSnapshot.account_id == accounts[0].id).order_by(NavSnapshot.ts).limit(120)
        ).all()
        if len(rows) >= 30:
            dates = [r.ts.strftime("%Y-%m-%d") for r in rows]
            portfolio = [float(r.nav) for r in rows]
            benchmark = [float(r.benchmark or r.nav) for r in rows]

    kpis = [
        {"label": "总 NAV",   "value": f"¥{total_asset:,.0f}",   "delta": "+18.45% 累计",       "trend": "up"},
        {"label": "今日收益", "value": f"+¥{today_pnl:,.0f}",    "delta": "+0.32%",             "trend": "up"},
        {"label": "运行策略", "value": f"{running} / {cnt_strategies}", "delta": "3 策略运行中", "trend": "flat"},
        {"label": "活跃告警", "value": str(alert_cnt),            "delta": "1 止损 · 1 单日亏损", "trend": "down"},
    ]

    # 最近事件
    activities = []
    rows = db.scalars(select(Alert).order_by(Alert.ts.desc()).limit(10)).all()
    if rows:
        for a in rows:
            activities.append({
                "time": a.ts.strftime("%H:%M:%S"),
                "level": a.level,
                "event": a.title,
                "detail": a.message or "",
            })
    else:
        activities = [
            {"time": "11:25:33", "level": "INFO", "event": "调仓完成", "detail": "value_quality 季度调仓 30 只"},
            {"time": "11:08:12", "level": "WARN", "event": "止损触发", "detail": "600276.SH 浮亏 -10.4% → 已平仓"},
            {"time": "10:33:50", "level": "INFO", "event": "成交",     "detail": "买入 000858.SZ × 2,000@138.20"},
            {"time": "09:45:01", "level": "CRIT", "event": "单日亏损", "detail": "组合 -5.12% 超过 -5% 阈值"},
            {"time": "09:30:00", "level": "INFO", "event": "盘前任务", "detail": "universe 过滤完成"},
            {"time": "08:30:15", "level": "INFO", "event": "QMT 连接", "detail": "已连接华泰 QMT 账户 ****1234"},
        ]

    # 策略表现
    runs = db.scalars(select(BacktestRun).where(BacktestRun.status == "finished").order_by(BacktestRun.created_at.desc()).limit(5)).all()
    if runs:
        strategies = [{
            "name": r.strategy,
            "category": "回测",
            "status": "完成",
            "total_return": float(r.total_return or 0),
            "annual_return": float(r.annual_return or 0),
            "sharpe": float(r.sharpe or 0),
            "max_drawdown": float(r.max_drawdown or 0),
            "win_rate": float(r.win_rate or 0),
            "turnover": float(r.turnover or 0),
        } for r in runs]
    else:
        strategies = [
            {"name": "multi_factor.value_quality", "category": "多因子", "status": "运行中", "total_return": 0.1845, "annual_return": 0.152, "sharpe": 1.42, "max_drawdown": -0.083, "win_rate": 0.62, "turnover": 3.2},
            {"name": "cta.turtle",                 "category": "CTA",   "status": "运行中", "total_return": 0.128,  "annual_return": 0.105, "sharpe": 0.98, "max_drawdown": -0.121, "win_rate": 0.48, "turnover": 8.5},
            {"name": "ml.lgbm_cs",                 "category": "机器学习", "status": "运行中", "total_return": 0.221, "annual_return": 0.183, "sharpe": 1.65, "max_drawdown": -0.098, "win_rate": 0.58, "turnover": 11.0},
            {"name": "stat_arb.etf_rotation",      "category": "套利",  "status": "已停止", "total_return": 0.051,  "annual_return": 0.042, "sharpe": 0.51, "max_drawdown": -0.065, "win_rate": 0.55, "turnover": 12.0},
            {"name": "event.dragon_tiger",         "category": "事件",  "status": "已停止", "total_return": -0.032, "annual_return": -0.026, "sharpe": -0.18, "max_drawdown": -0.15, "win_rate": 0.42, "turnover": 25.0},
        ]

    return {
        "kpis": kpis,
        "nav_dates": dates,
        "nav_portfolio": portfolio,
        "nav_benchmark": benchmark,
        "industry": INDUSTRY_WEIGHTS,
        "activities": activities,
        "strategies": strategies,
        "health": {
            "data_completeness": 98.5,
            "disk_usage_pct": 8.4,
            "tushare_quota_pct": 36.4,
        },
    }
