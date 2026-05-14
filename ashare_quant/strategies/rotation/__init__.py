"""行业轮动 / 风格轮动 / 大类资产配置."""
from ashare_quant.strategies.rotation.industry_momentum import IndustryMomentumRotation
from ashare_quant.strategies.rotation.merrill_clock import MerrillClockStrategy

__all__ = ["IndustryMomentumRotation", "MerrillClockStrategy"]
