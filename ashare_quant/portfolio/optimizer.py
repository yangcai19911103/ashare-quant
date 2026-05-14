"""组合优化器：等权 / 风险平价 / 最小方差 / 均值方差 / Black-Litterman。

cvxpy 是可选依赖，缺失时退化为等权 / 风险平价的解析解。
"""
from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd


def _cov(returns: pd.DataFrame, shrinkage: float = 0.10) -> np.ndarray:
    """收益的协方差矩阵 + Ledoit-Wolf 简化收缩。"""
    cov = returns.cov().values
    if cov.size == 0:
        return cov
    n = cov.shape[0]
    target = np.eye(n) * np.trace(cov) / n
    return (1 - shrinkage) * cov + shrinkage * target


class PortfolioOptimizer:
    """支持多种组合优化方法。

    使用例：
        opt = PortfolioOptimizer(method='risk_parity')
        weights = opt.optimize(returns_df)
    """

    def __init__(self,
                 method: Literal["equal", "risk_parity", "min_var", "mvo",
                                 "black_litterman"] = "equal",
                 max_weight: float = 0.10,
                 risk_aversion: float = 5.0,
                 shrinkage: float = 0.10) -> None:
        self.method = method
        self.max_weight = max_weight
        self.risk_aversion = risk_aversion
        self.shrinkage = shrinkage

    # ------------------------ 主入口 ------------------------
    def optimize(self, returns: pd.DataFrame,
                 expected_returns: pd.Series | None = None,
                 views: dict | None = None) -> pd.Series:
        if returns.empty:
            return pd.Series(dtype=float)
        cols = returns.columns.tolist()
        n = len(cols)
        if n == 1:
            return pd.Series([1.0], index=cols)

        if self.method == "equal":
            w = np.ones(n) / n
        elif self.method == "risk_parity":
            w = self._risk_parity(returns)
        elif self.method == "min_var":
            w = self._min_variance(returns)
        elif self.method == "mvo":
            w = self._mean_variance(returns, expected_returns)
        elif self.method == "black_litterman":
            w = self._black_litterman(returns, views or {})
        else:
            raise ValueError(f"未知方法：{self.method}")

        # clip + 归一
        w = np.clip(w, 0, self.max_weight)
        if w.sum() == 0:
            w = np.ones(n) / n
        else:
            w = w / w.sum()
        return pd.Series(w, index=cols)

    # ------------------------ 算法 ------------------------
    def _risk_parity(self, returns: pd.DataFrame, max_iter: int = 200,
                      tol: float = 1e-6) -> np.ndarray:
        """等风险贡献：用 Newton 迭代求解。"""
        cov = _cov(returns, self.shrinkage)
        n = cov.shape[0]
        w = np.ones(n) / n
        target = 1.0 / n
        for _ in range(max_iter):
            port_vol = np.sqrt(w @ cov @ w)
            mrc = cov @ w / port_vol             # marginal risk contribution
            rc = w * mrc / port_vol              # risk contribution proportion
            diff = rc - target
            if np.abs(diff).max() < tol:
                break
            # 简单梯度更新
            grad = mrc - port_vol * target / w
            w = w - 0.01 * grad
            w = np.clip(w, 1e-6, None)
            w = w / w.sum()
        return w

    def _min_variance(self, returns: pd.DataFrame) -> np.ndarray:
        cov = _cov(returns, self.shrinkage)
        try:
            import cvxpy as cp
            n = cov.shape[0]
            w = cp.Variable(n)
            prob = cp.Problem(
                cp.Minimize(cp.quad_form(w, cov)),
                [cp.sum(w) == 1, w >= 0, w <= self.max_weight],
            )
            prob.solve()
            if w.value is None:
                return np.ones(n) / n
            return np.array(w.value).flatten()
        except ImportError:
            # 解析解（无约束）：w ∝ inv(cov) @ 1
            n = cov.shape[0]
            try:
                inv = np.linalg.pinv(cov)
                w = inv @ np.ones(n)
                w = np.clip(w, 0, None)
                if w.sum() == 0:
                    return np.ones(n) / n
                return w / w.sum()
            except Exception:
                return np.ones(n) / n

    def _mean_variance(self, returns: pd.DataFrame,
                       expected_returns: pd.Series | None) -> np.ndarray:
        cov = _cov(returns, self.shrinkage)
        n = cov.shape[0]
        if expected_returns is None:
            mu = returns.mean().values * 252
        else:
            mu = expected_returns.reindex(returns.columns).fillna(0).values
        try:
            import cvxpy as cp
            w = cp.Variable(n)
            obj = cp.Maximize(mu @ w - 0.5 * self.risk_aversion * cp.quad_form(w, cov))
            prob = cp.Problem(obj, [cp.sum(w) == 1, w >= 0, w <= self.max_weight])
            prob.solve()
            if w.value is None:
                return np.ones(n) / n
            return np.array(w.value).flatten()
        except ImportError:
            inv = np.linalg.pinv(cov + 1e-6 * np.eye(n))
            w = inv @ mu / self.risk_aversion
            w = np.clip(w, 0, None)
            return w / w.sum() if w.sum() > 0 else np.ones(n) / n

    def _black_litterman(self, returns: pd.DataFrame, views: dict) -> np.ndarray:
        """简化的 BL：先验 = 市值加权（这里退化为等权先验）。

        views: {symbol: expected_excess_return}
        """
        cov = _cov(returns, self.shrinkage)
        n = cov.shape[0]
        cols = returns.columns.tolist()
        tau = 0.05
        prior = np.ones(n) / n
        pi = self.risk_aversion * cov @ prior

        if views:
            P = np.zeros((len(views), n))
            Q = []
            for i, (sym, q) in enumerate(views.items()):
                if sym in cols:
                    P[i, cols.index(sym)] = 1.0
                    Q.append(q)
            Q = np.array(Q).reshape(-1, 1)
            omega = np.diag(np.diag(P @ (tau * cov) @ P.T))
            try:
                inv_term = np.linalg.pinv(
                    np.linalg.pinv(tau * cov) + P.T @ np.linalg.pinv(omega) @ P
                )
                mu_bl = inv_term @ (
                    np.linalg.pinv(tau * cov) @ pi + P.T @ np.linalg.pinv(omega) @ Q.flatten()
                )
            except Exception:
                mu_bl = pi
        else:
            mu_bl = pi
        return self._mean_variance(returns,
                                   pd.Series(mu_bl, index=cols))
