"""QMT (迅投) 实盘网关：基于 XtQuant.xttrader。

环境要求：
- Windows 10/11 64位 + Python 3.10
- 券商提供的 MiniQMT 或 完整 QMT，且已登录
- ``pip install xtquant``（部分券商版本需要从 GitHub 安装）

注意：本模块导入时不强制依赖 xtquant，模块级 import 全部延迟到 connect()。
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Any, Callable

from ashare_quant.config import get
from ashare_quant.engine.event_driven.events import (
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)
from ashare_quant.execution.base_gateway import (
    BaseGateway,
    GatewayStatus,
    TickData,
)
from ashare_quant.logging_setup import logger


def _ensure_xtquant():
    try:
        from xtquant import xtconstant, xtdata  # type: ignore  # noqa: F401
        from xtquant.xttrader import XtQuantTrader  # type: ignore
        from xtquant.xttype import StockAccount  # type: ignore
        return xtconstant, xtdata, XtQuantTrader, StockAccount
    except ImportError as exc:
        raise ImportError(
            "未安装 xtquant，或当前环境不是 Windows + QMT 终端。\n"
            "请参考券商手册安装 MiniQMT 与 xtquant。"
        ) from exc


def _to_xt_code(symbol: str) -> str:
    """本项目格式 '600519.SH' → xtquant 期望的 '600519.SH'（恰好一致）。"""
    return symbol


def _xt_order_type(order: Order):
    from xtquant import xtconstant
    if order.order_type == OrderType.LIMIT:
        # 5: 限价单（深圳）；11：限价单（上海）
        suffix = order.symbol.split(".")[-1]
        return xtconstant.FIX_PRICE
    return xtconstant.LATEST_PRICE


def _xt_order_side(side: OrderSide):
    from xtquant import xtconstant
    return xtconstant.STOCK_BUY if side == OrderSide.BUY else xtconstant.STOCK_SELL


class QMTCallback:
    """xtquant 回调注入。"""

    def __init__(self, gateway: "QMTGateway") -> None:
        self.gw = gateway

    def on_disconnected(self):
        self.gw.status = GatewayStatus.DISCONNECTED
        logger.warning("QMT 连接断开")

    def on_stock_order(self, order):
        # 转成本项目 Order 状态
        local = self.gw._orders.get(str(order.order_id))
        if local:
            local.status = self._map_status(order.order_status)
            local.filled_qty = int(order.traded_volume)
            local.filled_price = float(order.traded_price) if order.traded_price else 0.0
            self.gw._emit_order(local)

    def on_stock_trade(self, trade):
        local = self.gw._orders.get(str(trade.order_id))
        if not local:
            return
        fill = Fill(
            order_id=local.order_id,
            symbol=local.symbol,
            trade_date=datetime.now(),
            side=local.side,
            quantity=int(trade.traded_volume),
            price=float(trade.traded_price),
            commission=0.0,  # QMT 不直接返回手续费，需要事后查询
        )
        self.gw._emit_fill(fill)

    @staticmethod
    def _map_status(xt_status: int) -> OrderStatus:
        # xt_status: 48 未成交 / 49 部成 / 50 全成 / 51 已撤 / 53 已拒
        return {
            48: OrderStatus.PENDING,
            49: OrderStatus.PARTIAL,
            50: OrderStatus.FILLED,
            51: OrderStatus.CANCELLED,
            53: OrderStatus.REJECTED,
        }.get(xt_status, OrderStatus.PENDING)


class QMTGateway(BaseGateway):
    """迅投 QMT 实盘网关。"""
    name = "qmt"

    def __init__(self) -> None:
        super().__init__()
        self._trader = None
        self._account = None
        self._account_id: str = ""
        self._orders: dict[str, Order] = {}
        self._lock = threading.Lock()

    # ------------------------ 连接 ------------------------
    def connect(self, qmt_path: str | None = None,
                account_id: str | None = None,
                account_type: str = "STOCK",
                session_id: int | None = None, **_: Any) -> bool:
        xtconstant, xtdata, XtQuantTrader, StockAccount = _ensure_xtquant()
        qmt_path = qmt_path or get("live.qmt_path")
        account_id = account_id or get("live.account_id")
        account_type = account_type or get("live.account_type", "STOCK")
        if not qmt_path or not account_id:
            raise RuntimeError("缺少 qmt_path 或 account_id 配置")

        sid = session_id or int(datetime.now().timestamp())
        self._trader = XtQuantTrader(qmt_path, sid)
        self._account = StockAccount(account_id, account_type)
        self._account_id = account_id
        cb = QMTCallback(self)
        self._trader.register_callback(cb)
        self._trader.start()

        ret = self._trader.connect()
        if ret != 0:
            self.status = GatewayStatus.ERROR
            raise RuntimeError(f"QMT 连接失败 code={ret}")
        ret = self._trader.subscribe(self._account)
        if ret != 0:
            self.status = GatewayStatus.ERROR
            raise RuntimeError(f"QMT 账户订阅失败 code={ret}")
        self.status = GatewayStatus.CONNECTED
        logger.info(f"QMT 连接成功，账户 {account_id}")
        return True

    def disconnect(self) -> None:
        if self._trader:
            try:
                self._trader.stop()
            except Exception:  # noqa: BLE001
                pass
        self.status = GatewayStatus.DISCONNECTED

    # ------------------------ 行情订阅（用 xtdata） ------------------------
    def subscribe(self, symbols: list[str]) -> None:
        from xtquant import xtdata  # type: ignore
        codes = [_to_xt_code(s) for s in symbols]
        xtdata.subscribe_quote(stock_code=codes, period="tick",
                                callback=self._on_xt_tick)

    def _on_xt_tick(self, data: dict) -> None:
        for sym, ticks in data.items():
            for t in ticks:
                tick = TickData(
                    symbol=sym,
                    timestamp=datetime.fromtimestamp(t.get("time", 0) / 1000),
                    last_price=float(t.get("lastPrice", 0)),
                    volume=float(t.get("volume", 0)),
                    amount=float(t.get("amount", 0)),
                )
                self._emit_tick(tick)

    # ------------------------ 下单 ------------------------
    def submit_order(self, order: Order) -> str:
        if self.status != GatewayStatus.CONNECTED:
            raise RuntimeError("未连接 QMT")
        with self._lock:
            xt_id = self._trader.order_stock(
                self._account,
                _to_xt_code(order.symbol),
                _xt_order_side(order.side),
                order.quantity,
                _xt_order_type(order),
                order.price or 0.0,
                "ashare-quant",
                order.order_id or uuid.uuid4().hex[:12],
            )
            order.order_id = str(xt_id)
            self._orders[order.order_id] = order
            self._emit_order(order)
        return order.order_id

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._trader.cancel_order_stock(self._account, int(order_id))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"撤单失败 {order_id}: {exc}")
            return False

    # ------------------------ 查询 ------------------------
    def query_positions(self) -> dict[str, dict]:
        if not self._trader:
            return {}
        positions = self._trader.query_stock_positions(self._account)
        out = {}
        for p in positions:
            out[p.stock_code] = {
                "quantity": int(p.volume),
                "available": int(p.can_use_volume),
                "avg_cost": float(p.avg_price),
                "last_price": 0.0,            # QMT 持仓不直接返回最新价，由行情侧补
                "market_value": float(p.market_value),
            }
        return out

    def query_account(self) -> dict:
        if not self._trader:
            return {}
        accs = self._trader.query_stock_asset(self._account)
        if not accs:
            return {}
        a = accs
        return {
            "cash": float(a.cash),
            "market_value": float(a.market_value),
            "nav": float(a.total_asset),
            "frozen_cash": float(a.frozen_cash),
        }
