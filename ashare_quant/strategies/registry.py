"""策略注册表：按短名（如 'multi_factor.value_quality'）解析到具体类。"""
from __future__ import annotations

from typing import Type

from ashare_quant.strategies.base import BaseStrategy


# 触发各子模块的注册
from ashare_quant.strategies.multi_factor import (
    EqualWeightMultiFactor,
    ICWeightedMultiFactor,
    ValueQualityStrategy,
    MomentumReversalStrategy,
    LowVolStrategy,
)
from ashare_quant.strategies.cta import (
    DualMACrossStrategy,
    MACDStrategy,
    BollingerBreakoutStrategy,
    DualThrustStrategy,
    TurtleStrategy,
    ATRChannelStrategy,
)
from ashare_quant.strategies.stat_arb import (
    PairsTradingStrategy,
    ETFRotationStrategy,
)
from ashare_quant.strategies.event_driven import (
    EarningsSurpriseStrategy,
    DragonTigerFollowStrategy,
    NorthFlowStrategy,
)
from ashare_quant.strategies.rotation import (
    IndustryMomentumRotation,
    MerrillClockStrategy,
)


_STRATEGIES: dict[str, Type[BaseStrategy]] = {
    # 多因子
    "multi_factor.equal_weight": EqualWeightMultiFactor,
    "multi_factor.ic_weighted": ICWeightedMultiFactor,
    "multi_factor.value_quality": ValueQualityStrategy,
    "multi_factor.momentum_reversal": MomentumReversalStrategy,
    "multi_factor.low_vol": LowVolStrategy,
    # CTA
    "cta.dual_ma": DualMACrossStrategy,
    "cta.macd": MACDStrategy,
    "cta.bollinger": BollingerBreakoutStrategy,
    "cta.dual_thrust": DualThrustStrategy,
    "cta.turtle": TurtleStrategy,
    "cta.atr_channel": ATRChannelStrategy,
    # 统计套利
    "stat_arb.pairs": PairsTradingStrategy,
    "stat_arb.etf_rotation": ETFRotationStrategy,
    # 事件驱动
    "event.earnings_surprise": EarningsSurpriseStrategy,
    "event.dragon_tiger": DragonTigerFollowStrategy,
    "event.north_flow": NorthFlowStrategy,
    # 行业轮动
    "rotation.industry_momentum": IndustryMomentumRotation,
    "rotation.merrill_clock": MerrillClockStrategy,
}

# 机器学习单列（lightgbm 是可选依赖）
try:
    from ashare_quant.strategies.ml import LightGBMCrossSectionStrategy
    _STRATEGIES["ml.lgbm_cs"] = LightGBMCrossSectionStrategy
except ImportError:
    pass


def list_strategies() -> list[str]:
    return sorted(_STRATEGIES.keys())


def get_strategy(name: str) -> Type[BaseStrategy]:
    if name not in _STRATEGIES:
        raise KeyError(f"未知策略：{name}\n可用：{list_strategies()}")
    return _STRATEGIES[name]


def create_strategy(name: str, **params) -> BaseStrategy:
    cls = get_strategy(name)
    return cls(**params)
