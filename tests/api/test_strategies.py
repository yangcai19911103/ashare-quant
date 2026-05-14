"""Strategies 路由测试。"""
from __future__ import annotations


def test_list_all(client):
    r = client.get("/api/strategies/")
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) >= 10
    names = {s["name"] for s in arr}
    assert "cta.turtle" in names
    assert "multi_factor.value_quality" in names


def test_filter_by_category(client):
    r = client.get("/api/strategies/", params={"category": "CTA"})
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) >= 1
    for s in arr:
        assert s["category"] == "CTA"


def test_filter_all_returns_all(client):
    a = client.get("/api/strategies/").json()
    b = client.get("/api/strategies/", params={"category": "all"}).json()
    assert len(a) == len(b)


def test_get_one(client):
    r = client.get("/api/strategies/cta.turtle")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "cta.turtle"
    assert data["category"] == "CTA"


def test_get_not_found(client):
    r = client.get("/api/strategies/nonexistent_strategy_xyz")
    assert r.status_code == 404


def test_strategy_fields_complete(client):
    arr = client.get("/api/strategies/").json()
    sample = arr[0]
    for k in ["name", "category", "description", "freq", "risk_level"]:
        assert k in sample
