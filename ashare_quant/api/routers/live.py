"""实盘交易路由（QMT 通道占位 + 双人审批）。"""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import Account, Alert, Order
from ..schemas import ManualOrderRequest

router = APIRouter()

LIVE_ACCT = "live_default"
QMT_STATE = {"connected": False, "account": None, "broker": None}
PENDING_APPROVALS: List[dict] = []


class QMTConnectRequest(BaseModel):
    broker: str = "华泰证券"
    account: str = "****1234"
    qmt_path: str = "D:\\国金QMT交易端\\userdata_mini"
    account_type: str = "STOCK"


def _connect_qmt_task():
    """模拟 QMT 连接流程。"""
    session = SessionLocal()
    try:
        steps = ["检查 QMT 客户端进程", "加载 XtQuant SDK", "登录账户", "订阅资金/持仓回调"]
        for i, s in enumerate(steps):
            time.sleep(0.6)
            session.add(Alert(level="INFO", source="qmt", title=f"[{i+1}/{len(steps)}] {s}", message="完成"))
            session.commit()
        QMT_STATE["connected"] = True
        acc = session.get(Account, LIVE_ACCT)
        if not acc:
            acc = Account(id=LIVE_ACCT, account_type="live", broker=QMT_STATE.get("broker"),
                          total_asset=1_184_520, cash=480_000, market_value=704_520,
                          frozen=0, today_pnl=3_827, total_pnl=184_520, status="connected")
            session.add(acc)
        else:
            acc.status = "connected"
        session.commit()
    finally:
        session.close()


@router.get("/status")
def get_status():
    return {**QMT_STATE, "pending_approvals": len(PENDING_APPROVALS)}


@router.post("/qmt/connect")
def connect_qmt(req: QMTConnectRequest):
    QMT_STATE["broker"] = req.broker
    QMT_STATE["account"] = req.account
    threading.Thread(target=_connect_qmt_task, daemon=True).start()
    return {"ok": True, "message": "连接中..."}


@router.post("/qmt/disconnect")
def disconnect_qmt():
    QMT_STATE["connected"] = False
    return {"ok": True}


@router.get("/account")
def get_live_account(db: Session = Depends(get_db)):
    acc = db.get(Account, LIVE_ACCT)
    if not acc:
        return None
    return {
        "id": acc.id, "broker": acc.broker, "total_asset": float(acc.total_asset),
        "cash": float(acc.cash), "market_value": float(acc.market_value),
        "today_pnl": float(acc.today_pnl), "total_pnl": float(acc.total_pnl),
        "status": acc.status,
    }


@router.get("/deployments")
def list_deployments():
    """已部署到实盘的策略列表。"""
    return [
        {"strategy": "multi_factor.value_quality", "capital": 500_000, "status": "stopped"},
        {"strategy": "cta.turtle",                 "capital": 300_000, "status": "stopped"},
        {"strategy": "ml.lgbm_cs",                 "capital": 200_000, "status": "stopped"},
    ]


@router.post("/deployments/{strategy}/{action}")
def deploy_action(strategy: str, action: str, db: Session = Depends(get_db)):
    if action not in {"start", "stop"}:
        raise HTTPException(400, "action must be start or stop")
    db.add(Alert(level="WARN", source="live", title=f"策略 {action}",
                 message=f"{strategy} 已 {action}（待双人审批）"))
    db.commit()
    return {"ok": True, "strategy": strategy, "action": action}


@router.post("/order")
def place_live_order(req: ManualOrderRequest):
    order_id = uuid.uuid4().hex[:16]
    item = {
        "id": order_id, "ts": datetime.now().isoformat(),
        "symbol": req.symbol, "side": req.side, "qty": req.qty,
        "order_type": req.order_type, "algo": req.algo,
        "algo_params": req.algo_params,
    }
    PENDING_APPROVALS.append(item)
    return {"order_id": order_id, "status": "pending_approval"}


@router.get("/approvals")
def list_approvals():
    return PENDING_APPROVALS


@router.post("/approvals/{order_id}/approve")
def approve(order_id: str, db: Session = Depends(get_db)):
    global PENDING_APPROVALS
    PENDING_APPROVALS = [x for x in PENDING_APPROVALS if x["id"] != order_id]
    db.add(Alert(level="INFO", source="live", title="订单审批通过", message=f"order_id={order_id}"))
    db.commit()
    return {"ok": True}


@router.post("/approvals/{order_id}/reject")
def reject(order_id: str, db: Session = Depends(get_db)):
    global PENDING_APPROVALS
    PENDING_APPROVALS = [x for x in PENDING_APPROVALS if x["id"] != order_id]
    db.add(Alert(level="WARN", source="live", title="订单审批拒绝", message=f"order_id={order_id}"))
    db.commit()
    return {"ok": True}


@router.post("/estimate")
def estimate_cost(req: ManualOrderRequest):
    price = req.price or 100.0
    amount = req.qty * price
    fee = round(amount * 0.00025, 2)
    stamp = round(amount * 0.001, 2) if req.side == "SELL" else 0
    return {"amount": amount, "fee": fee, "stamp": stamp, "total": amount + fee + stamp}
