"""Monitor 路由测试。"""
from __future__ import annotations


def test_snapshot_shape(client):
    r = client.get("/api/monitor/snapshot")
    assert r.status_code == 200
    data = r.json()
    for k in ["kpis", "risk", "nav", "positions", "alerts",
              "industry", "strategies", "today_ops"]:
        assert k in data


def test_snapshot_kpi_fields(client):
    data = client.get("/api/monitor/snapshot").json()
    k = data["kpis"]
    for f in ["total_asset", "today_pnl", "positions_count", "max_drawdown"]:
        assert f in k


def test_snapshot_risk_fields(client):
    data = client.get("/api/monitor/snapshot").json()
    risk = data["risk"]
    for name in ["drawdown", "daily_loss", "max_position", "max_industry", "turnover"]:
        assert name in risk
        for sub in ["current", "threshold", "usage_pct"]:
            assert sub in risk[name]


def test_snapshot_nav_aligned(client):
    data = client.get("/api/monitor/snapshot").json()
    n = data["nav"]
    assert len(n["ts"]) == len(n["portfolio"]) == len(n["benchmark"])


def test_snapshot_today_ops(client):
    data = client.get("/api/monitor/snapshot").json()
    for k in ["orders", "fills", "cancels", "rejects"]:
        assert k in data["today_ops"]


def test_system_metrics(client):
    r = client.get("/api/monitor/system")
    assert r.status_code == 200
    data = r.json()
    for k in ["cpu", "mem_used_gb", "mem_total_gb", "net_kbps", "feed_latency_ms"]:
        assert k in data
    assert 0 <= data["cpu"] <= 100
    assert data["mem_total_gb"] > 0
