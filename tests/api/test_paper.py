"""Paper trading 路由测试（后台 sim 线程已被 stub）。"""
from __future__ import annotations


def test_start_paper(client):
    r = client.post("/api/paper/start", json={
        "strategy": "multi_factor.value_quality",
        "init_capital": 500000,
        "replay_mode": "live",
        "start_date": "2026-05-14",
        "universe": "000300.SH",
    })
    assert r.status_code == 200
    body = r.json()
    assert "account_id" in body


def test_account_after_start(client):
    client.post("/api/paper/start", json={
        "strategy": "cta.turtle", "init_capital": 1_000_000,
        "replay_mode": "live", "start_date": "2026-05-14",
    })
    r = client.get("/api/paper/account")
    assert r.status_code == 200
    data = r.json()
    for k in ["id", "total_asset", "cash", "market_value",
              "today_pnl", "total_pnl", "status"]:
        assert k in data


def test_stop_paper(client):
    client.post("/api/paper/start", json={
        "strategy": "cta.turtle", "init_capital": 1_000_000,
        "replay_mode": "live",
    })
    r = client.post("/api/paper/stop")
    assert r.status_code == 200


def test_manual_order(client):
    # 必须先 start，否则没有账户
    client.post("/api/paper/start", json={
        "strategy": "cta.turtle", "init_capital": 1_000_000,
        "replay_mode": "live",
    })
    r = client.post("/api/paper/order", json={
        "symbol": "600519.SH", "side": "BUY", "qty": 100,
        "order_type": "MKT", "price": 1700,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "filled"
    assert len(body["order_id"]) == 16


def test_orders_and_fills_after_manual(client):
    client.post("/api/paper/start", json={"strategy": "cta.turtle"})
    client.post("/api/paper/order", json={
        "symbol": "000858.SZ", "side": "BUY", "qty": 200,
        "order_type": "LMT", "price": 138.20,
    })
    orders = client.get("/api/paper/orders").json()
    fills = client.get("/api/paper/fills").json()
    assert any(o["symbol"] == "000858.SZ" for o in orders)
    assert any(f["symbol"] == "000858.SZ" for f in fills)


def test_positions_endpoint(client):
    r = client.get("/api/paper/positions")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_nav_endpoint(client):
    r = client.get("/api/paper/nav")
    assert r.status_code == 200
    data = r.json()
    assert "ts" in data and "nav" in data and "benchmark" in data


def test_close_position_creates_sell(client, db_session):
    # 准备：直接插入一个持仓
    from ashare_quant.api.models import Account, Position
    if not db_session.get(Account, "paper_default"):
        db_session.add(Account(id="paper_default", account_type="paper",
                                total_asset=1_000_000, cash=900_000,
                                market_value=100_000, frozen=0,
                                today_pnl=0, total_pnl=0, status="idle"))
    if not db_session.get(Position, ("paper_default", "300750.SZ")):
        db_session.add(Position(account_id="paper_default", symbol="300750.SZ",
                                qty=300, available=300, cost_price=240,
                                last_price=242, market_value=72600,
                                pnl=600, pnl_pct=0.008, weight=0.07))
    db_session.commit()

    r = client.post("/api/paper/positions/300750.SZ/close")
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Position, ("paper_default", "300750.SZ")) is None


def test_close_nonexistent_position(client):
    r = client.post("/api/paper/positions/INVALID.SH/close")
    assert r.status_code == 404
