"""Backtest 路由测试（后台线程已被 conftest stub）。"""
from __future__ import annotations

import pytest


def _payload():
    return {
        "strategy": "multi_factor.value_quality",
        "engine": "event_driven",
        "universe": "000300.SH",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "init_capital": 1_000_000,
        "benchmark": "000300.SH",
        "fee_bps": 2.5,
        "slippage_bps": 2.0,
        "rebalance_freq": "M",
        "params": {"top_n": 30, "weighting": "equal"},
    }


def test_run_returns_run_id(client):
    r = client.post("/api/backtest/run", json=_payload())
    assert r.status_code == 200
    data = r.json()
    assert "run_id" in data
    assert len(data["run_id"]) == 16
    assert data["status"] == "pending"


def test_status_endpoint(client):
    rid = client.post("/api/backtest/run", json=_payload()).json()["run_id"]
    r = client.get(f"/api/backtest/status/{rid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == rid
    assert body["status"] in {"pending", "running", "finished", "failed"}
    assert 0 <= body["progress"] <= 100


def test_status_not_found(client):
    r = client.get("/api/backtest/status/no_such_run_id")
    assert r.status_code == 404


def test_result_when_not_finished(client):
    rid = client.post("/api/backtest/run", json=_payload()).json()["run_id"]
    r = client.get(f"/api/backtest/result/{rid}")
    # 后台被 stub，状态为 pending，应返回 409
    assert r.status_code == 409


def test_runs_list(client):
    # 提交几个
    for _ in range(2):
        client.post("/api/backtest/run", json=_payload())
    r = client.get("/api/backtest/runs")
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) >= 2
    for run in arr:
        for k in ["id", "strategy", "status", "progress"]:
            assert k in run


def test_run_validation_missing_strategy(client):
    bad = _payload()
    del bad["strategy"]
    r = client.post("/api/backtest/run", json=bad)
    assert r.status_code == 422


def test_run_completed_returns_full_result(client, db_session):
    """手动写一个 finished 的回测，验证 result 接口返回完整字段。"""
    import json
    import uuid
    from datetime import date, datetime, timezone

    from ashare_quant.api.models import BacktestNav, BacktestRun, BacktestTrade

    rid = uuid.uuid4().hex[:16]
    run = BacktestRun(
        id=rid, strategy="cta.turtle", engine="event_driven",
        start_date=date(2023, 1, 1), end_date=date(2023, 12, 31),
        init_capital=1_000_000, benchmark="000300.SH",
        status="finished", progress=100,
        total_return=0.15, annual_return=0.12, sharpe=1.2,
        max_drawdown=-0.08, calmar=1.5, win_rate=0.55, turnover=3.2,
        finished_at=datetime.now(timezone.utc).replace(tzinfo=None),
        result_json=json.dumps({}),
    )
    db_session.add(run)
    db_session.add(BacktestNav(run_id=rid, trade_date=date(2023, 1, 2), nav=1.0, benchmark_nav=1.0))
    db_session.add(BacktestNav(run_id=rid, trade_date=date(2023, 1, 3), nav=1.01, benchmark_nav=1.002))
    db_session.add(BacktestTrade(run_id=rid, trade_date=date(2023, 1, 3),
                                 symbol="600519.SH", side="BUY", qty=100,
                                 price=1700, amount=170000, fee=43))
    db_session.commit()

    r = client.get(f"/api/backtest/result/{rid}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == rid
    for k in ["metrics", "nav_dates", "nav_portfolio", "nav_benchmark",
              "drawdown", "monthly", "industry", "trades"]:
        assert k in data
    assert data["metrics"]["sharpe"] == 1.2
    assert len(data["trades"]) >= 1
