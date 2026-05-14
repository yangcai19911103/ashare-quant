"""Data 路由测试。"""
from __future__ import annotations


def test_list_sources(client):
    r = client.get("/api/data/sources")
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) >= 3
    for s in arr:
        assert "name" in s and "status" in s


def test_warehouse_stats(client):
    r = client.get("/api/data/warehouse")
    assert r.status_code == 200
    data = r.json()
    for k in ["instruments", "daily_rows", "earliest", "latest", "missing", "size_mb"]:
        assert k in data
    assert data["instruments"] >= 0


def test_calendar_query(client):
    r = client.get("/api/data/calendar", params={"date": "2026-05-14", "offset": 0})
    assert r.status_code == 200
    data = r.json()
    assert "date" in data and "is_open" in data
    assert isinstance(data["is_open"], bool)


def test_calendar_offset(client):
    r = client.get("/api/data/calendar", params={"date": "2026-05-14", "offset": -1})
    assert r.status_code == 200


def test_universe_query(client):
    r = client.post("/api/data/universe", json={
        "index_code": "000300.SH",
        "drop_st": True,
        "drop_suspend": True,
        "drop_new_60d": True,
    })
    assert r.status_code == 200
    data = r.json()
    assert "items" in data and "total" in data
    if data["items"]:
        item = data["items"][0]
        assert "symbol" in item and "name" in item


def test_data_init_creates_job(client):
    r = client.post("/api/data/init", json={
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "sources": ["akshare", "efinance"],
        "workers": 4,
        "options": {"stocks": True},
    })
    assert r.status_code == 200
    data = r.json()
    assert "job_id" in data and isinstance(data["job_id"], int)
    assert data["status"] == "pending"


def test_data_init_invalid_date(client):
    r = client.post("/api/data/init", json={"start_date": "not-a-date", "end_date": "2024-12-31"})
    assert r.status_code in {422, 400}


def test_job_status_endpoint(client):
    r = client.post("/api/data/init", json={
        "start_date": "2024-01-01", "end_date": "2024-12-31",
        "sources": ["akshare"], "workers": 2, "options": {},
    })
    job_id = r.json()["job_id"]
    r2 = client.get(f"/api/data/jobs/{job_id}")
    assert r2.status_code == 200
    body = r2.json()
    assert body["id"] == job_id
    assert "status" in body and "progress" in body


def test_job_status_not_found(client):
    r = client.get("/api/data/jobs/99999999")
    assert r.status_code == 404


def test_list_jobs(client):
    r = client.get("/api/data/jobs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_sql_select_query(client):
    r = client.post("/api/data/query", json={"sql": "SELECT 1 AS x"})
    assert r.status_code == 200
    data = r.json()
    # 兼容真实查询和 fallback：必有 columns / rows
    assert "columns" in data and "rows" in data


def test_sql_rejects_non_select(client):
    r = client.post("/api/data/query", json={"sql": "DROP TABLE daily_bar"})
    assert r.status_code == 400


def test_sql_empty_rejected(client):
    r = client.post("/api/data/query", json={"sql": ""})
    assert r.status_code in {400, 422}
