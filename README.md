# ashare-quant — A股全栈量化平台

面向 A 股的"研究 → 回测 → 模拟 → 实盘"全链路 Python 量化平台。

## 特性

- **数据层**：AkShare / Tushare / efinance 多源采集 → **MySQL** 持久化（utf8mb4 / InnoDB / 分区表）
- **因子层**：30+ 基础因子（价值/质量/成长/动量/反转/低波/情绪），行业市值中性化
- **回测引擎**：
  - 自研事件驱动引擎（严格遵循 A 股 T+1、涨跌停、停牌、费用模型）
  - Qlib 适配（因子研究、ML 训练、IC 评估）
  - VectorBT 适配（向量化参数扫描）
- **策略库**：六大类 30+ 成熟策略
  - 多因子选股、CTA 择时、统计套利、事件驱动、机器学习、行业轮动 + 组合优化
- **风控**：事前/事中/事后三道防线 + Brinson/Barra 归因
- **执行**：模拟撮合 SimBroker + vnpy_xtquant 实盘网关（QMT 通道）
- **监控**：Streamlit 研究看板 + Dash 实盘大屏 + 企微/钉钉告警
- **Web UI + REST API**：FastAPI 后端（OpenAPI 自动文档）+ 11 个静态 HTML 操作页（覆盖全部功能）

## 快速开始

```bash
# 1. 创建环境（Python 3.10+ 推荐）
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # Linux/Mac

# 2. 安装依赖
pip install -e .[dev]

# 3. 初始化数据（首次约 30 分钟）
python -m ashare_quant.cli.data init --start 2018-01-01

# 4. 跑一个 demo 回测
python -m ashare_quant.cli.backtest run --strategy multi_factor.value_quality

# 5. 启动研究看板
streamlit run ui/research_app.py
```

## Web UI + REST API（推荐）

```bash
# 1) MySQL 准备：CREATE DATABASE ashare_quant DEFAULT CHARSET utf8mb4;
# 2) 配置连接 (config/settings.yaml 的 mysql 节点 或 环境变量 ASHARE_MYSQL_URL)
# 3) 启动 API 服务（自动建表 + seed）
aq-api
# 浏览器打开：
#   http://localhost:8000/            (Web 操作页)
#   http://localhost:8000/api/docs    (Swagger UI)
```

详见 [`web/README.md`](web/README.md)。


## 项目结构

```
ashare-quant/
├── pyproject.toml
├── config/
│   ├── settings.yaml           # 全局配置
│   └── strategies/             # 各策略 yaml
├── ashare_quant/
│   ├── data/                   # 数据层
│   ├── factors/                # 因子库
│   ├── strategies/             # 策略库
│   ├── engine/                 # 回测引擎
│   ├── portfolio/              # 组合优化
│   ├── risk/                   # 风控
│   ├── execution/              # 执行/网关
│   ├── live/                   # 调度/守护
│   ├── ui/                     # 看板
│   └── cli/                    # 命令行
├── tests/
└── notebooks/
```

## A 股关键细节

- **T+1**：当日买入次日才可卖
- **涨跌停**：主板 10%、创业板/科创板 20%、ST 5%
- **撮合层模拟**：涨停板买不到、跌停板卖不出
- **费用模型**：千一卖出印花税 + 万 2.5 双向佣金 + 沪市过户费
- **新股 60 日剔除**：避免回测虚高

## 风险提示

- QMT 大多数券商需 50 万门槛；零售可用模拟模式或低门槛券商
- Tushare Pro 部分接口需积分（200-500 元/年）
- 本平台仅为研究框架，**不构成投资建议**，实盘前请充分验证

## License

MIT
