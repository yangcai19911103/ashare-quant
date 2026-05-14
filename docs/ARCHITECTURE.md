# 架构概览

```
                         ┌──────────────────────────────┐
                         │           UI 层               │
                         │ Streamlit / Dash / 企微钉钉   │
                         └──────────────▲───────────────┘
                                        │
   ┌────────────────────────────────────┼────────────────────────────────────┐
   │                                    │                                    │
┌──┴─────────────┐  ┌──────────────────┴──────────────────┐  ┌─────────────┴──┐
│  数据层         │  │       策略 / 引擎层                  │  │   执行层        │
│ ingest/        │→│  factors/  strategies/  engine/      │→ │  execution/    │
│ storage/       │  │     ▲                  ▲             │  │  sim/qmt/twap  │
│ calendar/      │  │     └────── risk/ ─────┘             │  └────────▲──────┘
└────────────────┘  └──────────────────────────────────────┘           │
                                                                       │
                                  ┌────────────────────────────────────┘
                                  │
                          ┌───────┴────────┐
                          │   live/         │
                          │ scheduler/runner│
                          │ alert/          │
                          └─────────────────┘
```

## 关键设计决策

### 1. 数据层
- **格式**：Parquet (列存 + 压缩 + 跨语言) + DuckDB（零运维 SQL）
- **粒度**：每只股票一个 parquet 文件，便于并发拉取/增量
- **adapter 抽象**：AkShare / Tushare / Mock / XtQuant 都实现 `BaseAdapter`
- **复权**：原始数据存"不复权 + adj_factor"，读取时按需变换

### 2. 因子层
- **基类 `Factor`**：所有因子提供 `compute(panel) -> DataFrame`
- **wide-format 面板**：`dict[field -> DataFrame(date×symbol)]`，向量化高效
- **direction**：正负方向自动对齐
- **注册表**：按短名引用 → 多策略复用

### 3. 引擎层
- **事件驱动**：精确刻画 A 股 T+1 / 涨跌停 / 停牌 / 费用模型
- **Qlib 适配**：因子研究 + ML 训练交给 Qlib（更专业）
- **VectorBT 适配**：CTA 参数扫描（5-10 倍速度）

### 4. 策略层
- **`BaseStrategy` 生命周期**：`on_start / on_bar / on_rebalance / on_end`
- **`StrategyContext`**：把 portfolio / broker / history / params 注入策略
- **`order_target_pct`**：自动算成 100 整数倍，处理 T+1 限制

### 5. 风控层
- **三道防线**：
  - 事前 `PreTradeRiskChecker`：单票/行业/流动性上限（拦截或裁减订单）
  - 事中 `PostTradeMonitor`：止损/止盈/单日亏损（产生告警）
  - 熔断 `halted`：组合最大回撤触发后停止下新单

### 6. 执行层
- **`BaseGateway`**：统一接口（connect/subscribe/submit/cancel/query）
- **`SimGateway`**：本地回放，用于模拟盘
- **`QMTGateway`**：xtquant 实盘
- **算法单**：TWAP / VWAP，把大单切成小单分批下出去

### 7. UI 层
- **Streamlit**：研究端，重交互
- **Dash**：实盘监控大屏，重稳定 / 实时

## 数据流（回测路径）

```
universe + history (Parquet)
        │
        ▼
factors/{N}.compute()   ────► factor panel (T×S)
        │
        ▼
strategy.on_rebalance(ctx, bars)
        │
        ├─ order_target_pct → SimBroker.pending_orders
        ▼
AshareMatcher.match(order, bar)
        │
   ┌────┴────┐
   ▼         ▼
 reject    Fill
              │
              ▼
       Portfolio.on_fill()
              │
              ▼
        nav_history
              │
              ▼
      BacktestResult.metrics()
```

## 数据流（实盘路径）

```
XtQuant tick stream
        │
        ▼
QMTGateway._on_xt_tick
        │
        ▼
StrategyRunner._on_tick / strategy.trigger()
        │
        ▼
PreTradeRiskChecker.check()
        │
        ▼
QMTGateway.submit_order()
        │
        ▼
xttrader.order_stock()  ──► 券商柜台
        │
        ▼
回报：QMTCallback.on_stock_trade
        │
        ▼
StrategyRunner._on_fill → PostTradeMonitor.update → alert()
```

## 扩展点

| 想做 | 在哪里加 |
|------|---------|
| 新数据源 | `data/ingest/<new>_adapter.py` 继承 `BaseAdapter` |
| 新因子   | `factors/<file>.py` 加 `@register` 装饰器 |
| 新策略   | `strategies/<category>/<name>.py`，注册到 `registry.py` |
| 新算法单 | `execution/algo/<name>.py` |
| 新网关   | `execution/<broker>_gateway.py` 继承 `BaseGateway` |
| 新风控规则 | `risk/pre_trade.py` 或 `risk/post_trade.py` |
