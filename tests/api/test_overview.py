"""Overview 路由测试。"""
from __future__ import annotations


def test_overview_shape(client):
    r = client.get("/api/overview/")
    assert r.status_code == 200
    data = r.json()
    for k in ["kpis", "nav_dates", "nav_portfolio", "nav_benchmark",
              "industry", "activities", "strategies", "health"]:
        assert k in data


def test_overview_kpi_structure(client):
    data = client.get("/api/overview/").json()
    assert len(data["kpis"]) >= 4
    for k in data["kpis"]:
        assert "label" in k and "value" in k


def test_overview_nav_aligned(client):
    data = client.get("/api/overview/").json()
    assert len(data["nav_dates"]) == len(data["nav_portfolio"])
    assert len(data["nav_dates"]) == len(data["nav_benchmark"])
    assert len(data["nav_dates"]) >= 30


def test_overview_activities_have_required_fields(client):
    data = client.get("/api/overview/").json()
    for a in data["activities"]:
        assert "time" in a and "level" in a and "event" in a
        assert a["level"] in {"INFO", "WARN", "CRIT"}


def test_overview_strategies_numeric_fields(client):
    data = client.get("/api/overview/").json()
    for s in data["strategies"]:
        assert "name" in s
        for n in ["total_return", "annual_return", "sharpe", "max_drawdown"]:
            assert isinstance(s[n], (int, float))


def test_overview_industry_sums_positive(client):
    data = client.get("/api/overview/").json()
    total = sum(data["industry"].values())
    assert total > 0


def test_overview_health_thresholds(client):
    data = client.get("/api/overview/").json()
    h = data["health"]
    for k in ["data_completeness", "disk_usage_pct", "tushare_quota_pct"]:
        assert k in h
        assert 0 <= h[k] <= 100
