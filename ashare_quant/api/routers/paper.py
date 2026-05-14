"""模拟盘路由。

后台 worker 委托给 :mod:`ashare_quant.api.services.paper_sim`。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, Fill, NavSnapshot, Order, Position
from ..schemas import ManualOrderRequest, StartPaperRequest
from ..services.paper_sim import (DEFAULT_PAPER_ACCOUNT, ensure_paper_account,
                                  is_paper_running, start_paper_sim,
                                  stop_paper_sim)

router = APIRouter()


@router.post("/start")
def start_paper(req: StartPaperRequest, db: Session = Depends(get_db)):
    if is_paper_running():
        return {"ok": False, "message": "已在运行"}
    ensure_paper_account(db, req.init_capital)
    started = start_paper_sim(req.strategy)
    return {"ok": started, "account_id": DEFAULT_PAPER_ACCOUNT}


@router.post("/stop")
def stop_paper(db: Session = Depends(get_db)):
    stop_paper_sim()
    acc = db.get(Account, DEFAULT_PAPER_ACCOUNT)
    if acc:
        acc.status = "idle"
        db.commit()
    return {"ok": True}


@router.get("/account")
def get_account(db: Session = Depends(get_db)):
    acc = db.get(Account, DEFAULT_PAPER_ACCOUNT)
    if not acc:
        return {"id": DEFAULT_PAPER_ACCOUNT, "total_asset": 1_000_000, "cash": 1_000_000,
                "market_value": 0, "frozen": 0, "today_pnl": 0, "total_pnl": 0, "status": "idle"}
    return {
        "id": acc.id, "total_asset": float(acc.total_asset), "cash": float(acc.cash),
        "market_value": float(acc.market_value), "frozen": float(acc.frozen),
        "today_pnl": float(acc.today_pnl), "total_pnl": float(acc.total_pnl),
        "status": acc.status,
    }


@router.get("/positions")
def get_positions(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Position).where(Position.account_id == DEFAULT_PAPER_ACCOUNT)
    ).all()
    return [{
        "symbol": p.symbol, "qty": p.qty, "available": p.available,
        "cost_price": float(p.cost_price), "last_price": float(p.last_price),
        "market_value": float(p.market_value), "pnl": float(p.pnl),
        "pnl_pct": float(p.pnl_pct), "weight": float(p.weight),
    } for p in rows]


@router.get("/orders")
def get_orders(limit: int = 30, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Order).where(Order.account_id == DEFAULT_PAPER_ACCOUNT)
        .order_by(desc(Order.ts)).limit(limit)
    ).all()
    return [{
        "id": o.id, "ts": o.ts.isoformat(), "symbol": o.symbol, "side": o.side,
        "qty": o.qty, "filled_qty": o.filled_qty, "price": float(o.price) if o.price else None,
        "avg_price": float(o.avg_price) if o.avg_price else None, "status": o.status,
        "order_type": o.order_type, "algo": o.algo,
    } for o in rows]


@router.get("/fills")
def get_fills(limit: int = 30, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Fill).where(Fill.account_id == DEFAULT_PAPER_ACCOUNT)
        .order_by(desc(Fill.ts)).limit(limit)
    ).all()
    return [{
        "id": f.id, "ts": f.ts.isoformat(), "symbol": f.symbol, "side": f.side,
        "qty": f.qty, "price": float(f.price), "amount": float(f.amount), "fee": float(f.fee),
    } for f in rows]


@router.get("/nav")
def get_nav(limit: int = 200, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(NavSnapshot).where(NavSnapshot.account_id == DEFAULT_PAPER_ACCOUNT)
        .order_by(NavSnapshot.ts).limit(limit)
    ).all()
    return {
        "ts": [r.ts.strftime("%H:%M:%S") for r in rows],
        "nav": [float(r.nav) for r in rows],
        "benchmark": [float(r.benchmark or r.nav) for r in rows],
    }


@router.post("/order")
def manual_order(req: ManualOrderRequest, db: Session = Depends(get_db)):
    order_id = uuid.uuid4().hex[:16]
    price = req.price or 100.0
    account_id = req.account_id or DEFAULT_PAPER_ACCOUNT
    o = Order(
        id=order_id, account_id=account_id, symbol=req.symbol,
        side=req.side, qty=req.qty, order_type=req.order_type, price=price,
        avg_price=price, filled_qty=req.qty, status="filled", algo=req.algo,
        algo_params=req.algo_params,
    )
    db.add(o)
    db.add(Fill(
        order_id=order_id, account_id=account_id, symbol=req.symbol,
        side=req.side, qty=req.qty, price=price, amount=req.qty * price,
        fee=round(req.qty * price * 0.00025, 2),
    ))
    db.commit()
    return {"order_id": order_id, "status": "filled"}


@router.post("/positions/{symbol}/close")
def close_position(symbol: str, db: Session = Depends(get_db)):
    pos = db.get(Position, (DEFAULT_PAPER_ACCOUNT, symbol))
    if not pos:
        raise HTTPException(404)
    order_id = uuid.uuid4().hex[:16]
    db.add(Order(
        id=order_id, account_id=DEFAULT_PAPER_ACCOUNT, symbol=symbol, side="SELL",
        qty=pos.qty, order_type="MKT", price=float(pos.last_price),
        avg_price=float(pos.last_price), filled_qty=pos.qty, status="filled",
    ))
    db.add(Fill(
        order_id=order_id, account_id=DEFAULT_PAPER_ACCOUNT, symbol=symbol, side="SELL",
        qty=pos.qty, price=float(pos.last_price),
        amount=pos.qty * float(pos.last_price),
        fee=round(pos.qty * float(pos.last_price) * 0.0011, 2),
    ))
    db.delete(pos)
    db.commit()
    return {"ok": True}
