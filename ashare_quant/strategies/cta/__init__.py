"""CTA / 择时策略."""
from ashare_quant.strategies.cta.dual_ma import DualMACrossStrategy
from ashare_quant.strategies.cta.macd import MACDStrategy
from ashare_quant.strategies.cta.bollinger import BollingerBreakoutStrategy
from ashare_quant.strategies.cta.dual_thrust import DualThrustStrategy
from ashare_quant.strategies.cta.turtle import TurtleStrategy
from ashare_quant.strategies.cta.atr_channel import ATRChannelStrategy

__all__ = [
    "DualMACrossStrategy",
    "MACDStrategy",
    "BollingerBreakoutStrategy",
    "DualThrustStrategy",
    "TurtleStrategy",
    "ATRChannelStrategy",
]
