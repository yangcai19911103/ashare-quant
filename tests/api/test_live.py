"""Live 路由测试。"""
from __future__ import annotations

import pytest

from ashare_quant.api.routers import live as live_router


@pytest.fixture(autouse=True)
def _reset_state():
    """每个用例重置全局 QMT 状态 + 待审批队列。"""
    live_router.QMT_STATE.update({"connected": False, "account": None, "broker": None})
    live_router.PENDING_APPROVALS.clear()
    yield
    live_router.QMT_STATE.update({"connected": False, "account": None, "broker": None})
    live_router.PENDING_APPROVALS.clear()


def test_initial_status_disconnected(client):
    r = client.get("/api/live/status")
    assert r.status_code == 200
    data = r.json()
    assert data["connected"] is False
    assert data["pending_approvals"] == 0


def test_qmt_connect_returns_ok(client):
    r = client.post("/api/live/qmt/connect", json={
        "broker": "华泰证券", "account": "****1234",
        "qmt_path": "D:\\QMT", "account_type": "STOCK",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # broker / account 已记录到全局 state
    assert live_router.QMT_STATE["broker"] == "华泰证券"


def test_qmt_disconnect(client):
    live_router.QMT_STATE["connected"] = True
    r = client.post("/api/live/qmt/disconnect")
    assert r.status_code == 200
    assert live_router.QMT_STATE["connected"] is False


def test_live_account_endpoint(client):
    r = client.get("/api/live/account")
    # 没有 live_default 时返回 None
    assert r.status_code == 200


def test_deployments_list(client):
    r = client.get("/api/live/deployments")
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) >= 1
    for d in arr:
        for k in ["strategy", "capital", "status"]:
            assert k in d


def test_deploy_action_valid(client):
    r = client.post("/api/live/deployments/cta.turtle/start")
    assert r.status_code == 200
    assert r.json()["action"] == "start"


def test_deploy_action_invalid(client):
    r = client.post("/api/live/deployments/cta.turtle/garbage")
    assert r.status_code == 400


def test_order_creates_pending_approval(client):
    r = client.post("/api/live/order", json={
        "symbol": "600519.SH", "side": "BUY", "qty": 100,
        "order_type": "MKT", "price": 1700,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending_approval"
    assert len(body["order_id"]) == 16
    assert len(live_router.PENDING_APPROVALS) == 1


def test_approve_flow(client):
    oid = client.post("/api/live/order", json={
        "symbol": "600519.SH", "side": "BUY", "qty": 100, "order_type": "MKT",
    }).json()["order_id"]
    assert len(live_router.PENDING_APPROVALS) == 1

    r = client.post(f"/api/live/approvals/{oid}/approve")
    assert r.status_code == 200
    assert len(live_router.PENDING_APPROVALS) == 0


def test_reject_flow(client):
    oid = client.post("/api/live/order", json={
        "symbol": "600519.SH", "side": "SELL", "qty": 100, "order_type": "MKT",
    }).json()["order_id"]
    r = client.post(f"/api/live/approvals/{oid}/reject")
    assert r.status_code == 200
    assert len(live_router.PENDING_APPROVALS) == 0


def test_list_approvals(client):
    client.post("/api/live/order", json={
        "symbol": "600519.SH", "side": "BUY", "qty": 100, "order_type": "MKT",
    })
    arr = client.get("/api/live/approvals").json()
    assert len(arr) == 1


def test_estimate_buy(client):
    r = client.post("/api/live/estimate", json={
        "symbol": "600519.SH", "side": "BUY", "qty": 100,
        "order_type": "MKT", "price": 1700,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["amount"] == 170000
    assert data["stamp"] == 0  # BUY 无印花税


def test_estimate_sell_has_stamp(client):
    r = client.post("/api/live/estimate", json={
        "symbol": "600519.SH", "side": "SELL", "qty": 100,
        "order_type": "MKT", "price": 1700,
    })
    data = r.json()
    assert data["stamp"] > 0  # SELL 千一印花税
