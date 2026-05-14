"""Factor 基类与注册机制。

设计：
- 每个 Factor 接收 wide-format 行情面板（dict[field -> DataFrame(date×symbol)]）
- 返回单个 wide-format 因子 DataFrame（date×symbol）
- 注册到全局 registry，便于按名引用、合成多因子
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd


class Factor(ABC):
    """因子基类。"""

    name: str = "base"
    direction: int = 1            # +1 越大越好；-1 越小越好
    category: str = "generic"     # value/quality/growth/momentum/reversal/volatility/sentiment

    def __init__(self, **params: Any) -> None:
        self.params = params

    @abstractmethod
    def compute(self, panel: dict[str, pd.DataFrame], **kwargs: Any) -> pd.DataFrame:
        """计算因子值（date×symbol）。"""

    # ------------------------ 工具 ------------------------
    @staticmethod
    def winsorize(df: pd.DataFrame, lower: float = 0.025,
                  upper: float = 0.975) -> pd.DataFrame:
        """按截面做缩尾。"""
        if df.empty:
            return df
        ql = df.quantile(lower, axis=1)
        qh = df.quantile(upper, axis=1)
        out = df.clip(lower=ql, upper=qh, axis=0)
        return out

    @staticmethod
    def zscore(df: pd.DataFrame) -> pd.DataFrame:
        """按截面做 z-score。"""
        if df.empty:
            return df
        mu = df.mean(axis=1)
        sd = df.std(axis=1).replace(0, np.nan)
        return df.sub(mu, axis=0).div(sd, axis=0)

    @staticmethod
    def rank_normalize(df: pd.DataFrame) -> pd.DataFrame:
        """按截面排名后转 [0,1]。"""
        if df.empty:
            return df
        return df.rank(axis=1, pct=True)

    def standardize(self, df: pd.DataFrame) -> pd.DataFrame:
        """缩尾 + zscore。"""
        return self.zscore(self.winsorize(df))

    def __repr__(self) -> str:
        params = ",".join(f"{k}={v}" for k, v in self.params.items())
        return f"<Factor {self.name}({params}) dir={self.direction:+d}>"


# =============================================================================
# 全局注册表
# =============================================================================
class FactorRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[..., Factor]] = {}

    def register(self, name: str | None = None):
        def deco(cls: type[Factor]):
            n = name or cls.name
            self._factories[n] = cls
            cls.name = n
            return cls
        return deco

    def get(self, name: str, **params) -> Factor:
        if name not in self._factories:
            raise KeyError(f"未注册的因子：{name}; 已注册：{list(self._factories)}")
        return self._factories[name](**params)

    def names(self) -> list[str]:
        return sorted(self._factories.keys())

    def by_category(self, category: str) -> list[str]:
        names = []
        for n, cls in self._factories.items():
            inst = cls()
            if inst.category == category:
                names.append(n)
        return sorted(names)


_REGISTRY = FactorRegistry()


def get_registry() -> FactorRegistry:
    return _REGISTRY


def register(name: str | None = None):
    return _REGISTRY.register(name)
