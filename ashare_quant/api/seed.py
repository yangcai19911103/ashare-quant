"""数据库 seed：填充演示数据。

仅在表为空时插入，已有数据则保留不动。
执行：
    python -m ashare_quant.api.seed
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from loguru import logger
from sqlalchemy import select

from .database import db_session, init_db
from .models import (Alert, AlertChannel, DataSource, FactorDef, FactorEval,
                     Instrument, RiskConfig, StrategyDef)
from .routers.factors import FACTOR_LIBRARY
from .routers.risk import DEFAULT_RISK
from .routers.strategies import STRATEGIES_CATALOG
from .utils import STOCK_POOL


def run_seed() -> None:
    logger.info("Seeding database with demo data ...")

    with db_session() as s:
        # data_source
        if s.scalar(select(DataSource).limit(1)) is None:
            for n, st, used, lim, note in [
                ("akshare",  "ok",  0,    0,    "免费"),
                ("tushare",  "ok",  1820, 5000, "积分受限"),
                ("efinance", "ok",  0,    0,    "兜底数据源"),
                ("xtquant",  "off", 0,    0,    "未连接 QMT"),
            ]:
                s.add(DataSource(name=n, status=st, quota_used=used, quota_limit=lim, note=note))

        # instruments
        if s.scalar(select(Instrument).limit(1)) is None:
            for sym, nm, ind, price, mc, pe in STOCK_POOL:
                exch = "SH" if sym.endswith(".SH") else "SZ"
                s.add(Instrument(
                    symbol=sym, name=nm, exchange=exch, industry=ind,
                    list_date=date(2010, 1, 1), is_st=0, status="L",
                    total_share=mc * 1e8,
                ))

        # factor_def
        if s.scalar(select(FactorDef).limit(1)) is None:
            for f in FACTOR_LIBRARY:
                s.add(FactorDef(name=f["name"], category=f["category"], direction=f["direction"]))
            # 默认 eval 指标
            today = date.today()
            preset_evals = {
                "momentum_20d": (0.054, 0.062, 0.82, 0.118, 1.42),
                "reversal_5d":  (-0.038, -0.044, 0.71, 0.084, 1.10),
                "volatility_20d": (-0.029, -0.035, 0.55, 0.062, 0.92),
                "turnover_20d": (-0.041, -0.046, 0.68, 0.078, 1.05),
                "pe_ttm":       (-0.032, -0.038, 0.50, 0.051, 0.88),
                "roe":          (0.048, 0.052, 0.78, 0.096, 1.21),
                "north_flow_5d": (0.026, 0.031, 0.45, 0.048, 0.85),
            }
            for fn, (ic, ric, ir, ls_ann, ls_sh) in preset_evals.items():
                s.add(FactorEval(
                    factor=fn, start_date=today - timedelta(days=365), end_date=today,
                    universe="000300.SH", ic_mean=ic, rank_ic_mean=ric, ic_ir=ir,
                    ic_win_rate=0.55, ls_annual=ls_ann, ls_sharpe=ls_sh,
                    ls_maxdd=-0.08,
                ))

        # strategy_def
        if s.scalar(select(StrategyDef).limit(1)) is None:
            for st in STRATEGIES_CATALOG:
                s.add(StrategyDef(
                    name=st["name"], cn_name=st["cn_name"], category=st["category"],
                    description=st["description"], freq=st["freq"], risk_level=st["risk_level"],
                ))

        # risk_config
        if s.scalar(select(RiskConfig).limit(1)) is None:
            for scope, conf in DEFAULT_RISK.items():
                s.add(RiskConfig(scope=scope, config_json=conf))

        # alert channels
        if s.scalar(select(AlertChannel).limit(1)) is None:
            for n, t, lvl, en in [
                ("企业微信 Webhook", "wechat", "INFO", 1),
                ("钉钉 Webhook", "dingtalk", "WARN", 1),
                ("邮件 SMTP", "email", "CRIT", 1),
                ("电话语音", "voice", "CRIT", 0),
                ("Slack", "slack", "INFO", 0),
            ]:
                s.add(AlertChannel(name=n, channel_type=t, min_level=lvl, enabled=en))

        # 一些示例告警
        if s.scalar(select(Alert).limit(1)) is None:
            now = datetime.now()
            for delta_min, lvl, src, title, msg in [
                (20,  "WARN", "in_trade",  "个股止损",     "600276.SH 浮亏 -10.4%, 已自动平仓"),
                (45,  "CRIT", "pre_trade", "行业暴露超标", "白酒行业占比 32% > 阈值 30%"),
                (60,  "INFO", "pre_trade", "盘前检查通过", "30 笔订单全部通过盘前风控"),
                (90,  "INFO", "execution", "成交确认",     "买入 000858.SZ × 2,000 @ 138.20"),
                (120, "INFO", "scheduler", "调仓完成",     "value_quality 季度调仓 30 只"),
            ]:
                s.add(Alert(ts=now - timedelta(minutes=delta_min), level=lvl,
                            source=src, title=title, message=msg))

    logger.info("Seeding done.")


def main():
    init_db(seed=False)
    run_seed()


if __name__ == "__main__":
    main()
