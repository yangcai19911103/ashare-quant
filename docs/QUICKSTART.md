# 快速上手

## 环境

- Python 3.10 / 3.11（推荐 3.10）
- Windows / Linux / macOS（QMT 实盘仅 Windows）

## 安装

```bash
# 1. 创建并激活虚拟环境
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2. 安装核心 + 常用扩展
pip install -e .[ml,opt,ui,dev]
```

## 第一次跑（用 mock 数据，无需网络）

```bash
# 运行单元测试，确认环境就绪
pytest tests/ -v
```

## 真实数据初始化

```bash
# 全量初始化（约 30-60 分钟，取决于网速）
aq-data init --start 2018-01-01

# 每日盘后增量更新（在调度器/cron 中定时调用）
aq-data update

# 查看交易日历
aq-data calendar

# 拉某个指数成分
aq-data index hs300
```

## 回测

```bash
# 列出所有内置策略
aq-backtest list

# 跑一个回测
aq-backtest run --strategy multi_factor.value_quality --universe hs300 \
    --start 2020-01-01 --end 2024-12-31 --save

# 自定义策略参数（JSON）
aq-backtest run --strategy cta.turtle \
    --params '{"entry_window": 20, "exit_window": 10}'
```

## 研究看板（Streamlit）

```bash
streamlit run ashare_quant/ui/research_app.py
```

包含三个 Tab：
- **因子探索**：选因子计算 IC / 分层 / 多空组合
- **策略回测**：一键回测 + 基准对比
- **历史报告**：浏览 reports/ 下保存的报告

## 模拟盘

```bash
aq-live paper --strategy cta.dual_ma \
    --symbols 600519.SH,000858.SZ --start 2024-01-01 --tick-interval 0.2
```

启动监控大屏（Dash）：

```bash
aq-live dashboard
# 然后浏览器打开 http://127.0.0.1:8050
```

## 实盘（QMT，仅 Windows）

1. 确认券商开通 QMT 权限（多数券商门槛 50 万）
2. 登录 MiniQMT 终端
3. 配置 `config/secrets.yaml`：

```yaml
live:
  qmt_path: "C:/迅投QMT/userdata_mini"
  account_id: "12345678"
  account_type: "STOCK"
  alert:
    enabled: true
    wechat_work_webhook: "https://qyapi.weixin.qq.com/..."
```

4. 测试告警通道：

```bash
aq-live alert-test
```

5. 灰度运行（建议先小资金 + 单策略）：

```bash
aq-live qmt --strategy multi_factor.value_quality --universe hs300
```

## 调度（每日自动化）

`ashare_quant.live.scheduler.TradingScheduler` 提供常用调度入口：

```python
from ashare_quant.live.scheduler import TradingScheduler
from ashare_quant.data import pipeline

s = TradingScheduler()
s.add("daily_update", pipeline.update_daily, hour=17, minute=30)
s.add("morning_warmup", my_warmup_fn, hour=8, minute=45)
s.start()
```

## 风险提示

- 所有内置策略均为研究框架，不构成投资建议
- 实盘前请：
  1. 在三段历史（IS/OOS/Live）上验证
  2. 参数稳健性测试（参数小幅扰动不应使策略大幅恶化）
  3. 小资金 + 灰度上线
