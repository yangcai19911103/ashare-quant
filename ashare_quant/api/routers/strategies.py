"""策略库路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import StrategyDef

router = APIRouter()


STRATEGIES_CATALOG = [
    {"cat": "mf", "name": "multi_factor.equal_weight",    "cn_name": "等权多因子",   "category": "多因子",  "freq": "月度",   "risk_level": "中",   "description": "多个因子等权合成，按截面排名等权配置头部股票。"},
    {"cat": "mf", "name": "multi_factor.ic_weighted",     "cn_name": "IC 加权多因子","category": "多因子",  "freq": "月度",   "risk_level": "中",   "description": "根据近 N 期 IC 动态计算因子权重。"},
    {"cat": "mf", "name": "multi_factor.value_quality",   "cn_name": "价值+质量",    "category": "多因子",  "freq": "季度",   "risk_level": "低",   "description": "低 PE/PB + 高 ROE / 利润增长。"},
    {"cat": "mf", "name": "multi_factor.momentum_reversal","cn_name": "动量+反转",   "category": "多因子",  "freq": "周度",   "risk_level": "中",   "description": "60d 动量 - 5d 反转双因子。"},
    {"cat": "mf", "name": "multi_factor.lowvol",          "cn_name": "低波动",       "category": "多因子",  "freq": "月度",   "risk_level": "低",   "description": "最低波动率股票组合。"},
    {"cat": "cta","name": "cta.dual_ma_cross",            "cn_name": "双均线",       "category": "CTA",     "freq": "日内",   "risk_level": "中",   "description": "5/20 日均线金叉买入死叉卖出。"},
    {"cat": "cta","name": "cta.macd",                     "cn_name": "MACD",         "category": "CTA",     "freq": "日内",   "risk_level": "中",   "description": "MACD 金叉 + 柱状图扩散。"},
    {"cat": "cta","name": "cta.bollinger_breakout",       "cn_name": "布林带突破",   "category": "CTA",     "freq": "日内",   "risk_level": "中",   "description": "突破上轨买入，回落中轨止盈。"},
    {"cat": "cta","name": "cta.dual_thrust",              "cn_name": "Dual Thrust",  "category": "CTA",     "freq": "日间",   "risk_level": "中高", "description": "波动幅度突破策略。"},
    {"cat": "cta","name": "cta.turtle",                   "cn_name": "海龟交易",     "category": "CTA",     "freq": "日间",   "risk_level": "中高", "description": "唐奇安通道 + ATR 仓位。"},
    {"cat": "cta","name": "cta.atr_channel",              "cn_name": "ATR 通道",     "category": "CTA",     "freq": "日间",   "risk_level": "中",   "description": "基于 ATR 自适应通道。"},
    {"cat": "arb","name": "stat_arb.pairs_trading",       "cn_name": "配对交易",     "category": "套利",    "freq": "日间",   "risk_level": "中",   "description": "协整对 z-score 偏离均值回归。"},
    {"cat": "arb","name": "stat_arb.etf_rotation",        "cn_name": "ETF 轮动",     "category": "套利",    "freq": "周度",   "risk_level": "低",   "description": "多 ETF 按动量轮动。"},
    {"cat": "event","name": "event.earnings_surprise",    "cn_name": "业绩超预期",   "category": "事件",    "freq": "事件",   "risk_level": "中",   "description": "季报 EPS 超预期 → 买入持有。"},
    {"cat": "event","name": "event.dragon_tiger",         "cn_name": "龙虎榜跟随",   "category": "事件",    "freq": "事件",   "risk_level": "高",   "description": "机构净买入榜首 → T+1 跟买。"},
    {"cat": "event","name": "event.north_flow",           "cn_name": "北向资金",     "category": "事件",    "freq": "日间",   "risk_level": "中",   "description": "连续 N 日大幅净流入 → 跟买。"},
    {"cat": "ml","name": "ml.lgbm_cs",                    "cn_name": "LightGBM 截面","category": "机器学习","freq": "周/月",  "risk_level": "中",   "description": "多因子作为特征，截面预测超额收益。"},
    {"cat": "ml","name": "ml.xgb_cs",                     "cn_name": "XGBoost 截面", "category": "机器学习","freq": "周/月",  "risk_level": "中",   "description": "XGBoost 截面回归。"},
    {"cat": "ml","name": "ml.lstm_ts",                    "cn_name": "LSTM 时序",    "category": "机器学习","freq": "日间",   "risk_level": "中高", "description": "股票级 LSTM 预测方向。"},
    {"cat": "rot","name": "rotation.industry_momentum",   "cn_name": "行业动量轮动", "category": "轮动",    "freq": "月度",   "risk_level": "中",   "description": "30 个申万一级行业按动量轮动。"},
    {"cat": "rot","name": "rotation.merrill_clock",       "cn_name": "美林时钟",     "category": "轮动",    "freq": "季度",   "risk_level": "低",   "description": "通胀 + 增长四象限切换。"},
    {"cat": "op","name": "portfolio.risk_parity",         "cn_name": "风险平价",     "category": "组合优化","freq": "月度",   "risk_level": "低",   "description": "各资产风险贡献相等。"},
]


@router.get("/")
def list_strategies(category: str | None = Query(None), db: Session = Depends(get_db)):
    rows = db.scalars(select(StrategyDef)).all()
    if rows:
        items = [{
            "name": r.name, "cn_name": r.cn_name, "category": r.category,
            "description": r.description, "freq": r.freq, "risk_level": r.risk_level,
            "default_params": r.default_params,
        } for r in rows]
    else:
        items = STRATEGIES_CATALOG
    if category and category != "all":
        items = [s for s in items if s.get("category") == category]
    return items


@router.get("/{name}")
def get_strategy(name: str, db: Session = Depends(get_db)):
    row = db.get(StrategyDef, name)
    if row:
        return {
            "name": row.name, "cn_name": row.cn_name, "category": row.category,
            "description": row.description, "freq": row.freq, "risk_level": row.risk_level,
            "default_params": row.default_params,
        }
    for s in STRATEGIES_CATALOG:
        if s["name"] == name:
            return s
    raise HTTPException(404, "strategy not found")
