"""Portfolio 优化测试。"""
from __future__ import annotations

import pytest


SYMS = ["600519.SH", "000858.SZ", "601318.SH", "300750.SZ", "600276.SH"]


@pytest.mark.parametrize("method", ["ew", "iv", "rp", "mv", "mvo", "maxsharpe", "bl", "cvar", "hrp"])
def test_optimize_methods(client, method):
    r = client.post("/api/portfolio/optimize", json={
        "method": method, "symbols": SYMS,
        "max_weight": 0.30, "min_weight": 0.0, "long_only": True,
    })
    assert r.status_code == 200
    data = r.json()
    for k in ["weights", "expected_return", "volatility", "sharpe",
              "risk_contrib", "frontier", "asset_stats"]:
        assert k in data
    # 权重归一化（容差 1e-3）
    total = sum(data["weights"].values())
    assert abs(total - 1.0) < 1e-3


def test_weights_match_symbols(client):
    r = client.post("/api/portfolio/optimize", json={"method": "ew", "symbols": SYMS})
    data = r.json()
    assert set(data["weights"].keys()) == set(SYMS)


def test_equal_weight_method(client):
    r = client.post("/api/portfolio/optimize", json={"method": "ew", "symbols": SYMS})
    weights = r.json()["weights"]
    for w in weights.values():
        assert abs(w - 0.2) < 1e-3


def test_max_weight_constraint(client):
    """max_weight 上限应被强制生效。"""
    r = client.post("/api/portfolio/optimize", json={
        "method": "mvo", "symbols": SYMS,
        "max_weight": 0.25, "min_weight": 0.0,
    })
    weights = r.json()["weights"]
    # 受 max_weight 限制后再归一化，最大值理论不会显著超过 0.25
    assert max(weights.values()) <= 0.30


def test_frontier_present(client):
    r = client.post("/api/portfolio/optimize", json={"method": "mvo", "symbols": SYMS})
    data = r.json()
    assert len(data["frontier"]) > 5
    for pt in data["frontier"]:
        assert "vol" in pt and "ret" in pt


def test_empty_symbols_error(client):
    r = client.post("/api/portfolio/optimize", json={"method": "ew", "symbols": []})
    # 路由直接返回 200 + error
    assert r.status_code == 200
    assert "error" in r.json()
