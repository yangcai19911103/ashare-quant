"""Reports 路由测试。"""
from __future__ import annotations

from datetime import date, datetime, timezone


def _make_report(db_session, rid, rtype="回测"):
    from ashare_quant.api.models import Report
    db_session.add(Report(
        id=rid, name=f"test_{rid}", report_type=rtype,
        strategy="cta.turtle", start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31), total_return=0.15,
        sharpe=1.2, max_drawdown=-0.08,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db_session.commit()


def test_list_reports_empty_fallback(client):
    r = client.get("/api/reports/")
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    # 至少返回 mock 或真实记录
    if arr:
        item = arr[0]
        for k in ["id", "name", "report_type", "total_return", "sharpe"]:
            assert k in item


def test_list_with_db_records(client, db_session):
    _make_report(db_session, "rep_t1")
    arr = client.get("/api/reports/").json()
    assert any(r["id"] == "rep_t1" for r in arr)


def test_filter_by_type(client, db_session):
    _make_report(db_session, "rep_t2", rtype="模拟盘")
    arr = client.get("/api/reports/", params={"report_type": "模拟盘"}).json()
    types = {r["report_type"] for r in arr}
    assert types == {"模拟盘"}


def test_get_by_id(client, db_session):
    _make_report(db_session, "rep_t3")
    r = client.get("/api/reports/rep_t3")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "rep_t3"


def test_get_not_found(client):
    r = client.get("/api/reports/no_such_report_xyz")
    assert r.status_code == 404


def test_compare_two_reports(client):
    r = client.get("/api/reports/compare", params={"ids": "a1,b2"})
    assert r.status_code == 200
    data = r.json()
    assert "dates" in data and "series" in data
    assert "a1" in data["series"] and "b2" in data["series"]
    assert "benchmark" in data["series"]
    # 序列长度一致
    n = len(data["dates"])
    for v in data["series"].values():
        assert len(v) == n


def test_compare_dedup_blank_ids(client):
    r = client.get("/api/reports/compare", params={"ids": "a, ,b,"})
    data = r.json()
    # 空 id 应该被剔除
    assert set(data["series"].keys()) - {"benchmark"} == {"a", "b"}
