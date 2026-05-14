"""LightGBM 横截面收益预测。

每个调仓日：
1. 用滚动窗口内的因子值（X）和未来 N 日收益（y）训练 LightGBM
2. 用最新一日的因子值预测下期收益
3. 选 Top-K 等权持有
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

import ashare_quant.factors.technical  # noqa: F401
from ashare_quant.factors import get_registry
from ashare_quant.factors.neutralize import winsorize_zscore
from ashare_quant.logging_setup import logger
from ashare_quant.strategies.base import BaseStrategy, StrategyContext


def _ensure_lightgbm():
    try:
        import lightgbm as lgb  # noqa: F401
        return lgb
    except ImportError as exc:
        raise ImportError("未安装 lightgbm：pip install lightgbm") from exc


class LightGBMCrossSectionStrategy(BaseStrategy):
    name = "lgbm_cs"
    rebalance_freq = "M"

    def __init__(self,
                 factors: Iterable[str] = ("mom_3m", "mom_6m", "rev_1m",
                                            "low_vol", "turnover_20d",
                                            "ma_cross", "rsi_14", "bbands_pos"),
                 train_window: int = 500,
                 forward_days: int = 21,
                 top_n: int = 20,
                 rebalance_freq: str = "M",
                 num_boost_round: int = 100):
        super().__init__(factors=list(factors), train_window=train_window,
                         forward_days=forward_days, top_n=top_n,
                         num_boost_round=num_boost_round)
        self.rebalance_freq = rebalance_freq

    def _build_panel(self, ctx: StrategyContext):
        close, op, high, low, vol, amt = {}, {}, {}, {}, {}, {}
        for sym, df in ctx.history.items():
            if df.empty:
                continue
            close[sym] = df["close"]
            op[sym] = df.get("open")
            high[sym] = df.get("high")
            low[sym] = df.get("low")
            vol[sym] = df.get("volume")
            amt[sym] = df.get("amount")
        return {
            "close": pd.DataFrame(close).sort_index(),
            "open": pd.DataFrame(op).sort_index(),
            "high": pd.DataFrame(high).sort_index(),
            "low": pd.DataFrame(low).sort_index(),
            "volume": pd.DataFrame(vol).sort_index(),
            "amount": pd.DataFrame(amt).sort_index(),
        }

    def _build_feature_matrix(self, panel) -> tuple[pd.DataFrame, pd.Series]:
        """把所有因子拼成 (T*N) × F 的 X，目标 y 为 N 日前向收益。"""
        reg = get_registry()
        feats = []
        for fname in self.params["factors"]:
            f = reg.get(fname)
            val = f.compute(panel)
            if val.empty:
                continue
            val = winsorize_zscore(val) * f.direction
            val = val.stack().rename(fname)
            feats.append(val)
        if not feats:
            return pd.DataFrame(), pd.Series(dtype=float)
        X = pd.concat(feats, axis=1).dropna()
        close = panel["close"]
        fwd = close.pct_change(self.params["forward_days"]).shift(-self.params["forward_days"])
        y = fwd.stack().rename("y")
        df = X.join(y, how="inner").dropna()
        return df.drop(columns=["y"]), df["y"]

    def on_rebalance(self, ctx: StrategyContext, bars):
        lgb = _ensure_lightgbm()
        panel = self._build_panel(ctx)
        if panel["close"].empty:
            return
        X, y = self._build_feature_matrix(panel)
        if X.empty:
            return
        # 用 train_window 日的窗口
        last_date = X.index.get_level_values(0).max()
        cutoff = last_date - pd.Timedelta(days=self.params["train_window"])
        mask = X.index.get_level_values(0) >= cutoff
        X_train, y_train = X[mask], y[mask]
        if len(X_train) < 200:
            logger.warning(f"训练样本不足 ({len(X_train)})，跳过 {last_date.date()}")
            return

        model = lgb.LGBMRegressor(
            n_estimators=self.params["num_boost_round"],
            learning_rate=0.05,
            max_depth=5,
            num_leaves=31,
            min_child_samples=30,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=-1,
        )
        model.fit(X_train, y_train)

        # 用最新一日所有股票预测
        latest_dt = X.index.get_level_values(0).max()
        X_pred = X.loc[latest_dt]
        preds = pd.Series(model.predict(X_pred), index=X_pred.index)
        chosen = preds.nlargest(self.params["top_n"]).index.tolist()

        per = 0.95 / max(len(chosen), 1)
        for sym in list(ctx.portfolio.positions):
            if sym not in chosen and ctx.portfolio.available_qty(sym) > 0 and sym in bars:
                ctx.order_target_pct(sym, 0.0, bars[sym].close)
        for sym in chosen:
            if sym in bars:
                ctx.order_target_pct(sym, per, bars[sym].open)

    def on_bar(self, ctx, bars):
        pass
