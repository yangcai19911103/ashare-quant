"""ORM 模型 CRUD 基础测试。"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import func, select

from ashare_quant.api.models import (Account, Alert, AlertChannel, BacktestNav,
                                     BacktestRun, BacktestTrade, DailyBar,
                                     DataJob, DataSource, FactorDef,
                                     FactorEval, Fill, Instrument, NavSnapshot,
                                     Order, Position, Report, RiskConfig,
                                     StrategyDef, TradeCalendar)


def test_seeded_data_sources_present(db_session):
    rows = db_session.scalars(select(DataSource)).all()
    names = {r.name for r in rows}
    assert {"akshare", "tushare", "efinance", "xtquant"} <= names


def test_seeded_instruments_present(db_session):
    cnt = db_session.scalar(select(func.count()).select_from(Instrument))
    assert cnt >= 10


def test_seeded_factor_defs(db_session):
    rows = db_session.scalars(select(FactorDef)).all()
    names = {r.name for r in rows}
    assert "momentum_20d" in names
    assert "roe" in names


def test_seeded_strategies(db_session):
    rows = db_session.scalars(select(StrategyDef)).all()
    names = {r.name for r in rows}
    assert "multi_factor.value_quality" in names
    assert "cta.turtle" in names


def test_seeded_risk_config(db_session):
    rows = db_session.scalars(select(RiskConfig)).all()
    scopes = {r.scope for r in rows}
    assert {"pre_trade", "in_trade", "post_trade"} <= scopes


def test_seeded_alert_channels(db_session):
    rows = db_session.scalars(select(AlertChannel)).all()
    assert len(rows) >= 3


def test_create_account_and_position(db_session):
    acc = Account(
        id="t_acct_1", account_type="paper", broker="sim",
        total_asset=100000, cash=80000, market_value=20000,
        frozen=0, today_pnl=0, total_pnl=0, status="idle",
    )
    db_session.add(acc)
    db_session.add(Position(
        account_id="t_acct_1", symbol="600519.SH", qty=100, available=0,
        cost_price=1700, last_price=1710, market_value=171000,
        pnl=1000, pnl_pct=0.006, weight=1.0,
    ))
    db_session.commit()
    got = db_session.get(Account, "t_acct_1")
    assert got and float(got.total_asset) == 100000
    pos = db_session.get(Position, ("t_acct_1", "600519.SH"))
    assert pos.qty == 100


def test_create_backtest_run(db_session):
    run = BacktestRun(
        id="bt_test_1", strategy="cta.turtle", engine="event_driven",
        start_date=date(2024, 1, 1), end_date=date(2024, 12, 31),
        init_capital=1_000_000, benchmark="000300.SH", status="pending", progress=0,
    )
    db_session.add(run)
    db_session.commit()
    assert db_session.get(BacktestRun, "bt_test_1") is not None


def test_alert_filterable(db_session):
    db_session.add(Alert(level="WARN", source="unit_test", title="x", message="y"))
    db_session.commit()
    rows = db_session.scalars(select(Alert).where(Alert.source == "unit_test")).all()
    assert len(rows) >= 1


def test_order_table_uses_quoting(db_session):
    """`order` 是 SQL 关键字，ORM 必须正确加引号。"""
    o = Order(id="o_test_1", account_id="t_acct_1", symbol="600519.SH",
              side="BUY", order_type="MKT", qty=100, status="pending")
    db_session.add(o)
    db_session.commit()
    assert db_session.get(Order, "o_test_1") is not None


def test_json_column_roundtrip(db_session):
    """JSON 字段在 SQLite (TEXT fallback) / MySQL 都应该正常读写。"""
    cfg = db_session.get(RiskConfig, "pre_trade")
    assert isinstance(cfg.config_json, dict)
    assert "max_single_position_pct" in cfg.config_json
