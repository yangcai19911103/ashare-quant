"""数据初始化后台任务。

完成进度模拟后，将演示用行情 / 日历 / 指数成分等写入 MySQL（可重复执行：先删区间内本批标的的日 K 再插入）。
"""
from __future__ import annotations

import random
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import DailyBar, DataJob, Fundamental, IndexMember, Instrument, TradeCalendar
from ..utils import STOCK_POOL, gen_price_series

_MAX_TRADING_DAYS = 2600
_CHUNK = 1000


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_date(val: Any) -> date:
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return date.fromisoformat(val[:10])
    raise ValueError(f"无法解析日期: {val!r}")


# 步骤模板（不含「完成」——落库后再写）
_STEPS = [
    "[1/5] 拉取全市场股票列表... 5247 只",
    "[2/5] 构建指数成分 HS300/ZZ500/ZZ800/ZZ1000",
    "[3/5] 拉取日 K 数据 (workers={workers})...",
    "[4/5] 拉取北向资金 / 龙虎榜 / 财报快报",
    "[5/5] 写入 MySQL daily_bar / fundamental",
]


def _weekday_trade_dates(start: date, end: date) -> list[date]:
    if start > end:
        start, end = end, start
    out: list[date] = []
    d = start
    while d <= end and len(out) < _MAX_TRADING_DAYS:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _materialize_demo_market_data(session: Session, params: dict) -> tuple[int, int, str]:
    """写入演示级日 K、交易日历、沪深300成分占位、简易财报。

    返回 (daily_bar 行数, trade_calendar 行数, 说明文本)。
    """
    start = _parse_date(params.get("start_date"))
    end = _parse_date(params.get("end_date"))
    days = _weekday_trade_dates(start, end)
    if not days:
        return 0, 0, "日期区间内无工作日，跳过落库"

    symbols = list(session.scalars(select(Instrument.symbol)).all())
    if not symbols:
        for sym, nm, ind, price, mc, _pe in STOCK_POOL:
            exch = "SH" if sym.endswith(".SH") else "SZ"
            session.merge(
                Instrument(
                    symbol=sym,
                    name=nm,
                    exchange=exch,
                    industry=ind,
                    list_date=date(2010, 1, 1),
                    is_st=0,
                    status="L",
                    total_share=mc * 1e8,
                )
            )
        session.flush()
        symbols = [t[0] for t in STOCK_POOL]

    price_lookup = {t[0]: float(t[3]) for t in STOCK_POOL}

    # 同一区间内重复 init：删掉本批标的日 K，避免主键冲突
    session.execute(
        delete(DailyBar).where(
            DailyBar.symbol.in_(symbols),
            DailyBar.trade_date >= days[0],
            DailyBar.trade_date <= days[-1],
        )
    )
    session.execute(
        delete(IndexMember).where(
            IndexMember.index_code == "000300.SH",
            IndexMember.symbol.in_(symbols),
        )
    )

    n_cal = 0
    for d in days:
        session.merge(TradeCalendar(trade_date=d, exchange="SSE", is_open=1))
        n_cal += 1

    w = round(1.0 / len(symbols), 6) if symbols else None
    for sym in symbols:
        session.add(
            IndexMember(
                index_code="000300.SH",
                symbol=sym,
                in_date=days[0],
                out_date=None,
                weight=w,
            )
        )

    n_bar = 0
    batch: list[DailyBar] = []
    for sym in symbols:
        base = price_lookup.get(sym, 50.0)
        rng = random.Random(hash(sym) % (2**32))
        seed = hash(sym) & 0xFFFFFFFF
        rel = gen_price_series(len(days), 1.0, 0.0006, 0.012, seed=seed)
        scale = base / rel[-1] if rel[-1] else 1.0
        closes = [round(x * scale, 4) for x in rel]
        prev_close = closes[0]
        for i, d in enumerate(days):
            c = closes[i]
            o = prev_close
            noise = 0.004
            hi = max(o, c) * (1 + rng.random() * noise)
            lo = min(o, c) * (1 - rng.random() * noise)
            vol = int(rng.uniform(0.4e6, 4.5e6))
            amt = round(c * vol, 2)
            pre = prev_close
            pct = round((c / pre - 1) * 100, 4) if pre else 0.0
            batch.append(
                DailyBar(
                    symbol=sym,
                    trade_date=d,
                    open=round(o, 4),
                    high=round(hi, 4),
                    low=round(lo, 4),
                    close=c,
                    pre_close=round(pre, 4),
                    volume=vol,
                    amount=amt,
                    turnover=round(rng.uniform(0.005, 0.03), 6),
                    pct_chg=pct,
                    adj_factor=1.0,
                )
            )
            prev_close = c
            n_bar += 1
            if len(batch) >= _CHUNK:
                session.add_all(batch)
                session.flush()
                batch.clear()
    if batch:
        session.add_all(batch)

    # 简易财报占位（便于 /api/data/query 有数据）
    for sym, _nm, _ind, _price, mc, pe in STOCK_POOL:
        if sym not in symbols:
            continue
        frng = random.Random(hash(sym) % (2**32))
        session.merge(
            Fundamental(
                symbol=sym,
                report_date=end,
                ann_date=end,
                pe_ttm=pe,
                pb=round(pe * 0.35, 4),
                ps_ttm=round(pe * 0.5, 4),
                roe=round(frng.uniform(0.08, 0.22), 6),
                roa=round(frng.uniform(0.03, 0.12), 6),
                net_profit=round(mc * 1e6, 4),
                net_profit_yoy=round(frng.uniform(-0.05, 0.25), 6),
                revenue_yoy=round(frng.uniform(-0.02, 0.18), 6),
                market_cap=round(mc * 1e8, 4),
            )
        )

    session.flush()
    msg = f"标的={len(symbols)} 交易日={len(days)} 区间={days[0]}~{days[-1]}"
    logger.info(f"data_init 落库: daily_bar={n_bar}, trade_calendar={n_cal}, {msg}")
    return n_bar, n_cal, msg


def run_data_init_job(job_id: int, params: dict, step_delay: float = 1.0) -> None:
    """后台数据初始化：先跑进度条，再写入可查询的演示行情数据。

    Args:
        job_id: data_job 主键
        params: 启动参数字典（需含 ``start_date`` / ``end_date``，可选 ``workers``）
        step_delay: 每步等待秒（测试时可置 0）
    """
    workers = params.get("workers", 4)
    steps = [s.format(workers=workers) for s in _STEPS]
    session = SessionLocal()
    try:
        job = session.get(DataJob, job_id)
        if job is None:
            logger.warning(f"DataJob #{job_id} 不存在，跳过")
            return
        job.status = "running"
        job.started_at = _now()
        session.commit()

        log_buf: list[str] = []
        for i, line in enumerate(steps, 1):
            if step_delay > 0:
                time.sleep(step_delay)
            log_buf.append(line)
            job = session.get(DataJob, job_id)
            if job is None:
                return
            job.progress = int(i / (len(steps) + 1) * 100)
            job.log = "\n".join(log_buf) + "\n"
            session.commit()

        n_bars, n_cal, extra = _materialize_demo_market_data(session, params)
        log_buf.append(f"[落库] daily_bar={n_bars} 行, trade_calendar={n_cal} 行 | {extra}")
        log_buf.append("完成 ✓")

        job = session.get(DataJob, job_id)
        if job is not None:
            job.progress = 100
            job.log = "\n".join(log_buf) + "\n"
            job.status = "success"
            job.finished_at = _now()
            session.commit()
        logger.info(f"DataJob #{job_id} 初始化完成")
    except Exception as e:
        logger.exception(f"DataJob #{job_id} 失败: {e}")
        try:
            job = session.get(DataJob, job_id)
            if job is not None:
                job.status = "failed"
                job.log = (job.log or "") + f"\nERROR: {e}\n"
                job.finished_at = _now()
                session.commit()
        except Exception:
            session.rollback()
    finally:
        session.close()
