"""统计套利策略."""
from ashare_quant.strategies.stat_arb.pairs_trading import PairsTradingStrategy
from ashare_quant.strategies.stat_arb.etf_rotation import ETFRotationStrategy

__all__ = ["PairsTradingStrategy", "ETFRotationStrategy"]
