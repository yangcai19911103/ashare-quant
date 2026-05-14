"""多因子选股策略."""
from ashare_quant.strategies.multi_factor.equal_weight import EqualWeightMultiFactor
from ashare_quant.strategies.multi_factor.ic_weighted import ICWeightedMultiFactor
from ashare_quant.strategies.multi_factor.value_quality import ValueQualityStrategy
from ashare_quant.strategies.multi_factor.momentum_reversal import MomentumReversalStrategy
from ashare_quant.strategies.multi_factor.low_vol import LowVolStrategy

__all__ = [
    "EqualWeightMultiFactor",
    "ICWeightedMultiFactor",
    "ValueQualityStrategy",
    "MomentumReversalStrategy",
    "LowVolStrategy",
]
