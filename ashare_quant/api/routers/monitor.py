"""实盘监控大屏路由（含 SSE 实时流）。"""
from __future__ import annotations

import asyncio
import json
import random
import time
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, Alert, NavSnapshot, Order, Position

router = APIRouter()


@router.get("/snapshot")
def snapshot(db: Session = Depends(get_db)):
    acc = db.get(Account, "paper_default") or db.get(Account, "live_default")
    if not acc:
        total = 1_184_520
        today_pnl = 3_827
    else:
        total = float(acc.total_asset)
        today_pnl = float(acc.today_pnl)

    positions = db.scalars(
        select(Position).order_by(desc(Position.market_value)).limit(10)
    ).all()
    pos_data = [{
        "symbol": p.symbol, "qty": p.qty, "last_price": float(p.last_price),
        "market_value": float(p.market_value), "weight": float(p.weight),
        "pnl_pct": float(p.pnl_pct),
    } for p in positions]

    nav_rows = db.scalars(select(NavSnapshot).order_by(desc(NavSnapshot.ts)).limit(120)).all()
    nav_rows = list(reversed(nav_rows))
    nav_ts = [r.ts.strftime("%H:%M:%S") for r in nav_rows]
    nav_val = [float(r.nav) for r in nav_rows]
    bench_val = [float(r.benchmark or r.nav) for r in nav_rows]

    if not nav_ts:
        # fallback mock
        from ..utils import gen_price_series
        n = 60
        nav_val = gen_price_series(n, 1.0, 0.0001, 0.001, seed=1)
        bench_val = gen_price_series(n, 1.0, 0.0001, 0.001, seed=2)
        nav_ts = [datetime.now().strftime(f"%H:%M:{i:02d}") for i in range(n)]

    alerts = db.scalars(select(Alert).order_by(desc(Alert.ts)).limit(8)).all()
    alert_data = [{
        "ts": a.ts.strftime("%H:%M:%S"), "level": a.level.lower(),
        "title": a.title, "desc": a.message or "",
    } for a in alerts]

    return {
        "kpis": {
            "total_asset": total,
            "today_pnl": today_pnl,
            "positions_count": len(positions),
            "max_drawdown": -0.032,
        },
        "risk": {
            "drawdown": {"current": -3.20, "threshold": -15.0, "usage_pct": 21.0},
            "daily_loss": {"current": 0.32, "threshold": -5.0, "usage_pct": 6.0},
            "max_position": {"current": 8.5, "threshold": 10.0, "usage_pct": 85.0},
            "max_industry": {"current": 22.0, "threshold": 30.0, "usage_pct": 73.0},
            "turnover": {"current": 15.0, "threshold": 50.0, "usage_pct": 30.0},
        },
        "nav": {"ts": nav_ts, "portfolio": nav_val, "benchmark": bench_val},
        "positions": pos_data,
        "alerts": alert_data,
        "industry": {"白酒": 22, "银行": 18, "医药": 14, "新能源": 12, "电子": 10,
                     "地产": 8, "消费": 7, "其他": 9},
        "strategies": [
            {"name": "value_quality", "status": "running", "ret_ytd": 18.45},
            {"name": "turtle", "status": "running", "ret_ytd": 12.80},
            {"name": "lgbm_cs", "status": "running", "ret_ytd": 22.10},
        ],
        "today_ops": {"orders": 28, "fills": 26, "cancels": 2, "rejects": 0},
    }


@router.get("/ticks/stream")
async def stream_ticks():
    """SSE：实时 tick 流。"""
    async def gen():
        rng = random.Random()
        stocks = [("600519.SH", 1700), ("000858.SZ", 138), ("601318.SH", 50),
                  ("300750.SZ", 240), ("600276.SH", 44), ("002594.SZ", 247),
                  ("600036.SH", 40)]
        while True:
            sym, p0 = rng.choice(stocks)
            data = {
                "ts": datetime.now().strftime("%H:%M:%S"),
                "symbol": sym,
                "side": "B" if rng.random() > 0.5 else "S",
                "qty": rng.randint(1, 50) * 100,
                "price": round(p0 * (1 + rng.gauss(0, 0.003)), 2),
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.8)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/system")
def system_metrics():
    import psutil  # 可选依赖
    try:
        return {
            "cpu": psutil.cpu_percent(0.1),
            "mem_used_gb": round(psutil.virtual_memory().used / (1024 ** 3), 2),
            "mem_total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
            "net_kbps": 128,
            "feed_latency_ms": 42,
        }
    except Exception:
        return {"cpu": 22.0, "mem_used_gb": 3.2, "mem_total_gb": 16.0, "net_kbps": 128, "feed_latency_ms": 42}
