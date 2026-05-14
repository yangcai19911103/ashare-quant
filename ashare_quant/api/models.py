"""SQLAlchemy ORM 模型，对应 sql/init_schema.sql。

所有表使用 InnoDB + utf8mb4；字段 comment 与 DDL 中 COMMENT 对齐，便于文档与数据库展示。
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
    """证券基础信息。"""

    __tablename__ = "instrument"
    __table_args__ = {"comment": "证券基础信息"}

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True, comment="证券代码，如 600519.SH")
    name: Mapped[str] = mapped_column(String(64), comment="证券简称")
    exchange: Mapped[str] = mapped_column(String(8), comment="交易所代码，如 SH、SZ")
    industry: Mapped[Optional[str]] = mapped_column(String(32), comment="行业分类")
    list_date: Mapped[Optional[date]] = mapped_column(Date, comment="上市日期")
    delist_date: Mapped[Optional[date]] = mapped_column(Date, comment="退市日期，未退市为空")
    is_st: Mapped[int] = mapped_column(SmallInteger, default=0, comment="是否 ST，0 否 1 是")
    status: Mapped[str] = mapped_column(String(16), default="L", comment="上市状态，如 L 上市")
    total_share: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), comment="总股本")
    float_share: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), comment="流通股本")


class TradeCalendar(Base):
    """交易日历。"""

    __tablename__ = "trade_calendar"
    __table_args__ = {"comment": "交易日历"}

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="自然日")
    exchange: Mapped[str] = mapped_column(String(8), default="SSE", comment="交易所，默认 SSE")
    is_open: Mapped[int] = mapped_column(SmallInteger, default=1, comment="是否交易日，1 交易 0 休市")


class DailyBar(Base):
    """日 K 线行情。"""

    __tablename__ = "daily_bar"
    __table_args__ = (
        Index("idx_dbar_trade_date", "trade_date"),
        {"comment": "日K线行情"},
    )

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True, comment="证券代码")
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="交易日")
    open: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), comment="开盘价")
    high: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), comment="最高价")
    low: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), comment="最低价")
    close: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), comment="收盘价")
    pre_close: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), comment="昨收价")
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, comment="成交量")
    amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), comment="成交额")
    turnover: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="换手率")
    pct_chg: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="涨跌幅")
    adj_factor: Mapped[float] = mapped_column(Numeric(12, 6), default=1.0, comment="复权因子")


class IndexMember(Base):
    """指数成分股。"""

    __tablename__ = "index_member"
    __table_args__ = {"comment": "指数成分"}

    index_code: Mapped[str] = mapped_column(String(16), primary_key=True, comment="指数代码，如 000300.SH")
    symbol: Mapped[str] = mapped_column(String(16), primary_key=True, comment="成分证券代码")
    in_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="纳入指数日期")
    out_date: Mapped[Optional[date]] = mapped_column(Date, comment="调出指数日期，仍在池内为空")
    weight: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="指数权重")


class Fundamental(Base):
    """财务与估值快照。"""

    __tablename__ = "fundamental"
    __table_args__ = {"comment": "财务与估值"}

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True, comment="证券代码")
    report_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="报告期")
    ann_date: Mapped[Optional[date]] = mapped_column(Date, comment="公告日")
    pe_ttm: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), comment="市盈率 TTM")
    pb: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), comment="市净率")
    ps_ttm: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), comment="市销率 TTM")
    roe: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), comment="净资产收益率")
    roa: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), comment="总资产收益率")
    net_profit: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), comment="净利润")
    net_profit_yoy: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), comment="净利润同比增速")
    revenue_yoy: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), comment="营收同比增速")
    market_cap: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), comment="市值")


class NorthFlow(Base):
    """北向资金持股与流向。"""

    __tablename__ = "north_flow"
    __table_args__ = {"comment": "北向资金"}

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="交易日")
    symbol: Mapped[str] = mapped_column(String(16), primary_key=True, comment="证券代码")
    net_amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), comment="净流入金额")
    hold_amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), comment="持股金额或持仓量")
    hold_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="持股占比等")


# ----------------- 数据源 / 任务 -----------------

class DataSource(Base):
    """外部数据源状态与配额。"""

    __tablename__ = "data_source"
    __table_args__ = {"comment": "数据源配置"}

    name: Mapped[str] = mapped_column(String(32), primary_key=True, comment="数据源标识，如 akshare")
    status: Mapped[str] = mapped_column(String(16), default="unknown", comment="连接或健康状态")
    quota_used: Mapped[int] = mapped_column(Integer, default=0, comment="已用配额")
    quota_limit: Mapped[int] = mapped_column(Integer, default=0, comment="配额上限")
    note: Mapped[Optional[str]] = mapped_column(String(255), comment="备注")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="最近更新时间")


class DataJob(Base):
    """异步数据任务记录。"""

    __tablename__ = "data_job"
    __table_args__ = {"comment": "数据任务"}

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True, comment="任务主键")
    job_type: Mapped[str] = mapped_column(String(32), comment="任务类型，如 data_init")
    params: Mapped[Optional[dict]] = mapped_column(JSON, comment="任务参数 JSON")
    status: Mapped[str] = mapped_column(String(16), default="pending", comment="状态 pending/running/success/failed")
    progress: Mapped[int] = mapped_column(Integer, default=0, comment="进度 0-100")
    log: Mapped[Optional[str]] = mapped_column(Text, comment="文本日志")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="开始时间")
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="结束时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), comment="创建时间")


# ----------------- 因子 -----------------

class FactorDef(Base):
    """因子定义。"""

    __tablename__ = "factor_def"
    __table_args__ = {"comment": "因子定义"}

    name: Mapped[str] = mapped_column(String(64), primary_key=True, comment="因子名称")
    category: Mapped[str] = mapped_column(String(32), comment="因子类别")
    direction: Mapped[str] = mapped_column(String(8), default="pos", comment="因子方向 pos/neg")
    formula: Mapped[Optional[str]] = mapped_column(Text, comment="公式或计算说明")
    params: Mapped[Optional[dict]] = mapped_column(JSON, comment="因子参数 JSON")
    description: Mapped[Optional[str]] = mapped_column(String(255), comment="描述")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), comment="创建时间")


class FactorValue(Base):
    """因子截面值。"""

    __tablename__ = "factor_value"
    __table_args__ = (Index("idx_fval_factor_date", "factor", "trade_date"), {"comment": "因子值"})

    factor: Mapped[str] = mapped_column(String(64), primary_key=True, comment="因子名称")
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="交易日")
    symbol: Mapped[str] = mapped_column(String(16), primary_key=True, comment="证券代码")
    value: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), comment="因子值")


class FactorEval(Base):
    """因子评价结果。"""

    __tablename__ = "factor_eval"
    __table_args__ = {"comment": "因子评价"}

    factor: Mapped[str] = mapped_column(String(64), primary_key=True, comment="因子名称")
    start_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="评价区间起始")
    end_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="评价区间结束")
    universe: Mapped[str] = mapped_column(String(32), primary_key=True, comment="股票池或指数代码")
    ic_mean: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="IC 均值")
    rank_ic_mean: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="Rank IC 均值")
    ic_ir: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="IC 信息比")
    ic_win_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="IC 胜率")
    ls_annual: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="多空组合年化收益")
    ls_sharpe: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="多空夏普")
    ls_maxdd: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="多空最大回撤")
    series_json: Mapped[Optional[dict]] = mapped_column(JSON, comment="评价序列等扩展 JSON")
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), comment="评价时间")


# ----------------- 策略 / 回测 -----------------

class StrategyDef(Base):
    """策略定义目录。"""

    __tablename__ = "strategy_def"
    __table_args__ = {"comment": "策略定义"}

    name: Mapped[str] = mapped_column(String(64), primary_key=True, comment="策略唯一标识")
    cn_name: Mapped[Optional[str]] = mapped_column(String(64), comment="中文名称")
    category: Mapped[str] = mapped_column(String(32), comment="策略类别")
    description: Mapped[Optional[str]] = mapped_column(String(512), comment="说明")
    freq: Mapped[Optional[str]] = mapped_column(String(16), comment="调仓频率")
    risk_level: Mapped[Optional[str]] = mapped_column(String(8), comment="风险等级")
    default_params: Mapped[Optional[dict]] = mapped_column(JSON, comment="默认参数 JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), comment="创建时间")


class BacktestRun(Base):
    """回测运行实例。"""

    __tablename__ = "backtest_run"
    __table_args__ = (
        Index("idx_bt_run_strategy", "strategy"),
        Index("idx_bt_run_status", "status"),
        {"comment": "回测运行"},
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="回测任务 ID")
    strategy: Mapped[str] = mapped_column(String(64), comment="策略名称")
    engine: Mapped[str] = mapped_column(String(16), default="event_driven", comment="回测引擎类型")
    universe: Mapped[Optional[str]] = mapped_column(String(32), comment="股票池或指数")
    start_date: Mapped[date] = mapped_column(Date, comment="回测起始日")
    end_date: Mapped[date] = mapped_column(Date, comment="回测结束日")
    init_capital: Mapped[float] = mapped_column(Numeric(20, 4), comment="初始资金")
    benchmark: Mapped[Optional[str]] = mapped_column(String(16), comment="基准代码")
    params: Mapped[Optional[dict]] = mapped_column(JSON, comment="运行参数 JSON")
    status: Mapped[str] = mapped_column(String(16), default="pending", comment="运行状态")
    progress: Mapped[int] = mapped_column(Integer, default=0, comment="进度百分比")
    current_date_progress: Mapped[Optional[date]] = mapped_column("current_date_progress", Date, comment="当前仿真到的交易日")
    log: Mapped[Optional[str]] = mapped_column(Text, comment="运行日志")
    total_return: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), comment="总收益率")
    annual_return: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), comment="年化收益率")
    sharpe: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="夏普比率")
    max_drawdown: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), comment="最大回撤")
    calmar: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="卡玛比率")
    win_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="胜率")
    turnover: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="换手率")
    result_json: Mapped[Optional[str]] = mapped_column(Text, comment="完整结果 JSON 文本")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), comment="创建时间")
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="完成时间")


class BacktestNav(Base):
    """回测净值序列。"""

    __tablename__ = "backtest_nav"
    __table_args__ = {"comment": "回测净值"}

    run_id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="回测任务 ID")
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="交易日")
    nav: Mapped[float] = mapped_column(Numeric(20, 8), comment="组合净值")
    benchmark_nav: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), comment="基准净值")
    drawdown: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), comment="回撤")


class BacktestTrade(Base):
    """回测成交明细。"""

    __tablename__ = "backtest_trade"
    __table_args__ = (
        Index("idx_bt_trd_run", "run_id"),
        Index("idx_bt_trd_sym", "symbol"),
        {"comment": "回测成交"},
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True, comment="成交记录主键")
    run_id: Mapped[str] = mapped_column(String(32), comment="回测任务 ID")
    trade_date: Mapped[date] = mapped_column(Date, comment="成交日")
    symbol: Mapped[str] = mapped_column(String(16), comment="标的代码")
    side: Mapped[str] = mapped_column(String(4), comment="买卖方向 BUY/SELL")
    qty: Mapped[int] = mapped_column(Integer, comment="成交数量")
    price: Mapped[float] = mapped_column(Numeric(12, 4), comment="成交价格")
    amount: Mapped[float] = mapped_column(Numeric(20, 4), comment="成交金额")
    fee: Mapped[float] = mapped_column(Numeric(12, 4), default=0, comment="手续费")
    pnl: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), comment="盈亏")


# ----------------- 风控 -----------------

class RiskConfig(Base):
    """风控规则配置。"""

    __tablename__ = "risk_config"
    __table_args__ = {"comment": "风控配置"}

    scope: Mapped[str] = mapped_column(String(32), primary_key=True, comment="作用域标识")
    config_json: Mapped[dict] = mapped_column(JSON, comment="风控规则 JSON")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")


class Alert(Base):
    """风控与系统告警记录。"""

    __tablename__ = "alert"
    __table_args__ = (
        Index("idx_alert_ts", "ts"),
        Index("idx_alert_level", "level"),
        {"comment": "告警记录"},
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True, comment="告警主键")
    ts: Mapped[datetime] = mapped_column(DateTime, default=func.now(), comment="告警时间")
    level: Mapped[str] = mapped_column(String(8), comment="级别 INFO/WARN/CRIT")
    source: Mapped[str] = mapped_column(String(32), comment="来源模块")
    title: Mapped[str] = mapped_column(String(128), comment="标题")
    message: Mapped[Optional[str]] = mapped_column(String(512), comment="正文")
    resolved: Mapped[int] = mapped_column(SmallInteger, default=0, comment="是否已处理 0/1")


class AlertChannel(Base):
    """告警推送渠道。"""

    __tablename__ = "alert_channel"
    __table_args__ = {"comment": "告警渠道"}

    name: Mapped[str] = mapped_column(String(32), primary_key=True, comment="渠道名称")
    channel_type: Mapped[str] = mapped_column(String(16), comment="渠道类型 webhook 等")
    config_json: Mapped[Optional[dict]] = mapped_column(JSON, comment="渠道配置 JSON")
    min_level: Mapped[str] = mapped_column(String(8), default="INFO", comment="最低推送级别")
    enabled: Mapped[int] = mapped_column(SmallInteger, default=1, comment="是否启用 0/1")


# ----------------- 账户 / 持仓 / 订单 -----------------

class Account(Base):
    """资金账户。"""

    __tablename__ = "account"
    __table_args__ = {"comment": "资金账户"}

    id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="账户 ID")
    account_type: Mapped[str] = mapped_column(String(16), comment="账户类型 模拟或实盘")
    broker: Mapped[Optional[str]] = mapped_column(String(32), comment="券商或通道")
    total_asset: Mapped[float] = mapped_column(Numeric(20, 4), default=0, comment="总资产")
    cash: Mapped[float] = mapped_column(Numeric(20, 4), default=0, comment="可用现金")
    market_value: Mapped[float] = mapped_column(Numeric(20, 4), default=0, comment="持仓市值")
    frozen: Mapped[float] = mapped_column(Numeric(20, 4), default=0, comment="冻结资金")
    today_pnl: Mapped[float] = mapped_column(Numeric(20, 4), default=0, comment="当日盈亏")
    total_pnl: Mapped[float] = mapped_column(Numeric(20, 4), default=0, comment="累计盈亏")
    status: Mapped[str] = mapped_column(String(16), default="idle", comment="账户状态")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")


class Position(Base):
    """账户持仓。"""

    __tablename__ = "position"
    __table_args__ = {"comment": "持仓"}

    account_id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="账户 ID")
    symbol: Mapped[str] = mapped_column(String(16), primary_key=True, comment="证券代码")
    qty: Mapped[int] = mapped_column(Integer, default=0, comment="持仓数量")
    available: Mapped[int] = mapped_column(Integer, default=0, comment="可卖数量")
    cost_price: Mapped[float] = mapped_column(Numeric(12, 4), comment="成本价")
    last_price: Mapped[float] = mapped_column(Numeric(12, 4), comment="最新价")
    market_value: Mapped[float] = mapped_column(Numeric(20, 4), comment="持仓市值")
    pnl: Mapped[float] = mapped_column(Numeric(20, 4), default=0, comment="浮动盈亏")
    pnl_pct: Mapped[float] = mapped_column(Numeric(12, 6), default=0, comment="浮动盈亏比例")
    weight: Mapped[float] = mapped_column(Numeric(10, 6), default=0, comment="占组合权重")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")


class Order(Base):
    """委托单（表名 order 为 SQL 保留字）。"""

    __tablename__ = "order"
    __table_args__ = (
        Index("idx_ord_acct", "account_id"),
        Index("idx_ord_status", "status"),
        Index("idx_ord_ts", "ts"),
        {"comment": "委托单"},
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, comment="订单 ID")
    account_id: Mapped[str] = mapped_column(String(32), comment="账户 ID")
    strategy: Mapped[Optional[str]] = mapped_column(String(64), comment="来源策略")
    symbol: Mapped[str] = mapped_column(String(16), comment="标的代码")
    side: Mapped[str] = mapped_column(String(4), comment="买卖方向")
    order_type: Mapped[str] = mapped_column(String(16), default="MKT", comment="订单类型")
    qty: Mapped[int] = mapped_column(Integer, comment="委托数量")
    filled_qty: Mapped[int] = mapped_column(Integer, default=0, comment="已成交数量")
    price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), comment="委托价格")
    avg_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), comment="成交均价")
    status: Mapped[str] = mapped_column(String(16), default="pending", comment="订单状态")
    algo: Mapped[Optional[str]] = mapped_column(String(16), comment="算法单类型")
    algo_params: Mapped[Optional[dict]] = mapped_column(JSON, comment="算法参数")
    ts: Mapped[datetime] = mapped_column(DateTime, default=func.now(), comment="下单时间")
    approved_by: Mapped[Optional[str]] = mapped_column(String(32), comment="审批人")


class Fill(Base):
    """成交回报。"""

    __tablename__ = "fill"
    __table_args__ = (
        Index("idx_fill_order", "order_id"),
        Index("idx_fill_acct_ts", "account_id", "ts"),
        {"comment": "成交回报"},
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True, comment="成交主键")
    order_id: Mapped[str] = mapped_column(String(40), comment="关联委托 ID")
    account_id: Mapped[str] = mapped_column(String(32), comment="账户 ID")
    symbol: Mapped[str] = mapped_column(String(16), comment="标的代码")
    side: Mapped[str] = mapped_column(String(4), comment="买卖方向")
    qty: Mapped[int] = mapped_column(Integer, comment="成交数量")
    price: Mapped[float] = mapped_column(Numeric(12, 4), comment="成交价格")
    amount: Mapped[float] = mapped_column(Numeric(20, 4), comment="成交金额")
    fee: Mapped[float] = mapped_column(Numeric(12, 4), default=0, comment="手续费")
    ts: Mapped[datetime] = mapped_column(DateTime, default=func.now(), comment="成交时间")


class NavSnapshot(Base):
    """账户净值快照。"""

    __tablename__ = "nav_snapshot"
    __table_args__ = {"comment": "净值快照"}

    account_id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="账户 ID")
    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True, comment="快照时间")
    nav: Mapped[float] = mapped_column(Numeric(20, 8), comment="组合净值")
    benchmark: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), comment="基准净值")


# ----------------- 报告 -----------------

class Report(Base):
    """报告归档。"""

    __tablename__ = "report"
    __table_args__ = (
        Index("idx_rpt_type", "report_type"),
        Index("idx_rpt_created", "created_at"),
        {"comment": "报告归档"},
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="报告 ID")
    name: Mapped[str] = mapped_column(String(128), comment="报告标题")
    report_type: Mapped[str] = mapped_column(String(32), comment="报告类型")
    strategy: Mapped[Optional[str]] = mapped_column(String(64), comment="关联策略")
    start_date: Mapped[Optional[date]] = mapped_column(Date, comment="区间起始")
    end_date: Mapped[Optional[date]] = mapped_column(Date, comment="区间结束")
    total_return: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), comment="总收益率")
    sharpe: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), comment="夏普比率")
    max_drawdown: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), comment="最大回撤")
    payload_json: Mapped[Optional[str]] = mapped_column(Text, comment="完整内容 JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), comment="创建时间")
