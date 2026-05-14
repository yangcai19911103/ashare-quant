"""Factors 路由测试。"""
from __future__ import annotations


def test_list_factors(client):
    r = client.get("/api/factors/")
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) > 0
    assert any(f["name"] == "momentum_20d" for f in arr)


def test_factor_registry(client):
    r = client.get("/api/factors/registry")
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) > 0
    for f in arr:
        assert "name" in f and "category" in f


def test_factor_compute_response(client):
    r = client.post("/api/factors/compute", json={
        "factor": "momentum_20d",
        "params": {"window": 20},
        "universe": "000300.SH",
        "start_date": "2023-01-01",
        "end_date": "2024-12-31",
        "forward_window": 5,
        "neutralize": ["industry", "size"],
        "winsorize": True,
        "zscore": True,
    })
    assert r.status_code == 200
    data = r.json()
    for k in ["factor", "ic_mean", "rank_ic_mean", "ic_ir", "ic_win_rate",
              "dates", "ic", "rank_ic", "quantile_nav", "monthly_ic", "quantile_stats"]:
        assert k in data
    assert data["factor"] == "momentum_20d"


def test_factor_compute_quantile_groups(client):
    r = client.post("/api/factors/compute", json={
        "factor": "roe",
        "start_date": "2024-01-01", "end_date": "2024-12-31",
    })
    data = r.json()
    # 10 个分组 + 1 个 LS
    assert "Q1" in data["quantile_nav"] and "Q10" in data["quantile_nav"]
    assert "LS" in data["quantile_nav"]
    assert len(data["quantile_stats"]) == 11


def test_factor_compute_ic_series_aligned(client):
    r = client.post("/api/factors/compute", json={
        "factor": "pe_ttm",
        "start_date": "2024-01-01", "end_date": "2024-12-31",
    })
    data = r.json()
    assert len(data["dates"]) == len(data["ic"]) == len(data["rank_ic"])


def test_factor_compute_invalid_payload(client):
    r = client.post("/api/factors/compute", json={"factor": "momentum_20d"})
    # 缺少必填日期
    assert r.status_code in {422, 400}
