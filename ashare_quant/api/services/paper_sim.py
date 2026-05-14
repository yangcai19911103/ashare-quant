"""模拟盘后台任务。

线程安全的全局状态：
    _sim_state.lock / _sim_state.running / _sim_state.thread
"""
from __future__ import annotations

import random
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Account, Fill, NavSnapshot, Order, Position
from ..utils import sample_universe

DEFAULT_PAPER_ACCOUNT = "paper_default"
_INIT_CAPITAL = 1_000_000.0


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class _SimState:
    running: bool = False
    thread: Optional[threading.Thread] = None
    lock: threading.Lock = threading.Lock()


_state = _SimState()


def is_paper_running() -> bool:
    return _state.running


def ensure_paper_account(session: Session, init_capital: Optional[float] = None) -> Account:
    """获取或创建默认模拟盘账户。"""
    acc = session.get(Account, DEFAULT_PAPER_ACCOUNT)
    if acc is None:
        cap = init_capital or _INIT_CAPITAL
        acc = Account(
            id=DEFAULT_PAPER_ACCOUNT, account_type="paper", broker="sim",
            total_asset=cap, cash=cap, market_value=0, frozen=0,
            today_pnl=0, total_pnl=0, status="idle",
        )
        session.add(acc)
        session.commit()
    return acc


def _seed_positions(session: Session, strategy: str) -> float:
    """自动建仓 6 只票，返回已用现金。"""
    symbols = sample_universe(6)
    spent = 0.0
    for info in symbols:
        sym = info["symbol"]
        qty = 1000
        price = info["last_price"]
        pos = session.get(Position, (DEFAULT_PAPER_ACCOUNT, sym))
        if pos is None:
            pos = Position(
                account_id=DEFAULT_PAPER_ACCOUNT, symbol=sym, qty=qty, available=0,
                cost_price=price, last_price=price, market_value=qty * price,
                pnl=0, pnl_pct=0, weight=0,
            )
            session.add(pos)
        order_id = uuid.uuid4().hex[:16]
        session.add(Order(
            id=order_id, account_id=DEFAULT_PAPER_ACCOUNT, strategy=strategy,
            symbol=sym, side="BUY", order_type="MKT", qty=qty,
            filled_qty=qty, avg_price=price, status="filled",
        ))
        session.add(Fill(
            order_id=order_id, account_id=DEFAULT_PAPER_ACCOUNT, symbol=sym,
            side="BUY", qty=qty, price=price, amount=qty * price,
            fee=round(qty * price * 0.00025, 2),
        ))
        spent += qty * price
    return spent


def _sim_worker(strategy: str, tick_seconds: float = 2.0) -> None:
    """模拟盘后台 tick：每 N 秒做一次价格漂移、写入 NAV 快照。"""
    session = SessionLocal()
    try:
        acc = ensure_paper_account(session)
        acc.status = "running"
        session.commit()

        spent = _seed_positions(session, strategy)
        acc.cash = max(0.0, float(acc.cash) - spent)
        session.commit()

        rng = random.Random()
        while _state.running:
            time.sleep(tick_seconds)
            positions = session.scalars(
                select(Position).where(Position.account_id == DEFAULT_PAPER_ACCOUNT)
            ).all()
            total_mv = 0.0
            for p in positions:
                new_price = float(p.last_price) * (1 + rng.gauss(0, 1) * 0.001)
                p.last_price = round(new_price, 4)
                p.market_value = round(new_price * p.qty, 4)
                p.pnl = round((new_price - float(p.cost_price)) * p.qty, 4)
                p.pnl_pct = round(new_price / float(p.cost_price) - 1, 6)
                total_mv += float(p.market_value)
            for p in positions:
                p.weight = round(float(p.market_value) / total_mv, 6) if total_mv > 0 else 0

            acc = session.get(Account, DEFAULT_PAPER_ACCOUNT)
            acc.market_value = round(total_mv, 4)
            acc.total_asset = round(float(acc.cash) + total_mv, 4)
            acc.total_pnl = round(float(acc.total_asset) - _INIT_CAPITAL, 4)
            acc.today_pnl = round(float(acc.total_asset) - _INIT_CAPITAL, 4)

            session.add(NavSnapshot(
                account_id=DEFAULT_PAPER_ACCOUNT, ts=_now(),
                nav=round(float(acc.total_asset) / _INIT_CAPITAL, 8),
                benchmark=1.0 + rng.gauss(0, 0.0005),
            ))
            session.commit()
    except Exception as e:
        logger.exception(f"paper sim worker 失败: {e}")
    finally:
        try:
            acc = session.get(Account, DEFAULT_PAPER_ACCOUNT)
            if acc is not None:
                acc.status = "idle"
                session.commit()
        except Exception:
            session.rollback()
        session.close()


def start_paper_sim(strategy: str) -> bool:
    """启动模拟盘线程，已在运行则返回 False。"""
    with _state.lock:
        if _state.running:
            return False
        _state.running = True
        _state.thread = threading.Thread(
            target=_sim_worker, args=(strategy,), daemon=True
        )
        _state.thread.start()
    return True


def stop_paper_sim() -> None:
    with _state.lock:
        _state.running = False
        _state.thread = None
