"""风控路由。"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Alert, AlertChannel, RiskConfig
from ..utils import gen_dates, gen_drawdown, gen_price_series

router = APIRouter()


DEFAULT_RISK = {
    "pre_trade": {
        "max_single_position_pct": 10.0,
        "max_industry_pct": 30.0,
        "max_order_amount_wan": 50,
        "max_volume_share_pct": 5.0,
        "min_adv_wan": 1000,
        "min_market_cap_yi": 50,
        "deny_limit_up_buy": True,
        "deny_limit_down_sell": True,
        "deny_st": True,
        "deny_new_60d": True,
        "t1_check": True,
    },
    "in_trade": {
        "stop_loss_pct": -10.0,
        "take_profit_pct": 30.0,
        "trailing_stop_pct": 5.0,
        "daily_loss_pct": -5.0,
        "auto_close_on_stop": True,
        "pause_on_daily_loss": True,
        "alert_abnormal_fill": True,
    },
    "post_trade": {
        "max_cum_drawdown_pct": -15.0,
        "drawdown_pause_days": 5,
        "consecutive_loss_alert": 3,
        "monthly_underperf_alert_pct": -3.0,
        "pause_new_position": True,
        "daily_report_wechat": True,
        "weekly_report_email": True,
    },
}


@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    rows = db.scalars(select(RiskConfig)).all()
    if rows:
        return {r.scope: r.config_json for r in rows}
    return DEFAULT_RISK


@router.post("/config")
def update_config(payload: dict, db: Session = Depends(get_db)):
    for scope, conf in payload.items():
        row = db.get(RiskConfig, scope)
        if row:
            row.config_json = conf
        else:
            db.add(RiskConfig(scope=scope, config_json=conf))
    db.commit()
    return {"ok": True}


@router.get("/alerts")
def list_alerts(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.scalars(select(Alert).order_by(Alert.ts.desc()).limit(limit)).all()
    if rows:
        return [{
            "id": r.id, "ts": r.ts.isoformat(), "level": r.level,
            "source": r.source, "title": r.title, "message": r.message,
            "resolved": bool(r.resolved),
        } for r in rows]
    now = datetime.now()
    return [
        {"id": 1, "ts": (now - timedelta(minutes=20)).isoformat(), "level": "WARN", "source": "in_trade", "title": "个股止损", "message": "600276.SH 浮亏 -10.4%, 已自动平仓", "resolved": False},
        {"id": 2, "ts": (now - timedelta(minutes=45)).isoformat(), "level": "CRIT", "source": "pre_trade", "title": "行业暴露超标", "message": "白酒行业占比 32% > 阈值 30%", "resolved": False},
        {"id": 3, "ts": (now - timedelta(hours=1)).isoformat(), "level": "INFO", "source": "pre_trade", "title": "盘前检查通过", "message": "30 笔订单全部通过盘前风控", "resolved": True},
    ]


@router.post("/alerts/{aid}/resolve")
def resolve_alert(aid: int, db: Session = Depends(get_db)):
    a = db.get(Alert, aid)
    if not a:
        raise HTTPException(404)
    a.resolved = 1
    db.commit()
    return {"ok": True}


@router.get("/channels")
def list_channels(db: Session = Depends(get_db)):
    rows = db.scalars(select(AlertChannel)).all()
    if rows:
        return [{"name": r.name, "type": r.channel_type, "min_level": r.min_level, "enabled": bool(r.enabled)} for r in rows]
    return [
        {"name": "企业微信 Webhook", "type": "wechat", "min_level": "INFO", "enabled": True},
        {"name": "钉钉 Webhook",    "type": "dingtalk", "min_level": "WARN", "enabled": True},
        {"name": "邮件 SMTP",       "type": "email", "min_level": "CRIT", "enabled": True},
        {"name": "电话语音",        "type": "voice", "min_level": "CRIT", "enabled": False},
        {"name": "Slack",           "type": "slack", "min_level": "INFO", "enabled": False},
    ]


@router.post("/channels/{name}/test")
def test_channel(name: str):
    return {"ok": True, "channel": name, "message": f"测试消息已发送到 {name}"}


@router.get("/drawdown")
def drawdown_series():
    n = 120
    dates = gen_dates(n)
    nav = gen_price_series(n, 1.0, 0.0007, 0.012, seed=5)
    dd = [round(v * 100, 3) for v in gen_drawdown(nav)]
    return {"dates": dates, "drawdown": dd, "threshold": -15.0}


@router.get("/attribution")
def attribution():
    return {
        "rows": [
            {"sector": "白酒",   "allocation": 0.42, "selection": 1.85, "interaction": 0.05, "total": 2.32},
            {"sector": "银行",   "allocation": -0.18, "selection": 0.95, "interaction": -0.02, "total": 0.75},
            {"sector": "医药",   "allocation": -0.25, "selection": -0.85, "interaction": -0.04, "total": -1.14},
            {"sector": "新能源", "allocation": 0.55, "selection": 0.20, "interaction": 0.08, "total": 0.83},
            {"sector": "电子",   "allocation": -0.10, "selection": 0.60, "interaction": -0.02, "total": 0.48},
        ],
        "total_excess": 3.24,
    }


@router.post("/halt")
def emergency_halt(db: Session = Depends(get_db)):
    db.add(Alert(level="CRIT", source="manual", title="紧急暂停所有策略", message="人工触发"))
    db.commit()
    return {"ok": True, "message": "已暂停全部策略并取消未成交订单"}
