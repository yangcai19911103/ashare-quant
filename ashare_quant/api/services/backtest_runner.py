"""回测后台任务。"""
from __future__ import annotations

import json
import random
import time
from datetime import datetime, timedelta, timezone

from loguru import logger

from ..database import SessionLocal
from ..models import BacktestNav, BacktestRun, BacktestTrade
from ..schemas import BacktestRequest
from ..utils import gen_price_series, metrics_from_nav


_TRADE_SYMBOLS = ("600519.SH", "000858.SZ", "601318.SH", "300750.SZ",
                  "000001.SZ", "600036.SH", "002594.SZ", "300059.SZ")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_trading_dates(req: BacktestRequest, min_days: int = 250) -> list[str]:
    days = max((req.end_date - req.start_date).days * 5 // 7, min_days)
    out: list[str] = []
    d = req.start_date
    while len(out) < days:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _gen_trades(dates: list[str], run_id: str, n: int = 20) -> list[dict]:
    rng = random.Random(run_id)
    trades = []
    for _ in range(n):
        d = dates[rng.randint(0, len(dates) - 1)]
        sym = rng.choice(_TRADE_SYMBOLS)
        side = rng.choice(["BUY", "SELL"])
        qty = rng.randint(1, 20) * 100
        price = round(rng.uniform(40, 1700), 2)
        trades.append({
            "trade_date": d, "symbol": sym, "side": side, "qty": qty,
            "price": price, "amount": qty * price,
            "fee": round(qty * price * 0.00025, 2),
        })
    return trades


def run_backtest_job(run_id: str, req: BacktestRequest, step_delay: float = 0.4) -> None:
    """生成 NAV 曲线 / 交易 / 指标并写库。"""
    session = SessionLocal()
    try:
        run = session.get(BacktestRun, run_id)
        if run is None:
            logger.warning(f"BacktestRun {run_id} 不存在，跳过")
            return
        run.status = "running"
        session.commit()

        dates = _build_trading_dates(req)
        seed = hash(run_id) & 0xFFFF
        nav = gen_price_series(len(dates), 1.0, 0.0008, 0.013, seed=seed)
        bench = gen_price_series(len(dates), 1.0, 0.0003, 0.011, seed=42)

        log_lines = ["> 加载数据...", f"> 初始化策略 {req.strategy}"]
        chunks = 10
        cs = len(dates) // chunks
        for ci in range(chunks):
            if step_delay > 0:
                time.sleep(step_delay)
            log_lines.append(f"> {dates[min(ci * cs, len(dates) - 1)]} 调仓 ✓")
            run = session.get(BacktestRun, run_id)
            if run is None:
                return
            run.progress = int((ci + 1) / chunks * 100)
            run.current_date_progress = datetime.fromisoformat(
                dates[min((ci + 1) * cs - 1, len(dates) - 1)]
            ).date()
            run.log = "\n".join(log_lines) + "\n"
            session.commit()

        m = metrics_from_nav(nav)
        trades = _gen_trades(dates, run_id)

        run = session.get(BacktestRun, run_id)
        if run is None:
            return
        run.status = "finished"
        run.progress = 100
        run.total_return = m["total_return"]
        run.annual_return = m["annual_return"]
        run.sharpe = m["sharpe"]
        run.max_drawdown = m["max_drawdown"]
        run.calmar = m["calmar"]
        run.win_rate = m["win_rate"]
        run.turnover = 3.2
        run.finished_at = _now()
        log_lines.append("> 回测完成 ✓")
        run.log = "\n".join(log_lines) + "\n"

        for d, v, b in zip(dates, nav, bench):
            session.add(BacktestNav(
                run_id=run_id, trade_date=datetime.fromisoformat(d).date(),
                nav=v, benchmark_nav=b,
            ))
        for t in trades:
            session.add(BacktestTrade(
                run_id=run_id, trade_date=datetime.fromisoformat(t["trade_date"]).date(),
                symbol=t["symbol"], side=t["side"], qty=t["qty"], price=t["price"],
                amount=t["amount"], fee=t["fee"],
            ))
        run.result_json = json.dumps({"trades_count": len(trades)})
        session.commit()
        logger.info(f"BacktestRun {run_id} 完成")
    except Exception as e:
        logger.exception(f"BacktestRun {run_id} 失败: {e}")
        session.rollback()
        try:
            run = session.get(BacktestRun, run_id)
            if run is not None:
                run.status = "failed"
                run.log = (run.log or "") + f"\nERROR: {e}\n"
                session.commit()
        except Exception:
            session.rollback()
    finally:
        session.close()
