"""SQLAlchemy ORM 模型，对应 sql/init_schema.sql。

所有表使用 InnoDB + utf8mb4，索引设计参考 schema 文件。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON, BigInteger, Date, DateTime, ForeignKey, Index, Integer, Numeric,
    SmallInteger, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

BigIntPK = BigInteger().with_variant(Integer(), "sqlite")
"""SQLite 不支持 BIGINT 自增主键，统一兼容 (MySQL 仍用 BIGINT)。"""


# ----------------- 行情 / 元数据 -----------------

class Instrument(Base):
    __tablename__ = "instrument"
    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    exchange: Mapped[str] = mapped_column(String(8))
    industry: Mapped[Optional[str]] = mapped_column(String(32))
    list_date: Mapped[Optional[date]] = mapped_column(Date)
    delist_date: Mapped[Optional[date]] = mapped_column(Date)
    is_st: Mapped[int] = mapped_column(SmallInteger, default=0)
    status: Mapped[str] = mapped_column(String(16), default="L")
    total_share: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))
    float_share: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))


class TradeCalendar(Base):
    __tablename__ = "trade_calendar"
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    exchange: Mapped[str] = mapped_column(String(8), default="SSE")
    is_open: Mapped[int] = mapped_column(SmallInteger, default=1)


class DailyBar(Base):
    __tablename__ = "daily_bar"
    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    high: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    low: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    close: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    pre_close: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))
    turnover: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    pct_chg: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    adj_factor: Mapped[float] = mapped_column(Numeric(12, 6), default=1.0)
    __table_args__ = (Index("idx_date", "trade_date"),)


class IndexMember(Base):
    __tablename__ = "index_member"
    index_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    in_date: Mapped[date] = mapped_column(Date, primary_key=True)
    out_date: Mapped[Optional[date]] = mapped_column(Date)
    weight: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))


class Fundamental(Base):
    __tablename__ = "fundamental"
    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, primary_key=True)
    ann_date: Mapped[Optional[date]] = mapped_column(Date)
    pe_ttm: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    pb: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    ps_ttm: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    roe: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    roa: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    net_profit: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))
    net_profit_yoy: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    revenue_yoy: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    market_cap: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))


class NorthFlow(Base):
    __tablename__ = "north_flow"
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    net_amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))
    hold_amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))
    hold_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))


# ----------------- 数据源 / 任务 -----------------

class DataSource(Base):
    __tablename__ = "data_source"
    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="unknown")
    quota_used: Mapped[int] = mapped_column(Integer, default=0)
    quota_limit: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[Optional[str]] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class DataJob(Base):
    __tablename__ = "data_job"
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(32))
    params: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    log: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


# ----------------- 因子 -----------------

class FactorDef(Base):
    __tablename__ = "factor_def"
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(32))
    direction: Mapped[str] = mapped_column(String(8), default="pos")
    formula: Mapped[Optional[str]] = mapped_column(Text)
    params: Mapped[Optional[dict]] = mapped_column(JSON)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class FactorValue(Base):
    __tablename__ = "factor_value"
    factor: Mapped[str] = mapped_column(String(64), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    value: Mapped[Optional[float]] = mapped_column(Numeric(20, 8))


class FactorEval(Base):
    __tablename__ = "factor_eval"
    factor: Mapped[str] = mapped_column(String(64), primary_key=True)
    start_date: Mapped[date] = mapped_column(Date, primary_key=True)
    end_date: Mapped[date] = mapped_column(Date, primary_key=True)
    universe: Mapped[str] = mapped_column(String(32), primary_key=True)
    ic_mean: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    rank_ic_mean: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    ic_ir: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    ic_win_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    ls_annual: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    ls_sharpe: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    ls_maxdd: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    series_json: Mapped[Optional[dict]] = mapped_column(JSON)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


# ----------------- 策略 / 回测 -----------------

class StrategyDef(Base):
    __tablename__ = "strategy_def"
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    cn_name: Mapped[Optional[str]] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32))
    description: Mapped[Optional[str]] = mapped_column(String(512))
    freq: Mapped[Optional[str]] = mapped_column(String(16))
    risk_level: Mapped[Optional[str]] = mapped_column(String(8))
    default_params: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class BacktestRun(Base):
    __tablename__ = "backtest_run"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    strategy: Mapped[str] = mapped_column(String(64))
    engine: Mapped[str] = mapped_column(String(16), default="event_driven")
    universe: Mapped[Optional[str]] = mapped_column(String(32))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    init_capital: Mapped[float] = mapped_column(Numeric(20, 4))
    benchmark: Mapped[Optional[str]] = mapped_column(String(16))
    params: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_date_progress: Mapped[Optional[date]] = mapped_column("current_date_progress", Date)
    log: Mapped[Optional[str]] = mapped_column(Text)
    total_return: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    annual_return: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    sharpe: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    max_drawdown: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    calmar: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    win_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    turnover: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    result_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class BacktestNav(Base):
    __tablename__ = "backtest_nav"
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    nav: Mapped[float] = mapped_column(Numeric(20, 8))
    benchmark_nav: Mapped[Optional[float]] = mapped_column(Numeric(20, 8))
    drawdown: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))


class BacktestTrade(Base):
    __tablename__ = "backtest_trade"
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32))
    trade_date: Mapped[date] = mapped_column(Date)
    symbol: Mapped[str] = mapped_column(String(16))
    side: Mapped[str] = mapped_column(String(4))
    qty: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Numeric(12, 4))
    amount: Mapped[float] = mapped_column(Numeric(20, 4))
    fee: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    pnl: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))


# ----------------- 风控 -----------------

class RiskConfig(Base):
    __tablename__ = "risk_config"
    scope: Mapped[str] = mapped_column(String(32), primary_key=True)
    config_json: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class Alert(Base):
    __tablename__ = "alert"
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    level: Mapped[str] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(128))
    message: Mapped[Optional[str]] = mapped_column(String(512))
    resolved: Mapped[int] = mapped_column(SmallInteger, default=0)


class AlertChannel(Base):
    __tablename__ = "alert_channel"
    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    channel_type: Mapped[str] = mapped_column(String(16))
    config_json: Mapped[Optional[dict]] = mapped_column(JSON)
    min_level: Mapped[str] = mapped_column(String(8), default="INFO")
    enabled: Mapped[int] = mapped_column(SmallInteger, default=1)


# ----------------- 账户 / 持仓 / 订单 -----------------

class Account(Base):
    __tablename__ = "account"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_type: Mapped[str] = mapped_column(String(16))
    broker: Mapped[Optional[str]] = mapped_column(String(32))
    total_asset: Mapped[float] = mapped_column(Numeric(20, 4), default=0)
    cash: Mapped[float] = mapped_column(Numeric(20, 4), default=0)
    market_value: Mapped[float] = mapped_column(Numeric(20, 4), default=0)
    frozen: Mapped[float] = mapped_column(Numeric(20, 4), default=0)
    today_pnl: Mapped[float] = mapped_column(Numeric(20, 4), default=0)
    total_pnl: Mapped[float] = mapped_column(Numeric(20, 4), default=0)
    status: Mapped[str] = mapped_column(String(16), default="idle")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class Position(Base):
    __tablename__ = "position"
    account_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    qty: Mapped[int] = mapped_column(Integer, default=0)
    available: Mapped[int] = mapped_column(Integer, default=0)
    cost_price: Mapped[float] = mapped_column(Numeric(12, 4))
    last_price: Mapped[float] = mapped_column(Numeric(12, 4))
    market_value: Mapped[float] = mapped_column(Numeric(20, 4))
    pnl: Mapped[float] = mapped_column(Numeric(20, 4), default=0)
    pnl_pct: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    weight: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class Order(Base):
    __tablename__ = "order"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(32))
    strategy: Mapped[Optional[str]] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(16))
    side: Mapped[str] = mapped_column(String(4))
    order_type: Mapped[str] = mapped_column(String(16), default="MKT")
    qty: Mapped[int] = mapped_column(Integer)
    filled_qty: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    avg_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    algo: Mapped[Optional[str]] = mapped_column(String(16))
    algo_params: Mapped[Optional[dict]] = mapped_column(JSON)
    ts: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    approved_by: Mapped[Optional[str]] = mapped_column(String(32))


class Fill(Base):
    __tablename__ = "fill"
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(40))
    account_id: Mapped[str] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(16))
    side: Mapped[str] = mapped_column(String(4))
    qty: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Numeric(12, 4))
    amount: Mapped[float] = mapped_column(Numeric(20, 4))
    fee: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    ts: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class NavSnapshot(Base):
    __tablename__ = "nav_snapshot"
    account_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    nav: Mapped[float] = mapped_column(Numeric(20, 8))
    benchmark: Mapped[Optional[float]] = mapped_column(Numeric(20, 8))


# ----------------- 报告 -----------------

class Report(Base):
    __tablename__ = "report"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    report_type: Mapped[str] = mapped_column(String(32))
    strategy: Mapped[Optional[str]] = mapped_column(String(64))
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    total_return: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    sharpe: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    max_drawdown: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    payload_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
