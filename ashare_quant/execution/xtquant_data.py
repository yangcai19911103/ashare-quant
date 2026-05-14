"""XtQuant 行情订阅适配器（仅行情，不涉及交易）。

仅在 Windows + QMT/Mini QMT 已经登录时可用。模块导入时不强制依赖 xtquant。
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from ashare_quant.execution.base_gateway import TickData
from ashare_quant.logging_setup import logger


def _ensure_xtquant():
    try:
        from xtquant import xtdata  # type: ignore
        return xtdata
    except ImportError as exc:
        raise ImportError(
            "未安装 xtquant：本模块仅在 Windows + 已登录 QMT 时可用。"
        ) from exc


class XtquantDataFeed:
    """通过 XtQuant 订阅实时 Tick → 转发到回调。"""

    def __init__(self) -> None:
        self._xtdata = None
        self._on_tick: list[Callable[[TickData], None]] = []

    def connect(self) -> None:
        self._xtdata = _ensure_xtquant()
        logger.info("XtQuant 行情连接成功")

    def subscribe(self, symbols: list[str]) -> None:
        if self._xtdata is None:
            raise RuntimeError("未连接，请先 connect()")
        # xtquant 格式：'600519.SH'，本项目格式一致
        self._xtdata.subscribe_quote(stock_code=symbols, period="tick",
                                      callback=self._on_xt_tick)

    def on_tick(self, cb: Callable[[TickData], None]) -> None:
        self._on_tick.append(cb)

    def _on_xt_tick(self, data: dict) -> None:
        for sym, ticks in data.items():
            for t in ticks:
                tick = TickData(
                    symbol=sym,
                    timestamp=datetime.fromtimestamp(t.get("time", 0) / 1000),
                    last_price=float(t.get("lastPrice", 0)),
                    bid_price=float(t.get("bidPrice", [0])[0]) if t.get("bidPrice") else 0,
                    ask_price=float(t.get("askPrice", [0])[0]) if t.get("askPrice") else 0,
                    bid_volume=int(t.get("bidVol", [0])[0]) if t.get("bidVol") else 0,
                    ask_volume=int(t.get("askVol", [0])[0]) if t.get("askVol") else 0,
                    volume=float(t.get("volume", 0)),
                    amount=float(t.get("amount", 0)),
                )
                for cb in self._on_tick:
                    try:
                        cb(tick)
                    except Exception:  # noqa: BLE001
                        pass
