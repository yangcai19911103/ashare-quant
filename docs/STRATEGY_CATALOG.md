# 策略目录（30+ 内置策略）

## 命名规则

策略短名：`<类别>.<名称>`，例如 `multi_factor.value_quality`

通过 `aq-backtest list` 可获取最新列表。

## 1. 多因子选股（`multi_factor.*`）

| 短名 | 因子组合 | 调仓频率 | 适用风格 |
|------|---------|----------|----------|
| `multi_factor.equal_weight`     | 自定义     | 月       | 通用模板 |
| `multi_factor.ic_weighted`      | 自定义+IC权重 | 月    | 适应性更强 |
| `multi_factor.value_quality`    | 价值+质量 | 季 | 偏价值（巴菲特风格简化） |
| `multi_factor.momentum_reversal`| 动量+反转 | 月 | 趋势 + 中短期反转 |
| `multi_factor.low_vol`          | 低波+质量 | 月 | 防御型 |

**典型参数**：

```bash
aq-backtest run --strategy multi_factor.value_quality \
    --params '{"top_n": 30, "rebalance_freq": "Q"}'
```

## 2. CTA / 择时（`cta.*`）

| 短名 | 描述 | 调仓 |
|------|------|------|
| `cta.dual_ma`     | 双均线金叉死叉 | 日 |
| `cta.macd`        | MACD + 量能过滤 | 日 |
| `cta.bollinger`   | 布林带突破 / 回归 | 日 |
| `cta.dual_thrust` | Dual Thrust 区间突破 | 日 |
| `cta.turtle`      | 海龟交易（20日突破 + ATR头寸 + 2N止损） | 日 |
| `cta.atr_channel` | ATR 通道 | 日 |

## 3. 统计套利（`stat_arb.*`）

| 短名 | 描述 |
|------|------|
| `stat_arb.pairs`        | 配对交易（协整 + Z-score；A 股 only long） |
| `stat_arb.etf_rotation` | 行业 / 主题 ETF 动量轮动 |

## 4. 事件驱动（`event.*`）

| 短名 | 触发事件 | 数据依赖 |
|------|---------|----------|
| `event.earnings_surprise` | 业绩预增超阈值 | `events/earnings_forecast.parquet` |
| `event.dragon_tiger`      | 龙虎榜机构净买 | `events/dragon_tiger.parquet` |
| `event.north_flow`        | 北向资金加仓 Top | `money_flow/north_by_stock.parquet` |

## 5. 机器学习（`ml.*`）

| 短名 | 模型 | 备注 |
|------|------|------|
| `ml.lgbm_cs` | LightGBM 横截面回归 | 每月重训，预测下月收益 |

> TFT / PatchTST / LSTM / RL 留有扩展点（见 `strategies/ml/`），按需补全。

## 6. 行业轮动（`rotation.*`）

| 短名 | 描述 |
|------|------|
| `rotation.industry_momentum` | 行业 / 行业ETF 动量轮动 |
| `rotation.merrill_clock`     | 美林时钟简化版（需要宏观数据） |

## 自定义策略

继承 `BaseStrategy` 即可：

```python
from ashare_quant.strategies.base import BaseStrategy, StrategyContext


class MyStrategy(BaseStrategy):
    name = "my"
    rebalance_freq = "M"

    def __init__(self, top_n: int = 10):
        super().__init__(top_n=top_n)

    def on_rebalance(self, ctx: StrategyContext, bars):
        # 用 ctx.history 计算信号，调 ctx.order_target_pct(...) 下单
        ...

    def on_bar(self, ctx, bars):
        pass
```

注册到 `ashare_quant/strategies/registry.py` 的 `_STRATEGIES` 字典即可被 CLI / UI 调用。
