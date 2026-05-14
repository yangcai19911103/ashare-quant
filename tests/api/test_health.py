"""基础健康检查 & 应用挂载。"""
from __future__ import annotations


def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "ashare-quant-api"


def test_openapi_schema_available(client):
    r = client.get("/api/openapi.json")
    assert r.status_code == 200
    data = r.json()
    assert "openapi" in data
    # 11 个核心 tag
    paths = data["paths"]
    expected_prefixes = [
        "/api/overview/",
        "/api/data/",
        "/api/factors/",
        "/api/strategies/",
        "/api/backtest/",
        "/api/risk/",
        "/api/portfolio/",
        "/api/paper/",
        "/api/live/",
        "/api/monitor/",
        "/api/reports/",
    ]
    for p in expected_prefixes:
        assert any(k.startswith(p) for k in paths), f"missing {p}"


def test_docs_available(client):
    r = client.get("/api/docs")
    assert r.status_code == 200
    assert "swagger" in r.text.lower() or "openapi" in r.text.lower()
