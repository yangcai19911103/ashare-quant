"""事件驱动回测引擎主循环。

工作流（每个交易日）：
1. ``on_open``: 释放昨日 T+1 锁仓
2. ``on_rebalance``（若是调仓日）：策略决定目标组合 → 下单
3. ``on_bar``: 策略可下单（CTA 类）
4. ``process_bars``: 撮合所有 pending 订单
5. ``on_close``: 更新最新价、记录 NAV
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

import pandas as pd
from tqdm import tqdm

from ashare_quant.config import get
from ashare_quant.data.calendar import get_calendar
from ashare_quant.data.storage import get_storage
from ashare_quant.engine.event_driven.broker_sim import SimBroker
from ashare_quant.engine.event_driven.events import Bar
from ashare_quant.engine.event_driven.matcher import AshareMatcher, FeeModel
from ashare_quant.engine.event_driven.portfolio import Portfolio
from ashare_quant.logging_setup import logger
from ashare_quant.strategies.base import BaseStrategy, StrategyContext


_FREQ_TO_OFFSET = {
    "D": None,
    "W": "W-FRI",
    "M": "BM",          # 月末
    "Q": "BQ",          # 季末
}


class BacktestEngine:
    """事件驱动回测引擎。"""

    def __init__(
        self,
        strategy: BaseStrategy,
        universe: list[str] | None = None,
        start: Any | None = None,
        end: Any | None = None,
        initial_cash: float | None = None,
        benchmark: str | None = None,
        adjust: str = "qfq",
        fee_model: FeeModel | None = None,
        trade_price: str = "next_open",
        rebalance_freq: str | None = None,
    ) -> None:
        self.strategy = strategy
        self.universe = universe or []
        self.start = pd.Timestamp(start or get("backtest.start", "2020-01-01"))
        self.end = pd.Timestamp(end or get("backtest.end", "2024-12-31"))
        self.initial_cash = float(initial_cash or get("backtest.initial_cash", 1e6))
        self.benchmark = benchmark or get("backtest.benchmark", "000300.SH")
        self.adjust = adjust
        self.trade_price = trade_price or get("backtest.trade_price", "next_open")
        self.rebalance_freq = (rebalance_freq or strategy.rebalance_freq
                               or get("backtest.rebalance_freq", "D"))

        # 组件
        self.portfolio = Portfolio(initial_cash=self.initial_cash)
        self.matcher = AshareMatcher(fee_model=fee_model, trade_price=self.trade_price)
        self.broker = SimBroker(self.portfolio, self.matcher)
        self.cal = get_calendar()

        # 缓存：每只股票的整段历史 DataFrame
        self._cache: dict[str, pd.DataFrame] = {}

    # ------------------------ 数据装载 ------------------------
    def _load_history(self) -> None:
        storage = get_storage()
        logger.info(f"加载历史数据：{len(self.universe)} 只 ({self.start.date()}~{self.end.date()})")
        for sym in self.universe:
            df = storage.read_daily(sym, start=self.start - pd.Timedelta(days=400),
                                    end=self.end, adjust=self.adjust)
            if df.empty:
                continue
            df = df.set_index("trade_date").sort_index()
            self._cache[sym] = df

    def _rebalance_days(self, trade_days: pd.DatetimeIndex) -> set[pd.Timestamp]:
        rule = _FREQ_TO_OFFSET.get(self.rebalance_freq.upper())
        if rule is None:
            return set(trade_days)
        marks = pd.date_range(self.start, self.end, freq=rule)
        # 把每个周期端点对齐到最近的交易日
        out: set[pd.Timestamp] = set()
        for m in marks:
            idx = trade_days.searchsorted(m, side="right") - 1
            if 0 <= idx < len(trade_days):
                out.add(trade_days[idx])
        return out

    # ------------------------ Bar 构造 ------------------------
    def _build_bars(self, dt: pd.Timestamp) -> dict[str, Bar]:
        bars: dict[str, Bar] = {}
        for sym, df in self._cache.items():
            if dt not in df.index:
                continue
            row = df.loc[dt]
            # 取前一天的 close（注意 prev_idx<0 时不要被 -1 索引到末尾）
            pos = df.index.searchsorted(dt)
            prev_close = float(df.iloc[pos - 1]["close"]) if pos >= 1 else None
            bars[sym] = Bar(
                symbol=sym,
                trade_date=dt.to_pydatetime(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0)),
                amount=float(row.get("amount", 0)),
                pct_chg=float(row.get("pct_chg", 0)),
                prev_close=prev_close,
            )
        return bars

    def _history_up_to(self, dt: pd.Timestamp) -> dict[str, pd.DataFrame]:
        return {sym: df.loc[:dt] for sym, df in self._cache.items()}

    # ------------------------ 主循环 ------------------------
    def run(self) -> "BacktestResult":
        self._load_history()
        if not self._cache:
            raise RuntimeError("universe 全部数据缺失")

        trade_days = self.cal.trade_days_between(self.start, self.end)
        if len(trade_days) == 0:
            raise RuntimeError("起止区间没有交易日")
        rebal_set = self._rebalance_days(trade_days)

        ctx = StrategyContext(
            trade_date=trade_days[0].to_pydatetime(),
            portfolio=self.portfolio,
            broker=self.broker,
            universe=self.universe,
            history={},
            params=self.strategy.params,
        )
        self.strategy.on_start(ctx)

        logger.info(f"开始回测：{len(trade_days)} 个交易日，调仓 {len(rebal_set)} 次")
        for dt in tqdm(trade_days, desc="backtest", ncols=80):
            ctx.trade_date = dt.to_pydatetime()
            self.portfolio.on_open(ctx.trade_date)

            bars = self._build_bars(dt)
            if not bars:
                continue
            ctx.history = self._history_up_to(dt)

            # 调仓
            if dt in rebal_set:
                try:
                    self.strategy.on_rebalance(ctx, bars)
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"on_rebalance 失败 {dt.date()}: {exc}")

            # 普通 Bar
            try:
                self.strategy.on_bar(ctx, bars)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"on_bar 失败 {dt.date()}: {exc}")

            self.broker.process_bars(bars)
            last_prices = {s: b.close for s, b in bars.items()}
            self.portfolio.on_close(ctx.trade_date, last_prices)

        self.strategy.on_end(ctx)
        return BacktestResult(self.portfolio, self.benchmark, self.start, self.end)


# =============================================================================
# 回测结果
# =============================================================================
class BacktestResult:
    def __init__(self, portfolio: Portfolio, benchmark: str,
                 start: pd.Timestamp, end: pd.Timestamp) -> None:
        self.portfolio = portfolio
        self.benchmark = benchmark
        self.start = start
        self.end = end

    @property
    def nav_series(self) -> pd.Series:
        if not self.portfolio.nav_history:
            return pd.Series(dtype=float)
        idx = [d for d, _ in self.portfolio.nav_history]
        vals = [v for _, v in self.portfolio.nav_history]
        return pd.Series(vals, index=pd.DatetimeIndex(idx))

    @property
    def returns(self) -> pd.Series:
        return self.nav_series.pct_change().dropna()

    def metrics(self) -> dict[str, float]:
        import numpy as np
        nav = self.nav_series
        if len(nav) < 2:
            return {}
        rets = nav.pct_change().dropna()
        n_days = len(rets)
        total_return = nav.iloc[-1] / nav.iloc[0] - 1
        ann_ret = (1 + total_return) ** (252 / max(n_days, 1)) - 1
        ann_vol = rets.std() * np.sqrt(252)
        sharpe = ann_ret / max(ann_vol, 1e-12)
        cum = nav / nav.iloc[0]
        dd = cum / cum.cummax() - 1
        max_dd = dd.min()
        calmar = ann_ret / abs(max_dd) if max_dd < 0 else float("nan")
        win = (rets > 0).mean()
        n_trades = len(self.portfolio.fills_history)
        return {
            "total_return": float(total_return),
            "ann_return": float(ann_ret),
            "ann_vol": float(ann_vol),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_dd),
            "calmar": float(calmar),
            "win_rate": float(win),
            "n_trades": n_trades,
            "final_nav": float(nav.iloc[-1]),
        }

    def report(self) -> pd.DataFrame:
        m = self.metrics()
        return pd.DataFrame(list(m.items()), columns=["metric", "value"])
