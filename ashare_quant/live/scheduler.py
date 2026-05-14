"""APScheduler 调度：盘前/盘中/盘后任务。"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ashare_quant.data.calendar import get_calendar
from ashare_quant.logging_setup import logger


class TradingScheduler:
    """A 股交易日调度器。"""

    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self.cal = get_calendar()

    def _guard(self, fn: Callable):
        """包装：自动跳过非交易日。"""
        def wrapped():
            today = datetime.today()
            if not self.cal.is_trade_day(today):
                logger.info(f"{today.date()} 非交易日，跳过 {fn.__name__}")
                return
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                logger.error(f"任务 {fn.__name__} 失败：{exc}")
        return wrapped

    def add(self, name: str, fn: Callable, *, hour: int, minute: int,
            day_of_week: str = "mon-fri", trade_day_only: bool = True) -> None:
        target = self._guard(fn) if trade_day_only else fn
        self.scheduler.add_job(
            target, CronTrigger(hour=hour, minute=minute, day_of_week=day_of_week),
            id=name, replace_existing=True, name=name,
        )
        logger.info(f"已注册任务 {name} @ {hour:02d}:{minute:02d}")

    def start(self) -> None:
        self.scheduler.start()

    def stop(self) -> None:
        self.scheduler.shutdown(wait=False)
