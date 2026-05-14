"""Risk 路由测试。"""
from __future__ import annotations


def test_get_config(client):
    r = client.get("/api/risk/config")
    assert r.status_code == 200
    data = r.json()
    for scope in ["pre_trade", "in_trade", "post_trade"]:
        assert scope in data
    assert data["pre_trade"]["max_single_position_pct"] > 0


def test_save_and_reload_config(client):
    cfg = client.get("/api/risk/config").json()
    cfg["pre_trade"]["max_single_position_pct"] = 8.8
    r = client.post("/api/risk/config", json=cfg)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    reload = client.get("/api/risk/config").json()
    assert float(reload["pre_trade"]["max_single_position_pct"]) == 8.8


def test_list_alerts(client):
    r = client.get("/api/risk/alerts")
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    if arr:
        a = arr[0]
        for k in ["id", "ts", "level", "source", "title"]:
            assert k in a
        assert a["level"] in {"INFO", "WARN", "CRIT"}


def test_resolve_alert(client, db_session):
    from ashare_quant.api.models import Alert
    a = Alert(level="INFO", source="unit_test", title="to_resolve")
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    aid = a.id

    r = client.post(f"/api/risk/alerts/{aid}/resolve")
    assert r.status_code == 200
    assert r.json()["ok"] is True

    db_session.expire_all()
    fresh = db_session.get(Alert, aid)
    assert fresh.resolved == 1


def test_resolve_alert_not_found(client):
    r = client.post("/api/risk/alerts/99999999/resolve")
    assert r.status_code == 404


def test_list_channels(client):
    r = client.get("/api/risk/channels")
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) >= 3
    for c in arr:
        assert "name" in c and "type" in c and "enabled" in c


def test_test_channel(client):
    r = client.post("/api/risk/channels/Slack/test")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True


def test_drawdown(client):
    r = client.get("/api/risk/drawdown")
    assert r.status_code == 200
    data = r.json()
    assert "dates" in data and "drawdown" in data
    assert len(data["dates"]) == len(data["drawdown"])
    assert data["threshold"] < 0


def test_attribution(client):
    r = client.get("/api/risk/attribution")
    assert r.status_code == 200
    data = r.json()
    assert "rows" in data and "total_excess" in data
    for x in data["rows"]:
        for k in ["sector", "allocation", "selection", "interaction", "total"]:
            assert k in x


def test_halt(client, db_session):
    from sqlalchemy import select
    from ashare_quant.api.models import Alert
    before = len(db_session.scalars(select(Alert)).all())
    r = client.post("/api/risk/halt")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    db_session.expire_all()
    after = len(db_session.scalars(select(Alert)).all())
    assert after == before + 1
