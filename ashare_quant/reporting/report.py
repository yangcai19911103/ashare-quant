"""统一回测报告：NAV / 指标 / 月度收益 / 交易明细 / 基准对比。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ashare_quant.config import project_root
from ashare_quant.data.storage import get_storage
from ashare_quant.engine.event_driven.engine import BacktestResult
from ashare_quant.logging_setup import logger


@dataclass
class BacktestReport:
    name: str
    nav: pd.Series
    metrics: dict[str, float]
    trades: pd.DataFrame
    benchmark_nav: pd.Series | None = None

    @property
    def returns(self) -> pd.Series:
        return self.nav.pct_change().dropna()

    def monthly_returns(self) -> pd.DataFrame:
        rets = self.returns
        if rets.empty:
            return pd.DataFrame()
        m = (1 + rets).resample("M").prod() - 1
        return m.to_frame("monthly_return")

    def alpha_vs_benchmark(self) -> dict[str, float]:
        if self.benchmark_nav is None or self.benchmark_nav.empty:
            return {}
        bench = self.benchmark_nav.reindex(self.nav.index).ffill()
        if bench.dropna().empty:
            return {}
        port = self.nav.pct_change().dropna()
        bench_r = bench.pct_change().dropna()
        common = port.index.intersection(bench_r.index)
        if len(common) < 30:
            return {}
        p = port.loc[common]
        b = bench_r.loc[common]
        cov = np.cov(p, b)[0, 1]
        var = b.var()
        beta = cov / var if var > 0 else float("nan")
        alpha_daily = p.mean() - beta * b.mean()
        ann_alpha = alpha_daily * 252
        excess = p - b
        info_ratio = excess.mean() / excess.std() * np.sqrt(252) if excess.std() > 0 else float("nan")
        return {
            "beta": float(beta),
            "ann_alpha": float(ann_alpha),
            "info_ratio": float(info_ratio),
            "excess_ann_return": float(((1 + excess).prod() ** (252 / len(excess)) - 1)),
        }

    def to_dict(self) -> dict:
        out = {
            "name": self.name,
            "metrics": self.metrics,
            "alpha_vs_benchmark": self.alpha_vs_benchmark(),
            "monthly_returns": self.monthly_returns().to_dict(orient="dict"),
            "n_trades": len(self.trades),
        }
        return out

    def save(self, out_dir: Path | str | None = None) -> Path:
        out_dir = Path(out_dir) if out_dir else project_root() / "reports" / self.name
        out_dir.mkdir(parents=True, exist_ok=True)
        self.nav.to_frame("nav").to_parquet(out_dir / "nav.parquet")
        self.trades.to_parquet(out_dir / "trades.parquet")
        pd.DataFrame(list(self.metrics.items()), columns=["metric", "value"]) \
          .to_csv(out_dir / "metrics.csv", index=False)
        logger.info(f"报告已保存到 {out_dir}")
        return out_dir


def _bench_nav(benchmark: str, start, end) -> pd.Series:
    df = get_storage().read_daily(benchmark, start=start, end=end, adjust="none")
    if df.empty:
        return pd.Series(dtype=float)
    df = df.set_index("trade_date").sort_index()
    return df["close"] / df["close"].iloc[0]


def generate_report(result: BacktestResult, name: str = "strategy") -> BacktestReport:
    nav = result.nav_series
    nav_norm = nav / max(nav.iloc[0], 1e-12) if len(nav) else nav

    fills = result.portfolio.fills_history
    if fills:
        trades = pd.DataFrame([{
            "trade_date": f.trade_date,
            "symbol": f.symbol,
            "side": f.side.value,
            "quantity": f.quantity,
            "price": f.price,
            "commission": f.commission,
            "stamp_duty": f.stamp_duty,
            "amount": f.gross_amount,
        } for f in fills])
    else:
        trades = pd.DataFrame()

    bench_nav = _bench_nav(result.benchmark, result.start, result.end)

    return BacktestReport(
        name=name,
        nav=nav_norm,
        metrics=result.metrics(),
        trades=trades,
        benchmark_nav=bench_nav,
    )
