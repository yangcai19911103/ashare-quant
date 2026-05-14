"""Pydantic 请求 / 响应 schema 定义。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------- Overview ---------------

class KpiCard(BaseModel):
    label: str
    value: str
    delta: Optional[str] = None
    trend: Optional[str] = None  # up / down / flat


class OverviewResponse(BaseModel):
    kpis: List[KpiCard]
    nav_dates: List[str]
    nav_portfolio: List[float]
    nav_benchmark: List[float]
    industry: Dict[str, float]
    activities: List[Dict[str, Any]]
    strategies: List[Dict[str, Any]]
    health: Dict[str, float]


# --------------- Data ---------------

class DataSourceItem(ORMModel):
    name: str
    status: str
    quota_used: int = 0
    quota_limit: int = 0
    note: Optional[str] = None


class WarehouseStats(BaseModel):
    instruments: int
    daily_rows: int
    earliest: Optional[str]
    latest: Optional[str]
    missing: int
    size_mb: float


class DataInitRequest(BaseModel):
    start_date: date
    end_date: date
    sources: List[str] = ["akshare", "efinance"]
    workers: int = 6
    options: Dict[str, bool] = {}


class DataJobItem(ORMModel):
    id: int
    job_type: str
    status: str
    progress: int
    log: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class UniverseRequest(BaseModel):
    index_code: str = "000300.SH"
    trade_date: Optional[date] = None
    drop_st: bool = True
    drop_suspend: bool = True
    drop_new_60d: bool = True


class UniverseItem(BaseModel):
    symbol: str
    name: str
    industry: Optional[str] = None
    list_date: Optional[date] = None
    market_cap: Optional[float] = None
    last_price: Optional[float] = None
    pe_ttm: Optional[float] = None
    in_pool: bool = True


class CalendarQuery(BaseModel):
    date: date
    offset: int = 0


class SqlQuery(BaseModel):
    sql: str = Field(..., min_length=1, max_length=10000)


# --------------- Factors ---------------

class FactorComputeRequest(BaseModel):
    factor: str
    params: Dict[str, Any] = {}
    universe: str = "000300.SH"
    start_date: date
    end_date: date
    forward_window: int = 5
    neutralize: List[str] = []
    winsorize: bool = True
    zscore: bool = True


class FactorEvalResponse(BaseModel):
    factor: str
    ic_mean: float
    rank_ic_mean: float
    ic_ir: float
    ic_win_rate: float
    ls_annual: float
    ls_sharpe: float
    dates: List[str]
    ic: List[float]
    rank_ic: List[float]
    quantile_nav: Dict[str, List[float]]   # Q1..Q10
    monthly_ic: List[Dict[str, Any]]
    quantile_stats: List[Dict[str, Any]]


# --------------- Strategies ---------------

class StrategyItem(ORMModel):
    name: str
    cn_name: Optional[str]
    category: str
    description: Optional[str]
    freq: Optional[str]
    risk_level: Optional[str]
    default_params: Optional[dict]


# --------------- Backtest ---------------

class BacktestRequest(BaseModel):
    strategy: str
    engine: str = "event_driven"
    universe: str = "000300.SH"
    start_date: date
    end_date: date
    init_capital: float = 1_000_000
    benchmark: Optional[str] = "000300.SH"
    fee_bps: float = 2.5
    stamp_bps: float = 10.0
    slippage_bps: float = 2.0
    rebalance_freq: str = "M"
    params: Dict[str, Any] = {}


class BacktestStatus(BaseModel):
    id: str
    status: str
    progress: int
    current_date: Optional[str] = None
    log: Optional[str] = None


class BacktestResult(BaseModel):
    id: str
    strategy: str
    metrics: Dict[str, float]
    nav_dates: List[str]
    nav_portfolio: List[float]
    nav_benchmark: List[float]
    drawdown: List[float]
    monthly: List[Dict[str, Any]]
    industry: Dict[str, float]
    industry_bench: Dict[str, float]
    trades: List[Dict[str, Any]]


# --------------- Risk ---------------

class RiskAlert(ORMModel):
    id: int
    ts: datetime
    level: str
    source: str
    title: str
    message: Optional[str]
    resolved: int


class AttributionRow(BaseModel):
    sector: str
    allocation: float
    selection: float
    interaction: float
    total: float


# --------------- Portfolio ---------------

class OptimizeRequest(BaseModel):
    method: str = "rp"
    symbols: List[str]
    lookback_days: int = 252
    max_weight: float = 0.20
    min_weight: float = 0.0
    risk_aversion: float = 2.5
    long_only: bool = True


class OptimizeResponse(BaseModel):
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe: float
    risk_contrib: Dict[str, float]
    frontier: List[Dict[str, float]]


# --------------- Paper / Live ---------------

class StartPaperRequest(BaseModel):
    strategy: str
    init_capital: float = 1_000_000
    replay_mode: str = "live"  # live / x10 / x60 / historical
    start_date: Optional[date] = None
    universe: str = "000300.SH"


class ManualOrderRequest(BaseModel):
    account_id: str = "paper_default"
    symbol: str
    side: str  # BUY / SELL
    qty: int
    order_type: str = "MKT"
    price: Optional[float] = None
    algo: Optional[str] = None
    algo_params: Dict[str, Any] = {}


# --------------- Reports ---------------

class ReportItem(ORMModel):
    id: str
    name: str
    report_type: str
    strategy: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    total_return: Optional[float]
    sharpe: Optional[float]
    max_drawdown: Optional[float]
    created_at: datetime
